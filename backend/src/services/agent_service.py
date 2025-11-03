"""
This file defines the service that coordinates the interaction between all the agents
"""
import asyncio
import json
from logging import getLogger
from typing import Optional
from fastapi import HTTPException
import threading

from ..agents.chat_agent.agent import ChatAgent
from ..agents.instruction_agent.agent import InstructionAgent
from ..api.schemas.recipe import Recipe, PromptHistory as PromptHistorySchema

from .query_service import get_recipe_gen_query, get_image_gen_query, get_chat_agent_query, get_instruction_query
from ..agents.image_agent.agent import ImageAgent
from ..agents.image_analyzer_agent import ImageAnalyzerAgent
from ..agents.recipe_agent import RecipeAgent
from ..db.bucket_session import get_bucket_session, get_async_bucket_session
from ..db.crud import recipe_crud, preparing_crud, cooking_crud, instruction_crud
from ..db.crud.bucket_base_repo import get_file, upload_file, save_image_bytes
from google.adk.sessions import InMemorySessionService
from ..agents.utils import create_text_query, create_docs_query
from ..db.database import get_async_db_context, get_db
from sqlalchemy.ext.asyncio import AsyncSession


logger = getLogger(__name__)

class AgentService:
    def __init__(self):
        self.session_service = InMemorySessionService()
        self.app_name = "Piatto"

        self.image_analyzer_agent = ImageAnalyzerAgent(self.app_name, self.session_service)
        self.recipe_agent = RecipeAgent(self.app_name, self.session_service)
        self.image_agent = ImageAgent(self.app_name, self.session_service)
        self.chat_agent = ChatAgent(self.app_name, self.session_service)
        self.instruction_agent = InstructionAgent(self.app_name, self.session_service)

    async def analyze_ingredients(self, user_id: str, file: bytes) -> str:
        """
        Analyze the ingredients in the uploaded image file.
        """

        query = create_docs_query("Analyze this image for food items.", [file])
        response = await self.image_analyzer_agent.run(
            user_id=user_id,
            state={},
            content=query,
        )

        output = response['output']
        if not isinstance(output, str):
            output = json.dumps(output)
        return output

    async def _generate_and_save_images_async(self, user_id, recipes, recipe_ids):
        """
        Internal async method that runs in a separate thread's event loop.
        Generates all images concurrently.
        """
        # Generate single image and update DB immediately
        async def generate_and_save_single_image(recipe_payload, recipe_id, idx):
            try:
                image = await self.image_agent.run(
                    user_id=user_id,
                    state={},
                    content=get_image_gen_query(recipe_payload),
                )

                async with get_async_bucket_session() as bs:
                    image_saved = await save_image_bytes(bs, user_id, "image", image, "recipe_image.png")

                # Update recipe with image URL
                async with get_async_db_context() as db:
                    await recipe_crud.update_recipe(db, recipe_id, image_url=image_saved['key'])

            except Exception as e:
                print(f"!!!BACKGROUND TASK: Error generating image for recipe {idx+1}: {e}")

        # Create all tasks concurrently using asyncio.create_task
        tasks = []
        for idx, recipe_payload in enumerate(recipes['recipes']):
            task = asyncio.create_task(generate_and_save_single_image(recipe_payload, recipe_ids[idx], idx))
            tasks.append(task)

        # Await all tasks to complete (they run in parallel)
        await asyncio.gather(*tasks, return_exceptions=True)

    # Rezepte Erstellen
    async def generate_recipe(
        self,
        user_id: str,
        prompt: str,
        written_ingredients: str,
        preparing_session_id: Optional[int] = None,
        background_tasks = None
    ):
        query = get_recipe_gen_query(prompt, written_ingredients)
        recipes =  await self.recipe_agent.run(
            user_id=user_id,
            state={},
            content=query,
        )
        # Save the recipes in db before generating images
        recipe_ids = []
        async with get_async_db_context() as db:
            for recipe in recipes['recipes']:
                recipe_db = await recipe_crud.create_recipe(
                    db=db,
                    user_id=user_id,
                    title=recipe['title'],
                    description=recipe['description'],
                    prompt=prompt,
                    ingredients=recipe['ingredients'],
                    total_time_minutes=recipe.get('total_time_minutes'),
                    difficulty=recipe['difficulty'],
                    food_category=recipe['food_category'],
                    important_notes=recipe.get('important_notes'),
                    cooking_overview=recipe.get('cooking_overview'),
                )
                recipe_ids.append(recipe_db.id)

            # Create or update preparing session with the generated recipes and metadata
            try:
                session = await preparing_crud.create_or_update_preparing_session(
                    db=db,
                    user_id=user_id,
                    recipe_ids=recipe_ids,
                    preparing_session_id=preparing_session_id,
                )
            except PermissionError as error:
                logger.warning("Preparing session %s cannot be updated by user %s", preparing_session_id, user_id)
                raise HTTPException(status_code=403,
                                    detail="Preparing session does not belong to the authenticated user") from error

        # Generate images in a separate thread (completely isolated from main event loop)
        background_tasks.add_task(self._generate_and_save_images_async, user_id, recipes, recipe_ids)
        return session.id

    async def generate_instruction(self, user_id: str, preparing_session_id: int, recipe_id: int) -> int:
        """
        Generate instructions for a recipe using the instruction agent.

        Args:
            user_id: The user ID
            preparing_session_id: The preparing session ID (unused but kept for API compatibility)
            recipe_id: The recipe ID to generate instructions for

        Returns:
            The recipe ID
        """
        async with get_async_db_context() as db:
            recipe = await recipe_crud.get_recipe_by_id(db, recipe_id)
            if not recipe:
                raise HTTPException(status_code=404, detail="Recipe not found")

        query = get_instruction_query(recipe)
        instructions_response = await self.instruction_agent.run(
            user_id=user_id,
            state={},
            content=query,
        )

        # Extract steps from the agent response
        # The agent returns an Instructions object with a 'steps' field
        if isinstance(instructions_response, dict):
            steps_data = instructions_response.get('steps', [])
        elif hasattr(instructions_response, 'steps'):
            steps_data = instructions_response.steps
        else:
            steps_data = []

        # Convert steps to list of dicts
        steps_list = []
        for step in steps_data:
            if isinstance(step, dict):
                steps_list.append(step)
            elif hasattr(step, 'model_dump'):
                steps_list.append(step.model_dump())
            elif hasattr(step, 'dict'):
                steps_list.append(step.dict())

        # Save instruction steps to database
        async with get_async_db_context() as db:
            await instruction_crud.create_instruction_steps(
                db=db,
                recipe_id=recipe_id,
                steps=steps_list
            )

        return recipe_id


    async def change_recipe(self, change_prompt: str, recipe_id: int,db, user_id: str) -> Recipe:
        # Prompt/Kontext an Agent übergeben
        # Agent returned agents/recipe_agent/schema.py:Recipe
        recipe = await recipe_crud.get_recipe_by_id(db, recipe_id)

        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        if recipe.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to modify this recipe")

        return HTTPException(status_code=501, detail="Not implemented yet")

        agent_return = ... # Agent call


        recipe = await recipe_crud.update_recipe(
            db=db,
            recipe_id=recipe_id,
            title=agent_return.name,
            description=agent_return.description,
            instructions=agent_return.instructions,
            ingredients=agent_return.ingredients,)
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        result = Recipe(
            id=recipe.id,
            title=recipe.title,
            description=recipe.description,
            prompt=recipe.prompt,
            ingredients=json.loads(recipe.ingredients),
            instructions=json.loads(recipe.instructions),
            image_url=recipe.image_url,
        )
        return result

    async def ask_question(self, user_id: str, cooking_session_id: int, prompt: str, db: AsyncSession):
        cooking_session = await cooking_crud.get_cooking_session_by_id(db, cooking_session_id)

        if cooking_session is None:
            raise HTTPException(status_code=404, detail="Cooking session not found")

        if cooking_session.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to interact with this cooking session")

        recipe: Optional[Recipe] = await recipe_crud.get_recipe_by_id(db, cooking_session.recipe_id)
        if recipe is None:
            raise HTTPException(status_code=404, detail="Recipe not found for this cooking session")

        prompt_history = await cooking_crud.get_prompt_history_by_cooking_session_id(db, cooking_session_id, user_id)
        if prompt_history is None:
            raise HTTPException(status_code=500, detail="Failed to retrieve prompt history for cooking session")

        query = get_chat_agent_query(prompt, recipe, cooking_session, prompt_history)

        # Log the final query sent to the chat agent
        logger.info("=" * 80)
        logger.info("CHAT AGENT QUERY")
        logger.info("=" * 80)
        logger.info("%s", query)
        logger.info("=" * 80)

        # STREAMING BACK THE AGENTS RESONSE @MARKUS
        response_chunks = []
        async for chunk in self.chat_agent.run(
            user_id=user_id,
            state={},
            content=query,
        ):
            if chunk is not None:
                response_chunks.append(chunk)

        response_text = "".join(response_chunks).strip()

        updated_prompt_history = await cooking_crud.update_prompt_history(
            db,
            prompt_history.id,
            prompt,
            response_text,
        )
        if updated_prompt_history is None:
            raise HTTPException(status_code=500, detail="Failed to update prompt history")

        return PromptHistorySchema(
            prompts=json.loads(updated_prompt_history.prompts),
            responses=json.loads(updated_prompt_history.responses)
        )



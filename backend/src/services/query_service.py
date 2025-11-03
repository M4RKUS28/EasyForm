"""
Utility class to get the queries for all the agents
As the queries are very text heavy, I do not want to build them up in the agent or state service.
"""
from google.genai import types
from ..agents.utils import create_text_query
import logging
import json

logger = logging.getLogger(__name__)

def get_recipe_gen_query(prompt: str, written_ingredients: str) -> types.Content:
    """ builds the query for the recipe generation agent """
    query = f"""
        System: What do you want to cook?
        User: {prompt}
        System: Any ingredients you want to use?
        User: {written_ingredients}
    """

    return create_text_query(query)

def get_image_gen_query(recipe: dict) -> types.Content:
    """ builds the query for the image generation agent """
    query = f"""
    Recipe Name: {recipe['title']}
    Description: {recipe['description']}
    Ingredients: {[ingr['name'] for ingr in recipe['ingredients']]}
"""
    return create_text_query(query)

def get_chat_agent_query(prompt: str, recipe, cooking_session, prompt_history) -> types.Content:
    """ builds the query for the chat agent """

    # Format instruction steps properly with clear structure
    instructions = "\n".join(
        f"  [{idx + 1}] {{\n"
        f"    heading: {step.heading}\n"
        f"    description: {step.description}\n"
        f"    animation: {step.animation}\n"
        f"    timer: {step.timer if step.timer else 'None'}\n"
        f"  }}"
        for idx, step in enumerate(recipe.instruction_steps)
    )

    # Format ingredients properly with clear structure
    ingredients_list = []
    for ing in recipe.ingredients:
        if ing.quantity and ing.unit:
            ingredients_list.append(f"  - {{ name: {ing.name}, quantity: {ing.quantity}, unit: {ing.unit} }}")
        elif ing.quantity:
            ingredients_list.append(f"  - {{ name: {ing.name}, quantity: {ing.quantity} }}")
        else:
            ingredients_list.append(f"  - {{ name: {ing.name}, unit: {ing.unit} }}")
    ingredients_formatted = "\n".join(ingredients_list)

    # Format chat history properly
    prompts = json.loads(prompt_history.prompts) if isinstance(prompt_history.prompts, str) else prompt_history.prompts
    responses = json.loads(prompt_history.responses) if isinstance(prompt_history.responses, str) else prompt_history.responses

    chat_history = []
    for i, prompt_text in enumerate(prompts):
        chat_history.append(f"  [{i + 1}] {{ role: User, message: {prompt_text} }}")
        if i < len(responses):
            chat_history.append(f"  [{i + 1}] {{ role: Assistant, message: {responses[i]} }}")

    chat_history_formatted = "\n".join(chat_history) if chat_history else "  [No previous conversation]"

    query = f"""
[Recipe] {{
  name: {recipe.title}
  description: {recipe.description}
}}

[Instructions] {{
{instructions}
}}

[Ingredients] {{
{ingredients_formatted}
}}

[Cooking Session] {{
  current_step: {cooking_session.state}
}}

[Chat History] {{
{chat_history_formatted}
}}

================================

[Next User Question]: {prompt}
    """

    return create_text_query(query)

def get_instruction_query(recipe) -> types.Content:
    """builds the query for the instruction generation agent"""
    query = f"""
    The user made the following initial prompt:
    {recipe.prompt}
    Upon that, the following recipe was generated:
    Recipe Name: {recipe.title}
    Description: {recipe.description}
    Ingredients: {recipe.ingredients}
    """

    return create_text_query(query)

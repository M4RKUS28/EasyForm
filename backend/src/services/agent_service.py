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

from .query_service import get_recipe_gen_query


from ..agents.image_analyzer_agent import ImageAnalyzerAgent



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


    async def analyze_ingredients(self, user_id: str, file: bytes) -> str:
        """
        """
        return ""

    async def _generate_and_save_images_async(self, user_id, recipes, recipe_ids):
        """
        """
       return None


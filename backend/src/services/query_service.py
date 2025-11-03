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
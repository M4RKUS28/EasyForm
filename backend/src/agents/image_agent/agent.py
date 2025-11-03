"""
Agent for generating custom images, e.g. an image of a recipe
"""
import asyncio
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

from ..utils import create_text_query, load_instruction_from_file


class ImageAgent:
    def __init__(self, app_name, session_service):
        self.client = genai.Client() # use normal gemini client because it is easier to use with image output
        self.full_instructions = load_instruction_from_file("image_agent/instructions.txt")

    async def run(self, user_id: str, state: dict, content: types.Content):
        user_text = content.parts[0].text if content.parts and content.parts[0].text else ""
        response = await self.client.aio.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[self.full_instructions + user_text],
        )

        candidates = getattr(response, "candidates", None)
        if candidates and len(candidates) > 0:
            candidate_content = getattr(candidates[0], "content", None)
            if candidate_content is not None and hasattr(candidate_content, "parts"):
                for part in candidate_content.parts:
                    if getattr(part, "inline_data", None) is not None:
                        return part.inline_data.data

        return None


async def test_agent():
    agent = ImageAgent("Test", None)
    query = """Image of a korean bbq"""

    data = await agent.run("1", {}, create_text_query(query))
    image = Image.open(BytesIO(data))
    image.save("generated_image.png")

if __name__ == '__main__':
    asyncio.run(test_agent())
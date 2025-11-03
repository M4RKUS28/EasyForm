import asyncio
from google import genai
from google.genai import types

from ..utils import load_instruction_from_file


class ChatAgent:
    def __init__(self, app_name: str, session_service):
        self.client = genai.Client()
        self.model = "gemini-live-2.5-flash-preview"
        self.config = {"response_modalities": ["TEXT"]}
        self.system_prompt = load_instruction_from_file("chat_agent/instructions.txt")

    async def run(self, user_id: str, state: dict, content: types.Content):
        async with self.client.aio.live.connect(model=self.model, config=self.config) as session:
            await session.send_client_content(
                turns=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(text=self.system_prompt),
                            *content.parts
                        ]
                    )
                ],
                turn_complete=True
            )

            async for response in session.receive():
                if response.text is not None:
                    # HIER KANNST DU DEN TEXT ZURÜCK STREAMEN e.g.
                    yield response.text
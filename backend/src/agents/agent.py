"""
This file defines the base class for all agents.
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

from google.genai import types

from ..config import settings

if not settings.AGENT_DEBUG_MODE:
    logging.getLogger("google_adk.google.adk.models.google_llm").setLevel(logging.WARNING)



class StandardAgent(ABC):
    """ This is the standard agent without structured output """
    @abstractmethod
    def __init__(self, app_name: str, session_service):
        self.app_name = app_name
        self.session_service = session_service
        self.model = "gemini-2.5-flash"

    async def run(self, user_id: str, state: dict, content: types.Content, debug: bool = False) -> Dict[str, Any]:
        """
        Wraps the event handling and runner from adk into a simple run() method that includes error handling
        and automatic retries for transient failures.
        
        :param user_id: id of the user
        :param state: the state created from the StateService
        :param content: the user query as a type.Content object
        :param debug: if true the method will print auxiliary outputs (all events)
        :return: the parsed dictionary response from the agent
        """
        max_retries: int = 1
        retry_delay: float = 2.0
        last_error = None
        
        for attempt in range(max_retries + 1):  # +1 for the initial attempt
            try:
                if debug:
                    logging.getLogger(__name__).debug("[Debug] Running agent with state: %s", json.dumps(state, indent=2))

                # Create session
                session = await self.session_service.create_session(
                    app_name=self.app_name,
                    user_id=user_id,
                    state=state
                )
                session_id = session.id

                # We iterate through events to find the final answer
                async for event in self.runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
                    if debug:
                        logging.getLogger(__name__).debug(
                            "  [Event] Author: %s, Type: %s, Final: %s, Content: %s",
                            event.author,
                            type(event).__name__,
                            event.is_final_response(),
                            event.content,
                        )

                    # is_final_response() marks the concluding message for the turn
                    if event.is_final_response():
                        if event.content and event.content.parts:
                            # Assuming text response in the first part
                            return {
                                "status": "success",
                                "output": event.content.parts[0].text
                            }
                        elif event.actions and event.actions.escalate:  # Handle potential errors/escalations
                            error_msg = f"Agent escalated: {event.error_message or 'No specific message.'}"
                            if attempt >= max_retries:
                                return {"status": "error", "message": error_msg}
                            last_error = error_msg
                            break  # Break out of event loop to trigger retry
                
                # If we get here, no final response was received
                error_msg = "Agent did not give a final response. Unknown error occurred."
                if attempt >= max_retries:
                    return {"status": "error", "message": error_msg}
                last_error = error_msg
                
            except Exception as e:
                if attempt >= max_retries:
                    raise  # Re-raise the exception if we've exhausted our retries
                last_error = str(e)
                if debug:
                    logging.getLogger(__name__).warning(
                        "[RETRY] Attempt %d failed, retrying in %s seconds... Error: %s",
                        attempt + 1,
                        retry_delay,
                        last_error,
                    )
                
            # Only sleep if we're going to retry
            if attempt < max_retries:
                import asyncio
                await asyncio.sleep(retry_delay)
        
        # This should theoretically never be reached due to the raise/return above
        return {
            "status": "error",
            "message": f"Max retries exceeded. Last error: {last_error}",
        }


class StructuredAgent(ABC):
    """ This is an agent that returns structured output. """
    @abstractmethod
    def __init__(self, app_name: str, session_service):
        self.app_name = app_name
        self.session_service = session_service
        self.model = "gemini-2.5-flash"
    async def run(self, user_id: str, state: dict, content: types.Content, debug: bool = False, max_retries: int = 1, retry_delay: float = 2.0) -> Dict[str, Any]:
        """
        Wraps the event handling and runner from adk into a simple run() method that includes error handling
        and automatic retries for transient failures.

        :param user_id: id of the user
        :param state: the state created from the StateService
        :param content: the user query as a type.Content object
        :param debug: if true the method will print auxiliary outputs (all events)
        :return: the parsed dictionary response from the agent
        """
        logger = logging.getLogger(__name__)
        logger.info(f"=== Agent.run() called for app: {self.app_name}, user: {user_id} ===")
        logger.info(f"Content type: {type(content)}")
        logger.info(f"Content parts count: {len(content.parts) if hasattr(content, 'parts') and content.parts else 0}")
        if hasattr(content, 'parts') and content.parts:
            for idx, part in enumerate(content.parts[:3]):  # Log first 3 parts
                logger.info(f"Content part {idx} type: {type(part)}")
                if hasattr(part, 'text'):
                    logger.info(f"Content part {idx} text preview: {part.text[:200] if part.text else 'EMPTY'}")
                if hasattr(part, 'inline_data'):
                    logger.info(f"Content part {idx} has inline_data: {part.inline_data is not None}")

        max_retries: int = 1
        retry_delay: float = 2.0
        last_error = None

        for attempt in range(max_retries + 1):  # +1 for the initial attempt
            logger.info(f"Attempt {attempt + 1}/{max_retries + 1}")
            try:
                logger.info("Creating session...")
                session = await self.session_service.create_session(
                    app_name=self.app_name,
                    user_id=user_id,
                    state=state
                )
                session_id = session.id
                logger.info(f"Session created: {session_id}")

                logger.info("Starting agent runner...")
                async for event in self.runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=content,
                ):
                    if debug:
                        logging.getLogger(__name__).debug(
                            "[Event] Author: %s, Type: %s, Final: %s",
                            event.author,
                            type(event).__name__,
                            event.is_final_response(),
                        )

                    if event.is_final_response():
                        if event.content and event.content.parts:
                            # Get the text from the Part object
                            json_text = event.content.parts[0].text

                            logger = logging.getLogger(__name__)
                            logger.info(f"Agent final response received, text length: {len(json_text) if json_text else 0}")
                            logger.info(f"JSON text type: {type(json_text)}")
                            logger.info(f"JSON text preview (first 500 chars): {json_text[:500] if json_text else 'EMPTY'}")
                            logger.info(f"JSON text preview (last 200 chars): {json_text[-200:] if json_text and len(json_text) > 200 else json_text}")

                            # Try parsing the json response into a dictionary
                            try:
                                logger.info("Attempting to parse JSON...")

                                # Strip markdown code block markers if present
                                cleaned_text = json_text.strip()
                                if cleaned_text.startswith("```json"):
                                    logger.info("Detected markdown JSON code block (```json), stripping markers...")
                                    cleaned_text = cleaned_text[7:]  # Remove ```json
                                elif cleaned_text.startswith("```"):
                                    logger.info("Detected markdown code block (```), stripping markers...")
                                    cleaned_text = cleaned_text[3:]  # Remove ```

                                if cleaned_text.endswith("```"):
                                    logger.info("Removing trailing ``` marker...")
                                    cleaned_text = cleaned_text[:-3]

                                cleaned_text = cleaned_text.strip()
                                logger.info(f"Cleaned text length: {len(cleaned_text)}")
                                logger.info(f"Cleaned text preview (first 200 chars): {cleaned_text[:200]}")

                                dict_response = json.loads(cleaned_text)
                                logger.info(f"JSON parsing successful! Result type: {type(dict_response)}")
                                logger.info(f"JSON result keys: {dict_response.keys() if isinstance(dict_response, dict) else 'NOT A DICT'}")
                                return dict_response
                            except json.JSONDecodeError as e:
                                error_msg = f"Error parsing JSON response: {e}"
                                logger.error(f"JSON parsing failed: {error_msg}")
                                logger.error(f"JSON error position: line {e.lineno}, column {e.colno}")
                                logger.error(f"Problematic text around error: {e.doc[max(0, e.pos-50):min(len(e.doc), e.pos+50)] if hasattr(e, 'doc') and e.doc else 'N/A'}")
                                if attempt >= max_retries:
                                    if debug:
                                        logger.error("%s", error_msg)
                                    raise
                                last_error = error_msg
                                logger.info(f"Retrying due to JSON parse error (attempt {attempt}/{max_retries})")
                                break  # Break out of event loop to trigger retry

                        elif event.actions and event.actions.escalate:  # Handle potential errors/escalations
                            error_msg = f"Agent escalated: {event.error_message or 'No specific message.'}"
                            if attempt >= max_retries:
                                return {"status": "error", "message": error_msg}
                            last_error = error_msg
                            break  # Break out of event loop to trigger retry
                
                # If we get here, no final response was received
                error_msg = "Agent did not give a final response. Unknown error occurred."
                if attempt >= max_retries:
                    return {"status": "error", "message": error_msg}
                last_error = error_msg
                
            except Exception as e:
                if attempt >= max_retries:
                    raise  # Re-raise the exception if we've exhausted our retries
                last_error = str(e)
                if debug:
                    logging.getLogger(__name__).warning(
                        "[RETRY] Attempt %d failed, retrying in %s seconds... Error: %s",
                        attempt + 1,
                        retry_delay,
                        last_error,
                    )
            
            # Only sleep if we're going to retry
            if attempt < max_retries:
                import asyncio
                await asyncio.sleep(retry_delay)
        
        # This should theoretically never be reached due to the raise/return above
        return {
            "status": "error",
            "message": f"Max retries exceeded. Last error: {last_error}",
        }
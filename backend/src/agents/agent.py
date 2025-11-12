"""
This file defines the base class for all agents.
"""
import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import ValidationError

from google.genai import types

from ..config import settings

try:
    from json_repair import repair_json
except ImportError:  # pragma: no cover - optional dependency
    repair_json = None

if not settings.AGENT_DEBUG_MODE:
    logging.getLogger("google_adk.google.adk.models.google_llm").setLevel(logging.WARNING)


def _escape_unescaped_control_chars(json_text: str) -> str:
    """Escape control characters that appear inside JSON strings without proper escaping."""
    result = []
    in_string = False
    escape_next = False

    for ch in json_text:
        if in_string:
            if escape_next:
                result.append(ch)
                escape_next = False
                continue

            if ch == '\\':
                result.append(ch)
                escape_next = True
            elif ch == '"':
                result.append(ch)
                in_string = False
            elif ord(ch) < 0x20:
                if ch == '\n':
                    result.append('\\n')
                elif ch == '\r':
                    result.append('\\r')
                elif ch == '\t':
                    result.append('\\t')
                else:
                    result.append(f"\\u{ord(ch):04x}")
            else:
                result.append(ch)
        else:
            result.append(ch)
            if ch == '"':
                in_string = True
                escape_next = False

    return "".join(result)



class StandardAgent(ABC):
    """ This is the standard agent without structured output """
    @abstractmethod
    def __init__(self, app_name: str, session_service):
        self.app_name = app_name
        self.session_service = session_service
        self.model = "gemini-2.5-flash"
        self._last_raw_response: Optional[str] = None

    @property
    def last_raw_response(self) -> Optional[str]:
        return self._last_raw_response

    async def run(
        self,
        user_id: str,
        state: dict,
        content: types.Content,
        debug: bool = False,
        max_retries: int = 1,
        retry_delay: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Wraps the event handling and runner from adk into a simple run() method that includes error handling
        and automatic retries for transient failures.
        """
        total_attempts = max(0, max_retries) + 1
        last_error = None
        self._last_raw_response = None

        for attempt in range(total_attempts):
            should_retry = False
            response_handled = False
            try:
                if debug:
                    logging.getLogger(__name__).debug(
                        "[Debug] Running agent with state: %s", json.dumps(state, indent=2)
                    )

                session = await self.session_service.create_session(
                    app_name=self.app_name,
                    user_id=user_id,
                    state=state,
                )
                session_id = session.id

                async for event in self.runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=content,
                ):
                    if debug:
                        logging.getLogger(__name__).debug(
                            "  [Event] Author: %s, Type: %s, Final: %s, Content: %s",
                            event.author,
                            type(event).__name__,
                            event.is_final_response(),
                            event.content,
                        )

                    if event.is_final_response():
                        response_handled = True
                        if event.content and event.content.parts:
                            text_segments = [
                                part.text
                                for part in event.content.parts
                                if hasattr(part, "text") and part.text
                            ]
                            merged_text = "".join(text_segments)
                            self._last_raw_response = merged_text
                            return {
                                "status": "success",
                                "output": merged_text,
                            }
                        if event.actions and event.actions.escalate:
                            error_msg = (
                                f"Agent escalated: {event.error_message or 'No specific message.'}"
                            )
                            if attempt == total_attempts - 1:
                                return {"status": "error", "message": error_msg}
                            last_error = error_msg
                            should_retry = True
                            break

                if should_retry:
                    continue

                error_msg = "Agent did not give a final response. Unknown error occurred."
                if response_handled:
                    last_error = error_msg
                    if attempt == total_attempts - 1:
                        return {"status": "error", "message": last_error}
                if attempt == total_attempts - 1:
                    return {"status": "error", "message": error_msg}
                last_error = error_msg

            except Exception as e:  # noqa: BLE001 - we want to surface agent failures
                last_error = str(e)
                if attempt == total_attempts - 1:
                    raise
                if debug:
                    logging.getLogger(__name__).warning(
                        "[RETRY] Attempt %d failed, retrying in %s seconds... Error: %s",
                        attempt + 1,
                        retry_delay,
                        last_error,
                    )

            if attempt < total_attempts - 1:
                await asyncio.sleep(retry_delay)

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
        self._last_raw_response: Optional[str] = None

    @property
    def last_raw_response(self) -> Optional[str]:
        return self._last_raw_response
    async def run(
        self,
        user_id: str,
        state: dict,
        content: types.Content,
        debug: bool = False,
        max_retries: int = 1,
        retry_delay: float = 2.0,
    ) -> Dict[str, Any]:
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

        total_attempts = max(0, max_retries) + 1
        last_error = None
        self._last_raw_response = None

        for attempt in range(total_attempts):
            logger.info(f"Attempt {attempt + 1}/{total_attempts}")
            should_retry = False
            final_response_handled = False
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
                        final_response_handled = True
                        if event.content and event.content.parts:
                            text_segments = [
                                part.text
                                for part in event.content.parts
                                if hasattr(part, "text") and part.text
                            ]
                            json_text = "".join(text_segments)
                            logger.info(
                                "Final response composed of %d text segment(s)",
                                len(text_segments),
                            )

                            logger = logging.getLogger(__name__)
                            logger.info(f"Agent final response received, text length: {len(json_text) if json_text else 0}")
                            logger.info(f"JSON text type: {type(json_text)}")
                            logger.info(f"JSON text preview (first 500 chars): {json_text[:500] if json_text else 'EMPTY'}")
                            logger.info(f"JSON text preview (last 200 chars): {json_text[-200:] if json_text and len(json_text) > 200 else json_text}")
                            logger.warning("Agent raw response (len=%d): %s", len(json_text) if json_text else 0, json_text if json_text else "EMPTY")

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

                                sanitized_text = _escape_unescaped_control_chars(cleaned_text)
                                if sanitized_text != cleaned_text:
                                    logger.info("Control characters sanitized before validation")
                                cleaned_text = sanitized_text

                                candidate_texts = [(cleaned_text, "cleaned")]
                                if repair_json is not None:
                                    try:
                                        repaired_text = repair_json(cleaned_text)
                                        if repaired_text and repaired_text != cleaned_text:
                                            candidate_texts.append((repaired_text, "json_repair"))
                                            logger.info("json-repair generated alternative candidate for parsing")
                                    except Exception as repair_error:  # noqa: BLE001
                                        logger.warning("json-repair failed to repair candidate: %s", repair_error)

                                parsed_response = None
                                fallback_json = None
                                last_decode_error = None

                                for candidate_text, candidate_label in candidate_texts:
                                    try:
                                        loaded_json = json.loads(candidate_text)
                                    except json.JSONDecodeError as decode_error:
                                        last_decode_error = decode_error
                                        logger.error(
                                            "JSON parsing failed (%s candidate): %s",
                                            candidate_label,
                                            decode_error,
                                        )
                                        logger.error(
                                            "Problematic text around error (%s candidate): %s",
                                            candidate_label,
                                            candidate_text[max(0, decode_error.pos - 50): min(len(candidate_text), decode_error.pos + 50)]
                                            if candidate_text else "N/A",
                                        )
                                        continue

                                    output_model = getattr(self, "output_model", None)
                                    if output_model is not None:
                                        try:
                                            model_instance = output_model.model_validate(loaded_json)
                                            parsed_response = model_instance.model_dump()
                                            logger.info(
                                                "Structured output validated against %s using %s candidate",
                                                output_model.__name__,
                                                candidate_label,
                                            )
                                            break
                                        except ValidationError as validation_error:
                                            logger.error(
                                                "Structured output validation failed (%s candidate): %s",
                                                candidate_label,
                                                validation_error,
                                            )
                                            fallback_json = loaded_json
                                            continue
                                    else:
                                        parsed_response = loaded_json
                                        break

                                if parsed_response is None and fallback_json is not None:
                                    logger.info("Using fallback raw JSON after validation failure")
                                    parsed_response = fallback_json

                                if parsed_response is None:
                                    if last_decode_error is not None:
                                        raise last_decode_error
                                    raise ValueError("Failed to parse agent response into JSON")

                                logger.info(f"JSON parsing successful! Result type: {type(parsed_response)}")
                                if isinstance(parsed_response, dict):
                                    logger.info(f"JSON result keys: {parsed_response.keys()}")
                                logger.warning("Agent structured output: %s", parsed_response)
                                self._last_raw_response = cleaned_text
                                return parsed_response
                            except json.JSONDecodeError as e:
                                error_msg = f"Error parsing JSON response: {e}"
                                logger.error(f"JSON parsing failed: {error_msg}")
                                logger.error(f"JSON error position: line {e.lineno}, column {e.colno}")
                                logger.error(f"Problematic text around error: {e.doc[max(0, e.pos-50):min(len(e.doc), e.pos+50)] if hasattr(e, 'doc') and e.doc else 'N/A'}")
                                last_error = error_msg
                                if attempt == total_attempts - 1:
                                    if debug:
                                        logger.error("%s", error_msg)
                                    raise
                                should_retry = True
                                last_error = error_msg
                                logger.info(
                                    "Retrying due to JSON parse error (attempt %d/%d)",
                                    attempt + 1,
                                    total_attempts,
                                )
                                break

                        elif event.actions and event.actions.escalate:  # Handle potential errors/escalations
                            error_msg = f"Agent escalated: {event.error_message or 'No specific message.'}"
                            if attempt == total_attempts - 1:
                                return {"status": "error", "message": error_msg}
                            last_error = error_msg
                            should_retry = True
                            break
                
                if should_retry:
                    continue

                # If we get here, no final response was received
                if not final_response_handled:
                    error_msg = "Agent did not give a final response. Unknown error occurred."
                    if attempt == total_attempts - 1:
                        return {"status": "error", "message": error_msg}
                    last_error = error_msg

            except Exception as e:
                if attempt == total_attempts - 1:
                    raise  # Re-raise the exception if we've exhausted our retries
                last_error = str(e)
                if debug:
                    logging.getLogger(__name__).warning(
                        "[RETRY] Attempt %d failed, retrying in %s seconds... Error: %s",
                        attempt + 1,
                        retry_delay,
                        last_error,
                    )

            if attempt < total_attempts - 1:
                await asyncio.sleep(retry_delay)

        # This should theoretically never be reached due to the raise/return above
        return {
            "status": "error",
            "message": f"Max retries exceeded. Last error: {last_error}",
        }

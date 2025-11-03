# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from typing import List

from google.genai import types
import logging

logger = logging.getLogger(__name__)


def create_text_query(query: str) -> types.Content:
    """ Takes a string and returns a user query that can be sent to an agent """
    return types.Content(role="user", parts=[types.Part(text=query)])


def create_docs_query(query: str, images: List[bytes]) -> types.Content:
    """ Takes a string and fastapi UploadFile object and returns a user query that can be sent to an agent """
    parts = [types.Part(text=query)]
    for image in images:
        parts.append(types.Part.from_bytes(
            data=image,
            mime_type="image/png",
        ))
    return types.Content(role="user", parts=parts)


# ------- Loading system instructions for agents -------

def load_instruction_from_file(
    filename: str, default_instruction: str = "Default instruction."
) -> str:
    """Reads instruction text from a single file relative to this script."""
    instruction = default_instruction
    try:
        # Construct path relative to the current script file (__file__)
        filepath = os.path.join(os.path.dirname(__file__), filename)
        with open(filepath, "r", encoding="utf-8") as f:
            instruction = f.read()
            logger.info("Successfully loaded instruction from %s", filename)
    except FileNotFoundError:
            logger.warning("Instruction file not found: %s. Using default.", filepath)
    except Exception as e:
            logger.exception("ERROR loading instruction file %s: %s. Using default.", filepath, e)
    return instruction


def load_instructions_from_files(filenames: List[str], separator: str = "\n\n---\n\n") -> str:
    """
    Loads and combines multiple instruction files into a single string.

    Args:
        filenames: List of file paths relative to the calling script
        separator: String to separate content from different files

    Returns:
        Combined instruction string
    """
    combined_instructions = []

    for filename in filenames:
        try:
            filepath = os.path.join(os.path.dirname(__file__), filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
                combined_instructions.append(f"# {os.path.basename(filename)}\n\n{content}")
        except FileNotFoundError:
            logger.warning("Instruction file not found: %s", filepath)
        except Exception as e:
            logger.exception("ERROR loading instruction file %s: %s", filepath, e)

    return separator.join(combined_instructions)


# ------- Multi-part content creation for form analysis -------

def create_multipart_query(
    query: str,
    pdf_files: List[bytes] = None,
    images: List[bytes] = None,
    screenshots: List[bytes] = None
) -> types.Content:
    """
    Creates a multi-part query with text, PDFs, images, and screenshots.
    All files are sent directly to Gemini for processing.

    Args:
        query: Text query/prompt
        pdf_files: List of PDF file bytes
        images: List of image file bytes
        screenshots: List of screenshot bytes (base64 decoded)

    Returns:
        types.Content object ready to send to an agent
    """
    parts = [types.Part(text=query)]

    # Add PDFs
    if pdf_files:
        for pdf_bytes in pdf_files:
            parts.append(types.Part.from_bytes(
                data=pdf_bytes,
                mime_type="application/pdf"
            ))

    # Add images (from user uploads)
    if images:
        for image_bytes in images:
            # Try to detect image format, default to PNG
            parts.append(types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/png"  # Gemini handles various formats
            ))

    # Add screenshots
    if screenshots:
        for screenshot_bytes in screenshots:
            parts.append(types.Part.from_bytes(
                data=screenshot_bytes,
                mime_type="image/png"
            ))

    return types.Content(role="user", parts=parts)
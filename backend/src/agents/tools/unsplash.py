# -* - coding: utf-8 -* -
# !/usr/bin/env python3

import os
from dataclasses import dataclass
from typing import List, Dict, Optional, Annotated

import httpx
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


@dataclass
class UnsplashPhoto:
    id: str
    description: str
    urls: Dict[str, str]
    width: int
    height: int


async def search_photos(
        query: str,
        page: int = 1,
        per_page: int = 10,
        order_by: str = "relevant",
        color: Optional[str] = None,
        orientation: Optional[str] = None,
) -> List[UnsplashPhoto]:
    """
    Search for Unsplash photos.

    Args:
        query: Search keyword.
        page: Page number (1-based, integer only).
        per_page: Results per page (1-30, integer only).
        order_by: Sort method ('relevant' or 'latest').
        color: Color filter (optional; 'black_and_white', 'black', 'white', 'yellow', 'orange', 'red', 'purple', 'magenta', 'green', 'teal', 'blue').
        orientation: Orientation filter (optional; 'landscape', 'portrait', 'squarish').

    Returns:
        List[UnsplashPhoto]: List of search results containing photo objects.
    """
    access_key = os.getenv("UNSPLASH_ACCESS_KEY")
    if not access_key:
        raise ValueError("Missing UNSPLASH_ACCESS_KEY environment variable")

    # Validate and constrain parameters
    page = max(1, int(page))
    per_page = max(1, min(int(per_page), 30))

    params = {
        "query": query,
        "page": page,
        "per_page": per_page,
        "order_by": order_by,
    }
    if color:
        params["color"] = color
    if orientation:
        params["orientation"] = orientation

    headers = {
        "Accept-Version": "v1",
        "Authorization": f"Client-ID {access_key}"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.unsplash.com/search/photos",
                params=params,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

            return [
                UnsplashPhoto(
                    id=photo["id"],
                    description=photo.get("description") or "No description available",  # Handle None
                    urls=photo["urls"],
                    width=photo["width"],
                    height=photo["height"]
                )
                for photo in data["results"]
            ]
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error: %s - %s", e.response.status_code, e.response.text)
        raise
    except Exception as e:
        logger.exception("Request error: %s", str(e))
        raise

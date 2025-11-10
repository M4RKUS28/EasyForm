"""
Script to truncate ChromaDB collection.
Run this when migrating to a new embedding model.

Usage:
    python scripts/truncate_chromadb.py
"""
import sys
import os
from pathlib import Path

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb
from chromadb.config import Settings
from src.config import settings as app_settings


def truncate_collection():
    """Delete and recreate the ChromaDB collection."""
    print(f"Connecting to ChromaDB at {app_settings.CHROMA_HOST}:{app_settings.CHROMA_PORT}")

    client = chromadb.HttpClient(
        host=app_settings.CHROMA_HOST,
        port=app_settings.CHROMA_PORT,
        settings=Settings(
            anonymized_telemetry=False,
            allow_reset=False
        ),
        ssl=True
    )

    collection_name = app_settings.CHROMA_COLLECTION_NAME

    try:
        # Try to delete existing collection
        client.delete_collection(name=collection_name)
        print(f"✅ Deleted existing collection: {collection_name}")
    except Exception as e:
        print(f"ℹ️  Collection doesn't exist or couldn't be deleted: {e}")

    # Create new collection
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )

    print(f"✅ Created new collection: {collection_name}")
    print(f"📊 Collection count: {collection.count()}")
    print(f"🎯 Using embedding model: {app_settings.EMBEDDING_MODEL}")
    print(f"📐 Embedding dimensions: {app_settings.EMBEDDING_DIMENSIONS}")
    print("\n⚠️  Note: You'll need to re-upload all files to regenerate embeddings!")


if __name__ == "__main__":
    response = input(f"This will DELETE all data in ChromaDB collection '{app_settings.CHROMA_COLLECTION_NAME}'. Continue? (yes/no): ")
    if response.lower() == "yes":
        truncate_collection()
    else:
        print("❌ Cancelled.")

"""
Script to truncate ChromaDB collections (text and image).
Run this when migrating to new embedding models or to reset RAG data.

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


def truncate_collections():
    """Delete and recreate both ChromaDB collections (text and image)."""
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

    collections = [
        {
            "name": app_settings.CHROMA_TEXT_COLLECTION_NAME,
            "embedding_model": app_settings.TEXT_EMBEDDING_MODEL,
            "dimensions": app_settings.TEXT_EMBEDDING_DIMENSIONS,
            "description": "Text collection (text chunks + OCR)"
        },
        {
            "name": app_settings.CHROMA_IMAGE_COLLECTION_NAME,
            "embedding_model": app_settings.IMAGE_EMBEDDING_MODEL,
            "dimensions": app_settings.IMAGE_EMBEDDING_DIMENSIONS,
            "description": "Image collection (visual embeddings)"
        }
    ]

    print("\n" + "="*80)
    print("TRUNCATING CHROMADB COLLECTIONS")
    print("="*80 + "\n")

    for col_info in collections:
        collection_name = col_info["name"]

        print(f"\n📦 Processing: {col_info['description']}")
        print(f"   Collection: {collection_name}")

        try:
            # Try to delete existing collection
            client.delete_collection(name=collection_name)
            print(f"   ✅ Deleted existing collection")
        except Exception as e:
            print(f"   ℹ️  Collection doesn't exist or couldn't be deleted: {e}")

        # Create new collection
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

        print(f"   ✅ Created new collection")
        print(f"   📊 Collection count: {collection.count()}")
        print(f"   🎯 Embedding model: {col_info['embedding_model']}")
        print(f"   📐 Embedding dimensions: {col_info['dimensions']}")

    print("\n" + "="*80)
    print("✅ TRUNCATION COMPLETE")
    print("="*80)
    print("\n⚠️  IMPORTANT: You'll need to re-upload all files to regenerate embeddings!")
    print("   Both text and image embeddings have been cleared.\n")


if __name__ == "__main__":
    print("\n⚠️  WARNING: This will DELETE all data in BOTH ChromaDB collections:")
    print(f"   1. Text Collection: {app_settings.CHROMA_TEXT_COLLECTION_NAME}")
    print(f"   2. Image Collection: {app_settings.CHROMA_IMAGE_COLLECTION_NAME}")
    print()

    response = input("Continue? (yes/no): ")
    if response.lower() == "yes":
        truncate_collections()
    else:
        print("❌ Cancelled.")

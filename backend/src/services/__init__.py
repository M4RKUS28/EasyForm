"""
Services module for EasyForm backend.
Contains business logic and integration services.
"""
from .agent_service import AgentService
from .file_service import upload_file, get_user_files, get_file, delete_file
from .form_service import (
    schedule_form_analysis_task,
    cancel_form_analysis_task,
    process_form_analysis_async
)
from .user_service import (
    get_users,
    update_user,
    change_password,
    delete_user
)

# RAG Services
from .document_processing_service import (
    DocumentProcessingService,
    get_document_processing_service
)
from .embedding_service import (
    EmbeddingService,
    get_embedding_service
)
from .rag_service import (
    RAGService,
    get_rag_service
)

__all__ = [
    # Agent service
    "AgentService",
    # File service
    "upload_file",
    "get_user_files",
    "get_file",
    "delete_file",
    # Form service
    "schedule_form_analysis_task",
    "cancel_form_analysis_task",
    "process_form_analysis_async",
    # User service
    "get_users",
    "update_user",
    "change_password",
    "delete_user",
    # RAG services
    "DocumentProcessingService",
    "get_document_processing_service",
    "EmbeddingService",
    "get_embedding_service",
    "RAGService",
    "get_rag_service",
]

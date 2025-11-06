"""
Services module for EasyForm backend.
Contains business logic and integration services.
"""
from .agent_service import AgentService
from .file_service import upload_file, get_user_files, get_file, delete_file
from .form_service import (
    analyze_form,
    schedule_form_analysis_task,
    cancel_form_analysis_task,
    process_form_analysis_async
)
from .user_service import (
    create_user,
    authenticate_user,
    update_user,
    delete_user,
    get_user_by_id,
    get_user_by_username,
    get_user_by_email
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
    "analyze_form",
    "schedule_form_analysis_task",
    "cancel_form_analysis_task",
    "process_form_analysis_async",
    # User service
    "create_user",
    "authenticate_user",
    "update_user",
    "delete_user",
    "get_user_by_id",
    "get_user_by_username",
    "get_user_by_email",
    # RAG services
    "DocumentProcessingService",
    "get_document_processing_service",
    "EmbeddingService",
    "get_embedding_service",
    "RAGService",
    "get_rag_service",
]

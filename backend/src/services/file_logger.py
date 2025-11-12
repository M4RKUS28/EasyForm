"""
File Logger Service - Logs agent requests, responses, and media to disk for debugging.

This service creates detailed logs for each /analyze request, organizing data by:
- User ID
- Date & Time (YYYY-MM-DD_HH-MM)
- Request ID
- Agent (1: Form Parser, 2: Solution Generator, 3: Action Generator)

For each agent, it logs:
- query.txt: Agent prompt/input
- response.txt: Agent output
- log.txt: Terminal/logger output
- media/: Screenshots and images
- rag/ (Agent 2 only): RAG queries, responses, and source files
"""
import io
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class FileLogger:
    """
    Handles structured file logging for the 3-agent analysis system.

    Directory structure:
    ./log/
      └── [USER_ID]/
          └── [YYYY-MM-DD]_[HH-MM]_[REQUEST_ID]/
              ├── Agent_1_Form_Parser/
              │   ├── media/
              │   ├── query.txt
              │   ├── response.txt
              │   └── log.txt
              ├── Agent_2_Solution_Generator/
              │   ├── question_0/
              │   │   ├── media/
              │   │   ├── rag/
              │   │   │   ├── query.txt
              │   │   │   ├── response.txt
              │   │   │   └── [rag_images]
              │   │   ├── query.txt
              │   │   ├── response.txt
              │   │   └── log.txt
              │   ├── question_1/
              │   │   ├── media/
              │   │   ├── rag/
              │   │   ├── query.txt
              │   │   ├── response.txt
              │   │   └── log.txt
              │   └── ...
              └── Agent_3_Action_Generator/
                  ├── media/
                  ├── query.txt
                  ├── response.txt
                  └── log.txt
    """

    AGENT_NAMES = {
        1: "Agent_1_Form_Parser",
        2: "Agent_2_Solution_Generator",
        3: "Agent_3_Action_Generator",
    }

    def __init__(self, user_id: str, request_id: str, base_path: str = "./log"):
        """
        Initialize FileLogger for a specific request.

        Args:
            user_id: User ID
            request_id: Request ID
            base_path: Base directory for logs (default: ./log)
        """
        self.user_id = user_id
        self.request_id = request_id
        self.base_path = Path(base_path)

        # Add date and time prefix to folder name: YYYY-MM-DD_HH_MM_request_id
        current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M")
        folder_name = f"{current_datetime}_{request_id}"
        self.request_path = self.base_path / user_id / folder_name

        # Create base request directory
        self._create_directory_structure()

        logger.info(
            f"FileLogger initialized for user={user_id}, request={request_id}, path={self.request_path}"
        )

    def _create_directory_structure(self):
        """Create the complete directory structure for all agents."""
        try:
            # Create directories for each agent
            for agent_num in [1, 2, 3]:
                agent_dir = self.request_path / self.AGENT_NAMES[agent_num]
                agent_dir.mkdir(parents=True, exist_ok=True)

                # Create media folder only for Agent 1 and 3
                # Agent 2 uses per-question subdirectories, so no base folders
                if agent_num in [1, 3]:
                    (agent_dir / "media").mkdir(exist_ok=True)

            logger.info(f"Created directory structure at {self.request_path}")
        except Exception as e:
            logger.error(f"Failed to create directory structure: {e}", exc_info=True)

    def _get_agent_dir(self, agent_num: int, subdir: Optional[str] = None) -> Path:
        """
        Get the directory path for a specific agent.

        Args:
            agent_num: Agent number (1, 2, or 3)
            subdir: Optional subdirectory name (e.g., "question_0", "batch_1")

        Returns:
            Path to agent directory (with optional subdirectory)
        """
        agent_dir = self.request_path / self.AGENT_NAMES[agent_num]
        if subdir:
            agent_dir = agent_dir / subdir
            # Create subdirectory if it doesn't exist
            agent_dir.mkdir(parents=True, exist_ok=True)
        return agent_dir

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        return "".join(c if c.isalnum() or c in "._- " else "_" for c in name)

    def log_agent_query(self, agent_num: int, query: str, subdir: Optional[str] = None):
        """
        Log agent query/prompt to query.txt.

        Args:
            agent_num: Agent number (1, 2, or 3)
            query: Query text/prompt
            subdir: Optional subdirectory name (e.g., "question_0", "batch_1")
        """
        try:
            query_file = self._get_agent_dir(agent_num, subdir) / "query.txt"
            with open(query_file, "w", encoding="utf-8") as f:
                f.write(query)
            subdir_info = f" in {subdir}" if subdir else ""
            logger.debug(f"Logged query for {self.AGENT_NAMES[agent_num]}{subdir_info} ({len(query)} chars)")
        except Exception as e:
            logger.error(f"Failed to log query for agent {agent_num}: {e}", exc_info=True)

    def log_agent_response(self, agent_num: int, response: Any, subdir: Optional[str] = None):
        """
        Log agent response to response.txt.

        Args:
            agent_num: Agent number (1, 2, or 3)
            response: Response data (will be JSON-serialized if dict/list)
            subdir: Optional subdirectory name (e.g., "question_0", "batch_1")
        """
        try:
            response_file = self._get_agent_dir(agent_num, subdir) / "response.txt"

            # Convert response to string
            if isinstance(response, (dict, list)):
                response_str = json.dumps(response, indent=2, ensure_ascii=False)
            else:
                response_str = str(response)

            with open(response_file, "w", encoding="utf-8") as f:
                f.write(response_str)
            subdir_info = f" in {subdir}" if subdir else ""
            logger.debug(f"Logged response for {self.AGENT_NAMES[agent_num]}{subdir_info} ({len(response_str)} chars)")
        except Exception as e:
            logger.error(f"Failed to log response for agent {agent_num}: {e}", exc_info=True)

    def log_agent_output(self, agent_num: int, message: str, subdir: Optional[str] = None):
        """
        Append log message to log.txt (simulates terminal output).

        Args:
            agent_num: Agent number (1, 2, or 3)
            message: Log message to append
            subdir: Optional subdirectory name (e.g., "question_0", "batch_1")
        """
        try:
            log_file = self._get_agent_dir(agent_num, subdir) / "log.txt"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{message}\n")
        except Exception as e:
            logger.error(f"Failed to log output for agent {agent_num}: {e}", exc_info=True)

    def save_screenshot(self, agent_num: int, screenshot_bytes: bytes, index: int, subdir: Optional[str] = None):
        """
        Save screenshot to media/ folder.

        Args:
            agent_num: Agent number (1, 2, or 3)
            screenshot_bytes: Screenshot image bytes
            index: Screenshot index (for naming)
            subdir: Optional subdirectory name (e.g., "question_0", "batch_1")
        """
        try:
            filename = f"screenshot_{index}.png"
            self.save_agent_media(agent_num, filename, screenshot_bytes, subdir=subdir)
        except Exception as e:
            logger.error(f"Failed to save screenshot for agent {agent_num}: {e}", exc_info=True)

    def save_screenshots(self, agent_num: int, screenshots: List[bytes], subdir: Optional[str] = None):
        """
        Save multiple screenshots to media/ folder.

        Args:
            agent_num: Agent number (1, 2, or 3)
            screenshots: List of screenshot image bytes
            subdir: Optional subdirectory name (e.g., "question_0", "batch_1")
        """
        for idx, screenshot_bytes in enumerate(screenshots):
            self.save_screenshot(agent_num, screenshot_bytes, idx, subdir)
        subdir_info = f" in {subdir}" if subdir else ""
        logger.info(f"Saved {len(screenshots)} screenshots for {self.AGENT_NAMES[agent_num]}{subdir_info}")

    def save_agent_media(self, agent_num: int, filename: str, data: bytes, subdir: Optional[str] = None):
        """
        Persist arbitrary binary attachments (pdf/image/etc.) to the agent's media folder.

        Args:
            agent_num: Agent number (1, 2, or 3)
            filename: Suggested filename (will be sanitized)
            data: Attachment byte content
            subdir: Optional subdirectory name (e.g., "question_0", "batch_1")
        """
        try:
            media_dir = self._get_agent_dir(agent_num, subdir) / "media"
            media_dir.mkdir(parents=True, exist_ok=True)
            safe_name = self._sanitize_filename(filename).strip() or "attachment.bin"
            filepath = media_dir / safe_name
            with open(filepath, "wb") as f:
                f.write(data)
            subdir_info = f" in {subdir}" if subdir else ""
            logger.debug(
                f"Saved media file for {self.AGENT_NAMES[agent_num]}{subdir_info}: {safe_name} ({len(data)} bytes)"
            )
        except Exception as e:
            logger.error(f"Failed to save media file {filename}: {e}", exc_info=True)

    # ===== RAG Logging (Agent 2 only) =====

    def log_rag_query(self, query: str, subdir: Optional[str] = None):
        """
        Log RAG search query to rag/query.txt (Agent 2 only).

        Args:
            query: RAG search query
            subdir: Optional subdirectory name (e.g., "question_0")
        """
        try:
            if subdir:
                # Per-question RAG: question_X/rag/query.txt
                rag_dir = self._get_agent_dir(2, subdir) / "rag"
            else:
                # Global RAG: rag/query.txt
                rag_dir = self._get_agent_dir(2) / "rag"

            rag_dir.mkdir(parents=True, exist_ok=True)
            query_file = rag_dir / "query.txt"

            # Append query with separator if file exists
            mode = "a" if query_file.exists() else "w"
            with open(query_file, mode, encoding="utf-8") as f:
                if mode == "a":
                    f.write("\n" + "="*80 + "\n")
                f.write(query)
            subdir_info = f" in {subdir}" if subdir else ""
            logger.debug(f"Logged RAG query{subdir_info} ({len(query)} chars)")
        except Exception as e:
            logger.error(f"Failed to log RAG query: {e}", exc_info=True)

    def log_rag_response(self, response: Dict[str, List], subdir: Optional[str] = None):
        """
        Log RAG retrieval response to rag/response.txt (Agent 2 only).

        Args:
            response: RAG response dict with 'text_chunks' and 'image_chunks'
            subdir: Optional subdirectory name (e.g., "question_0")
        """
        try:
            if subdir:
                # Per-question RAG: question_X/rag/response.txt
                rag_dir = self._get_agent_dir(2, subdir) / "rag"
            else:
                # Global RAG: rag/response.txt
                rag_dir = self._get_agent_dir(2) / "rag"

            rag_dir.mkdir(parents=True, exist_ok=True)
            response_file = rag_dir / "response.txt"

            # Format response
            response_str = json.dumps(response, indent=2, ensure_ascii=False, default=str)

            # Append response with separator if file exists
            mode = "a" if response_file.exists() else "w"
            with open(response_file, mode, encoding="utf-8") as f:
                if mode == "a":
                    f.write("\n" + "="*80 + "\n")
                f.write(response_str)
            subdir_info = f" in {subdir}" if subdir else ""
            logger.debug(f"Logged RAG response{subdir_info} ({len(response_str)} chars)")
        except Exception as e:
            logger.error(f"Failed to log RAG response: {e}", exc_info=True)

    def log_rag_chunk_counts(
        self,
        text_chunks: int,
        image_chunks: int,
        scope: str,
        subdir: Optional[str] = None,
    ):
        """
        Append RAG chunk count metadata to rag/chunk_counts.jsonl.

        Args:
            text_chunks: Number of retrieved text chunks
            image_chunks: Number of retrieved image chunks
            scope: Human-readable scope identifier (e.g., "question_1", "total")
            subdir: Optional subdirectory name (e.g., "question_0")
        """
        try:
            if subdir:
                rag_dir = self._get_agent_dir(2, subdir) / "rag"
            else:
                rag_dir = self._get_agent_dir(2) / "rag"

            rag_dir.mkdir(parents=True, exist_ok=True)
            chunk_file = rag_dir / "chunk_counts.jsonl"
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "scope": scope,
                "text_chunks": text_chunks,
                "image_chunks": image_chunks,
            }
            with open(chunk_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False))
                f.write("\n")
            subdir_info = f" in {subdir}" if subdir else ""
            logger.debug(
                "Logged RAG chunk counts%s: scope=%s text=%d image=%d",
                subdir_info,
                scope,
                text_chunks,
                image_chunks,
            )
        except Exception as e:
            logger.error(f"Failed to log RAG chunk counts: {e}", exc_info=True)

    def save_rag_image(self, image_bytes: bytes, source_name: str, index: int, subdir: Optional[str] = None):
        """
        Save RAG-retrieved image to rag/ folder (Agent 2 only).

        Args:
            image_bytes: Image bytes
            source_name: Source file name (for naming)
            index: Image index
            subdir: Optional subdirectory name (e.g., "question_0")
        """
        try:
            if subdir:
                # Per-question RAG: question_X/rag/
                rag_dir = self._get_agent_dir(2, subdir) / "rag"
            else:
                # Global RAG: rag/
                rag_dir = self._get_agent_dir(2) / "rag"

            rag_dir.mkdir(parents=True, exist_ok=True)

            # Sanitize source name for filename
            safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in source_name)
            filename = f"rag_image_{index}_{safe_name}.png"
            filepath = rag_dir / filename

            with open(filepath, "wb") as f:
                f.write(image_bytes)
            logger.debug(f"Saved RAG image to {filepath} ({len(image_bytes)} bytes)")
        except Exception as e:
            logger.error(f"Failed to save RAG image: {e}", exc_info=True)

    def save_rag_file(self, file_bytes: bytes, filename: str, subdir: Optional[str] = None):
        """
        Save RAG source file to rag/ folder (Agent 2 only).

        Args:
            file_bytes: File bytes
            filename: Original filename
            subdir: Optional subdirectory name (e.g., "question_0")
        """
        try:
            if subdir:
                # Per-question RAG: question_X/rag/
                rag_dir = self._get_agent_dir(2, subdir) / "rag"
            else:
                # Global RAG: rag/
                rag_dir = self._get_agent_dir(2) / "rag"

            rag_dir.mkdir(parents=True, exist_ok=True)

            # Sanitize filename
            safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in filename)
            filepath = rag_dir / safe_name

            with open(filepath, "wb") as f:
                f.write(file_bytes)
            logger.debug(f"Saved RAG file to {filepath} ({len(file_bytes)} bytes)")
        except Exception as e:
            logger.error(f"Failed to save RAG file: {e}", exc_info=True)

    # ===== Utility Methods =====

    def get_log_path(self) -> str:
        """Get the absolute path to this request's log directory."""
        return str(self.request_path.absolute())

    def cleanup(self):
        """Optional cleanup method (currently does nothing - manual cleanup)."""
        pass


# ===== Custom Log Handler for capturing logger output =====

class AgentLogHandler(logging.Handler):
    """
    Custom logging handler that captures log messages and writes them to agent log.txt files.
    """

    def __init__(self, file_logger: FileLogger, agent_num: int):
        """
        Initialize handler.

        Args:
            file_logger: FileLogger instance
            agent_num: Agent number to log for
        """
        super().__init__()
        self.file_logger = file_logger
        self.agent_num = agent_num
        self.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))

    def emit(self, record: logging.LogRecord):
        """
        Emit a log record to the agent's log.txt file.

        Args:
            record: Log record to emit
        """
        try:
            msg = self.format(record)
            self.file_logger.log_agent_output(self.agent_num, msg)
        except Exception:
            self.handleError(record)


def create_file_logger(user_id: str, request_id: str, enabled: bool = False) -> Optional[FileLogger]:
    """
    Factory function to create FileLogger if logging is enabled.

    Args:
        user_id: User ID
        request_id: Request ID
        enabled: Whether file logging is enabled (from LOG_FILE setting)

    Returns:
        FileLogger instance if enabled, None otherwise
    """
    if not enabled:
        return None

    try:
        return FileLogger(user_id, request_id)
    except Exception as e:
        logger.error(f"Failed to create FileLogger: {e}", exc_info=True)
        # Don't fail the request if logging fails
        return None

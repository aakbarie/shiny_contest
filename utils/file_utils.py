"""
Secure file handling utilities.

This module provides utilities for:
- Safe filename generation
- Secure file cleanup
- Temporary file management
"""

import os
import re
import tempfile
import uuid
from pathlib import Path
from contextlib import contextmanager
from typing import Generator, Optional
import logging

from config import config

logger = logging.getLogger(__name__)


class FileSystemError(Exception):
    """Custom exception for file system errors."""
    pass


def get_safe_filename(original_filename: str, prefix: str = "") -> str:
    """
    Generate a safe filename from user input.

    Args:
        original_filename: Original filename from user
        prefix: Optional prefix for the filename

    Returns:
        Safe filename with unique identifier

    Examples:
        >>> get_safe_filename("my data.csv")
        'my_data_abc123.csv'
        >>> get_safe_filename("../../etc/passwd", "upload")
        'upload_etc_passwd_abc123.txt'
    """
    # Get the file extension
    path = Path(original_filename)
    ext = path.suffix.lower()

    # Get the base name without extension
    base = path.stem

    # Remove any path components (security)
    base = os.path.basename(base)

    # Replace unsafe characters with underscores
    base = re.sub(r'[^\w\-]', '_', base)

    # Remove consecutive underscores
    base = re.sub(r'_+', '_', base)

    # Trim to reasonable length
    max_base_length = 50
    if len(base) > max_base_length:
        base = base[:max_base_length]

    # Remove leading/trailing underscores
    base = base.strip('_')

    # If base is empty, use a default
    if not base:
        base = "file"

    # Add prefix if provided
    if prefix:
        prefix = re.sub(r'[^\w\-]', '_', prefix)
        base = f"{prefix}_{base}"

    # Add unique identifier to prevent collisions
    unique_id = uuid.uuid4().hex[:8]

    # Ensure extension is safe
    if ext and ext not in {".csv", ".py", ".txt"}:
        ext = ".txt"
    elif not ext:
        ext = ".txt"

    return f"{base}_{unique_id}{ext}"


@contextmanager
def secure_temp_file(
    suffix: str = "",
    prefix: str = "shiny_",
    dir: Optional[Path] = None,
    delete: bool = True
) -> Generator[Path, None, None]:
    """
    Context manager for secure temporary file creation and cleanup.

    Args:
        suffix: File suffix/extension
        prefix: File prefix
        dir: Directory for temp file (default: config.temp_dir)
        delete: Whether to delete file after use

    Yields:
        Path to temporary file

    Example:
        >>> with secure_temp_file(suffix=".py") as temp_path:
        ...     temp_path.write_text("print('hello')")
        ...     # File is automatically deleted after block
    """
    temp_dir = dir or config.temp_dir
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Create temporary file
    fd, temp_path = tempfile.mkstemp(
        suffix=suffix,
        prefix=prefix,
        dir=str(temp_dir)
    )

    try:
        # Close the file descriptor
        os.close(fd)

        # Convert to Path object
        temp_path_obj = Path(temp_path)

        # Set restrictive permissions (owner read/write only)
        temp_path_obj.chmod(0o600)

        logger.debug(f"Created temporary file: {temp_path_obj}")

        yield temp_path_obj

    finally:
        # Cleanup
        if delete:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    logger.debug(f"Deleted temporary file: {temp_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temp file {temp_path}: {e}")


@contextmanager
def secure_temp_directory(
    prefix: str = "shiny_",
    dir: Optional[Path] = None,
    delete: bool = True
) -> Generator[Path, None, None]:
    """
    Context manager for secure temporary directory creation and cleanup.

    Args:
        prefix: Directory prefix
        dir: Parent directory (default: config.temp_dir)
        delete: Whether to delete directory after use

    Yields:
        Path to temporary directory

    Example:
        >>> with secure_temp_directory() as temp_dir:
        ...     (temp_dir / "file.txt").write_text("content")
        ...     # Directory is automatically deleted after block
    """
    parent_dir = dir or config.temp_dir
    parent_dir.mkdir(parents=True, exist_ok=True)

    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix=prefix, dir=str(parent_dir))
    temp_dir_obj = Path(temp_dir)

    # Set restrictive permissions
    temp_dir_obj.chmod(0o700)

    logger.debug(f"Created temporary directory: {temp_dir_obj}")

    try:
        yield temp_dir_obj
    finally:
        # Cleanup
        if delete:
            try:
                import shutil
                if temp_dir_obj.exists():
                    shutil.rmtree(temp_dir_obj)
                    logger.debug(f"Deleted temporary directory: {temp_dir_obj}")
            except Exception as e:
                logger.warning(f"Failed to delete temp directory {temp_dir_obj}: {e}")


def secure_file_cleanup(file_path: Path, max_retries: int = 3) -> bool:
    """
    Safely delete a file with retries.

    Args:
        file_path: Path to file to delete
        max_retries: Maximum number of deletion attempts

    Returns:
        True if file was deleted, False otherwise
    """
    if not file_path.exists():
        logger.debug(f"File does not exist, skipping cleanup: {file_path}")
        return True

    for attempt in range(max_retries):
        try:
            file_path.unlink()
            logger.info(f"Deleted file: {file_path}")
            return True
        except Exception as e:
            logger.warning(
                f"Failed to delete file {file_path} "
                f"(attempt {attempt + 1}/{max_retries}): {e}"
            )
            if attempt < max_retries - 1:
                import time
                time.sleep(0.1)  # Brief delay before retry

    logger.error(f"Failed to delete file after {max_retries} attempts: {file_path}")
    return False


def ensure_directory(directory: Path, create: bool = True) -> Path:
    """
    Ensure a directory exists and is writable.

    Args:
        directory: Path to directory
        create: Whether to create if it doesn't exist

    Returns:
        Path to directory

    Raises:
        FileSystemError: If directory cannot be created or is not writable
    """
    if not directory.exists():
        if create:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created directory: {directory}")
            except Exception as e:
                raise FileSystemError(f"Failed to create directory {directory}: {e}")
        else:
            raise FileSystemError(f"Directory does not exist: {directory}")

    if not directory.is_dir():
        raise FileSystemError(f"Path is not a directory: {directory}")

    # Check if writable (try to create a temp file)
    try:
        test_file = directory / f".write_test_{uuid.uuid4().hex[:8]}"
        test_file.touch()
        test_file.unlink()
    except Exception as e:
        raise FileSystemError(f"Directory is not writable: {directory}: {e}")

    return directory


def get_file_size_mb(file_path: Path) -> float:
    """
    Get file size in megabytes.

    Args:
        file_path: Path to file

    Returns:
        File size in MB
    """
    if not file_path.exists():
        return 0.0

    size_bytes = file_path.stat().st_size
    return size_bytes / (1024 * 1024)


def is_path_safe(path: Path, allowed_parent: Path) -> bool:
    """
    Check if a path is safe (within allowed parent directory).

    Args:
        path: Path to check
        allowed_parent: Allowed parent directory

    Returns:
        True if path is safe, False otherwise

    Example:
        >>> is_path_safe(Path("/tmp/upload/file.csv"), Path("/tmp/upload"))
        True
        >>> is_path_safe(Path("/etc/passwd"), Path("/tmp/upload"))
        False
    """
    try:
        # Resolve to absolute paths
        abs_path = path.resolve()
        abs_parent = allowed_parent.resolve()

        # Check if path is relative to allowed parent
        abs_path.relative_to(abs_parent)
        return True
    except (ValueError, RuntimeError):
        # ValueError: path is not relative to parent
        # RuntimeError: infinite loop in resolution
        return False

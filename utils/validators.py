"""
Input validation utilities for secure file uploads and user inputs.

This module provides validators for:
- File uploads (size, type, content)
- User text inputs (length, content)
- CSV data structure
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd

from config import config


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


class FileValidator:
    """Validator for file uploads with security checks."""

    # Allowed file extensions
    ALLOWED_EXTENSIONS = {".csv"}

    # MIME types for CSV (basic check without python-magic for now)
    CSV_MIME_TYPES = {
        "text/csv",
        "application/csv",
        "text/plain",  # Sometimes CSV files are detected as plain text
    }

    def __init__(self, max_size_mb: Optional[int] = None):
        """
        Initialize file validator.

        Args:
            max_size_mb: Maximum file size in MB (default from config)
        """
        self.max_size_bytes = (
            (max_size_mb * 1024 * 1024)
            if max_size_mb
            else config.max_file_size_bytes
        )

    def validate_upload(self, file_info: Dict) -> None:
        """
        Validate uploaded file.

        Args:
            file_info: File information dict from Shiny input

        Raises:
            ValidationError: If file fails validation
        """
        if not file_info:
            raise ValidationError("No file provided")

        # Validate file name
        filename = file_info.get("name", "")
        if not filename:
            raise ValidationError("File name is missing")

        self._validate_filename(filename)

        # Validate file size
        file_path = file_info.get("datapath", "")
        if not file_path or not os.path.exists(file_path):
            raise ValidationError("File path is invalid")

        self._validate_file_size(file_path)

        # Validate file extension
        self._validate_extension(filename)

    def _validate_filename(self, filename: str) -> None:
        """
        Validate filename for security issues.

        Args:
            filename: Name of the file

        Raises:
            ValidationError: If filename is invalid
        """
        # Check for path traversal attempts
        if ".." in filename or "/" in filename or "\\" in filename:
            raise ValidationError("Invalid filename: path traversal detected")

        # Check for hidden files
        if filename.startswith("."):
            raise ValidationError("Hidden files are not allowed")

        # Check for reasonable length
        if len(filename) > 255:
            raise ValidationError("Filename too long (max 255 characters)")

        # Check for null bytes
        if "\x00" in filename:
            raise ValidationError("Invalid filename: null byte detected")

    def _validate_file_size(self, file_path: str) -> None:
        """
        Validate file size.

        Args:
            file_path: Path to the file

        Raises:
            ValidationError: If file is too large
        """
        file_size = os.path.getsize(file_path)
        if file_size > self.max_size_bytes:
            max_mb = self.max_size_bytes / (1024 * 1024)
            actual_mb = file_size / (1024 * 1024)
            raise ValidationError(
                f"File too large: {actual_mb:.2f}MB (max {max_mb:.0f}MB)"
            )

        if file_size == 0:
            raise ValidationError("File is empty")

    def _validate_extension(self, filename: str) -> None:
        """
        Validate file extension.

        Args:
            filename: Name of the file

        Raises:
            ValidationError: If extension is not allowed
        """
        ext = Path(filename).suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            allowed = ", ".join(self.ALLOWED_EXTENSIONS)
            raise ValidationError(f"Invalid file type. Allowed: {allowed}")

    def validate_csv_content(self, file_path: str) -> pd.DataFrame:
        """
        Validate CSV file content and structure.

        Args:
            file_path: Path to CSV file

        Returns:
            Validated DataFrame

        Raises:
            ValidationError: If CSV content is invalid
        """
        try:
            # Try to read CSV with pandas
            df = pd.read_csv(file_path)
        except pd.errors.EmptyDataError:
            raise ValidationError("CSV file is empty")
        except pd.errors.ParserError as e:
            raise ValidationError(f"Invalid CSV format: {str(e)}")
        except Exception as e:
            raise ValidationError(f"Failed to read CSV: {str(e)}")

        # Validate DataFrame
        if df.empty:
            raise ValidationError("CSV file contains no data")

        if len(df.columns) == 0:
            raise ValidationError("CSV file has no columns")

        # Check for reasonable row count (prevent DoS)
        max_rows = 100000  # Configurable if needed
        if len(df) > max_rows:
            raise ValidationError(
                f"CSV too large: {len(df)} rows (max {max_rows})"
            )

        # Validate column names
        self._validate_column_names(df.columns.tolist())

        return df

    def _validate_column_names(self, columns: List[str]) -> None:
        """
        Validate CSV column names.

        Args:
            columns: List of column names

        Raises:
            ValidationError: If column names are invalid
        """
        if not columns:
            raise ValidationError("CSV must have at least one column")

        for col in columns:
            # Check for empty column names
            if not col or str(col).strip() == "":
                raise ValidationError("Column names cannot be empty")

            # Check for excessively long column names
            if len(str(col)) > 200:
                raise ValidationError(
                    f"Column name too long: {str(col)[:50]}... (max 200 chars)"
                )

        # Check for duplicate column names
        if len(columns) != len(set(columns)):
            duplicates = [col for col in columns if columns.count(col) > 1]
            raise ValidationError(f"Duplicate column names: {set(duplicates)}")


class InputValidator:
    """Validator for user text inputs."""

    # Patterns that might indicate prompt injection
    SUSPICIOUS_PATTERNS = [
        r"ignore\s+previous\s+instructions",
        r"ignore\s+all\s+previous",
        r"disregard\s+previous",
        r"forget\s+previous",
        r"new\s+instructions:",
        r"system\s*:",
        r"<\s*script",  # XSS attempt
        r"javascript:",  # XSS attempt
    ]

    def __init__(self, max_length: Optional[int] = None):
        """
        Initialize input validator.

        Args:
            max_length: Maximum input length (default from config)
        """
        self.max_length = max_length or config.max_description_length

    def validate_description(self, description: str) -> str:
        """
        Validate user description input.

        Args:
            description: User-provided description

        Returns:
            Sanitized description

        Raises:
            ValidationError: If description is invalid
        """
        if not description:
            raise ValidationError("Description cannot be empty")

        # Check length
        if len(description) > self.max_length:
            raise ValidationError(
                f"Description too long: {len(description)} chars "
                f"(max {self.max_length})"
            )

        # Check for null bytes
        if "\x00" in description:
            raise ValidationError("Invalid description: null byte detected")

        # Check for potential prompt injection
        self._check_prompt_injection(description)

        # Sanitize and return
        return self._sanitize_text(description)

    def _check_prompt_injection(self, text: str) -> None:
        """
        Check for potential prompt injection patterns.

        Args:
            text: Text to check

        Raises:
            ValidationError: If suspicious patterns detected
        """
        text_lower = text.lower()

        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                raise ValidationError(
                    "Input contains suspicious content. "
                    "Please rephrase your description."
                )

    def _sanitize_text(self, text: str) -> str:
        """
        Sanitize text input.

        Args:
            text: Text to sanitize

        Returns:
            Sanitized text
        """
        # Remove any control characters except newlines and tabs
        sanitized = "".join(
            char for char in text
            if char == "\n" or char == "\t" or (ord(char) >= 32 and ord(char) != 127)
        )

        # Normalize whitespace
        sanitized = " ".join(sanitized.split())

        return sanitized.strip()

    def validate_checkbox(self, value: bool) -> bool:
        """
        Validate checkbox input (simple type check).

        Args:
            value: Checkbox value

        Returns:
            Validated boolean

        Raises:
            ValidationError: If value is not boolean
        """
        if not isinstance(value, bool):
            raise ValidationError("Invalid checkbox value")
        return value

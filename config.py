"""
Configuration management for Shiny App Generator.

This module loads and validates configuration from environment variables.
Copy .env.example to .env and customize for your environment.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    def __init__(self):
        """Initialize configuration with validation."""
        self._validate_required_vars()
        self._ensure_directories()

    # ========================================================================
    # LLM Configuration
    # ========================================================================
    @property
    def llm_model(self) -> str:
        """LLM model name for Ollama."""
        return os.getenv("LLM_MODEL", "deepseek-coder-v2")

    @property
    def ollama_base_url(self) -> str:
        """Ollama API base URL."""
        return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # ========================================================================
    # Server Configuration
    # ========================================================================
    @property
    def app_host(self) -> str:
        """Application host address."""
        return os.getenv("APP_HOST", "0.0.0.0")

    @property
    def app_port(self) -> int:
        """Application port number."""
        return int(os.getenv("APP_PORT", "8050"))

    # ========================================================================
    # Security Settings
    # ========================================================================
    @property
    def max_file_size_mb(self) -> int:
        """Maximum file upload size in MB."""
        return int(os.getenv("MAX_FILE_SIZE_MB", "50"))

    @property
    def max_file_size_bytes(self) -> int:
        """Maximum file upload size in bytes."""
        return self.max_file_size_mb * 1024 * 1024

    @property
    def max_description_length(self) -> int:
        """Maximum length for user description input."""
        return int(os.getenv("MAX_DESCRIPTION_LENGTH", "1000"))

    @property
    def code_execution_timeout(self) -> int:
        """Code execution timeout in seconds."""
        return int(os.getenv("CODE_EXECUTION_TIMEOUT", "30"))

    @property
    def max_memory_mb(self) -> int:
        """Maximum memory for generated app in MB."""
        return int(os.getenv("MAX_MEMORY_MB", "512"))

    # ========================================================================
    # File Storage
    # ========================================================================
    @property
    def upload_dir(self) -> Path:
        """Directory for uploaded files."""
        return Path(os.getenv("UPLOAD_DIR", "./uploads"))

    @property
    def generated_dir(self) -> Path:
        """Directory for generated apps."""
        return Path(os.getenv("GENERATED_DIR", "./generated_apps"))

    @property
    def temp_dir(self) -> Path:
        """Temporary directory for code execution."""
        return Path(os.getenv("TEMP_DIR", "./temp"))

    # ========================================================================
    # Logging Configuration
    # ========================================================================
    @property
    def log_level(self) -> str:
        """Logging level."""
        level = os.getenv("LOG_LEVEL", "INFO").upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        return level if level in valid_levels else "INFO"

    @property
    def log_file(self) -> Optional[Path]:
        """Log file path, None for console only."""
        log_file = os.getenv("LOG_FILE", "")
        return Path(log_file) if log_file else None

    @property
    def enable_request_id(self) -> bool:
        """Enable request ID tracking."""
        return os.getenv("ENABLE_REQUEST_ID", "true").lower() == "true"

    # ========================================================================
    # Rate Limiting
    # ========================================================================
    @property
    def rate_limit_enabled(self) -> bool:
        """Enable rate limiting."""
        return os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"

    @property
    def rate_limit_per_minute(self) -> int:
        """Maximum requests per minute."""
        return int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))

    # ========================================================================
    # Features
    # ========================================================================
    @property
    def pygwalker_default(self) -> bool:
        """Enable PyGWalker by default."""
        return os.getenv("PYGWALKER_DEFAULT", "true").lower() == "true"

    @property
    def enable_code_download(self) -> bool:
        """Enable code download feature."""
        return os.getenv("ENABLE_CODE_DOWNLOAD", "true").lower() == "true"

    # ========================================================================
    # Development Settings
    # ========================================================================
    @property
    def debug(self) -> bool:
        """Enable debug mode."""
        return os.getenv("DEBUG", "false").lower() == "true"

    @property
    def environment(self) -> str:
        """Environment name: development, staging, production."""
        return os.getenv("ENVIRONMENT", "development")

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == "development"

    # ========================================================================
    # Validation & Setup
    # ========================================================================
    def _validate_required_vars(self):
        """Validate that critical configuration is present."""
        # Check that numeric values are valid
        try:
            assert self.app_port > 0 and self.app_port < 65536, "APP_PORT must be between 1-65535"
            assert self.max_file_size_mb > 0, "MAX_FILE_SIZE_MB must be positive"
            assert self.max_description_length > 0, "MAX_DESCRIPTION_LENGTH must be positive"
            assert self.code_execution_timeout > 0, "CODE_EXECUTION_TIMEOUT must be positive"
            assert self.max_memory_mb > 0, "MAX_MEMORY_MB must be positive"
        except (ValueError, AssertionError) as e:
            raise ValueError(f"Invalid configuration: {e}")

    def _ensure_directories(self):
        """Create required directories if they don't exist."""
        directories = [
            self.upload_dir,
            self.generated_dir,
            self.temp_dir,
        ]

        # Create log directory if log file is specified
        if self.log_file:
            directories.append(self.log_file.parent)

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def get_summary(self) -> dict:
        """Get configuration summary for logging (without sensitive data)."""
        return {
            "llm_model": self.llm_model,
            "app_host": self.app_host,
            "app_port": self.app_port,
            "environment": self.environment,
            "debug": self.debug,
            "log_level": self.log_level,
            "max_file_size_mb": self.max_file_size_mb,
            "rate_limit_enabled": self.rate_limit_enabled,
        }


# Global configuration instance
config = Config()

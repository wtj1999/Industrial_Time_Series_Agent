"""
System configuration settings for Industrial Time Series Agent System.
"""

import os
from typing import Optional, List
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class DatabaseConfig(BaseModel):
    """Database configuration for session storage."""
    backend: str = Field(default="sqlite", description="Database backend: sqlite, postgresql, redis")
    connection_string: Optional[str] = Field(default=None, description="Database connection string")
    table_name: str = Field(default="sessions", description="Table name for sessions")


class Settings(BaseModel):
    """Main application settings."""

    # Application
    app_name: str = "Industrial Time Series Agent System"
    version: str = "1.0.0"
    debug: bool = True

    # LLM Configuration (flat format)
    MODEL_NAME: str = Field(default=os.getenv("MODEL_NAME", "Qwen3-235B-A22B"), description="Model name")
    BASE_URL: Optional[str] = Field(default=os.getenv("BASE_URL", "http://10.2.131.172:8000/v1"), description="Base URL for API")
    API_KEY: str = Field(default=os.getenv("API_KEY", "EMPTY"), description="API key")
    TEMPERATURE: float = Field(default=float(os.getenv("TEMPERATURE", "0.7")), description="Temperature for generation")
    TIMEOUT: int = Field(default=int(os.getenv("TIMEOUT", "600")), description="Request timeout in seconds")

    # Database Configuration
    database: DatabaseConfig = Field(
        default_factory=lambda: DatabaseConfig(
            backend=os.getenv("DB_BACKEND", "sqlite"),
            connection_string=os.getenv("DB_CONNECTION_STRING", "sqlite:///sessions.db"),
            table_name=os.getenv("DB_TABLE_NAME", "sessions")
        )
    )

    # Agent Configuration
    max_conversation_history: int = Field(
        default=int(os.getenv("MAX_CONVERSATION_HISTORY", "50")),
        description="Maximum number of conversation turns to keep"
    )
    session_timeout_minutes: int = Field(
        default=int(os.getenv("SESSION_TIMEOUT_MINUTES", "30")),
        description="Session timeout in minutes"
    )

    # Analysis Configuration
    default_prediction_steps: int = Field(
        default=int(os.getenv("DEFAULT_PREDICTION_STEPS", "25")),
        description="Default prediction steps"
    )
    max_prediction_steps: int = Field(
        default=int(os.getenv("MAX_PREDICTION_STEPS", "100")),
        description="Maximum prediction steps allowed"
    )

    # Supported Tasks
    supported_tasks: List[str] = Field(
        default=[
            "prediction",
            "anomaly_detection",
            "trend_analysis",
            "correlation_analysis",
            "data_explanation",
            "report_generation",
            "comparative_analysis"
        ],
        description="List of supported task types"
    )

    # File Upload Configuration
    max_file_size_mb: int = Field(
        default=int(os.getenv("MAX_FILE_SIZE_MB", "100")),
        description="Maximum file upload size in MB"
    )
    allowed_file_extensions: List[str] = Field(
        default=[".csv", ".xlsx", ".parquet"],
        description="Allowed file extensions"
    )

    # Caching Configuration
    enable_caching: bool = Field(
        default=os.getenv("ENABLE_CACHING", "true").lower() == "true",
        description="Enable caching for better performance"
    )
    cache_ttl_seconds: int = Field(
        default=int(os.getenv("CACHE_TTL_SECONDS", "3600")),
        description="Cache time-to-live in seconds"
    )


# Global settings instance
settings = Settings()

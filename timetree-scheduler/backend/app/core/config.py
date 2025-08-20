"""
Configuration settings for TimeTree Scheduler API.

Uses Pydantic Settings for environment variable management with validation.
"""

import secrets
from typing import List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Environment
    ENVIRONMENT: str = Field(default="development", description="Application environment")
    DEBUG: bool = Field(default=False, description="Debug mode")
    
    # Database
    DATABASE_URL: str = Field(..., description="PostgreSQL database URL")
    DATABASE_URL_TEST: Optional[str] = Field(None, description="Test database URL")
    
    # TimeTree API
    TIMETREE_CLIENT_ID: str = Field(..., description="TimeTree OAuth client ID")
    TIMETREE_CLIENT_SECRET: str = Field(..., description="TimeTree OAuth client secret")
    TIMETREE_REDIRECT_URI: str = Field(
        default="http://localhost:8000/auth/timetree/callback",
        description="TimeTree OAuth redirect URI"
    )
    TIMETREE_API_BASE_URL: str = Field(
        default="https://timetreeapis.com",
        description="TimeTree API base URL"
    )
    TIMETREE_TIMEOUT_SECONDS: int = Field(default=10, description="TimeTree API timeout")
    TIMETREE_MAX_RETRIES: int = Field(default=3, description="TimeTree API max retries")
    
    # OpenAI API
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key")
    OPENAI_MODEL: str = Field(
        default="gpt-4o",
        description="OpenAI model to use"
    )
    AI_TIMEOUT_SECONDS: int = Field(default=30, description="AI API timeout")
    MAX_RETRY_ATTEMPTS: int = Field(default=3, description="Max AI retry attempts")
    
    # Security
    SECRET_KEY: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="JWT secret key"
    )
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="Access token expiration in minutes"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        description="Refresh token expiration in days"
    )
    ENCRYPTION_KEY: str = Field(..., description="32-byte encryption key for tokens")
    
    # Redis (Optional)
    REDIS_URL: Optional[str] = Field(None, description="Redis URL for caching")
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(default="json", description="Log format (json/text)")
    
    # Observability
    SENTRY_DSN: Optional[str] = Field(None, description="Sentry DSN for error tracking")
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = Field(
        None,
        description="OpenTelemetry OTLP endpoint"
    )
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, description="Rate limit per minute")
    RATE_LIMIT_PER_HOUR: int = Field(default=1000, description="Rate limit per hour")
    
    # CORS
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins"
    )
    ALLOWED_METHODS: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        description="Allowed CORS methods"
    )
    ALLOWED_HEADERS: List[str] = Field(
        default=["*"],
        description="Allowed CORS headers"
    )
    
    # File Upload
    MAX_FILE_SIZE_MB: int = Field(default=10, description="Max file size in MB")
    ALLOWED_FILE_TYPES: List[str] = Field(
        default=["image/jpeg", "image/png", "application/pdf"],
        description="Allowed file MIME types"
    )
    
    @validator("ALLOWED_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        """Parse comma-separated CORS origins."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("ALLOWED_METHODS", pre=True)
    def parse_cors_methods(cls, v):
        """Parse comma-separated CORS methods."""
        if isinstance(v, str):
            return [method.strip() for method in v.split(",")]
        return v
    
    @validator("ALLOWED_HEADERS", pre=True)
    def parse_cors_headers(cls, v):
        """Parse comma-separated CORS headers."""
        if isinstance(v, str):
            return [header.strip() for header in v.split(",")]
        return v
    
    @validator("ALLOWED_FILE_TYPES", pre=True)
    def parse_file_types(cls, v):
        """Parse comma-separated file types."""
        if isinstance(v, str):
            return [file_type.strip() for file_type in v.split(",")]
        return v
    
    @validator("ENCRYPTION_KEY")
    def validate_encryption_key(cls, v):
        """Validate encryption key length."""
        if len(v.encode()) != 32:
            raise ValueError("ENCRYPTION_KEY must be exactly 32 bytes")
        return v
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v.upper()
    
    @validator("LOG_FORMAT")
    def validate_log_format(cls, v):
        """Validate log format."""
        valid_formats = ["json", "text"]
        if v.lower() not in valid_formats:
            raise ValueError(f"LOG_FORMAT must be one of {valid_formats}")
        return v.lower()
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


# Global settings instance
settings = Settings()


def get_database_url(use_test: bool = False) -> str:
    """Get database URL for current environment."""
    if use_test and settings.DATABASE_URL_TEST:
        return settings.DATABASE_URL_TEST
    return settings.DATABASE_URL


def is_production() -> bool:
    """Check if running in production environment."""
    return settings.ENVIRONMENT.lower() == "production"


def is_development() -> bool:
    """Check if running in development environment."""
    return settings.ENVIRONMENT.lower() == "development"


def is_testing() -> bool:
    """Check if running in test environment."""
    return settings.ENVIRONMENT.lower() == "test"
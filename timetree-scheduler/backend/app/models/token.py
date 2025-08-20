"""
Token model for storing TimeTree OAuth tokens.

Handles encrypted storage of access and refresh tokens.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base
from app.core.security import security


class TimeTreeToken(Base):
    """
    TimeTree OAuth token storage with encryption.
    
    Stores encrypted access and refresh tokens for TimeTree API access.
    """
    
    __tablename__ = "timetree_tokens"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    # Foreign key to User
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the user who owns this token"
    )
    
    # Encrypted tokens
    encrypted_access_token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Encrypted TimeTree access token"
    )
    
    encrypted_refresh_token: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Encrypted TimeTree refresh token"
    )
    
    # Token metadata
    token_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Bearer",
        comment="Token type (usually Bearer)"
    )
    
    scope: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Token scope permissions"
    )
    
    # Expiration
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Token expiration timestamp"
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Token creation timestamp"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Token last update timestamp"
    )
    
    # Relationship
    user = relationship("User", back_populates="timetree_tokens")
    
    def __repr__(self) -> str:
        return f"<TimeTreeToken(id={self.id}, user_id={self.user_id}, expires_at={self.expires_at})>"
    
    def set_access_token(self, access_token: str) -> None:
        """
        Set and encrypt the access token.
        
        Args:
            access_token: Plain text access token
        """
        self.encrypted_access_token = security.encrypt_data(access_token)
    
    def get_access_token(self) -> str:
        """
        Get and decrypt the access token.
        
        Returns:
            str: Plain text access token
        """
        return security.decrypt_data(self.encrypted_access_token)
    
    def set_refresh_token(self, refresh_token: str) -> None:
        """
        Set and encrypt the refresh token.
        
        Args:
            refresh_token: Plain text refresh token
        """
        if refresh_token:
            self.encrypted_refresh_token = security.encrypt_data(refresh_token)
        else:
            self.encrypted_refresh_token = None
    
    def get_refresh_token(self) -> Optional[str]:
        """
        Get and decrypt the refresh token.
        
        Returns:
            Optional[str]: Plain text refresh token or None
        """
        if self.encrypted_refresh_token:
            return security.decrypt_data(self.encrypted_refresh_token)
        return None
    
    def is_expired(self) -> bool:
        """
        Check if the token is expired.
        
        Returns:
            bool: True if token is expired
        """
        if not self.expires_at:
            return False
        
        return datetime.now(timezone.utc) >= self.expires_at
    
    def is_expiring_soon(self, minutes: int = 5) -> bool:
        """
        Check if the token is expiring soon.
        
        Args:
            minutes: Number of minutes to consider as "soon"
        
        Returns:
            bool: True if token expires within the specified minutes
        """
        if not self.expires_at:
            return False
        
        from datetime import timedelta
        threshold = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        return self.expires_at <= threshold
    
    def update_from_token_response(self, token_data: dict) -> None:
        """
        Update token from TimeTree token response.
        
        Args:
            token_data: Token response from TimeTree API
        """
        # Set tokens
        if "access_token" in token_data:
            self.set_access_token(token_data["access_token"])
        
        if "refresh_token" in token_data:
            self.set_refresh_token(token_data["refresh_token"])
        
        # Set metadata
        if "token_type" in token_data:
            self.token_type = token_data["token_type"]
        
        if "scope" in token_data:
            self.scope = token_data["scope"]
        
        # Set expiration
        if "expires_in" in token_data:
            from datetime import timedelta
            expires_in_seconds = int(token_data["expires_in"])
            self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
        
        # Update timestamp
        self.updated_at = datetime.now(timezone.utc)
    
    def to_dict(self, include_tokens: bool = False) -> dict:
        """
        Convert token to dictionary representation.
        
        Args:
            include_tokens: Whether to include decrypted tokens (use with caution)
        
        Returns:
            dict: Token dictionary
        """
        result = {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "token_type": self.token_type,
            "scope": self.scope,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_expired": self.is_expired(),
            "is_expiring_soon": self.is_expiring_soon(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_tokens:
            result.update({
                "access_token": self.get_access_token(),
                "refresh_token": self.get_refresh_token(),
            })
        
        return result
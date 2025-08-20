"""
User model for TimeTree Scheduler.

Represents users authenticated via TimeTree OAuth.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class User(Base):
    """
    User model for authenticated users.
    
    Stores basic user information from TimeTree OAuth and local preferences.
    """
    
    __tablename__ = "users"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    # TimeTree integration
    timetree_user_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="TimeTree user ID from OAuth"
    )
    
    # Basic information
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User email address"
    )
    
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="User display name"
    )
    
    avatar_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User avatar image URL"
    )
    
    # Preferences
    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Asia/Seoul",
        comment="User's preferred timezone"
    )
    
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="ko",
        comment="User's preferred language"
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether the user account is active"
    )
    
    is_premium: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the user has premium features"
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Account creation timestamp"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last update timestamp"
    )
    
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last login timestamp"
    )
    
    # Relationships
    timetree_tokens = relationship(
        "TimeTreeToken",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    calendars = relationship(
        "Calendar",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    events = relationship(
        "Event",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, name={self.name})>"
    
    def update_last_login(self) -> None:
        """Update the last login timestamp."""
        self.last_login_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> dict:
        """Convert user to dictionary representation."""
        return {
            "id": str(self.id),
            "timetree_user_id": self.timetree_user_id,
            "email": self.email,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "timezone": self.timezone,
            "language": self.language,
            "is_active": self.is_active,
            "is_premium": self.is_premium,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }
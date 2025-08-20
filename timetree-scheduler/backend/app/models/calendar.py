"""
Calendar model for TimeTree calendars.

Represents TimeTree calendars that users have access to.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class Calendar(Base):
    """
    TimeTree calendar model.
    
    Represents calendars that users can access via TimeTree API.
    """
    
    __tablename__ = "calendars"
    
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
        comment="Reference to the user who has access to this calendar"
    )
    
    # TimeTree calendar information
    timetree_calendar_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="TimeTree calendar ID"
    )
    
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Calendar display name"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Calendar description"
    )
    
    color: Mapped[Optional[str]] = mapped_column(
        String(7),  # Hex color code
        nullable=True,
        comment="Calendar color (hex code)"
    )
    
    # Calendar type and permissions
    calendar_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="shared",
        comment="Calendar type (personal, shared, etc.)"
    )
    
    permission: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="read_write",
        comment="User's permission level (read_only, read_write, admin)"
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this calendar is active for the user"
    )
    
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this is the user's default calendar"
    )
    
    # Metadata from TimeTree
    timetree_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Raw calendar data from TimeTree API"
    )
    
    # Sync information
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last time calendar was synced from TimeTree"
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Calendar creation timestamp"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Calendar last update timestamp"
    )
    
    # Relationships
    user = relationship("User", back_populates="calendars")
    events = relationship(
        "Event",
        back_populates="calendar",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Calendar(id={self.id}, name={self.name}, timetree_id={self.timetree_calendar_id})>"
    
    def update_sync_timestamp(self) -> None:
        """Update the last synced timestamp."""
        self.last_synced_at = datetime.now(timezone.utc)
    
    def can_write(self) -> bool:
        """
        Check if user has write permission to this calendar.
        
        Returns:
            bool: True if user can create/edit events
        """
        return self.permission in ["read_write", "admin"]
    
    def can_admin(self) -> bool:
        """
        Check if user has admin permission to this calendar.
        
        Returns:
            bool: True if user can manage calendar settings
        """
        return self.permission == "admin"
    
    def update_from_timetree_data(self, timetree_data: dict) -> None:
        """
        Update calendar from TimeTree API response.
        
        Args:
            timetree_data: Calendar data from TimeTree API
        """
        attributes = timetree_data.get("attributes", {})
        
        # Update basic information
        if "name" in attributes:
            self.name = attributes["name"]
        
        if "description" in attributes:
            self.description = attributes["description"]
        
        if "color" in attributes:
            self.color = attributes["color"]
        
        if "calendar_type" in attributes:
            self.calendar_type = attributes["calendar_type"]
        
        # Store raw data
        self.timetree_data = timetree_data
        
        # Update sync timestamp
        self.update_sync_timestamp()
    
    def to_dict(self) -> dict:
        """Convert calendar to dictionary representation."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "timetree_calendar_id": self.timetree_calendar_id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "calendar_type": self.calendar_type,
            "permission": self.permission,
            "is_active": self.is_active,
            "is_default": self.is_default,
            "can_write": self.can_write(),
            "can_admin": self.can_admin(),
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
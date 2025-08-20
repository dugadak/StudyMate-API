"""
Event model for calendar events.

Represents both parsed events (before TimeTree creation) and synced events.
"""

from datetime import datetime, timezone
from typing import Optional, List
import hashlib

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class Event(Base):
    """
    Calendar event model.
    
    Represents events that can be created in TimeTree calendars,
    including both AI-parsed events and synced events from TimeTree.
    """
    
    __tablename__ = "events"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    # Foreign keys
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the user who created this event"
    )
    
    calendar_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calendars.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Reference to the calendar (null for unconfirmed events)"
    )
    
    # TimeTree integration
    timetree_event_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="TimeTree event ID after creation"
    )
    
    # Event details
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Event title"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Event description"
    )
    
    location: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Event location"
    )
    
    # Timing
    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Event start timestamp"
    )
    
    end_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Event end timestamp"
    )
    
    all_day: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this is an all-day event"
    )
    
    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Asia/Seoul",
        comment="Event timezone"
    )
    
    # Categorization
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="schedule",
        comment="Event category (schedule, task, milestone, reminder)"
    )
    
    labels: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Event labels/tags"
    )
    
    # AI parsing information
    original_input: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Original natural language input"
    )
    
    ai_confidence: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="AI parsing confidence score (0.0-1.0)"
    )
    
    parsed_elements: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Detailed parsing information from AI"
    )
    
    # Status and workflow
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="draft",
        comment="Event status (draft, confirmed, synced, cancelled)"
    )
    
    is_confirmed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether user has confirmed this event"
    )
    
    # Idempotency for duplicate prevention
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="Idempotency key for duplicate prevention"
    )
    
    # TimeTree sync information
    timetree_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Raw event data from TimeTree API"
    )
    
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last time event was synced with TimeTree"
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Event creation timestamp"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Event last update timestamp"
    )
    
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Event confirmation timestamp"
    )
    
    # Relationships
    user = relationship("User", back_populates="events")
    calendar = relationship("Calendar", back_populates="events")
    
    # Indexes for performance
    __table_args__ = (
        Index("ix_events_user_status", "user_id", "status"),
        Index("ix_events_calendar_start", "calendar_id", "start_at"),
        Index("ix_events_user_start", "user_id", "start_at"),
        Index("ix_events_idempotency", "user_id", "idempotency_key"),
    )
    
    def __repr__(self) -> str:
        return f"<Event(id={self.id}, title={self.title}, status={self.status})>"
    
    def generate_idempotency_key(self) -> str:
        """
        Generate idempotency key for duplicate prevention.
        
        Returns:
            str: SHA-256 hash of key event attributes
        """
        key_data = f"{self.user_id}:{self.calendar_id}:{self.title}:{self.start_at.isoformat()}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def confirm_event(self) -> None:
        """Mark event as confirmed by user."""
        self.is_confirmed = True
        self.status = "confirmed"
        self.confirmed_at = datetime.now(timezone.utc)
    
    def sync_with_timetree(self, timetree_event_id: str, timetree_data: dict = None) -> None:
        """
        Mark event as synced with TimeTree.
        
        Args:
            timetree_event_id: TimeTree event ID
            timetree_data: Raw event data from TimeTree
        """
        self.timetree_event_id = timetree_event_id
        self.status = "synced"
        self.last_synced_at = datetime.now(timezone.utc)
        
        if timetree_data:
            self.timetree_data = timetree_data
    
    def update_from_timetree_data(self, timetree_data: dict) -> None:
        """
        Update event from TimeTree API response.
        
        Args:
            timetree_data: Event data from TimeTree API
        """
        attributes = timetree_data.get("attributes", {})
        
        # Update basic information
        if "title" in attributes:
            self.title = attributes["title"]
        
        if "description" in attributes:
            self.description = attributes["description"]
        
        if "location" in attributes:
            self.location = attributes["location"]
        
        if "category" in attributes:
            self.category = attributes["category"]
        
        # Update timing
        if "start_at" in attributes:
            self.start_at = datetime.fromisoformat(
                attributes["start_at"].replace('Z', '+00:00')
            )
        
        if "end_at" in attributes:
            self.end_at = datetime.fromisoformat(
                attributes["end_at"].replace('Z', '+00:00')
            )
        
        if "all_day" in attributes:
            self.all_day = attributes["all_day"]
        
        # Store raw data
        self.timetree_data = timetree_data
        
        # Update sync timestamp
        self.last_synced_at = datetime.now(timezone.utc)
    
    def get_duration_minutes(self) -> Optional[int]:
        """
        Get event duration in minutes.
        
        Returns:
            Optional[int]: Duration in minutes, or None if no end time
        """
        if not self.end_at:
            return None
        
        delta = self.end_at - self.start_at
        return int(delta.total_seconds() / 60)
    
    def is_past(self) -> bool:
        """
        Check if event is in the past.
        
        Returns:
            bool: True if event has already ended
        """
        end_time = self.end_at or self.start_at
        return end_time < datetime.now(timezone.utc)
    
    def is_upcoming(self, hours: int = 24) -> bool:
        """
        Check if event is upcoming within specified hours.
        
        Args:
            hours: Number of hours to look ahead
        
        Returns:
            bool: True if event starts within the specified hours
        """
        from datetime import timedelta
        threshold = datetime.now(timezone.utc) + timedelta(hours=hours)
        return self.start_at <= threshold and not self.is_past()
    
    def conflicts_with(self, other_start: datetime, other_end: datetime) -> bool:
        """
        Check if this event conflicts with another time range.
        
        Args:
            other_start: Other event start time
            other_end: Other event end time
        
        Returns:
            bool: True if there's a time conflict
        """
        my_end = self.end_at or self.start_at
        
        # Events conflict if they overlap
        return (self.start_at < other_end and my_end > other_start)
    
    def to_dict(self, include_ai_data: bool = True) -> dict:
        """
        Convert event to dictionary representation.
        
        Args:
            include_ai_data: Whether to include AI parsing data
        
        Returns:
            dict: Event dictionary
        """
        result = {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "calendar_id": str(self.calendar_id) if self.calendar_id else None,
            "timetree_event_id": self.timetree_event_id,
            "title": self.title,
            "description": self.description,
            "location": self.location,
            "start_at": self.start_at.isoformat(),
            "end_at": self.end_at.isoformat() if self.end_at else None,
            "all_day": self.all_day,
            "timezone": self.timezone,
            "category": self.category,
            "labels": self.labels or [],
            "status": self.status,
            "is_confirmed": self.is_confirmed,
            "duration_minutes": self.get_duration_minutes(),
            "is_past": self.is_past(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
        }
        
        if include_ai_data:
            result.update({
                "original_input": self.original_input,
                "ai_confidence": self.ai_confidence,
                "parsed_elements": self.parsed_elements,
            })
        
        return result
    
    def to_timetree_payload(self) -> dict:
        """
        Convert event to TimeTree API payload format.
        
        Returns:
            dict: TimeTree-compatible event data
        """
        payload = {
            "data": {
                "attributes": {
                    "title": self.title,
                    "category": self.category,
                    "all_day": self.all_day,
                    "start_at": self.start_at.isoformat(),
                    "start_timezone": self.timezone,
                }
            }
        }
        
        # Add optional fields
        if self.description:
            payload["data"]["attributes"]["description"] = self.description
        
        if self.location:
            payload["data"]["attributes"]["location"] = self.location
        
        if not self.all_day and self.end_at:
            payload["data"]["attributes"]["end_at"] = self.end_at.isoformat()
            payload["data"]["attributes"]["end_timezone"] = self.timezone
        
        return payload
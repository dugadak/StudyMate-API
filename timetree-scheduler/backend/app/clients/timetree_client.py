"""
TimeTree API client for OAuth and calendar operations.

Handles authentication, calendar access, and event management with TimeTree API.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode

import httpx
import structlog
from httpx import AsyncClient, Response

from app.core.config import settings
from app.core.logger import log_timetree_request, mask_sensitive_data
from app.core.security import security

logger = structlog.get_logger(__name__)


class TimeTreeAPIError(Exception):
    """Base exception for TimeTree API errors."""
    
    def __init__(self, message: str, status_code: int = None, response_data: dict = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}
        super().__init__(message)


class TimeTreeRateLimitError(TimeTreeAPIError):
    """Exception raised when hitting TimeTree API rate limits."""
    
    def __init__(self, retry_after: int = None):
        self.retry_after = retry_after
        message = f"Rate limit exceeded. Retry after {retry_after} seconds." if retry_after else "Rate limit exceeded."
        super().__init__(message, 429)


class TimeTreeClient:
    """
    TimeTree API client with OAuth support and comprehensive error handling.
    
    Supports both Authorization Code flow and Personal Access Token authentication.
    """
    
    def __init__(self):
        self.base_url = settings.TIMETREE_API_BASE_URL
        self.client_id = settings.TIMETREE_CLIENT_ID
        self.client_secret = settings.TIMETREE_CLIENT_SECRET
        self.redirect_uri = settings.TIMETREE_REDIRECT_URI
        self.timeout = settings.TIMETREE_TIMEOUT_SECONDS
        self.max_retries = settings.TIMETREE_MAX_RETRIES
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        headers: Dict[str, str] = None,
        params: Dict[str, Any] = None,
        data: Dict[str, Any] = None,
        json_data: Dict[str, Any] = None,
        access_token: str = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Make HTTP request to TimeTree API with retry logic and error handling.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            headers: Request headers
            params: Query parameters
            data: Form data
            json_data: JSON data
            access_token: OAuth access token
            retry_count: Current retry attempt
        
        Returns:
            Dict[str, Any]: Response data
        
        Raises:
            TimeTreeAPIError: On API errors
            TimeTreeRateLimitError: On rate limit errors
        """
        url = f"{self.base_url}{endpoint}"
        
        # Prepare headers
        request_headers = {
            "User-Agent": "TimeTree-Scheduler/1.0.0",
            "Accept": "application/json",
        }
        
        if access_token:
            request_headers["Authorization"] = f"Bearer {access_token}"
        
        if headers:
            request_headers.update(headers)
        
        # Log request (mask sensitive data)
        log_data = {
            "url": url,
            "method": method,
            "headers": mask_sensitive_data(request_headers),
            "params": params,
        }
        
        if json_data:
            log_data["json_data"] = mask_sensitive_data(json_data)
        
        start_time = datetime.now(timezone.utc)
        
        try:
            async with AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    params=params,
                    data=data,
                    json=json_data,
                )
                
                duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                
                # Extract rate limit info
                rate_limit_remaining = response.headers.get("X-RateLimit-Remaining")
                rate_limit_remaining = int(rate_limit_remaining) if rate_limit_remaining else None
                
                # Log response
                log_timetree_request(
                    endpoint=endpoint,
                    method=method,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    rate_limit_remaining=rate_limit_remaining,
                    success=response.is_success,
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    
                    if retry_count < self.max_retries:
                        logger.warning(
                            "Rate limited, retrying",
                            retry_after=retry_after,
                            retry_count=retry_count
                        )
                        await asyncio.sleep(retry_after)
                        return await self._make_request(
                            method, endpoint, headers, params, data, json_data, access_token, retry_count + 1
                        )
                    else:
                        raise TimeTreeRateLimitError(retry_after)
                
                # Handle other client errors
                if response.status_code >= 400:
                    error_data = {}
                    try:
                        error_data = response.json()
                    except Exception:
                        error_data = {"message": response.text}
                    
                    error_message = error_data.get("message", f"HTTP {response.status_code}")
                    
                    log_timetree_request(
                        endpoint=endpoint,
                        method=method,
                        status_code=response.status_code,
                        duration_ms=duration_ms,
                        success=False,
                        error=error_message,
                    )
                    
                    raise TimeTreeAPIError(
                        message=error_message,
                        status_code=response.status_code,
                        response_data=error_data
                    )
                
                # Return successful response
                return response.json() if response.content else {}
                
        except httpx.TimeoutException:
            error_msg = f"Request timeout after {self.timeout} seconds"
            logger.error("TimeTree API timeout", endpoint=endpoint, timeout=self.timeout)
            
            if retry_count < self.max_retries:
                await asyncio.sleep(2 ** retry_count)  # Exponential backoff
                return await self._make_request(
                    method, endpoint, headers, params, data, json_data, access_token, retry_count + 1
                )
            
            raise TimeTreeAPIError(error_msg)
        
        except httpx.NetworkError as e:
            error_msg = f"Network error: {str(e)}"
            logger.error("TimeTree API network error", endpoint=endpoint, error=str(e))
            
            if retry_count < self.max_retries:
                await asyncio.sleep(2 ** retry_count)  # Exponential backoff
                return await self._make_request(
                    method, endpoint, headers, params, data, json_data, access_token, retry_count + 1
                )
            
            raise TimeTreeAPIError(error_msg)
    
    def get_authorization_url(self, state: str = None) -> str:
        """
        Generate TimeTree OAuth authorization URL.
        
        Args:
            state: Optional state parameter for CSRF protection
        
        Returns:
            str: Authorization URL
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "read write",
        }
        
        if state:
            params["state"] = state
        
        auth_url = f"https://timetreeapp.com/oauth/authorize?{urlencode(params)}"
        
        logger.info("Generated authorization URL", 
                   client_id=self.client_id[:8] + "...",
                   redirect_uri=self.redirect_uri)
        
        return auth_url
    
    async def exchange_code_for_token(self, code: str, state: str = None) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from callback
            state: State parameter for verification
        
        Returns:
            Dict[str, Any]: Token response with access_token, refresh_token, etc.
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "code": code,
            "grant_type": "authorization_code",
        }
        
        response = await self._make_request(
            method="POST",
            endpoint="/oauth/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        logger.info("Successfully exchanged code for token",
                   expires_in=response.get("expires_in"))
        
        return response
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Valid refresh token
        
        Returns:
            Dict[str, Any]: New token response
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        
        response = await self._make_request(
            method="POST",
            endpoint="/oauth/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        logger.info("Successfully refreshed access token",
                   expires_in=response.get("expires_in"))
        
        return response
    
    async def get_current_user(self, access_token: str) -> Dict[str, Any]:
        """
        Get current user information.
        
        Args:
            access_token: Valid access token
        
        Returns:
            Dict[str, Any]: User information
        """
        return await self._make_request(
            method="GET",
            endpoint="/user",
            access_token=access_token
        )
    
    async def get_calendars(self, access_token: str) -> List[Dict[str, Any]]:
        """
        Get user's calendars.
        
        Args:
            access_token: Valid access token
        
        Returns:
            List[Dict[str, Any]]: List of calendars
        """
        response = await self._make_request(
            method="GET",
            endpoint="/calendars",
            access_token=access_token
        )
        
        calendars = response.get("data", [])
        
        logger.info("Retrieved calendars", count=len(calendars))
        
        return calendars
    
    async def get_calendar(self, calendar_id: str, access_token: str) -> Dict[str, Any]:
        """
        Get specific calendar information.
        
        Args:
            calendar_id: Calendar ID
            access_token: Valid access token
        
        Returns:
            Dict[str, Any]: Calendar information
        """
        response = await self._make_request(
            method="GET",
            endpoint=f"/calendars/{calendar_id}",
            access_token=access_token
        )
        
        return response.get("data", {})
    
    async def get_events(
        self,
        calendar_id: str,
        access_token: str,
        days: int = 7,
        timezone: str = "Asia/Seoul"
    ) -> List[Dict[str, Any]]:
        """
        Get events from calendar.
        
        Args:
            calendar_id: Calendar ID
            access_token: Valid access token
            days: Number of days to fetch (default: 7)
            timezone: Timezone for events (default: Asia/Seoul)
        
        Returns:
            List[Dict[str, Any]]: List of events
        """
        params = {
            "days": days,
            "timezone": timezone,
        }
        
        response = await self._make_request(
            method="GET",
            endpoint=f"/calendars/{calendar_id}/upcoming_events",
            params=params,
            access_token=access_token
        )
        
        events = response.get("data", [])
        
        logger.info("Retrieved events", 
                   calendar_id=calendar_id,
                   count=len(events),
                   days=days)
        
        return events
    
    async def create_event(
        self,
        calendar_id: str,
        event_data: Dict[str, Any],
        access_token: str
    ) -> Dict[str, Any]:
        """
        Create new event in calendar.
        
        Args:
            calendar_id: Calendar ID
            event_data: Event data (title, start_at, end_at, etc.)
            access_token: Valid access token
        
        Returns:
            Dict[str, Any]: Created event data
        """
        # Prepare event payload
        payload = {
            "data": {
                "attributes": {
                    "title": event_data["title"],
                    "category": event_data.get("category", "schedule"),
                    "all_day": event_data.get("all_day", False),
                    "start_at": event_data["start_at"],
                    "start_timezone": event_data.get("start_timezone", "Asia/Seoul"),
                    "description": event_data.get("description", ""),
                    "location": event_data.get("location", ""),
                }
            }
        }
        
        # Add end_at if not all_day
        if not event_data.get("all_day", False) and "end_at" in event_data:
            payload["data"]["attributes"]["end_at"] = event_data["end_at"]
            payload["data"]["attributes"]["end_timezone"] = event_data.get("end_timezone", "Asia/Seoul")
        
        response = await self._make_request(
            method="POST",
            endpoint=f"/calendars/{calendar_id}/events",
            json_data=payload,
            access_token=access_token
        )
        
        event = response.get("data", {})
        
        logger.info("Created event",
                   calendar_id=calendar_id,
                   event_id=event.get("id"),
                   title=event_data["title"])
        
        return event
    
    async def update_event(
        self,
        calendar_id: str,
        event_id: str,
        event_data: Dict[str, Any],
        access_token: str
    ) -> Dict[str, Any]:
        """
        Update existing event.
        
        Args:
            calendar_id: Calendar ID
            event_id: Event ID
            event_data: Updated event data
            access_token: Valid access token
        
        Returns:
            Dict[str, Any]: Updated event data
        """
        payload = {
            "data": {
                "attributes": event_data
            }
        }
        
        response = await self._make_request(
            method="PUT",
            endpoint=f"/calendars/{calendar_id}/events/{event_id}",
            json_data=payload,
            access_token=access_token
        )
        
        event = response.get("data", {})
        
        logger.info("Updated event",
                   calendar_id=calendar_id,
                   event_id=event_id)
        
        return event
    
    async def delete_event(
        self,
        calendar_id: str,
        event_id: str,
        access_token: str
    ) -> bool:
        """
        Delete event from calendar.
        
        Args:
            calendar_id: Calendar ID
            event_id: Event ID
            access_token: Valid access token
        
        Returns:
            bool: True if successfully deleted
        """
        await self._make_request(
            method="DELETE",
            endpoint=f"/calendars/{calendar_id}/events/{event_id}",
            access_token=access_token
        )
        
        logger.info("Deleted event",
                   calendar_id=calendar_id,
                   event_id=event_id)
        
        return True
    
    async def check_event_conflicts(
        self,
        calendar_id: str,
        start_at: str,
        end_at: str,
        access_token: str,
        exclude_event_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        Check for conflicting events in the given time range.
        
        Args:
            calendar_id: Calendar ID
            start_at: Start time (ISO format)
            end_at: End time (ISO format)
            access_token: Valid access token
            exclude_event_id: Event ID to exclude from conflict check
        
        Returns:
            List[Dict[str, Any]]: List of conflicting events
        """
        # Get events for the time period
        events = await self.get_events(calendar_id, access_token, days=30)
        
        conflicts = []
        target_start = datetime.fromisoformat(start_at.replace('Z', '+00:00'))
        target_end = datetime.fromisoformat(end_at.replace('Z', '+00:00'))
        
        for event in events:
            if exclude_event_id and event.get("id") == exclude_event_id:
                continue
            
            try:
                event_start = datetime.fromisoformat(
                    event["attributes"]["start_at"].replace('Z', '+00:00')
                )
                event_end_str = event["attributes"].get("end_at")
                
                if event_end_str:
                    event_end = datetime.fromisoformat(event_end_str.replace('Z', '+00:00'))
                else:
                    # If no end time, assume 1 hour duration
                    event_end = event_start.replace(hour=event_start.hour + 1)
                
                # Check for overlap
                if (target_start < event_end and target_end > event_start):
                    conflicts.append(event)
                    
            except (ValueError, KeyError) as e:
                logger.warning("Failed to parse event time", 
                             event_id=event.get("id"),
                             error=str(e))
                continue
        
        logger.info("Checked event conflicts",
                   calendar_id=calendar_id,
                   conflicts_found=len(conflicts))
        
        return conflicts


# Global TimeTree client instance
timetree_client = TimeTreeClient()
import pytest
import json
from unittest.mock import patch, AsyncMock
from fastapi import status
from httpx import AsyncClient

from app.models.event import Event
from app.models.calendar import Calendar

@pytest.mark.asyncio
class TestEventRoutes:
    """Test event-related API endpoints."""
    
    async def test_parse_event_success(
        self, 
        async_client: AsyncClient,
        premium_auth_headers: dict,
        sample_parsing_request: dict,
        mock_claude_response: dict
    ):
        """Test successful event parsing."""
        with patch('app.services.nlp_service.nlp_service.parse_natural_language_to_event') as mock_parse:
            mock_parse.return_value = mock_claude_response
            
            response = await async_client.post(
                "/api/v1/events/parse",
                json=sample_parsing_request,
                headers=premium_auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["success"] is True
            assert "parsed_event" in data
            assert data["confidence_score"] == 0.95
            assert "suggestions" in data

    async def test_parse_event_without_subscription(
        self, 
        async_client: AsyncClient,
        auth_headers: dict,
        sample_parsing_request: dict
    ):
        """Test parsing request without active subscription."""
        response = await async_client.post(
            "/api/v1/events/parse",
            json=sample_parsing_request,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED
        assert "subscription required" in response.json()["detail"].lower()

    async def test_parse_event_unauthenticated(
        self, 
        async_client: AsyncClient,
        sample_parsing_request: dict
    ):
        """Test parsing request without authentication."""
        response = await async_client.post(
            "/api/v1/events/parse",
            json=sample_parsing_request
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_create_event_success(
        self,
        async_client: AsyncClient,
        premium_auth_headers: dict,
        sample_event_data: dict,
        mock_timetree_response: dict,
        db_session
    ):
        """Test successful event creation."""
        create_request = {
            "calendar_id": "cal_123",
            "original_text": "내일 오후 3시에 치과 예약",
            **sample_event_data
        }
        
        with patch('app.services.event_service.event_service.create_timetree_event') as mock_create:
            mock_create.return_value = mock_timetree_response
            
            with patch('app.services.user_service.user_service.get_user_with_timetree_auth') as mock_user:
                mock_user.return_value = type('obj', (object,), {
                    'timetree_access_token': 'fake_token'
                })()
                
                response = await async_client.post(
                    "/api/v1/events/create",
                    json=create_request,
                    headers=premium_auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert data["success"] is True
                assert "event" in data
                assert data["event"]["id"] == "tt_event_123"

    async def test_create_event_without_timetree_auth(
        self,
        async_client: AsyncClient,
        premium_auth_headers: dict,
        sample_event_data: dict,
        db_session
    ):
        """Test event creation without TimeTree authentication."""
        create_request = {
            "calendar_id": "cal_123",
            "original_text": "내일 오후 3시에 치과 예약",
            **sample_event_data
        }
        
        with patch('app.services.user_service.user_service.get_user_with_timetree_auth') as mock_user:
            mock_user.return_value = type('obj', (object,), {
                'timetree_access_token': None
            })()
            
            response = await async_client.post(
                "/api/v1/events/create",
                json=create_request,
                headers=premium_auth_headers
            )
            
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            assert "timetree authentication required" in response.json()["detail"].lower()

    async def test_get_user_events(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session,
        test_user
    ):
        """Test retrieving user events."""
        # Create a test event in database
        event = Event(
            timetree_event_id="tt_event_123",
            user_id=test_user.id,
            title="테스트 이벤트",
            start_at="2024-08-20T14:00:00+09:00",
            end_at="2024-08-20T15:00:00+09:00",
            category="work"
        )
        db_session.add(event)
        db_session.commit()
        
        with patch('app.services.event_service.event_service.get_user_events') as mock_get:
            mock_get.return_value = [{
                "id": "tt_event_123",
                "title": "테스트 이벤트",
                "start_at": "2024-08-20T14:00:00+09:00",
                "category": "work"
            }]
            
            response = await async_client.get(
                "/api/v1/events/",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["success"] is True
            assert len(data["events"]) == 1
            assert data["events"][0]["title"] == "테스트 이벤트"

    async def test_delete_event_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        db_session,
        test_user
    ):
        """Test successful event deletion."""
        event_id = "tt_event_123"
        
        with patch('app.services.event_service.event_service.delete_user_event') as mock_delete:
            mock_delete.return_value = True
            
            response = await async_client.delete(
                f"/api/v1/events/{event_id}",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["success"] is True
            assert "deleted successfully" in data["message"]

    async def test_delete_event_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test deleting non-existent event."""
        event_id = "nonexistent_event"
        
        with patch('app.services.event_service.event_service.delete_user_event') as mock_delete:
            mock_delete.return_value = False
            
            response = await async_client.delete(
                f"/api/v1/events/{event_id}",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"].lower()

    async def test_parse_and_create_event_success(
        self,
        async_client: AsyncClient,
        premium_auth_headers: dict,
        sample_parsing_request: dict,
        mock_claude_response: dict,
        mock_timetree_response: dict
    ):
        """Test combined parse and create operation."""
        calendar_id = "cal_123"
        
        with patch('app.services.nlp_service.nlp_service.parse_natural_language_to_event') as mock_parse:
            mock_parse.return_value = mock_claude_response
            
            with patch('app.services.event_service.event_service.create_timetree_event') as mock_create:
                mock_create.return_value = mock_timetree_response
                
                with patch('app.services.user_service.user_service.get_user_with_timetree_auth') as mock_user:
                    mock_user.return_value = type('obj', (object,), {
                        'timetree_access_token': 'fake_token'
                    })()
                    
                    response = await async_client.post(
                        f"/api/v1/events/parse-and-create?calendar_id={calendar_id}",
                        json=sample_parsing_request,
                        headers=premium_auth_headers
                    )
                    
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    
                    assert data["success"] is True
                    assert "event" in data
                    assert "confidence" in data["message"]
                    assert "metadata" in data
                    assert data["metadata"]["confidence_score"] == 0.95

    async def test_rate_limiting(
        self,
        async_client: AsyncClient,
        premium_auth_headers: dict,
        sample_parsing_request: dict
    ):
        """Test rate limiting on endpoints."""
        with patch('app.core.rate_limiter.RateLimiter.check_rate_limit') as mock_rate_limit:
            mock_rate_limit.side_effect = Exception("Rate limit exceeded")
            
            response = await async_client.post(
                "/api/v1/events/parse",
                json=sample_parsing_request,
                headers=premium_auth_headers
            )
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    async def test_invalid_event_data(
        self,
        async_client: AsyncClient,
        premium_auth_headers: dict
    ):
        """Test with invalid event data."""
        invalid_request = {
            "calendar_id": "",  # Empty calendar ID
            "title": "",  # Empty title
            "start_at": "invalid-date"  # Invalid date format
        }
        
        response = await async_client.post(
            "/api/v1/events/create",
            json=invalid_request,
            headers=premium_auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_ai_service_error(
        self,
        async_client: AsyncClient,
        premium_auth_headers: dict,
        sample_parsing_request: dict
    ):
        """Test handling of AI service errors."""
        with patch('app.services.nlp_service.nlp_service.parse_natural_language_to_event') as mock_parse:
            mock_parse.side_effect = Exception("AI service unavailable")
            
            response = await async_client.post(
                "/api/v1/events/parse",
                json=sample_parsing_request,
                headers=premium_auth_headers
            )
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "failed to parse" in response.json()["detail"].lower()

    async def test_event_query_parameters(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test event listing with query parameters."""
        with patch('app.services.event_service.event_service.get_user_events') as mock_get:
            mock_get.return_value = []
            
            response = await async_client.get(
                "/api/v1/events/?calendar_id=cal_123&limit=10&offset=0",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            mock_get.assert_called_once()
            
            # Check that parameters were passed correctly
            call_args = mock_get.call_args
            assert call_args.kwargs["calendar_id"] == "cal_123"
            assert call_args.kwargs["limit"] == 10
            assert call_args.kwargs["offset"] == 0

@pytest.mark.integration
class TestEventIntegration:
    """Integration tests for event functionality."""
    
    async def test_full_event_lifecycle(
        self,
        async_client: AsyncClient,
        premium_auth_headers: dict,
        db_session,
        test_user_with_subscription
    ):
        """Test complete event lifecycle: parse -> create -> retrieve -> delete."""
        parsing_request = {
            "text": "내일 오후 2시에 중요한 회의",
            "timezone": "Asia/Seoul"
        }
        
        mock_parsed_data = {
            "title": "중요한 회의",
            "start_at": "2024-08-20T14:00:00+09:00",
            "end_at": "2024-08-20T15:00:00+09:00",
            "category": "work",
            "confidence": 0.9
        }
        
        mock_timetree_event = {
            "id": "tt_event_456",
            "title": "중요한 회의",
            "start_at": "2024-08-20T14:00:00+09:00",
            "calendar_id": "cal_456"
        }
        
        # 1. Parse event
        with patch('app.services.nlp_service.nlp_service.parse_natural_language_to_event') as mock_parse:
            mock_parse.return_value = mock_parsed_data
            
            parse_response = await async_client.post(
                "/api/v1/events/parse",
                json=parsing_request,
                headers=premium_auth_headers
            )
            
            assert parse_response.status_code == status.HTTP_200_OK
            parsed_data = parse_response.json()
            assert parsed_data["success"] is True
        
        # 2. Create event
        create_request = {
            "calendar_id": "cal_456",
            "original_text": parsing_request["text"],
            **mock_parsed_data
        }
        
        with patch('app.services.event_service.event_service.create_timetree_event') as mock_create:
            mock_create.return_value = mock_timetree_event
            
            with patch('app.services.user_service.user_service.get_user_with_timetree_auth') as mock_user:
                mock_user.return_value = type('obj', (object,), {
                    'timetree_access_token': 'valid_token'
                })()
                
                create_response = await async_client.post(
                    "/api/v1/events/create",
                    json=create_request,
                    headers=premium_auth_headers
                )
                
                assert create_response.status_code == status.HTTP_200_OK
                created_data = create_response.json()
                assert created_data["success"] is True
                event_id = created_data["event"]["id"]
        
        # 3. Retrieve events
        with patch('app.services.event_service.event_service.get_user_events') as mock_get:
            mock_get.return_value = [mock_timetree_event]
            
            get_response = await async_client.get(
                "/api/v1/events/",
                headers=premium_auth_headers
            )
            
            assert get_response.status_code == status.HTTP_200_OK
            get_data = get_response.json()
            assert len(get_data["events"]) == 1
        
        # 4. Delete event
        with patch('app.services.event_service.event_service.delete_user_event') as mock_delete:
            mock_delete.return_value = True
            
            delete_response = await async_client.delete(
                f"/api/v1/events/{event_id}",
                headers=premium_auth_headers
            )
            
            assert delete_response.status_code == status.HTTP_200_OK
            delete_data = delete_response.json()
            assert delete_data["success"] is True
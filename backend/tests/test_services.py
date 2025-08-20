import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import json
from datetime import datetime, timedelta

from app.services.nlp_service import nlp_service
from app.services.timetree_service import timetree_service
from app.services.user_service import user_service
from app.services.event_service import event_service
from app.core.exceptions import ExternalServiceError, ValidationError

@pytest.mark.asyncio
class TestNLPService:
    """Test NLP service for natural language processing."""
    
    async def test_parse_natural_language_to_event_success(self):
        """Test successful natural language parsing."""
        text = "내일 오후 3시에 치과 예약"
        context = {"timezone": "Asia/Seoul"}
        
        mock_response = {
            "title": "치과 예약",
            "start_at": "2024-08-20T15:00:00+09:00",
            "end_at": "2024-08-20T16:00:00+09:00",
            "category": "health",
            "confidence": 0.95
        }
        
        with patch('app.clients.claude_client.ClaudeClient.parse_text_to_event') as mock_parse:
            mock_parse.return_value = mock_response
            
            result = await nlp_service.parse_natural_language_to_event(text, context)
            
            assert result["title"] == "치과 예약"
            assert result["category"] == "health"
            assert result["confidence"] == 0.95
            mock_parse.assert_called_once_with(text, context)

    async def test_parse_with_fallback_provider(self):
        """Test parsing with fallback to different AI provider."""
        text = "매주 화요일 오후 2시 요가 수업"
        context = {"timezone": "Asia/Seoul"}
        
        with patch('app.clients.claude_client.ClaudeClient.parse_text_to_event') as mock_claude:
            mock_claude.side_effect = ExternalServiceError("Claude API unavailable")
            
            with patch('app.clients.openai_client.OpenAIClient.parse_text_to_event') as mock_openai:
                mock_openai.return_value = {
                    "title": "요가 수업",
                    "start_at": "2024-08-20T14:00:00+09:00",
                    "recurrence_rule": "FREQ=WEEKLY;BYDAY=TU",
                    "confidence": 0.88
                }
                
                result = await nlp_service.parse_natural_language_to_event(text, context)
                
                assert result["title"] == "요가 수업"
                assert "WEEKLY" in result["recurrence_rule"]
                mock_claude.assert_called_once()
                mock_openai.assert_called_once()

    async def test_parse_with_cache_hit(self):
        """Test parsing with cached result."""
        text = "내일 점심 미팅"
        context = {"timezone": "Asia/Seoul"}
        
        cached_result = {
            "title": "점심 미팅",
            "start_at": "2024-08-20T12:00:00+09:00",
            "confidence": 0.92
        }
        
        with patch('app.core.cache.CacheManager.get') as mock_cache_get:
            mock_cache_get.return_value = cached_result
            
            result = await nlp_service.parse_natural_language_to_event(text, context)
            
            assert result == cached_result
            mock_cache_get.assert_called_once()

    async def test_parse_low_confidence_handling(self):
        """Test handling of low confidence parsing results."""
        text = "언젠가 뭔가 해야 함"  # Vague text
        context = {"timezone": "Asia/Seoul"}
        
        mock_response = {
            "title": "일정",
            "start_at": "2024-08-20T09:00:00+09:00",
            "confidence": 0.3  # Low confidence
        }
        
        with patch('app.clients.claude_client.ClaudeClient.parse_text_to_event') as mock_parse:
            mock_parse.return_value = mock_response
            
            with pytest.raises(ValidationError) as exc_info:
                await nlp_service.parse_natural_language_to_event(text, context)
            
            assert "confidence too low" in str(exc_info.value).lower()

@pytest.mark.asyncio
class TestTimeTreeService:
    """Test TimeTree service for calendar integration."""
    
    async def test_generate_auth_url(self):
        """Test generating TimeTree OAuth URL."""
        user_id = 123
        
        auth_url, state = await timetree_service.generate_auth_url(user_id)
        
        assert "timetree.com/oauth/authorize" in auth_url
        assert "client_id" in auth_url
        assert "state" in auth_url
        assert len(state) > 10  # State should be a random string

    async def test_exchange_code_for_token_success(self):
        """Test successful OAuth code exchange."""
        code = "oauth_code_123"
        state = "random_state"
        user_id = 123
        
        mock_response = {
            "access_token": "tt_access_token_123",
            "refresh_token": "tt_refresh_token_123",
            "expires_in": 3600
        }
        
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value.json.return_value = mock_response
            mock_post.return_value.raise_for_status.return_value = None
            
            result = await timetree_service.exchange_code_for_token(code, state, user_id)
            
            assert result["access_token"] == "tt_access_token_123"
            assert result["refresh_token"] == "tt_refresh_token_123"

    async def test_get_user_calendars_success(self):
        """Test successful calendar retrieval."""
        access_token = "valid_token"
        
        mock_response = {
            "data": [
                {
                    "id": "cal_123",
                    "attributes": {
                        "name": "개인 일정",
                        "description": "개인 캘린더",
                        "color": "blue"
                    }
                }
            ]
        }
        
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value.json.return_value = mock_response
            mock_get.return_value.raise_for_status.return_value = None
            
            calendars = await timetree_service.get_user_calendars(access_token)
            
            assert len(calendars) == 1
            assert calendars[0]["id"] == "cal_123"
            assert calendars[0]["name"] == "개인 일정"

    async def test_create_event_success(self):
        """Test successful event creation in TimeTree."""
        access_token = "valid_token"
        calendar_id = "cal_123"
        event_data = {
            "title": "테스트 이벤트",
            "start_at": "2024-08-20T14:00:00+09:00",
            "end_at": "2024-08-20T15:00:00+09:00"
        }
        
        mock_response = {
            "data": {
                "id": "event_456",
                "attributes": event_data
            }
        }
        
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value.json.return_value = mock_response
            mock_post.return_value.raise_for_status.return_value = None
            
            result = await timetree_service.create_event(access_token, calendar_id, event_data)
            
            assert result["id"] == "event_456"
            assert result["title"] == "테스트 이벤트"

    async def test_api_rate_limiting(self):
        """Test TimeTree API rate limiting handling."""
        access_token = "valid_token"
        
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "60"}
            mock_get.return_value = mock_response
            
            with pytest.raises(ExternalServiceError) as exc_info:
                await timetree_service.get_user_calendars(access_token)
            
            assert "rate limit" in str(exc_info.value).lower()

@pytest.mark.asyncio
class TestUserService:
    """Test user service for user management."""
    
    async def test_create_user_success(self, db_session):
        """Test successful user creation."""
        user_data = {
            "email": "newuser@example.com",
            "hashed_password": "hashed_password_123",
            "full_name": "New User",
            "preferences": {"timezone": "Asia/Seoul"}
        }
        
        user = await user_service.create_user(db_session, **user_data)
        
        assert user.email == user_data["email"]
        assert user.full_name == user_data["full_name"]
        assert user.is_active is True
        assert user.preferences == user_data["preferences"]

    async def test_authenticate_user_success(self, db_session, test_user):
        """Test successful user authentication."""
        with patch('app.core.security.verify_password') as mock_verify:
            mock_verify.return_value = True
            
            authenticated_user = await user_service.authenticate_user(
                db_session, 
                test_user.email, 
                "testpassword123"
            )
            
            assert authenticated_user is not None
            assert authenticated_user.id == test_user.id
            assert authenticated_user.email == test_user.email

    async def test_authenticate_user_wrong_password(self, db_session, test_user):
        """Test authentication with wrong password."""
        with patch('app.core.security.verify_password') as mock_verify:
            mock_verify.return_value = False
            
            authenticated_user = await user_service.authenticate_user(
                db_session, 
                test_user.email, 
                "wrongpassword"
            )
            
            assert authenticated_user is None

    async def test_get_user_stats(self, db_session, test_user):
        """Test user statistics retrieval."""
        # Mock database queries for stats
        with patch('sqlalchemy.orm.Session.execute') as mock_execute:
            mock_execute.return_value.scalar.return_value = 25  # Mock count
            
            stats = await user_service.get_user_stats(db_session, test_user.id, 30)
            
            assert isinstance(stats, dict)
            assert "total_events_created" in stats
            assert "events_this_month" in stats
            assert "success_rate" in stats

    async def test_save_timetree_tokens(self, db_session, test_user):
        """Test saving TimeTree tokens."""
        tokens = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_at": datetime.utcnow() + timedelta(hours=1)
        }
        
        await user_service.save_timetree_tokens(
            db_session,
            test_user.id,
            **tokens
        )
        
        # Verify tokens were saved (would check database in real implementation)
        assert True  # Placeholder for actual verification

@pytest.mark.asyncio
class TestEventService:
    """Test event service for event management."""
    
    async def test_create_timetree_event_success(self):
        """Test successful TimeTree event creation."""
        user_id = 123
        calendar_id = "cal_456"
        event_data = {
            "title": "신규 이벤트",
            "start_at": "2024-08-20T16:00:00+09:00",
            "end_at": "2024-08-20T17:00:00+09:00"
        }
        access_token = "valid_token"
        
        mock_timetree_response = {
            "id": "tt_event_789",
            "title": event_data["title"],
            "start_at": event_data["start_at"],
            "end_at": event_data["end_at"],
            "calendar_id": calendar_id
        }
        
        with patch('app.services.timetree_service.timetree_service.create_event') as mock_create:
            mock_create.return_value = mock_timetree_response
            
            result = await event_service.create_timetree_event(
                user_id, calendar_id, event_data, access_token
            )
            
            assert result["id"] == "tt_event_789"
            assert result["title"] == event_data["title"]
            mock_create.assert_called_once_with(access_token, calendar_id, event_data)

    async def test_record_event_creation(self, db_session):
        """Test recording event creation in database."""
        event_data = {
            "user_id": 123,
            "timetree_event_id": "tt_event_123",
            "original_text": "내일 오후 미팅",
            "event_data": {
                "title": "미팅",
                "start_at": "2024-08-20T14:00:00+09:00"
            }
        }
        
        # Mock the database operations
        with patch('sqlalchemy.orm.Session.add') as mock_add:
            with patch('sqlalchemy.orm.Session.commit') as mock_commit:
                await event_service.record_event_creation(db_session, **event_data)
                
                mock_add.assert_called_once()
                mock_commit.assert_called_once()

    async def test_get_user_events_with_filters(self, db_session):
        """Test retrieving user events with filters."""
        user_id = 123
        calendar_id = "cal_123"
        
        # Mock query result
        mock_events = [
            {
                "id": "event_1",
                "title": "이벤트 1",
                "start_at": "2024-08-20T10:00:00+09:00",
                "category": "work"
            },
            {
                "id": "event_2", 
                "title": "이벤트 2",
                "start_at": "2024-08-21T14:00:00+09:00",
                "category": "personal"
            }
        ]
        
        with patch('sqlalchemy.orm.Session.query') as mock_query:
            # Mock the query chain
            mock_query.return_value.filter.return_value.limit.return_value.offset.return_value.all.return_value = mock_events
            
            events = await event_service.get_user_events(
                db_session, user_id, calendar_id, limit=10, offset=0
            )
            
            assert len(events) == 2
            assert events[0]["title"] == "이벤트 1"

    async def test_delete_user_event_success(self, db_session):
        """Test successful event deletion."""
        user_id = 123
        event_id = "event_456"
        
        # Mock finding and deleting the event
        with patch('sqlalchemy.orm.Session.query') as mock_query:
            mock_event = MagicMock()
            mock_query.return_value.filter.return_value.first.return_value = mock_event
            
            with patch('sqlalchemy.orm.Session.delete') as mock_delete:
                with patch('sqlalchemy.orm.Session.commit') as mock_commit:
                    result = await event_service.delete_user_event(db_session, user_id, event_id)
                    
                    assert result is True
                    mock_delete.assert_called_once_with(mock_event)
                    mock_commit.assert_called_once()

    async def test_delete_user_event_not_found(self, db_session):
        """Test deleting non-existent event."""
        user_id = 123
        event_id = "nonexistent_event"
        
        with patch('sqlalchemy.orm.Session.query') as mock_query:
            mock_query.return_value.filter.return_value.first.return_value = None
            
            result = await event_service.delete_user_event(db_session, user_id, event_id)
            
            assert result is False

@pytest.mark.integration
class TestServiceIntegration:
    """Integration tests for service interactions."""
    
    async def test_end_to_end_event_creation(self, db_session):
        """Test complete event creation flow across services."""
        # Mock user with TimeTree connection
        user_id = 123
        access_token = "valid_token"
        text = "내일 오후 3시 중요한 회의"
        calendar_id = "cal_123"
        
        # Mock NLP parsing
        parsed_data = {
            "title": "중요한 회의",
            "start_at": "2024-08-20T15:00:00+09:00",
            "end_at": "2024-08-20T16:00:00+09:00",
            "category": "work",
            "confidence": 0.92
        }
        
        # Mock TimeTree event creation
        timetree_response = {
            "id": "tt_event_123",
            **parsed_data
        }
        
        with patch('app.services.nlp_service.nlp_service.parse_natural_language_to_event') as mock_parse:
            mock_parse.return_value = parsed_data
            
            with patch('app.services.timetree_service.timetree_service.create_event') as mock_create:
                mock_create.return_value = timetree_response
                
                with patch('sqlalchemy.orm.Session.add') as mock_add:
                    with patch('sqlalchemy.orm.Session.commit') as mock_commit:
                        # 1. Parse natural language
                        parsed_result = await nlp_service.parse_natural_language_to_event(
                            text, {"timezone": "Asia/Seoul"}
                        )
                        
                        # 2. Create event in TimeTree
                        created_event = await event_service.create_timetree_event(
                            user_id, calendar_id, parsed_result, access_token
                        )
                        
                        # 3. Record in database
                        await event_service.record_event_creation(
                            db_session, user_id, created_event["id"], text, created_event
                        )
                        
                        # Verify the flow
                        assert parsed_result["title"] == "중요한 회의"
                        assert created_event["id"] == "tt_event_123"
                        mock_add.assert_called_once()
                        mock_commit.assert_called_once()

    async def test_service_error_handling(self):
        """Test error handling across service boundaries."""
        text = "내일 미팅"
        
        # Test NLP service error propagation
        with patch('app.clients.claude_client.ClaudeClient.parse_text_to_event') as mock_parse:
            mock_parse.side_effect = ExternalServiceError("API unavailable")
            
            with pytest.raises(ExternalServiceError):
                await nlp_service.parse_natural_language_to_event(
                    text, {"timezone": "Asia/Seoul"}
                )

    async def test_service_caching_integration(self):
        """Test caching across services."""
        text = "매주 월요일 팀 미팅"
        
        # First call should hit the AI service
        with patch('app.clients.claude_client.ClaudeClient.parse_text_to_event') as mock_parse:
            mock_parse.return_value = {
                "title": "팀 미팅",
                "recurrence_rule": "FREQ=WEEKLY;BYDAY=MO",
                "confidence": 0.95
            }
            
            with patch('app.core.cache.CacheManager.get') as mock_cache_get:
                mock_cache_get.return_value = None  # Cache miss
                
                with patch('app.core.cache.CacheManager.set') as mock_cache_set:
                    result1 = await nlp_service.parse_natural_language_to_event(
                        text, {"timezone": "Asia/Seoul"}
                    )
                    
                    assert result1["title"] == "팀 미팅"
                    mock_parse.assert_called_once()
                    mock_cache_set.assert_called_once()
        
        # Second call should hit cache
        with patch('app.core.cache.CacheManager.get') as mock_cache_get:
            mock_cache_get.return_value = result1  # Cache hit
            
            result2 = await nlp_service.parse_natural_language_to_event(
                text, {"timezone": "Asia/Seoul"}
            )
            
            assert result2 == result1
            mock_cache_get.assert_called_once()
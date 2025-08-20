import pytest
from unittest.mock import patch, AsyncMock
from fastapi import status
from httpx import AsyncClient

from app.core.security import verify_password, create_access_token
from app.models.user import User

@pytest.mark.asyncio
class TestAuthRoutes:
    """Test authentication-related API endpoints."""
    
    async def test_register_success(
        self,
        async_client: AsyncClient,
        db_session
    ):
        """Test successful user registration."""
        registration_data = {
            "email": "newuser@example.com",
            "password": "strongpassword123",
            "full_name": "New User",
            "preferences": {
                "timezone": "Asia/Seoul",
                "notification_enabled": True
            }
        }
        
        response = await async_client.post(
            "/api/v1/auth/register",
            json=registration_data
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["email"] == registration_data["email"]
        assert data["full_name"] == registration_data["full_name"]
        assert data["is_active"] is True
        assert "id" in data
        assert "password" not in data  # Password should not be in response

    async def test_register_duplicate_email(
        self,
        async_client: AsyncClient,
        test_user: User
    ):
        """Test registration with already existing email."""
        registration_data = {
            "email": test_user.email,  # Use existing user's email
            "password": "strongpassword123",
            "full_name": "Another User"
        }
        
        response = await async_client.post(
            "/api/v1/auth/register",
            json=registration_data
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already registered" in response.json()["detail"].lower()

    async def test_register_invalid_email(
        self,
        async_client: AsyncClient
    ):
        """Test registration with invalid email format."""
        registration_data = {
            "email": "invalid-email",
            "password": "strongpassword123",
            "full_name": "Test User"
        }
        
        response = await async_client.post(
            "/api/v1/auth/register",
            json=registration_data
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_login_success(
        self,
        async_client: AsyncClient,
        test_user: User
    ):
        """Test successful login."""
        login_data = {
            "username": test_user.email,
            "password": "testpassword123"  # This should match the password used in test_user fixture
        }
        
        response = await async_client.post(
            "/api/v1/auth/login",
            data=login_data  # Note: OAuth2PasswordRequestForm expects form data
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert "user" in data
        assert data["user"]["email"] == test_user.email

    async def test_login_invalid_credentials(
        self,
        async_client: AsyncClient,
        test_user: User
    ):
        """Test login with invalid credentials."""
        login_data = {
            "username": test_user.email,
            "password": "wrongpassword"
        }
        
        response = await async_client.post(
            "/api/v1/auth/login",
            data=login_data
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "incorrect" in response.json()["detail"].lower()

    async def test_login_nonexistent_user(
        self,
        async_client: AsyncClient
    ):
        """Test login with non-existent user."""
        login_data = {
            "username": "nonexistent@example.com",
            "password": "anypassword"
        }
        
        response = await async_client.post(
            "/api/v1/auth/login",
            data=login_data
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_logout_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test successful logout."""
        response = await async_client.post(
            "/api/v1/auth/logout",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "successfully logged out" in data["message"].lower()

    async def test_get_current_user_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_user: User
    ):
        """Test retrieving current user information."""
        with patch('app.services.user_service.user_service.get_user_detail') as mock_get_detail:
            mock_user_detail = type('obj', (object,), {
                'id': test_user.id,
                'email': test_user.email,
                'full_name': test_user.full_name,
                'is_active': test_user.is_active,
                'created_at': test_user.created_at,
                'preferences': test_user.preferences,
                'subscription': None,
                'timetree_access_token': None
            })()
            mock_get_detail.return_value = mock_user_detail
            
            response = await async_client.get(
                "/api/v1/auth/me",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["id"] == test_user.id
            assert data["email"] == test_user.email
            assert data["full_name"] == test_user.full_name
            assert data["timetree_connected"] is False

    async def test_get_current_user_unauthenticated(
        self,
        async_client: AsyncClient
    ):
        """Test retrieving current user without authentication."""
        response = await async_client.get("/api/v1/auth/me")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_timetree_auth_url(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test getting TimeTree OAuth URL."""
        mock_auth_url = "https://timetree.com/oauth/authorize?client_id=test&state=random_state"
        mock_state = "random_state"
        
        with patch('app.services.timetree_service.timetree_service.generate_auth_url') as mock_generate:
            mock_generate.return_value = (mock_auth_url, mock_state)
            
            response = await async_client.get(
                "/api/v1/auth/timetree/connect",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["auth_url"] == mock_auth_url
            assert data["state"] == mock_state

    async def test_timetree_oauth_callback_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_user: User
    ):
        """Test successful TimeTree OAuth callback."""
        callback_data = {
            "code": "oauth_code_123",
            "state": "valid_state"
        }
        
        mock_token_data = {
            "access_token": "tt_access_token_123",
            "refresh_token": "tt_refresh_token_123",
            "expires_at": "2024-09-19T12:00:00Z"
        }
        
        with patch('app.services.timetree_service.timetree_service.exchange_code_for_token') as mock_exchange:
            mock_exchange.return_value = mock_token_data
            
            with patch('app.services.user_service.user_service.save_timetree_tokens') as mock_save:
                mock_save.return_value = None
                
                response = await async_client.post(
                    "/api/v1/auth/timetree/callback",
                    json=callback_data,
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert "connected successfully" in data["message"].lower()

    async def test_timetree_oauth_callback_invalid_code(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test TimeTree OAuth callback with invalid code."""
        callback_data = {
            "code": "invalid_code",
            "state": "some_state"
        }
        
        with patch('app.services.timetree_service.timetree_service.exchange_code_for_token') as mock_exchange:
            mock_exchange.side_effect = Exception("Invalid authorization code")
            
            response = await async_client.post(
                "/api/v1/auth/timetree/callback",
                json=callback_data,
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    async def test_disconnect_timetree_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test successful TimeTree disconnection."""
        with patch('app.services.user_service.user_service.disconnect_timetree') as mock_disconnect:
            mock_disconnect.return_value = None
            
            response = await async_client.delete(
                "/api/v1/auth/timetree/disconnect",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert "disconnected successfully" in data["message"].lower()

    async def test_update_profile_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_user: User
    ):
        """Test successful profile update."""
        update_data = {
            "full_name": "Updated Name",
            "preferences": {
                "timezone": "America/New_York",
                "notification_enabled": False
            }
        }
        
        with patch('app.services.user_service.user_service.update_user_profile') as mock_update:
            mock_updated_user = type('obj', (object,), {
                'id': test_user.id,
                'email': test_user.email,
                'full_name': update_data["full_name"],
                'is_active': True,
                'created_at': test_user.created_at,
                'preferences': update_data["preferences"]
            })()
            mock_update.return_value = mock_updated_user
            
            response = await async_client.put(
                "/api/v1/auth/profile",
                json=update_data,
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["full_name"] == update_data["full_name"]
            assert data["preferences"] == update_data["preferences"]

    async def test_rate_limiting_login(
        self,
        async_client: AsyncClient,
        test_user: User
    ):
        """Test rate limiting on login endpoint."""
        login_data = {
            "username": test_user.email,
            "password": "wrongpassword"
        }
        
        with patch('app.core.rate_limiter.RateLimiter.check_rate_limit') as mock_rate_limit:
            mock_rate_limit.side_effect = Exception("Rate limit exceeded")
            
            response = await async_client.post(
                "/api/v1/auth/login",
                data=login_data
            )
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    async def test_rate_limiting_registration(
        self,
        async_client: AsyncClient
    ):
        """Test rate limiting on registration endpoint."""
        registration_data = {
            "email": "test@example.com",
            "password": "password123",
            "full_name": "Test User"
        }
        
        with patch('app.core.rate_limiter.RateLimiter.check_rate_limit') as mock_rate_limit:
            mock_rate_limit.side_effect = Exception("Rate limit exceeded")
            
            response = await async_client.post(
                "/api/v1/auth/register",
                json=registration_data
            )
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

@pytest.mark.integration
class TestAuthIntegration:
    """Integration tests for authentication flow."""
    
    async def test_complete_auth_flow(
        self,
        async_client: AsyncClient,
        db_session
    ):
        """Test complete authentication flow: register -> login -> access protected resource."""
        # 1. Register new user
        registration_data = {
            "email": "integration@example.com",
            "password": "strongpassword123",
            "full_name": "Integration Test User"
        }
        
        register_response = await async_client.post(
            "/api/v1/auth/register",
            json=registration_data
        )
        
        assert register_response.status_code == status.HTTP_200_OK
        user_data = register_response.json()
        
        # 2. Login with registered user
        login_data = {
            "username": registration_data["email"],
            "password": registration_data["password"]
        }
        
        login_response = await async_client.post(
            "/api/v1/auth/login",
            data=login_data
        )
        
        assert login_response.status_code == status.HTTP_200_OK
        login_data = login_response.json()
        
        access_token = login_data["access_token"]
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        
        # 3. Access protected resource
        with patch('app.services.user_service.user_service.get_user_detail') as mock_get_detail:
            mock_user_detail = type('obj', (object,), {
                'id': user_data["id"],
                'email': user_data["email"],
                'full_name': user_data["full_name"],
                'is_active': True,
                'created_at': user_data["created_at"],
                'preferences': user_data.get("preferences", {}),
                'subscription': None,
                'timetree_access_token': None
            })()
            mock_get_detail.return_value = mock_user_detail
            
            profile_response = await async_client.get(
                "/api/v1/auth/me",
                headers=auth_headers
            )
            
            assert profile_response.status_code == status.HTTP_200_OK
            profile_data = profile_response.json()
            
            assert profile_data["email"] == registration_data["email"]
            assert profile_data["full_name"] == registration_data["full_name"]
        
        # 4. Logout
        logout_response = await async_client.post(
            "/api/v1/auth/logout",
            headers=auth_headers
        )
        
        assert logout_response.status_code == status.HTTP_200_OK

    async def test_timetree_connection_flow(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_user: User
    ):
        """Test TimeTree connection flow: get auth URL -> callback -> disconnect."""
        # 1. Get TimeTree auth URL
        mock_auth_url = "https://timetree.com/oauth/authorize?client_id=test&state=state123"
        mock_state = "state123"
        
        with patch('app.services.timetree_service.timetree_service.generate_auth_url') as mock_generate:
            mock_generate.return_value = (mock_auth_url, mock_state)
            
            auth_url_response = await async_client.get(
                "/api/v1/auth/timetree/connect",
                headers=auth_headers
            )
            
            assert auth_url_response.status_code == status.HTTP_200_OK
            auth_data = auth_url_response.json()
            
            assert auth_data["auth_url"] == mock_auth_url
            assert auth_data["state"] == mock_state
        
        # 2. Handle OAuth callback
        callback_data = {
            "code": "oauth_code_456",
            "state": mock_state
        }
        
        mock_token_data = {
            "access_token": "tt_token_456",
            "refresh_token": "tt_refresh_456"
        }
        
        with patch('app.services.timetree_service.timetree_service.exchange_code_for_token') as mock_exchange:
            mock_exchange.return_value = mock_token_data
            
            with patch('app.services.user_service.user_service.save_timetree_tokens') as mock_save:
                mock_save.return_value = None
                
                callback_response = await async_client.post(
                    "/api/v1/auth/timetree/callback",
                    json=callback_data,
                    headers=auth_headers
                )
                
                assert callback_response.status_code == status.HTTP_200_OK
        
        # 3. Disconnect TimeTree
        with patch('app.services.user_service.user_service.disconnect_timetree') as mock_disconnect:
            mock_disconnect.return_value = None
            
            disconnect_response = await async_client.delete(
                "/api/v1/auth/timetree/disconnect",
                headers=auth_headers
            )
            
            assert disconnect_response.status_code == status.HTTP_200_OK
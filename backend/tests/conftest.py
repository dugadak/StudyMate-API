import pytest
import asyncio
from typing import AsyncGenerator, Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import httpx

from app.main import app
from app.core.database import get_db, Base
from app.core.config import settings
from app.models.user import User
from app.models.subscription import SubscriptionPlan
from app.services.user_service import user_service
from app.core.security import create_access_token, get_password_hash

# Test database URL (SQLite in-memory for fast tests)
TEST_DATABASE_URL = "sqlite:///./test.db"

# Create test engine
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_session():
    """Create a fresh database session for each test."""
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def override_get_db(db_session):
    """Override the get_db dependency."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def client(override_get_db) -> TestClient:
    """Create a test client."""
    return TestClient(app)

@pytest.fixture
async def async_client(override_get_db) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create an async test client."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
async def test_user(db_session) -> User:
    """Create a test user."""
    user_data = {
        "email": "test@example.com",
        "full_name": "Test User",
        "hashed_password": get_password_hash("testpassword123"),
        "is_active": True,
        "preferences": {
            "timezone": "Asia/Seoul",
            "default_calendar_name": "개인 일정"
        }
    }
    
    user = User(**user_data)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    return user

@pytest.fixture
async def test_user_with_subscription(db_session, test_user) -> User:
    """Create a test user with an active subscription."""
    # First create a subscription plan
    plan = SubscriptionPlan(
        name="Test Premium",
        description="Test premium plan",
        price=1999,
        currency="USD",
        interval="monthly",
        features={
            "max_events_per_month": -1,
            "ai_parsing_requests": -1,
            "calendar_sync": True,
            "priority_support": True
        },
        is_active=True
    )
    db_session.add(plan)
    db_session.commit()
    
    # Create user subscription
    from app.models.subscription import UserSubscription
    from datetime import datetime, timedelta
    
    subscription = UserSubscription(
        user_id=test_user.id,
        plan_id=plan.id,
        status="active",
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30)
    )
    db_session.add(subscription)
    db_session.commit()
    
    return test_user

@pytest.fixture
def auth_headers(test_user) -> dict:
    """Create authentication headers for test user."""
    access_token = create_access_token(data={"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {access_token}"}

@pytest.fixture
def premium_auth_headers(test_user_with_subscription) -> dict:
    """Create authentication headers for premium test user."""
    access_token = create_access_token(data={"sub": str(test_user_with_subscription.id)})
    return {"Authorization": f"Bearer {access_token}"}

@pytest.fixture
def sample_event_data() -> dict:
    """Sample event data for testing."""
    return {
        "title": "테스트 미팅",
        "description": "중요한 테스트 미팅입니다",
        "start_at": "2024-08-20T14:00:00+09:00",
        "end_at": "2024-08-20T15:00:00+09:00",
        "all_day": False,
        "location": "서울시 강남구",
        "category": "work"
    }

@pytest.fixture
def sample_parsing_request() -> dict:
    """Sample parsing request data for testing."""
    return {
        "text": "내일 오후 3시에 치과 예약",
        "timezone": "Asia/Seoul",
        "default_calendar_id": None
    }

@pytest.fixture
def mock_timetree_response() -> dict:
    """Mock TimeTree API response."""
    return {
        "id": "tt_event_123",
        "title": "치과 예약",
        "description": "",
        "start_at": "2024-08-20T15:00:00+09:00",
        "end_at": "2024-08-20T16:00:00+09:00",
        "all_day": False,
        "location": None,
        "calendar_id": "cal_123",
        "created_at": "2024-08-19T12:00:00+09:00",
        "updated_at": "2024-08-19T12:00:00+09:00"
    }

@pytest.fixture
def mock_claude_response() -> dict:
    """Mock Claude AI parsing response."""
    return {
        "title": "치과 예약",
        "description": None,
        "start_at": "2024-08-20T15:00:00+09:00",
        "end_at": "2024-08-20T16:00:00+09:00",
        "start_timezone": "Asia/Seoul",
        "end_timezone": "Asia/Seoul",
        "all_day": False,
        "location": None,
        "recurrence_rule": None,
        "category": "health",
        "confidence": 0.95,
        "suggestions": ["치과명을 추가하시겠습니까?"],
        "extracted_entities": {
            "datetime": "내일 오후 3시",
            "location": None,
            "duration": None,
            "participants": None
        }
    }

# Test configuration overrides
@pytest.fixture(autouse=True)
def override_settings():
    """Override settings for testing."""
    original_values = {}
    
    # Override settings for testing
    test_overrides = {
        "TESTING": True,
        "DATABASE_URL": TEST_DATABASE_URL,
        "ACCESS_TOKEN_EXPIRE_MINUTES": 30,
        "RATE_LIMITING_ENABLED": False,  # Disable for tests
        "EXTERNAL_API_TIMEOUT": 5,  # Shorter timeout for tests
    }
    
    for key, value in test_overrides.items():
        if hasattr(settings, key):
            original_values[key] = getattr(settings, key)
            setattr(settings, key, value)
    
    yield
    
    # Restore original values
    for key, value in original_values.items():
        setattr(settings, key, value)

# Async test helpers
@pytest.fixture
def anyio_backend():
    """Configure anyio backend for async tests."""
    return "asyncio"

class MockResponse:
    """Mock HTTP response for testing external APIs."""
    
    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code
    
    def json(self):
        return self.json_data
    
    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                message=f"HTTP {self.status_code}",
                request=None,
                response=self
            )

@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    return MockResponse({
        "choices": [{
            "message": {
                "content": '{"title": "치과 예약", "start_at": "2024-08-20T15:00:00+09:00", "confidence": 0.95}'
            }
        }]
    })

@pytest.fixture
def mock_timetree_api_response():
    """Mock TimeTree API response."""
    return MockResponse({
        "data": {
            "id": "tt_event_123",
            "type": "event",
            "attributes": {
                "title": "치과 예약",
                "start_at": "2024-08-20T15:00:00+09:00",
                "end_at": "2024-08-20T16:00:00+09:00",
                "all_day": False
            }
        }
    })

# Database seeding helpers
@pytest.fixture
async def seed_subscription_plans(db_session):
    """Seed database with default subscription plans."""
    plans_data = [
        {
            "name": "Free",
            "description": "Basic plan",
            "price": 0,
            "currency": "USD",
            "interval": "monthly",
            "features": {
                "max_events_per_month": 10,
                "ai_parsing_requests": 50
            },
            "is_active": True
        },
        {
            "name": "Premium",
            "description": "Premium plan",
            "price": 1999,
            "currency": "USD", 
            "interval": "monthly",
            "features": {
                "max_events_per_month": -1,
                "ai_parsing_requests": -1,
                "priority_support": True
            },
            "is_active": True
        }
    ]
    
    for plan_data in plans_data:
        plan = SubscriptionPlan(**plan_data)
        db_session.add(plan)
    
    db_session.commit()

# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "asyncio: mark test to run with asyncio"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
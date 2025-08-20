"""
TimeTree Scheduler - Main FastAPI Application

Natural language to TimeTree calendar integration service.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import create_tables, engine
from app.core.logger import setup_logging
from app.middleware.cors import setup_cors
from app.middleware.exception import setup_exception_handlers
from app.middleware.logging import setup_logging_middleware
from app.routers import auth, calendars, chat, events, health

# Setup structured logging
setup_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    logger.info("Starting TimeTree Scheduler API", version="1.0.0")
    
    # Create database tables
    await create_tables()
    logger.info("Database tables created/verified")
    
    # Initialize any background tasks or connections here
    if settings.SENTRY_DSN:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[
                FastApiIntegration(auto_enabling=True),
                SqlalchemyIntegration(),
            ],
            traces_sample_rate=0.1,
            environment=settings.ENVIRONMENT,
        )
        logger.info("Sentry monitoring initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down TimeTree Scheduler API")
    await engine.dispose()


# Create FastAPI application
app = FastAPI(
    title="TimeTree Scheduler API",
    description="Natural language to TimeTree calendar integration service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Setup middleware
setup_cors(app)
setup_logging_middleware(app)
setup_exception_handlers(app)

# Include routers
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(events.router, prefix="/events", tags=["Events"])
app.include_router(calendars.router, prefix="/calendars", tags=["Calendars"])


@app.get("/")
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "message": "TimeTree Scheduler API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "status": "healthy"
    }


@app.get("/openapi.json")
async def custom_openapi():
    """Custom OpenAPI schema with enhanced documentation."""
    from fastapi.openapi.utils import get_openapi
    
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="TimeTree Scheduler API",
        version="1.0.0",
        description="""
        ## TimeTree Scheduler API
        
        자연어로 입력한 일정을 AI가 파싱하여 TimeTree 캘린더에 자동 등록하는 서비스입니다.
        
        ### 주요 기능
        - 🗣️ 자연어 일정 입력 ("내일 오후 2시 회의")
        - 🤖 ChatGPT AI 기반 스마트 파싱
        - 📅 TimeTree OAuth 연동
        - 🔄 실시간 일정 미리보기
        - 🌏 한국 시간대 자동 처리
        
        ### 인증
        - TimeTree OAuth 2.0을 통한 사용자 인증
        - JWT 토큰 기반 API 접근 제어
        
        ### 사용 예시
        ```python
        # 1. 자연어 일정 파싱
        POST /chat/message
        {
            "message": "내일 오후 2시 팀 회의",
            "calendar_id": "calendar_123"
        }
        
        # 2. 파싱 결과 미리보기
        # Response: 파싱된 이벤트 정보
        
        # 3. TimeTree 등록 확인
        POST /events/confirm
        {
            "event_id": "temp_event_123"
        }
        ```
        """,
        routes=app.routes,
    )
    
    # Add custom schema information
    openapi_schema["info"]["contact"] = {
        "name": "TimeTree Scheduler Support",
        "email": "support@timetree-scheduler.com",
        "url": "https://github.com/your-username/timetree-scheduler"
    }
    
    openapi_schema["info"]["license"] = {
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    }
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        },
        "TimeTreeOAuth": {
            "type": "oauth2",
            "flows": {
                "authorizationCode": {
                    "authorizationUrl": "https://timetreeapp.com/oauth/authorize",
                    "tokenUrl": "https://timetreeapp.com/oauth/token",
                    "scopes": {
                        "read": "Read calendar data",
                        "write": "Create and modify events"
                    }
                }
            }
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
    )
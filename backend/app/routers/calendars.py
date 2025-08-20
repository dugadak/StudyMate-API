from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import structlog

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.services.user_service import user_service
from app.services.timetree_service import timetree_service
from app.schemas.calendar import (
    CalendarResponse,
    CalendarListResponse,
    CalendarMemberResponse
)
from app.schemas.user import User
from app.core.exceptions import ExternalServiceError
from app.core.rate_limiter import RateLimiter

router = APIRouter(prefix="/calendars", tags=["calendars"])
logger = structlog.get_logger(__name__)
rate_limiter = RateLimiter()

@router.get("/", response_model=CalendarListResponse)
async def get_user_calendars(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자의 TimeTree 캘린더 목록을 조회합니다.
    """
    try:
        await rate_limiter.check_rate_limit(
            f"get_calendars:{current_user.id}",
            max_requests=60,
            window_seconds=3600
        )
        
        logger.info("캘린더 목록 조회", user_id=current_user.id)
        
        # 사용자의 TimeTree 토큰 확인
        user_data = await user_service.get_user_with_timetree_auth(db, current_user.id)
        
        if not user_data.timetree_access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="TimeTree authentication required"
            )
        
        # TimeTree API에서 캘린더 목록 조회
        calendars = await timetree_service.get_user_calendars(
            access_token=user_data.timetree_access_token
        )
        
        logger.info("캘린더 목록 조회 완료", 
                   user_id=current_user.id, 
                   calendar_count=len(calendars))
        
        return CalendarListResponse(
            success=True,
            calendars=calendars,
            total=len(calendars)
        )
        
    except HTTPException:
        raise
    except ExternalServiceError as e:
        logger.error("TimeTree API 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        logger.error("캘린더 목록 조회 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve calendars"
        )

@router.get("/{calendar_id}", response_model=CalendarResponse)
async def get_calendar_detail(
    calendar_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    특정 캘린더의 상세 정보를 조회합니다.
    """
    try:
        await rate_limiter.check_rate_limit(
            f"get_calendar:{current_user.id}",
            max_requests=100,
            window_seconds=3600
        )
        
        logger.info("캘린더 상세 조회", 
                   user_id=current_user.id, 
                   calendar_id=calendar_id)
        
        # 사용자의 TimeTree 토큰 확인
        user_data = await user_service.get_user_with_timetree_auth(db, current_user.id)
        
        if not user_data.timetree_access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="TimeTree authentication required"
            )
        
        # TimeTree API에서 캘린더 상세 정보 조회
        calendar = await timetree_service.get_calendar_detail(
            calendar_id=calendar_id,
            access_token=user_data.timetree_access_token
        )
        
        if not calendar:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Calendar not found"
            )
        
        logger.info("캘린더 상세 조회 완료", 
                   user_id=current_user.id, 
                   calendar_id=calendar_id)
        
        return CalendarResponse(
            success=True,
            calendar=calendar
        )
        
    except HTTPException:
        raise
    except ExternalServiceError as e:
        logger.error("TimeTree API 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        logger.error("캘린더 상세 조회 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve calendar"
        )

@router.get("/{calendar_id}/members", response_model=List[CalendarMemberResponse])
async def get_calendar_members(
    calendar_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    캘린더 멤버 목록을 조회합니다.
    """
    try:
        await rate_limiter.check_rate_limit(
            f"get_members:{current_user.id}",
            max_requests=60,
            window_seconds=3600
        )
        
        logger.info("캘린더 멤버 조회", 
                   user_id=current_user.id, 
                   calendar_id=calendar_id)
        
        # 사용자의 TimeTree 토큰 확인
        user_data = await user_service.get_user_with_timetree_auth(db, current_user.id)
        
        if not user_data.timetree_access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="TimeTree authentication required"
            )
        
        # TimeTree API에서 캘린더 멤버 조회
        members = await timetree_service.get_calendar_members(
            calendar_id=calendar_id,
            access_token=user_data.timetree_access_token
        )
        
        logger.info("캘린더 멤버 조회 완료", 
                   user_id=current_user.id, 
                   calendar_id=calendar_id,
                   member_count=len(members))
        
        return members
        
    except HTTPException:
        raise
    except ExternalServiceError as e:
        logger.error("TimeTree API 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        logger.error("캘린더 멤버 조회 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve calendar members"
        )

@router.get("/{calendar_id}/events")
async def get_calendar_events(
    calendar_id: str,
    days: Optional[int] = 30,
    timezone: Optional[str] = "Asia/Seoul",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    캘린더의 이벤트 목록을 조회합니다.
    """
    try:
        await rate_limiter.check_rate_limit(
            f"get_events:{current_user.id}",
            max_requests=60,
            window_seconds=3600
        )
        
        logger.info("캘린더 이벤트 조회", 
                   user_id=current_user.id, 
                   calendar_id=calendar_id,
                   days=days)
        
        # 사용자의 TimeTree 토큰 확인
        user_data = await user_service.get_user_with_timetree_auth(db, current_user.id)
        
        if not user_data.timetree_access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="TimeTree authentication required"
            )
        
        # TimeTree API에서 이벤트 목록 조회
        events = await timetree_service.get_calendar_events(
            calendar_id=calendar_id,
            access_token=user_data.timetree_access_token,
            days=days,
            timezone=timezone
        )
        
        logger.info("캘린더 이벤트 조회 완료", 
                   user_id=current_user.id, 
                   calendar_id=calendar_id,
                   event_count=len(events))
        
        return {
            "success": True,
            "events": events,
            "total": len(events),
            "calendar_id": calendar_id,
            "query_days": days
        }
        
    except HTTPException:
        raise
    except ExternalServiceError as e:
        logger.error("TimeTree API 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        logger.error("캘린더 이벤트 조회 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve calendar events"
        )

@router.post("/{calendar_id}/sync")
async def sync_calendar(
    calendar_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    캘린더를 로컬 데이터베이스와 동기화합니다.
    """
    try:
        await rate_limiter.check_rate_limit(
            f"sync_calendar:{current_user.id}",
            max_requests=10,
            window_seconds=3600
        )
        
        logger.info("캘린더 동기화 시작", 
                   user_id=current_user.id, 
                   calendar_id=calendar_id)
        
        # 사용자의 TimeTree 토큰 확인
        user_data = await user_service.get_user_with_timetree_auth(db, current_user.id)
        
        if not user_data.timetree_access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="TimeTree authentication required"
            )
        
        # 동기화 작업 시작 (백그라운드 작업으로 처리)
        sync_result = await timetree_service.sync_calendar(
            calendar_id=calendar_id,
            user_id=current_user.id,
            access_token=user_data.timetree_access_token
        )
        
        logger.info("캘린더 동기화 완료", 
                   user_id=current_user.id, 
                   calendar_id=calendar_id,
                   synced_events=sync_result.get('synced_events', 0))
        
        return {
            "success": True,
            "message": "Calendar synchronized successfully",
            "synced_events": sync_result.get('synced_events', 0),
            "last_sync": sync_result.get('last_sync')
        }
        
    except HTTPException:
        raise
    except ExternalServiceError as e:
        logger.error("TimeTree API 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        logger.error("캘린더 동기화 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync calendar"
        )
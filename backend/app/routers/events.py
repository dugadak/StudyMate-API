from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import structlog

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.services.nlp_service import nlp_service
from app.services.event_service import event_service
from app.services.user_service import user_service
from app.schemas.event import (
    ParseEventRequest, 
    ParseEventResponse,
    CreateEventRequest,
    EventResponse,
    EventListResponse
)
from app.schemas.user import User
from app.core.exceptions import ValidationError, ExternalServiceError
from app.core.rate_limiter import RateLimiter

router = APIRouter(prefix="/events", tags=["events"])
logger = structlog.get_logger(__name__)
rate_limiter = RateLimiter()

@router.post("/parse", response_model=ParseEventResponse)
async def parse_event(
    request: ParseEventRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    자연어 텍스트를 파싱하여 TimeTree 이벤트 형식으로 변환합니다.
    
    이 엔드포인트는 한국어 자연어 입력을 받아 Claude AI를 통해
    TimeTree API에서 사용할 수 있는 이벤트 데이터로 변환합니다.
    """
    try:
        # 사용자 요청 제한 확인
        await rate_limiter.check_rate_limit(
            f"parse_event:{current_user.id}", 
            max_requests=50, 
            window_seconds=3600
        )
        
        logger.info("자연어 이벤트 파싱 요청", 
                   user_id=current_user.id, 
                   text_length=len(request.text))
        
        # 사용자의 구독 상태 확인
        user_data = await user_service.get_user_with_subscription(db, current_user.id)
        
        if not user_data.subscription or not user_data.subscription.is_active:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Active subscription required for AI parsing"
            )
        
        # NLP 서비스를 통한 이벤트 파싱
        parsed_data = await nlp_service.parse_natural_language_to_event(
            text=request.text,
            user_context={
                "timezone": request.timezone or "Asia/Seoul",
                "default_calendar": request.default_calendar_id,
                "user_preferences": user_data.preferences
            }
        )
        
        logger.info("이벤트 파싱 완료", 
                   user_id=current_user.id,
                   event_title=parsed_data.get('title'))
        
        return ParseEventResponse(
            success=True,
            parsed_event=parsed_data,
            confidence_score=parsed_data.get('confidence', 0.85),
            suggestions=parsed_data.get('suggestions', [])
        )
        
    except ValidationError as e:
        logger.error("이벤트 파싱 검증 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    except ExternalServiceError as e:
        logger.error("외부 서비스 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    
    except Exception as e:
        logger.error("이벤트 파싱 중 예상치 못한 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse event"
        )

@router.post("/create", response_model=EventResponse)
async def create_event(
    request: CreateEventRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    파싱된 이벤트 데이터를 TimeTree 캘린더에 생성합니다.
    
    이 엔드포인트는 파싱된 이벤트 데이터를 받아
    사용자의 TimeTree 캘린더에 실제 이벤트를 생성합니다.
    """
    try:
        # 사용자 요청 제한 확인
        await rate_limiter.check_rate_limit(
            f"create_event:{current_user.id}", 
            max_requests=30, 
            window_seconds=3600
        )
        
        logger.info("TimeTree 이벤트 생성 요청", 
                   user_id=current_user.id,
                   calendar_id=request.calendar_id,
                   event_title=request.title)
        
        # 사용자 TimeTree 인증 정보 확인
        user_data = await user_service.get_user_with_timetree_auth(db, current_user.id)
        
        if not user_data.timetree_access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="TimeTree authentication required"
            )
        
        # 이벤트 생성
        created_event = await event_service.create_timetree_event(
            user_id=current_user.id,
            calendar_id=request.calendar_id,
            event_data=request.dict(exclude={'calendar_id'}),
            access_token=user_data.timetree_access_token
        )
        
        # 이벤트 기록 저장 (멱등성 보장)
        await event_service.record_event_creation(
            db=db,
            user_id=current_user.id,
            timetree_event_id=created_event['id'],
            original_text=request.original_text,
            event_data=created_event
        )
        
        logger.info("TimeTree 이벤트 생성 완료", 
                   user_id=current_user.id,
                   timetree_event_id=created_event['id'])
        
        return EventResponse(
            success=True,
            event=created_event,
            message="Event created successfully"
        )
        
    except ValidationError as e:
        logger.error("이벤트 생성 검증 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    except ExternalServiceError as e:
        logger.error("TimeTree API 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    
    except Exception as e:
        logger.error("이벤트 생성 중 예상치 못한 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create event"
        )

@router.get("/", response_model=EventListResponse)
async def get_user_events(
    calendar_id: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자가 생성한 이벤트 목록을 조회합니다.
    """
    try:
        logger.info("사용자 이벤트 목록 조회", 
                   user_id=current_user.id,
                   calendar_id=calendar_id)
        
        events = await event_service.get_user_events(
            db=db,
            user_id=current_user.id,
            calendar_id=calendar_id,
            limit=limit,
            offset=offset
        )
        
        return EventListResponse(
            success=True,
            events=events,
            total=len(events)
        )
        
    except Exception as e:
        logger.error("이벤트 목록 조회 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve events"
        )

@router.delete("/{event_id}")
async def delete_event(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    생성된 이벤트를 삭제합니다.
    """
    try:
        logger.info("이벤트 삭제 요청", 
                   user_id=current_user.id,
                   event_id=event_id)
        
        # 이벤트 소유권 확인 및 삭제
        success = await event_service.delete_user_event(
            db=db,
            user_id=current_user.id,
            event_id=event_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found or access denied"
            )
        
        return {"success": True, "message": "Event deleted successfully"}
        
    except Exception as e:
        logger.error("이벤트 삭제 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete event"
        )

@router.post("/parse-and-create", response_model=EventResponse)
async def parse_and_create_event(
    request: ParseEventRequest,
    calendar_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    자연어 텍스트를 파싱하고 즉시 TimeTree 이벤트를 생성합니다.
    
    이 엔드포인트는 파싱과 생성을 한 번에 처리하는 편의 기능입니다.
    """
    try:
        # 사용자 요청 제한 확인 (더 엄격한 제한)
        await rate_limiter.check_rate_limit(
            f"parse_and_create:{current_user.id}", 
            max_requests=20, 
            window_seconds=3600
        )
        
        logger.info("자연어 파싱 및 이벤트 생성 요청", 
                   user_id=current_user.id,
                   calendar_id=calendar_id,
                   text_length=len(request.text))
        
        # 1단계: 자연어 파싱
        parse_response = await parse_event(request, current_user, db)
        
        if not parse_response.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to parse natural language"
            )
        
        # 2단계: 이벤트 생성
        create_request = CreateEventRequest(
            calendar_id=calendar_id,
            original_text=request.text,
            **parse_response.parsed_event
        )
        
        create_response = await create_event(create_request, current_user, db)
        
        logger.info("자연어 파싱 및 이벤트 생성 완료", 
                   user_id=current_user.id,
                   confidence=parse_response.confidence_score)
        
        return EventResponse(
            success=True,
            event=create_response.event,
            message=f"Event created with {parse_response.confidence_score:.1%} confidence",
            metadata={
                "confidence_score": parse_response.confidence_score,
                "suggestions": parse_response.suggestions,
                "parsed_from": request.text
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("자연어 파싱 및 이벤트 생성 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse and create event"
        )
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import structlog

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.services.user_service import user_service
from app.services.subscription_service import subscription_service
from app.schemas.user import User, UserResponse, UserStatsResponse, UserPreferencesUpdate
from app.schemas.subscription import SubscriptionResponse
from app.core.exceptions import ValidationError
from app.core.rate_limiter import RateLimiter

router = APIRouter(prefix="/users", tags=["users"])
logger = structlog.get_logger(__name__)
rate_limiter = RateLimiter()

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    현재 사용자의 상세 프로필을 반환합니다.
    """
    try:
        logger.info("사용자 프로필 조회", user_id=current_user.id)
        
        user_detail = await user_service.get_user_detail(db, current_user.id)
        
        return UserResponse(
            id=user_detail.id,
            email=user_detail.email,
            full_name=user_detail.full_name,
            is_active=user_detail.is_active,
            created_at=user_detail.created_at,
            updated_at=user_detail.updated_at,
            preferences=user_detail.preferences,
            subscription=user_detail.subscription,
            timetree_connected=bool(user_detail.timetree_access_token),
            usage_stats=user_detail.usage_stats
        )
        
    except Exception as e:
        logger.error("사용자 프로필 조회 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user profile"
        )

@router.put("/me/preferences", response_model=UserResponse)
async def update_user_preferences(
    preferences: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자 환경설정을 업데이트합니다.
    """
    try:
        logger.info("사용자 환경설정 업데이트", user_id=current_user.id)
        
        updated_user = await user_service.update_user_preferences(
            db=db,
            user_id=current_user.id,
            preferences=preferences.dict(exclude_unset=True)
        )
        
        logger.info("사용자 환경설정 업데이트 완료", user_id=current_user.id)
        
        return UserResponse(
            id=updated_user.id,
            email=updated_user.email,
            full_name=updated_user.full_name,
            is_active=updated_user.is_active,
            created_at=updated_user.created_at,
            updated_at=updated_user.updated_at,
            preferences=updated_user.preferences
        )
        
    except ValidationError as e:
        logger.error("환경설정 업데이트 검증 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    except Exception as e:
        logger.error("환경설정 업데이트 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )

@router.get("/me/stats", response_model=UserStatsResponse)
async def get_user_stats(
    days: Optional[int] = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자의 사용 통계를 조회합니다.
    """
    try:
        await rate_limiter.check_rate_limit(
            f"user_stats:{current_user.id}",
            max_requests=30,
            window_seconds=3600
        )
        
        logger.info("사용자 통계 조회", user_id=current_user.id, days=days)
        
        stats = await user_service.get_user_stats(
            db=db,
            user_id=current_user.id,
            days=days
        )
        
        return UserStatsResponse(
            total_events_created=stats['total_events_created'],
            events_this_month=stats['events_this_month'],
            ai_parsing_requests=stats['ai_parsing_requests'],
            success_rate=stats['success_rate'],
            most_used_categories=stats['most_used_categories'],
            average_events_per_day=stats['average_events_per_day'],
            time_saved_estimation=stats['time_saved_estimation'],
            calendar_usage=stats['calendar_usage']
        )
        
    except Exception as e:
        logger.error("사용자 통계 조회 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user stats"
        )

@router.get("/me/subscription", response_model=SubscriptionResponse)
async def get_user_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자의 구독 정보를 조회합니다.
    """
    try:
        logger.info("사용자 구독 정보 조회", user_id=current_user.id)
        
        subscription = await subscription_service.get_user_subscription(
            db=db,
            user_id=current_user.id
        )
        
        if not subscription:
            return SubscriptionResponse(
                is_active=False,
                plan_name="Free",
                features_available={
                    "max_events_per_month": 10,
                    "ai_parsing_requests": 50,
                    "calendar_sync": False,
                    "priority_support": False
                }
            )
        
        return SubscriptionResponse(
            is_active=subscription.is_active,
            plan_name=subscription.plan.name,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            features_available=subscription.plan.features,
            usage_this_month=subscription.usage_this_month,
            next_billing_date=subscription.next_billing_date
        )
        
    except Exception as e:
        logger.error("구독 정보 조회 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve subscription info"
        )

@router.delete("/me")
async def delete_user_account(
    confirmation: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자 계정을 삭제합니다.
    """
    try:
        # 확인 문구 검증
        if confirmation != "DELETE_MY_ACCOUNT":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid confirmation string"
            )
        
        logger.info("사용자 계정 삭제 요청", user_id=current_user.id)
        
        # 사용자 계정 및 관련 데이터 삭제
        await user_service.delete_user_account(db, current_user.id)
        
        logger.info("사용자 계정 삭제 완료", user_id=current_user.id)
        
        return {"message": "Account deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("사용자 계정 삭제 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account"
        )

@router.post("/me/export-data")
async def export_user_data(
    format: str = "json",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자 데이터를 내보냅니다 (GDPR 준수).
    """
    try:
        await rate_limiter.check_rate_limit(
            f"export_data:{current_user.id}",
            max_requests=3,
            window_seconds=86400  # 하루에 3번만 허용
        )
        
        logger.info("사용자 데이터 내보내기 요청", 
                   user_id=current_user.id, 
                   format=format)
        
        if format not in ["json", "csv"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Supported formats: json, csv"
            )
        
        # 사용자 데이터 수집
        export_data = await user_service.export_user_data(
            db=db,
            user_id=current_user.id,
            format=format
        )
        
        logger.info("사용자 데이터 내보내기 완료", user_id=current_user.id)
        
        return {
            "success": True,
            "data": export_data,
            "format": format,
            "exported_at": "2024-08-19T12:00:00Z"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("사용자 데이터 내보내기 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export user data"
        )

@router.post("/me/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자 비밀번호를 변경합니다.
    """
    try:
        await rate_limiter.check_rate_limit(
            f"change_password:{current_user.id}",
            max_requests=5,
            window_seconds=3600
        )
        
        logger.info("비밀번호 변경 요청", user_id=current_user.id)
        
        # 현재 비밀번호 확인 및 새 비밀번호로 변경
        success = await user_service.change_password(
            db=db,
            user_id=current_user.id,
            current_password=current_password,
            new_password=new_password
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        logger.info("비밀번호 변경 완료", user_id=current_user.id)
        
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except ValidationError as e:
        logger.error("비밀번호 변경 검증 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    except Exception as e:
        logger.error("비밀번호 변경 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )
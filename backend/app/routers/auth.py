from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import structlog

from app.core.database import get_db
from app.core.security import create_access_token, verify_password, get_password_hash
from app.core.config import settings
from app.middleware.auth import get_current_user
from app.services.user_service import user_service
from app.services.timetree_service import timetree_service
from app.schemas.auth import (
    UserCreate,
    UserResponse,
    Token,
    TimeTreeAuthURL,
    TimeTreeCallback
)
from app.schemas.user import User
from app.models.user import User as UserModel
from app.core.exceptions import ValidationError
from app.core.rate_limiter import RateLimiter

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = structlog.get_logger(__name__)
rate_limiter = RateLimiter()

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """
    새 사용자를 등록합니다.
    """
    try:
        await rate_limiter.check_rate_limit(
            f"register:{user_data.email}",
            max_requests=5,
            window_seconds=3600
        )
        
        logger.info("사용자 등록 요청", email=user_data.email)
        
        # 이메일 중복 확인
        existing_user = await user_service.get_user_by_email(db, user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # 비밀번호 해시화
        hashed_password = get_password_hash(user_data.password)
        
        # 사용자 생성
        user = await user_service.create_user(
            db=db,
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            preferences=user_data.preferences or {}
        )
        
        logger.info("사용자 등록 완료", user_id=user.id, email=user.email)
        
        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at,
            preferences=user.preferences
        )
        
    except ValidationError as e:
        logger.error("사용자 등록 검증 오류", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    except Exception as e:
        logger.error("사용자 등록 중 오류", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.post("/login", response_model=Token)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    사용자 로그인을 처리합니다.
    """
    try:
        await rate_limiter.check_rate_limit(
            f"login:{form_data.username}",
            max_requests=10,
            window_seconds=900  # 15분
        )
        
        logger.info("로그인 시도", email=form_data.username)
        
        # 사용자 인증
        user = await user_service.authenticate_user(
            db, form_data.username, form_data.password
        )
        
        if not user:
            logger.warning("로그인 실패", email=form_data.username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # JWT 토큰 생성
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)}, expires_delta=access_token_expires
        )
        
        # 리프레시 토큰을 HttpOnly 쿠키로 설정
        response.set_cookie(
            key="refresh_token",
            value=access_token,  # 실제로는 별도의 refresh token 생성 필요
            httponly=True,
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            samesite="lax",
            secure=not settings.DEBUG
        )
        
        # 로그인 기록 저장
        await user_service.record_login(db, user.id)
        
        logger.info("로그인 성공", user_id=user.id, email=user.email)
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                created_at=user.created_at,
                preferences=user.preferences
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("로그인 중 오류", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@router.post("/logout")
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user)
):
    """
    사용자 로그아웃을 처리합니다.
    """
    try:
        logger.info("로그아웃", user_id=current_user.id)
        
        # 리프레시 토큰 쿠키 제거
        response.delete_cookie(key="refresh_token", httponly=True)
        
        return {"message": "Successfully logged out"}
        
    except Exception as e:
        logger.error("로그아웃 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    현재 로그인한 사용자 정보를 반환합니다.
    """
    try:
        user_detail = await user_service.get_user_detail(db, current_user.id)
        
        return UserResponse(
            id=user_detail.id,
            email=user_detail.email,
            full_name=user_detail.full_name,
            is_active=user_detail.is_active,
            created_at=user_detail.created_at,
            preferences=user_detail.preferences,
            subscription=user_detail.subscription,
            timetree_connected=bool(user_detail.timetree_access_token)
        )
        
    except Exception as e:
        logger.error("사용자 정보 조회 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user information"
        )

@router.get("/timetree/connect", response_model=TimeTreeAuthURL)
async def get_timetree_auth_url(
    current_user: User = Depends(get_current_user)
):
    """
    TimeTree OAuth 인증 URL을 생성합니다.
    """
    try:
        logger.info("TimeTree 인증 URL 요청", user_id=current_user.id)
        
        auth_url, state = await timetree_service.generate_auth_url(
            user_id=current_user.id
        )
        
        return TimeTreeAuthURL(
            auth_url=auth_url,
            state=state
        )
        
    except Exception as e:
        logger.error("TimeTree 인증 URL 생성 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate TimeTree auth URL"
        )

@router.post("/timetree/callback")
async def timetree_oauth_callback(
    callback_data: TimeTreeCallback,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    TimeTree OAuth 콜백을 처리합니다.
    """
    try:
        logger.info("TimeTree OAuth 콜백 처리", user_id=current_user.id)
        
        # 인증 코드를 액세스 토큰으로 교환
        token_data = await timetree_service.exchange_code_for_token(
            code=callback_data.code,
            state=callback_data.state,
            user_id=current_user.id
        )
        
        # 토큰 저장
        await user_service.save_timetree_tokens(
            db=db,
            user_id=current_user.id,
            access_token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token'),
            expires_at=token_data.get('expires_at')
        )
        
        logger.info("TimeTree 연동 완료", user_id=current_user.id)
        
        return {"message": "TimeTree connected successfully"}
        
    except ValidationError as e:
        logger.error("TimeTree 콜백 검증 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    except Exception as e:
        logger.error("TimeTree 콜백 처리 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to connect TimeTree"
        )

@router.delete("/timetree/disconnect")
async def disconnect_timetree(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    TimeTree 연동을 해제합니다.
    """
    try:
        logger.info("TimeTree 연동 해제 요청", user_id=current_user.id)
        
        await user_service.disconnect_timetree(db, current_user.id)
        
        logger.info("TimeTree 연동 해제 완료", user_id=current_user.id)
        
        return {"message": "TimeTree disconnected successfully"}
        
    except Exception as e:
        logger.error("TimeTree 연동 해제 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disconnect TimeTree"
        )

@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자 프로필을 업데이트합니다.
    """
    try:
        logger.info("프로필 업데이트 요청", user_id=current_user.id)
        
        updated_user = await user_service.update_user_profile(
            db=db,
            user_id=current_user.id,
            profile_data=profile_data
        )
        
        logger.info("프로필 업데이트 완료", user_id=current_user.id)
        
        return UserResponse(
            id=updated_user.id,
            email=updated_user.email,
            full_name=updated_user.full_name,
            is_active=updated_user.is_active,
            created_at=updated_user.created_at,
            preferences=updated_user.preferences
        )
        
    except ValidationError as e:
        logger.error("프로필 업데이트 검증 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    except Exception as e:
        logger.error("프로필 업데이트 중 오류", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )
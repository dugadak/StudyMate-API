"""
Authentication router for TimeTree OAuth flow.

Handles OAuth authorization, callback, token management, and user sessions.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.timetree_client import timetree_client, TimeTreeAPIError
from app.core.database import get_db
from app.core.security import security, token_manager
from app.models.user import User
from app.models.token import TimeTreeToken
from app.schemas.user import UserResponse, TokenResponse
from app.services.auth_service import auth_service
from app.utils.idempotency import generate_idempotency_key

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/timetree/login")
async def timetree_login(
    request: Request,
    redirect_to: Optional[str] = Query(None, description="URL to redirect after successful auth")
) -> Dict[str, str]:
    """
    Start TimeTree OAuth flow.
    
    Args:
        request: FastAPI request object
        redirect_to: Optional URL to redirect after successful authentication
    
    Returns:
        Dict[str, str]: Authorization URL and state token
    """
    try:
        # Generate state token for CSRF protection
        state_token = security.generate_state_token()
        
        # Store state and redirect URL in session (or cache)
        # For now, we'll include it in the state parameter
        state_data = {
            "token": state_token,
            "redirect_to": redirect_to,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Create authorization URL
        auth_url = timetree_client.get_authorization_url(state=state_token)
        
        logger.info("TimeTree OAuth flow started",
                   client_ip=request.client.host,
                   user_agent=request.headers.get("user-agent"),
                   redirect_to=redirect_to)
        
        return {
            "authorization_url": auth_url,
            "state": state_token,
            "message": "TimeTree 로그인 페이지로 이동하세요."
        }
        
    except Exception as e:
        logger.error("Failed to start OAuth flow", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth 인증 시작에 실패했습니다."
        )


@router.get("/timetree/callback")
async def timetree_callback(
    request: Request,
    code: str = Query(..., description="Authorization code from TimeTree"),
    state: Optional[str] = Query(None, description="State parameter for CSRF protection"),
    error: Optional[str] = Query(None, description="OAuth error parameter"),
    db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    """
    Handle TimeTree OAuth callback.
    
    Args:
        request: FastAPI request object
        code: Authorization code from TimeTree
        state: State parameter for CSRF verification
        error: OAuth error if authorization failed
        db: Database session
    
    Returns:
        RedirectResponse: Redirect to frontend with success/error parameters
    """
    try:
        # Handle OAuth errors
        if error:
            logger.warning("OAuth authorization failed",
                         error=error,
                         client_ip=request.client.host)
            
            error_params = urlencode({
                "error": "authorization_failed",
                "message": f"TimeTree 인증이 거부되었습니다: {error}"
            })
            return RedirectResponse(
                url=f"http://localhost:3000/auth/callback?{error_params}",
                status_code=302
            )
        
        # Verify state parameter (basic verification)
        if not state:
            logger.error("Missing state parameter in OAuth callback")
            error_params = urlencode({
                "error": "invalid_state",
                "message": "잘못된 인증 요청입니다."
            })
            return RedirectResponse(
                url=f"http://localhost:3000/auth/callback?{error_params}",
                status_code=302
            )
        
        # Exchange code for access token
        try:
            token_response = await timetree_client.exchange_code_for_token(code, state)
        except TimeTreeAPIError as e:
            logger.error("Failed to exchange code for token",
                        error=str(e),
                        status_code=e.status_code)
            
            error_params = urlencode({
                "error": "token_exchange_failed",
                "message": "토큰 교환에 실패했습니다."
            })
            return RedirectResponse(
                url=f"http://localhost:3000/auth/callback?{error_params}",
                status_code=302
            )
        
        # Get user information from TimeTree
        access_token = token_response["access_token"]
        try:
            timetree_user = await timetree_client.get_current_user(access_token)
        except TimeTreeAPIError as e:
            logger.error("Failed to get user information",
                        error=str(e),
                        status_code=e.status_code)
            
            error_params = urlencode({
                "error": "user_info_failed",
                "message": "사용자 정보 조회에 실패했습니다."
            })
            return RedirectResponse(
                url=f"http://localhost:3000/auth/callback?{error_params}",
                status_code=302
            )
        
        # Create or update user in database
        user = await auth_service.get_or_create_user_from_timetree(
            db=db,
            timetree_user=timetree_user,
            token_data=token_response
        )
        
        # Generate JWT tokens
        token_pair = token_manager.create_token_pair(
            user_id=str(user.id),
            additional_claims={
                "email": user.email,
                "name": user.name,
                "timetree_user_id": user.timetree_user_id
            }
        )
        
        logger.info("User successfully authenticated",
                   user_id=user.id,
                   email=user.email,
                   timetree_user_id=user.timetree_user_id)
        
        # Prepare success redirect with tokens
        success_params = urlencode({
            "success": "true",
            "access_token": token_pair["access_token"],
            "refresh_token": token_pair["refresh_token"],
            "user_id": str(user.id),
            "message": "로그인이 완료되었습니다."
        })
        
        return RedirectResponse(
            url=f"http://localhost:3000/auth/callback?{success_params}",
            status_code=302
        )
        
    except Exception as e:
        logger.error("OAuth callback processing failed",
                    error=str(e),
                    client_ip=request.client.host)
        
        error_params = urlencode({
            "error": "internal_error",
            "message": "인증 처리 중 오류가 발생했습니다."
        })
        return RedirectResponse(
            url=f"http://localhost:3000/auth/callback?{error_params}",
            status_code=302
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """
    Refresh access token using refresh token.
    
    Args:
        refresh_token: Valid refresh token
        db: Database session
    
    Returns:
        TokenResponse: New token pair
    """
    try:
        # Verify refresh token
        payload = security.verify_token(refresh_token, "refresh")
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="유효하지 않은 리프레시 토큰입니다."
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="토큰에서 사용자 정보를 찾을 수 없습니다."
            )
        
        # Verify user exists
        user = await auth_service.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="사용자를 찾을 수 없습니다."
            )
        
        # Generate new token pair
        new_token_pair = token_manager.create_token_pair(
            user_id=user_id,
            additional_claims={
                "email": user.email,
                "name": user.name,
                "timetree_user_id": user.timetree_user_id
            }
        )
        
        logger.info("Token refreshed successfully", user_id=user_id)
        
        return TokenResponse(**new_token_pair)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Token refresh failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="토큰 갱신에 실패했습니다."
        )


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(auth_service.get_current_user)
) -> Dict[str, str]:
    """
    Logout user and invalidate tokens.
    
    Args:
        request: FastAPI request object
        current_user: Current authenticated user
    
    Returns:
        Dict[str, str]: Logout confirmation message
    """
    try:
        # In a production system, you might want to:
        # 1. Add tokens to a blacklist
        # 2. Clear server-side sessions
        # 3. Revoke TimeTree tokens if needed
        
        logger.info("User logged out",
                   user_id=current_user.id,
                   email=current_user.email,
                   client_ip=request.client.host)
        
        return {
            "message": "로그아웃이 완료되었습니다.",
            "status": "success"
        }
        
    except Exception as e:
        logger.error("Logout failed", 
                    user_id=current_user.id,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="로그아웃 처리에 실패했습니다."
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(auth_service.get_current_user)
) -> UserResponse:
    """
    Get current user information.
    
    Args:
        current_user: Current authenticated user
    
    Returns:
        UserResponse: User information
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        timetree_user_id=current_user.timetree_user_id,
        avatar_url=current_user.avatar_url,
        timezone=current_user.timezone,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        last_login_at=current_user.last_login_at
    )


@router.delete("/me")
async def delete_user_account(
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Delete user account and all associated data.
    
    Args:
        current_user: Current authenticated user
        db: Database session
    
    Returns:
        Dict[str, str]: Deletion confirmation message
    """
    try:
        # Delete user and cascade related data
        await auth_service.delete_user(db, current_user.id)
        
        logger.info("User account deleted",
                   user_id=current_user.id,
                   email=current_user.email)
        
        return {
            "message": "계정이 완전히 삭제되었습니다.",
            "status": "success"
        }
        
    except Exception as e:
        logger.error("Account deletion failed",
                    user_id=current_user.id,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="계정 삭제에 실패했습니다."
        )
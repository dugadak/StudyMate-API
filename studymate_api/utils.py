"""
Utility functions for StudyMate API

This module provides common utility functions used across the application.
"""

from typing import Optional, Any, Dict
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
import hashlib
import secrets


class StandardResponse:
    """표준화된 API 응답 형식을 제공하는 클래스"""
    
    @staticmethod
    def success(data: Any = None, message: str = "Success", status_code: int = status.HTTP_200_OK) -> Response:
        """
        성공 응답 생성
        
        Args:
            data: 응답 데이터
            message: 성공 메시지
            status_code: HTTP 상태 코드
            
        Returns:
            Response: 표준화된 성공 응답
        """
        return Response({
            'success': True,
            'message': message,
            'data': data,
            'timestamp': timezone.now().isoformat()
        }, status=status_code)
    
    @staticmethod
    def error(message: str = "Error occurred", errors: Any = None, status_code: int = status.HTTP_400_BAD_REQUEST) -> Response:
        """
        에러 응답 생성
        
        Args:
            message: 에러 메시지
            errors: 상세 에러 정보
            status_code: HTTP 상태 코드
            
        Returns:
            Response: 표준화된 에러 응답
        """
        return Response({
            'success': False,
            'message': message,
            'errors': errors,
            'timestamp': timezone.now().isoformat()
        }, status=status_code)
    
    @staticmethod
    def paginated(data: Any, count: int, page: int, total_pages: int, message: str = "Success") -> Response:
        """
        페이지네이션된 응답 생성
        
        Args:
            data: 응답 데이터
            count: 전체 항목 수
            page: 현재 페이지
            total_pages: 전체 페이지 수
            message: 성공 메시지
            
        Returns:
            Response: 표준화된 페이지네이션 응답
        """
        return Response({
            'success': True,
            'message': message,
            'data': data,
            'pagination': {
                'count': count,
                'current_page': page,
                'total_pages': total_pages
            },
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_200_OK)


class OptimizedPageNumberPagination(PageNumberPagination):
    """최적화된 페이지네이션 클래스"""
    
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        """
        페이지네이션된 응답 반환
        
        Args:
            data: 페이지네이션된 데이터
            
        Returns:
            Response: 표준화된 페이지네이션 응답
        """
        return StandardResponse.paginated(
            data=data,
            count=self.page.paginator.count,
            page=self.page.number,
            total_pages=self.page.paginator.num_pages
        )


def get_client_ip(request) -> str:
    """
    요청에서 클라이언트 IP 주소 추출
    
    Args:
        request: Django request 객체
        
    Returns:
        str: 클라이언트 IP 주소
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # 프록시를 통한 경우 첫 번째 IP 반환
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        # 직접 연결인 경우
        ip = request.META.get('REMOTE_ADDR', '')
    
    return ip


def get_user_agent(request) -> str:
    """
    요청에서 User-Agent 추출
    
    Args:
        request: Django request 객체
        
    Returns:
        str: User-Agent 문자열
    """
    return request.META.get('HTTP_USER_AGENT', '')


def generate_cache_key(prefix: str, **kwargs) -> str:
    """
    캐시 키 생성
    
    Args:
        prefix: 캐시 키 접두사
        **kwargs: 캐시 키 생성에 사용할 매개변수
        
    Returns:
        str: 생성된 캐시 키
    """
    # 매개변수를 정렬하여 일관된 키 생성
    sorted_params = sorted(kwargs.items())
    param_str = '_'.join([f"{k}:{v}" for k, v in sorted_params if v is not None])
    
    if param_str:
        # 긴 키를 해시로 단축
        if len(param_str) > 200:
            param_hash = hashlib.md5(param_str.encode()).hexdigest()
            return f"{prefix}:{param_hash}"
        return f"{prefix}:{param_str}"
    
    return prefix


def generate_secure_token(length: int = 32) -> str:
    """
    보안 토큰 생성
    
    Args:
        length: 토큰 길이 (기본값: 32)
        
    Returns:
        str: 생성된 보안 토큰
    """
    return secrets.token_urlsafe(length)


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """
    사용자 입력 정제
    
    Args:
        text: 정제할 텍스트
        max_length: 최대 길이
        
    Returns:
        str: 정제된 텍스트
    """
    if not text:
        return ""
    
    # 길이 제한
    text = text[:max_length]
    
    # 제어 문자 제거
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
    
    # 앞뒤 공백 제거
    text = text.strip()
    
    return text


def calculate_reading_time(text: str, words_per_minute: int = 200) -> int:
    """
    텍스트 읽기 시간 계산 (분 단위)
    
    Args:
        text: 텍스트
        words_per_minute: 분당 읽기 속도
        
    Returns:
        int: 예상 읽기 시간 (분)
    """
    if not text:
        return 0
    
    # 한글과 영문을 구분하여 단어 수 계산
    # 한글은 공백 기준, 영문은 실제 단어 수
    import re
    
    # 한글 문자 수 (공백 제외)
    korean_chars = len(re.findall(r'[가-힣]', text))
    # 영문 단어 수
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    
    # 한글은 분당 400자, 영문은 분당 200단어로 계산
    korean_time = korean_chars / 400
    english_time = english_words / words_per_minute
    
    total_time = korean_time + english_time
    
    # 최소 1분
    return max(1, round(total_time))


class DataValidator:
    """데이터 검증 유틸리티 클래스"""
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """
        이메일 형식 검증
        
        Args:
            email: 검증할 이메일 주소
            
        Returns:
            bool: 유효한 이메일인지 여부
        """
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def is_valid_phone(phone: str) -> bool:
        """
        전화번호 형식 검증 (한국 전화번호)
        
        Args:
            phone: 검증할 전화번호
            
        Returns:
            bool: 유효한 전화번호인지 여부
        """
        import re
        # 한국 전화번호 패턴 (010-xxxx-xxxx, 01x-xxx-xxxx 등)
        pattern = r'^01[0-9]-?[0-9]{3,4}-?[0-9]{4}$'
        return bool(re.match(pattern, phone.replace(' ', '')))
    
    @staticmethod
    def is_safe_url(url: str, allowed_hosts: list = None) -> bool:
        """
        안전한 URL인지 검증
        
        Args:
            url: 검증할 URL
            allowed_hosts: 허용된 호스트 목록
            
        Returns:
            bool: 안전한 URL인지 여부
        """
        from urllib.parse import urlparse
        
        if not url:
            return False
        
        try:
            parsed = urlparse(url)
            
            # 상대 URL은 허용
            if not parsed.netloc:
                return True
            
            # 허용된 호스트 확인
            if allowed_hosts and parsed.netloc not in allowed_hosts:
                return False
            
            # 프로토콜 확인 (http, https만 허용)
            if parsed.scheme not in ('http', 'https', ''):
                return False
            
            return True
        except:
            return False
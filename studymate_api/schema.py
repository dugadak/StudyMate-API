"""
API 스키마 정의 및 문서화 개선

이 모듈은 다음을 제공합니다:
- 표준화된 API 응답 스키마
- 에러 응답 스키마 
- 예제 응답 데이터
- API 태그 및 그룹화
- 필드 설명 및 검증 규칙
"""

from drf_spectacular.utils import (
    extend_schema, extend_schema_view, extend_schema_serializer,
    OpenApiParameter, OpenApiExample, OpenApiResponse
)
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.plumbing import build_parameter_type
from rest_framework import serializers
from typing import Dict, Any, List, Optional
import json


# API 태그 정의
API_TAGS = {
    'auth': '인증/사용자 관리',
    'study': '학습 관리',
    'quiz': '퀴즈 시스템',
    'subscription': '구독 관리',
    'notifications': '알림 시스템',
    'admin': '관리자 기능',
    'monitoring': '모니터링'
}


# 표준 응답 스키마
class StandardResponseSerializer(serializers.Serializer):
    """표준 API 응답 스키마"""
    
    success = serializers.BooleanField(
        default=True,
        help_text="요청 성공 여부"
    )
    message = serializers.CharField(
        max_length=255,
        required=False,
        help_text="응답 메시지"
    )
    data = serializers.JSONField(
        required=False,
        help_text="응답 데이터"
    )
    timestamp = serializers.DateTimeField(
        help_text="응답 시간 (ISO 8601 형식)"
    )


class ErrorResponseSerializer(serializers.Serializer):
    """에러 응답 스키마"""
    
    error = serializers.BooleanField(
        default=True,
        help_text="에러 발생 여부"
    )
    error_id = serializers.CharField(
        max_length=36,
        help_text="에러 추적 ID (UUID)"
    )
    code = serializers.CharField(
        max_length=50,
        help_text="에러 코드"
    )
    message = serializers.CharField(
        max_length=255,
        help_text="에러 메시지"
    )
    details = serializers.JSONField(
        required=False,
        help_text="에러 상세 정보"
    )
    timestamp = serializers.DateTimeField(
        help_text="에러 발생 시간 (ISO 8601 형식)"
    )


class PaginatedResponseSerializer(serializers.Serializer):
    """페이지네이션 응답 스키마"""
    
    count = serializers.IntegerField(
        help_text="전체 항목 수"
    )
    next = serializers.URLField(
        required=False,
        allow_null=True,
        help_text="다음 페이지 URL"
    )
    previous = serializers.URLField(
        required=False,
        allow_null=True,
        help_text="이전 페이지 URL"
    )
    results = serializers.ListField(
        help_text="결과 데이터 배열"
    )


# 공통 파라미터 정의
COMMON_PARAMETERS = {
    'page': OpenApiParameter(
        name='page',
        type=OpenApiTypes.INT,
        location=OpenApiParameter.QUERY,
        description='페이지 번호 (1부터 시작)',
        required=False,
        example=1
    ),
    'page_size': OpenApiParameter(
        name='page_size',
        type=OpenApiTypes.INT,
        location=OpenApiParameter.QUERY,
        description='페이지당 항목 수 (최대 100)',
        required=False,
        example=20
    ),
    'search': OpenApiParameter(
        name='search',
        type=OpenApiTypes.STR,
        location=OpenApiParameter.QUERY,
        description='검색 키워드',
        required=False,
        example='파이썬'
    ),
    'ordering': OpenApiParameter(
        name='ordering',
        type=OpenApiTypes.STR,
        location=OpenApiParameter.QUERY,
        description='정렬 기준 (-를 붙이면 내림차순)',
        required=False,
        example='-created_at'
    ),
    'fields': OpenApiParameter(
        name='fields',
        type=OpenApiTypes.STR,
        location=OpenApiParameter.QUERY,
        description='반환할 필드 목록 (쉼표로 구분)',
        required=False,
        example='id,name,description'
    )
}


# 예제 응답 데이터
EXAMPLE_RESPONSES = {
    'success_response': OpenApiExample(
        '성공 응답',
        value={
            'success': True,
            'message': '요청이 성공적으로 처리되었습니다.',
            'data': {
                'id': 1,
                'name': '예제 데이터'
            },
            'timestamp': '2024-01-01T12:00:00Z'
        },
        status_codes=['200']
    ),
    
    'error_response': OpenApiExample(
        '에러 응답',
        value={
            'error': True,
            'error_id': '123e4567-e89b-12d3-a456-426614174000',
            'code': 'VALIDATION_ERROR',
            'message': '입력 데이터가 올바르지 않습니다.',
            'details': {
                'field_errors': {
                    'email': ['올바른 이메일 주소를 입력하세요.']
                }
            },
            'timestamp': '2024-01-01T12:00:00Z'
        },
        status_codes=['400']
    ),
    
    'paginated_response': OpenApiExample(
        '페이지네이션 응답',
        value={
            'count': 100,
            'next': 'https://api.studymate.com/items/?page=3',
            'previous': 'https://api.studymate.com/items/?page=1',
            'results': [
                {
                    'id': 1,
                    'name': '예제 항목 1'
                },
                {
                    'id': 2,
                    'name': '예제 항목 2'
                }
            ]
        },
        status_codes=['200']
    )
}


# 표준 응답 설정
STANDARD_RESPONSES = {
    200: OpenApiResponse(
        response=StandardResponseSerializer,
        description='요청 성공',
        examples=[EXAMPLE_RESPONSES['success_response']]
    ),
    400: OpenApiResponse(
        response=ErrorResponseSerializer,
        description='잘못된 요청',
        examples=[EXAMPLE_RESPONSES['error_response']]
    ),
    401: OpenApiResponse(
        response=ErrorResponseSerializer,
        description='인증 실패'
    ),
    403: OpenApiResponse(
        response=ErrorResponseSerializer,
        description='권한 부족'
    ),
    404: OpenApiResponse(
        response=ErrorResponseSerializer,
        description='리소스 없음'
    ),
    429: OpenApiResponse(
        response=ErrorResponseSerializer,
        description='요청 제한 초과'
    ),
    500: OpenApiResponse(
        response=ErrorResponseSerializer,
        description='서버 내부 오류'
    )
}


def get_paginated_response_schema(serializer_class):
    """페이지네이션된 응답 스키마 생성"""
    class PaginatedSerializer(PaginatedResponseSerializer):
        results = serializers.ListField(
            child=serializer_class(),
            help_text=f"{serializer_class.__name__} 배열"
        )
    
    return PaginatedSerializer


def get_standard_schema_operation(**kwargs):
    """표준 스키마 작업 설정"""
    default_responses = {**STANDARD_RESPONSES}
    
    if 'responses' in kwargs:
        default_responses.update(kwargs.pop('responses'))
    
    return extend_schema(
        responses=default_responses,
        **kwargs
    )


# 스키마 데코레이터 함수들
def auth_schema(**kwargs):
    """인증 관련 API 스키마"""
    return get_standard_schema_operation(
        tags=[API_TAGS['auth']],
        **kwargs
    )


def study_schema(**kwargs):
    """학습 관련 API 스키마"""
    return get_standard_schema_operation(
        tags=[API_TAGS['study']],
        **kwargs
    )


def quiz_schema(**kwargs):
    """퀴즈 관련 API 스키마"""
    return get_standard_schema_operation(
        tags=[API_TAGS['quiz']],
        **kwargs
    )


def subscription_schema(**kwargs):
    """구독 관련 API 스키마"""
    return get_standard_schema_operation(
        tags=[API_TAGS['subscription']],
        **kwargs
    )


def notification_schema(**kwargs):
    """알림 관련 API 스키마"""
    return get_standard_schema_operation(
        tags=[API_TAGS['notifications']],
        **kwargs
    )


def admin_schema(**kwargs):
    """관리자 관련 API 스키마"""
    return get_standard_schema_operation(
        tags=[API_TAGS['admin']],
        **kwargs
    )


def monitoring_schema(**kwargs):
    """모니터링 관련 API 스키마"""
    return get_standard_schema_operation(
        tags=[API_TAGS['monitoring']],
        **kwargs
    )


# API 예제 데이터
class APIExamples:
    """API 예제 데이터 모음"""
    
    # 사용자 인증 관련
    LOGIN_REQUEST = {
        'email': 'user@example.com',
        'password': 'password123'
    }
    
    LOGIN_RESPONSE = {
        'success': True,
        'message': '로그인이 성공적으로 완료되었습니다.',
        'data': {
            'access_token': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
            'refresh_token': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
            'user': {
                'id': 1,
                'email': 'user@example.com',
                'name': '홍길동'
            }
        },
        'timestamp': '2024-01-01T12:00:00Z'
    }
    
    # 과목 관련
    SUBJECT_LIST_RESPONSE = {
        'count': 50,
        'next': 'https://api.studymate.com/api/study/subjects/?page=2',
        'previous': None,
        'results': [
            {
                'id': 1,
                'name': '파이썬 프로그래밍',
                'description': '파이썬 기초부터 고급까지',
                'category': 'programming',
                'total_learners': 1245,
                'average_rating': 4.5,
                'is_active': True
            }
        ]
    }
    
    # 학습 요약 관련
    STUDY_SUMMARY_CREATE_REQUEST = {
        'subject_id': 1,
        'content_request': '파이썬의 기본 문법에 대해 설명해주세요',
        'difficulty_level': 'intermediate',
        'preferred_length': 'medium'
    }
    
    STUDY_SUMMARY_RESPONSE = {
        'success': True,
        'message': '학습 요약이 성공적으로 생성되었습니다.',
        'data': {
            'id': 123,
            'title': '파이썬 기본 문법',
            'content': '파이썬은 간결하고 읽기 쉬운 프로그래밍 언어입니다...',
            'difficulty_level': 'intermediate',
            'estimated_reading_time': 5,
            'generated_at': '2024-01-01T12:00:00Z'
        },
        'timestamp': '2024-01-01T12:00:00Z'
    }
    
    # 퀴즈 관련
    QUIZ_ATTEMPT_REQUEST = {
        'quiz_id': 1,
        'answers': [
            {'question_id': 1, 'selected_answer': 'A'},
            {'question_id': 2, 'selected_answer': 'C'}
        ]
    }
    
    QUIZ_RESULT_RESPONSE = {
        'success': True,
        'message': '퀴즈가 성공적으로 제출되었습니다.',
        'data': {
            'attempt_id': 456,
            'score': 85,
            'total_questions': 10,
            'correct_answers': 8,
            'completion_time': 240,
            'passed': True
        },
        'timestamp': '2024-01-01T12:00:00Z'
    }
    
    # 에러 응답
    VALIDATION_ERROR = {
        'error': True,
        'error_id': '123e4567-e89b-12d3-a456-426614174000',
        'code': 'VALIDATION_ERROR',
        'message': '입력 데이터가 올바르지 않습니다.',
        'details': {
            'field_errors': {
                'email': ['올바른 이메일 주소를 입력하세요.'],
                'password': ['비밀번호는 최소 8자 이상이어야 합니다.']
            }
        },
        'timestamp': '2024-01-01T12:00:00Z'
    }
    
    AUTHENTICATION_ERROR = {
        'error': True,
        'error_id': '123e4567-e89b-12d3-a456-426614174001',
        'code': 'AUTHENTICATION_ERROR',
        'message': '인증이 필요합니다.',
        'details': {},
        'timestamp': '2024-01-01T12:00:00Z'
    }
    
    RATE_LIMIT_ERROR = {
        'error': True,
        'error_id': '123e4567-e89b-12d3-a456-426614174002',
        'code': 'RATE_LIMIT_EXCEEDED',
        'message': '요청 제한을 초과했습니다.',
        'details': {
            'retry_after': 3600
        },
        'timestamp': '2024-01-01T12:00:00Z'
    }


# 스키마 설정 클래스
class SchemaConfig:
    """API 스키마 설정"""
    
    TITLE = 'StudyMate API'
    DESCRIPTION = '''
StudyMate API는 AI 기반 학습 플랫폼을 위한 RESTful API입니다.

## 기능

- **사용자 관리**: 회원가입, 로그인, 프로필 관리
- **학습 관리**: AI 기반 학습 요약 생성 및 관리
- **퀴즈 시스템**: 동적 퀴즈 생성 및 평가
- **구독 관리**: Stripe 기반 구독 및 결제 관리
- **알림 시스템**: 개인화된 학습 알림

## 인증

API는 JWT (JSON Web Token) 기반 인증을 사용합니다.

```
Authorization: Bearer <your-access-token>
```

## 응답 형식

모든 API 응답은 표준화된 JSON 형식을 따릅니다:

```json
{
  "success": true,
  "message": "요청이 성공적으로 처리되었습니다.",
  "data": {},
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 에러 처리

에러 발생 시 다음 형식으로 응답합니다:

```json
{
  "error": true,
  "error_id": "uuid",
  "code": "ERROR_CODE",
  "message": "에러 메시지",
  "details": {},
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 제한사항

- API 호출은 사용자별로 시간당 1000회로 제한됩니다
- AI 생성 요청은 시간당 20회로 제한됩니다
- 대용량 요청은 비동기로 처리됩니다
    '''
    
    VERSION = '1.0.0'
    CONTACT = {
        'name': 'StudyMate API 지원팀',
        'email': 'support@studymate.com'
    }
    SERVERS = [
        {
            'url': 'https://api.studymate.com',
            'description': '운영 서버'
        },
        {
            'url': 'https://staging-api.studymate.com',
            'description': '스테이징 서버'
        },
        {
            'url': 'http://localhost:8000',
            'description': '개발 서버'
        }
    ]


# 내보낼 주요 구성 요소
__all__ = [
    'StandardResponseSerializer',
    'ErrorResponseSerializer',
    'PaginatedResponseSerializer',
    'API_TAGS',
    'COMMON_PARAMETERS',
    'EXAMPLE_RESPONSES',
    'STANDARD_RESPONSES',
    'get_paginated_response_schema',
    'get_standard_schema_operation',
    'auth_schema',
    'study_schema',
    'quiz_schema',
    'subscription_schema',
    'notification_schema',
    'admin_schema',
    'monitoring_schema',
    'APIExamples',
    'SchemaConfig'
]
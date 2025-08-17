"""
API 스키마 후처리 및 전처리 훅

이 모듈은 drf-spectacular 스키마 생성 과정에서
사용되는 커스텀 훅을 제공합니다.
"""

from typing import Dict, Any, List
import re


def postprocess_schema_enums(result: Dict[str, Any], generator, request, public: bool) -> Dict[str, Any]:
    """
    스키마의 Enum 값들을 후처리합니다.
    
    - 한국어 설명 추가
    - 값 정규화
    - 예제 값 추가
    """
    
    # Enum 값 매핑
    enum_descriptions = {
        'DifficultyLevelEnum': {
            'beginner': '초급 - 기초 개념 학습',
            'intermediate': '중급 - 실무 활용 학습', 
            'advanced': '고급 - 심화 개념 학습',
            'expert': '전문가 - 최고 수준 학습'
        },
        'CategoryEnum': {
            'programming': '프로그래밍 - 개발 언어 및 프레임워크',
            'data_science': '데이터 사이언스 - 분석 및 머신러닝',
            'design': '디자인 - UI/UX 및 그래픽 디자인',
            'business': '비즈니스 - 경영 및 마케팅',
            'language': '어학 - 외국어 학습',
            'science': '과학 - 자연과학 및 공학',
            'humanities': '인문학 - 철학, 역사, 문학'
        },
        'ContentTypeEnum': {
            'summary': '요약 - 핵심 내용 정리',
            'explanation': '설명 - 상세한 개념 해설',
            'example': '예제 - 실습 중심 학습',
            'quiz': '퀴즈 - 이해도 확인'
        },
        'SubscriptionStatusEnum': {
            'active': '활성 - 정상 이용 중',
            'inactive': '비활성 - 이용 정지',
            'trial': '체험 - 무료 체험 중',
            'expired': '만료 - 구독 기간 종료',
            'cancelled': '취소 - 사용자 취소'
        },
        'PaymentMethodEnum': {
            'card': '카드 - 신용/체크카드',
            'bank_transfer': '계좌이체 - 무통장 입금',
            'paypal': '페이팔 - PayPal 결제',
            'apple_pay': '애플페이 - Apple Pay',
            'google_pay': '구글페이 - Google Pay'
        }
    }
    
    # 컴포넌트 스키마에서 Enum 처리
    if 'components' in result and 'schemas' in result['components']:
        for schema_name, schema_data in result['components']['schemas'].items():
            if schema_name.endswith('Enum') and schema_name in enum_descriptions:
                descriptions = enum_descriptions[schema_name]
                
                # enum 값에 설명 추가
                if 'enum' in schema_data:
                    schema_data['description'] = f"선택 가능한 값:\n" + "\n".join([
                        f"- `{value}`: {descriptions.get(value, value)}"
                        for value in schema_data['enum']
                    ])
                
                # 예제 값 추가
                if schema_data['enum']:
                    schema_data['example'] = schema_data['enum'][0]
    
    return result


def preprocess_exclude_paths(endpoints, method, **kwargs) -> List:
    """
    특정 경로를 스키마에서 제외합니다.
    
    - 관리자 전용 경로
    - 내부 API 경로
    - 디버깅 경로
    """
    
    excluded_patterns = [
        r'^/admin/',           # Django 관리자
        r'^/silk/',            # Silk 프로파일러
        r'^/__debug__/',       # Debug Toolbar
        r'^/internal/',        # 내부 API
        r'^/test/',            # 테스트 경로
    ]
    
    filtered_endpoints = []
    
    for (path, method, callback) in endpoints:
        # 제외 패턴 확인
        should_exclude = any(
            re.match(pattern, path) 
            for pattern in excluded_patterns
        )
        
        if not should_exclude:
            filtered_endpoints.append((path, method, callback))
    
    return filtered_endpoints


def postprocess_schema_paths(result: Dict[str, Any], generator, request, public: bool) -> Dict[str, Any]:
    """
    스키마의 경로들을 후처리합니다.
    
    - 한국어 태그 적용
    - 공통 파라미터 추가
    - 응답 예제 개선
    """
    
    # 태그 한국어 매핑
    tag_mapping = {
        'auth': '인증/사용자 관리',
        'study': '학습 관리', 
        'quiz': '퀴즈 시스템',
        'subscription': '구독 관리',
        'notifications': '알림 시스템',
        'admin': '관리자 기능',
        'monitoring': '모니터링'
    }
    
    if 'paths' in result:
        for path, methods in result['paths'].items():
            for method, operation in methods.items():
                # 태그 한국어화
                if 'tags' in operation:
                    operation['tags'] = [
                        tag_mapping.get(tag, tag) 
                        for tag in operation['tags']
                    ]
                
                # 공통 에러 응답 추가
                if 'responses' in operation:
                    # 기본 에러 응답이 없으면 추가
                    error_responses = {
                        '400': {
                            'description': '잘못된 요청',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/ErrorResponse'}
                                }
                            }
                        },
                        '401': {
                            'description': '인증 필요',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/ErrorResponse'}
                                }
                            }
                        },
                        '403': {
                            'description': '권한 부족',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/ErrorResponse'}
                                }
                            }
                        },
                        '429': {
                            'description': '요청 제한 초과',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/ErrorResponse'}
                                }
                            }
                        },
                        '500': {
                            'description': '서버 내부 오류',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/ErrorResponse'}
                                }
                            }
                        }
                    }
                    
                    for code, response in error_responses.items():
                        if code not in operation['responses']:
                            operation['responses'][code] = response
    
    return result


def add_security_schemes(result: Dict[str, Any], generator, request, public: bool) -> Dict[str, Any]:
    """
    보안 스키마를 추가합니다.
    
    - JWT Bearer 토큰
    - API 키 (필요한 경우)
    """
    
    if 'components' not in result:
        result['components'] = {}
    
    if 'securitySchemes' not in result['components']:
        result['components']['securitySchemes'] = {}
    
    # JWT Bearer 토큰 스키마
    result['components']['securitySchemes']['bearerAuth'] = {
        'type': 'http',
        'scheme': 'bearer',
        'bearerFormat': 'JWT',
        'description': 'JWT 액세스 토큰을 사용한 인증'
    }
    
    # API 키 스키마 (필요한 경우)
    result['components']['securitySchemes']['apiKey'] = {
        'type': 'apiKey',
        'in': 'header',
        'name': 'X-API-Key',
        'description': 'API 키를 사용한 인증 (특별한 경우에만 사용)'
    }
    
    # 전역 보안 요구사항 설정
    if 'security' not in result:
        result['security'] = [
            {'bearerAuth': []}
        ]
    
    return result


def add_common_examples(result: Dict[str, Any], generator, request, public: bool) -> Dict[str, Any]:
    """
    공통 예제들을 추가합니다.
    
    - 표준 응답 예제
    - 에러 응답 예제
    - 페이지네이션 예제
    """
    
    if 'components' not in result:
        result['components'] = {}
    
    if 'examples' not in result['components']:
        result['components']['examples'] = {}
    
    # 성공 응답 예제
    result['components']['examples']['SuccessResponse'] = {
        'summary': '성공 응답',
        'value': {
            'success': True,
            'message': '요청이 성공적으로 처리되었습니다.',
            'data': {},
            'timestamp': '2024-01-01T12:00:00Z'
        }
    }
    
    # 에러 응답 예제들
    error_examples = {
        'ValidationError': {
            'summary': '유효성 검증 오류',
            'value': {
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
            }
        },
        'AuthenticationError': {
            'summary': '인증 오류',
            'value': {
                'error': True,
                'error_id': '123e4567-e89b-12d3-a456-426614174001',
                'code': 'AUTHENTICATION_ERROR',
                'message': '인증이 필요합니다.',
                'details': {},
                'timestamp': '2024-01-01T12:00:00Z'
            }
        },
        'PermissionError': {
            'summary': '권한 오류',
            'value': {
                'error': True,
                'error_id': '123e4567-e89b-12d3-a456-426614174002',
                'code': 'PERMISSION_ERROR',
                'message': '이 작업을 수행할 권한이 없습니다.',
                'details': {},
                'timestamp': '2024-01-01T12:00:00Z'
            }
        },
        'RateLimitError': {
            'summary': '요청 제한 오류',
            'value': {
                'error': True,
                'error_id': '123e4567-e89b-12d3-a456-426614174003',
                'code': 'RATE_LIMIT_EXCEEDED',
                'message': '요청 제한을 초과했습니다.',
                'details': {
                    'retry_after': 3600
                },
                'timestamp': '2024-01-01T12:00:00Z'
            }
        }
    }
    
    result['components']['examples'].update(error_examples)
    
    # 페이지네이션 예제
    result['components']['examples']['PaginatedResponse'] = {
        'summary': '페이지네이션 응답',
        'value': {
            'count': 100,
            'next': 'https://api.studymate.com/items/?page=3',
            'previous': 'https://api.studymate.com/items/?page=1',
            'results': []
        }
    }
    
    return result


# 내보낼 함수들
__all__ = [
    'postprocess_schema_enums',
    'preprocess_exclude_paths',
    'postprocess_schema_paths',
    'add_security_schemes',
    'add_common_examples'
]
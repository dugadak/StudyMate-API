"""
StudyMate API 타입 정의

공통적으로 사용되는 타입 힌트들을 정의합니다.
"""

from typing import Dict, List, Optional, Union, Any, Tuple, TypeVar, Generic
from typing_extensions import TypedDict, Literal, Protocol
from django.db import models
from django.http import HttpRequest, HttpResponse
from rest_framework.request import Request
from rest_framework.response import Response
from datetime import datetime, timedelta
from decimal import Decimal

# Generic types
T = TypeVar('T')
ModelType = TypeVar('ModelType', bound=models.Model)

# HTTP types
HTTPMethod = Literal['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
StatusCode = Literal[200, 201, 400, 401, 403, 404, 409, 422, 429, 500, 502, 503]

# API Response types
class APIResponseData(TypedDict, total=False):
    """표준 API 응답 데이터 구조"""
    success: bool
    message: str
    data: Dict[str, Any]
    errors: List[str]
    timestamp: str
    request_id: str

class ErrorDetail(TypedDict):
    """에러 상세 정보"""
    code: str
    message: str
    field: Optional[str]
    details: Optional[Dict[str, Any]]

class PaginationInfo(TypedDict):
    """페이지네이션 정보"""
    count: int
    next: Optional[str]
    previous: Optional[str]
    page_size: int
    current_page: int
    total_pages: int

class PaginatedResponse(TypedDict):
    """페이지네이션된 응답"""
    results: List[Dict[str, Any]]
    pagination: PaginationInfo

# User related types
class UserInfo(TypedDict):
    """사용자 기본 정보"""
    id: int
    email: str
    username: str
    is_active: bool
    is_verified: bool

class LoginCredentials(TypedDict):
    """로그인 자격증명"""
    email: str
    password: str

class TokenPair(TypedDict):
    """JWT 토큰 쌍"""
    access: str
    refresh: str

# Study related types
StudyType = Literal['summary', 'quiz', 'flashcard', 'mindmap']
DifficultyLevel = Literal['beginner', 'intermediate', 'advanced']
ContentType = Literal['text', 'pdf', 'image', 'video', 'audio']

class StudyContent(TypedDict):
    """학습 콘텐츠"""
    title: str
    content: str
    content_type: ContentType
    difficulty: DifficultyLevel
    tags: List[str]
    metadata: Dict[str, Any]

class StudySummary(TypedDict):
    """학습 요약"""
    main_points: List[str]
    key_concepts: List[str]
    summary_text: str
    estimated_reading_time: int

# Quiz related types
QuestionType = Literal['multiple_choice', 'true_false', 'short_answer', 'essay']

class QuizQuestion(TypedDict):
    """퀴즈 질문"""
    id: int
    question: str
    question_type: QuestionType
    options: Optional[List[str]]
    correct_answer: str
    explanation: str
    difficulty: DifficultyLevel
    points: int

class QuizResult(TypedDict):
    """퀴즈 결과"""
    score: int
    total_points: int
    percentage: float
    correct_answers: int
    total_questions: int
    time_taken: timedelta
    passed: bool

# Subscription related types
SubscriptionStatus = Literal['active', 'inactive', 'cancelled', 'expired', 'trial']
PlanType = Literal['free', 'basic', 'premium', 'enterprise']

class SubscriptionInfo(TypedDict):
    """구독 정보"""
    id: int
    plan_type: PlanType
    status: SubscriptionStatus
    started_at: datetime
    expires_at: Optional[datetime]
    auto_renewal: bool

class PaymentInfo(TypedDict):
    """결제 정보"""
    amount: Decimal
    currency: str
    payment_method: str
    status: str
    transaction_id: str

# Notification types
NotificationType = Literal['info', 'warning', 'error', 'success']
NotificationChannel = Literal['email', 'push', 'sms', 'in_app']

class NotificationData(TypedDict):
    """알림 데이터"""
    title: str
    message: str
    notification_type: NotificationType
    channel: NotificationChannel
    metadata: Dict[str, Any]

# Cache related types
CacheKey = str
CacheValue = Union[str, int, float, bool, Dict[str, Any], List[Any]]
CacheTTL = int  # seconds

# Security types
class SecurityEvent(TypedDict):
    """보안 이벤트"""
    event_type: str
    severity: Literal['low', 'medium', 'high', 'critical']
    user_id: Optional[int]
    ip_address: str
    user_agent: str
    timestamp: datetime
    details: Dict[str, Any]

# Performance types
class PerformanceMetric(TypedDict):
    """성능 메트릭"""
    operation: str
    duration_ms: float
    query_count: int
    memory_usage: Optional[int]
    cpu_usage: Optional[float]
    timestamp: datetime

# File upload types
FileType = Literal['image', 'pdf', 'document', 'video', 'audio']

class FileInfo(TypedDict):
    """파일 정보"""
    filename: str
    size: int
    content_type: str
    file_type: FileType
    url: str
    uploaded_at: datetime

# AI Service types
AIProvider = Literal['openai', 'anthropic', 'together']

class AIRequest(TypedDict):
    """AI 서비스 요청"""
    provider: AIProvider
    model: str
    prompt: str
    max_tokens: Optional[int]
    temperature: Optional[float]
    metadata: Dict[str, Any]

class AIResponse(TypedDict):
    """AI 서비스 응답"""
    content: str
    usage: Dict[str, int]
    model: str
    provider: AIProvider
    response_time: float

# Database types
class DatabaseConfig(TypedDict):
    """데이터베이스 설정"""
    ENGINE: str
    NAME: str
    USER: str
    PASSWORD: str
    HOST: str
    PORT: int
    OPTIONS: Dict[str, Any]

# Settings types
class CacheConfig(TypedDict):
    """캐시 설정"""
    BACKEND: str
    LOCATION: str
    TIMEOUT: int
    OPTIONS: Dict[str, Any]

# Protocol classes for duck typing
class Serializable(Protocol):
    """직렬화 가능한 객체 프로토콜"""
    def to_dict(self) -> Dict[str, Any]: ...

class Cacheable(Protocol):
    """캐시 가능한 객체 프로토콜"""
    def get_cache_key(self) -> str: ...
    def get_cache_ttl(self) -> int: ...

class Loggable(Protocol):
    """로그 가능한 객체 프로토콜"""
    def get_log_data(self) -> Dict[str, Any]: ...

# Custom Generic Classes
class ServiceResult(Generic[T]):
    """서비스 결과를 나타내는 제네릭 클래스"""
    
    def __init__(self, success: bool, data: Optional[T] = None, 
                 error: Optional[str] = None, errors: Optional[List[str]] = None):
        self.success = success
        self.data = data
        self.error = error
        self.errors = errors or []
    
    @property
    def is_success(self) -> bool:
        return self.success
    
    @property
    def is_error(self) -> bool:
        return not self.success

class CacheManager(Generic[T]):
    """캐시 매니저 제네릭 클래스"""
    
    def get(self, key: CacheKey) -> Optional[T]: ...
    def set(self, key: CacheKey, value: T, timeout: CacheTTL) -> bool: ...
    def delete(self, key: CacheKey) -> bool: ...

# Function type aliases
RequestHandler = callable[[Request], Response]
ViewFunction = callable[[HttpRequest], HttpResponse]
Validator = callable[[Any], bool]
Transformer = callable[[T], T]

# Utility types
JSONData = Dict[str, Any]
QueryParams = Dict[str, Union[str, List[str]]]
Headers = Dict[str, str]
Cookies = Dict[str, str]

# Export all types
__all__ = [
    # Generic types
    'T', 'ModelType',
    
    # HTTP types
    'HTTPMethod', 'StatusCode',
    
    # API types
    'APIResponseData', 'ErrorDetail', 'PaginationInfo', 'PaginatedResponse',
    
    # User types
    'UserInfo', 'LoginCredentials', 'TokenPair',
    
    # Study types
    'StudyType', 'DifficultyLevel', 'ContentType', 'StudyContent', 'StudySummary',
    
    # Quiz types
    'QuestionType', 'QuizQuestion', 'QuizResult',
    
    # Subscription types
    'SubscriptionStatus', 'PlanType', 'SubscriptionInfo', 'PaymentInfo',
    
    # Notification types
    'NotificationType', 'NotificationChannel', 'NotificationData',
    
    # Cache types
    'CacheKey', 'CacheValue', 'CacheTTL',
    
    # Security types
    'SecurityEvent',
    
    # Performance types
    'PerformanceMetric',
    
    # File types
    'FileType', 'FileInfo',
    
    # AI types
    'AIProvider', 'AIRequest', 'AIResponse',
    
    # Config types
    'DatabaseConfig', 'CacheConfig',
    
    # Protocol types
    'Serializable', 'Cacheable', 'Loggable',
    
    # Generic classes
    'ServiceResult', 'CacheManager',
    
    # Function types
    'RequestHandler', 'ViewFunction', 'Validator', 'Transformer',
    
    # Utility types
    'JSONData', 'QueryParams', 'Headers', 'Cookies',
]
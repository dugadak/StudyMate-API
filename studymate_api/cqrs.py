"""
CQRS (Command Query Responsibility Segregation) 패턴 구현

명령과 조회를 분리하여 성능과 확장성을 향상시키는 아키텍처 패턴을 제공합니다.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic, Union
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from django.core.cache import cache
from django.db import transaction, models
from django.utils import timezone
from django.contrib.auth import get_user_model
import json
import uuid

from studymate_api.metrics import track_system_event, EventType

logger = logging.getLogger(__name__)
User = get_user_model()

T = TypeVar('T')
R = TypeVar('R')


class CommandStatus(Enum):
    """명령 실행 상태"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QueryType(Enum):
    """조회 타입"""
    REAL_TIME = "real_time"      # 실시간 조회
    CACHED = "cached"            # 캐시된 조회
    MATERIALIZED = "materialized" # 구체화된 뷰


@dataclass
class CommandResult:
    """명령 실행 결과"""
    command_id: str
    status: CommandStatus
    result: Any = None
    error_message: Optional[str] = None
    execution_time: float = 0.0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'command_id': self.command_id,
            'status': self.status.value,
            'result': self.result,
            'error_message': self.error_message,
            'execution_time': self.execution_time,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class QueryResult(Generic[T]):
    """조회 결과"""
    query_id: str
    query_type: QueryType
    data: T
    cache_hit: bool = False
    execution_time: float = 0.0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()


# 기본 명령 인터페이스
class Command(ABC):
    """명령 기본 인터페이스"""
    
    def __init__(self, user_id: Optional[int] = None):
        self.command_id = str(uuid.uuid4())
        self.user_id = user_id
        self.timestamp = timezone.now()
    
    @abstractmethod
    def validate(self) -> bool:
        """명령 유효성 검사"""
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """명령을 딕셔너리로 변환"""
        return {
            'command_id': self.command_id,
            'command_type': self.__class__.__name__,
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat(),
            'data': self._get_data()
        }
    
    @abstractmethod
    def _get_data(self) -> Dict[str, Any]:
        """명령 데이터 반환"""
        pass


# 기본 조회 인터페이스
class Query(ABC, Generic[T]):
    """조회 기본 인터페이스"""
    
    def __init__(self, user_id: Optional[int] = None, use_cache: bool = True):
        self.query_id = str(uuid.uuid4())
        self.user_id = user_id
        self.use_cache = use_cache
        self.timestamp = timezone.now()
    
    @abstractmethod
    def get_cache_key(self) -> str:
        """캐시 키 생성"""
        pass
    
    @abstractmethod
    def get_cache_timeout(self) -> int:
        """캐시 만료 시간 (초)"""
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """조회를 딕셔너리로 변환"""
        return {
            'query_id': self.query_id,
            'query_type': self.__class__.__name__,
            'user_id': self.user_id,
            'use_cache': self.use_cache,
            'timestamp': self.timestamp.isoformat()
        }


# 명령 핸들러 인터페이스
class CommandHandler(ABC, Generic[T]):
    """명령 핸들러 기본 인터페이스"""
    
    @abstractmethod
    def handle(self, command: T) -> CommandResult:
        """명령 처리"""
        pass


# 조회 핸들러 인터페이스
class QueryHandler(ABC, Generic[T, R]):
    """조회 핸들러 기본 인터페이스"""
    
    @abstractmethod
    def handle(self, query: T) -> QueryResult[R]:
        """조회 처리"""
        pass


class CommandBus:
    """명령 버스 - 명령을 적절한 핸들러로 라우팅"""
    
    def __init__(self):
        self._handlers: Dict[Type[Command], CommandHandler] = {}
        self._middleware: List[callable] = []
    
    def register_handler(self, command_type: Type[Command], handler: CommandHandler):
        """명령 핸들러 등록"""
        self._handlers[command_type] = handler
        logger.info(f"Command handler registered: {command_type.__name__} -> {handler.__class__.__name__}")
    
    def add_middleware(self, middleware: callable):
        """미들웨어 추가"""
        self._middleware.append(middleware)
    
    def dispatch(self, command: Command) -> CommandResult:
        """명령 실행"""
        if not command.validate():
            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.FAILED,
                error_message="Command validation failed"
            )
        
        command_type = type(command)
        if command_type not in self._handlers:
            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.FAILED,
                error_message=f"No handler registered for {command_type.__name__}"
            )
        
        handler = self._handlers[command_type]
        
        try:
            start_time = timezone.now()
            
            # 미들웨어 실행
            for middleware in self._middleware:
                middleware(command)
            
            # 명령 실행
            result = handler.handle(command)
            
            # 실행 시간 계산
            execution_time = (timezone.now() - start_time).total_seconds()
            result.execution_time = execution_time
            
            # 메트릭 추적
            track_system_event(EventType.API_REQUEST, {
                'command_type': command_type.__name__,
                'status': result.status.value,
                'execution_time': execution_time
            })
            
            logger.info(f"Command executed: {command_type.__name__} [{result.status.value}] in {execution_time:.3f}s")
            
            return result
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Command execution failed: {command_type.__name__} - {error_message}")
            
            track_system_event(EventType.API_ERROR, {
                'command_type': command_type.__name__,
                'error_message': error_message
            })
            
            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.FAILED,
                error_message=error_message
            )


class QueryBus:
    """조회 버스 - 조회를 적절한 핸들러로 라우팅"""
    
    def __init__(self):
        self._handlers: Dict[Type[Query], QueryHandler] = {}
        self._middleware: List[callable] = []
    
    def register_handler(self, query_type: Type[Query], handler: QueryHandler):
        """조회 핸들러 등록"""
        self._handlers[query_type] = handler
        logger.info(f"Query handler registered: {query_type.__name__} -> {handler.__class__.__name__}")
    
    def add_middleware(self, middleware: callable):
        """미들웨어 추가"""
        self._middleware.append(middleware)
    
    def dispatch(self, query: Query[T]) -> QueryResult[T]:
        """조회 실행"""
        query_type = type(query)
        if query_type not in self._handlers:
            raise ValueError(f"No handler registered for {query_type.__name__}")
        
        handler = self._handlers[query_type]
        
        try:
            start_time = timezone.now()
            cache_hit = False
            
            # 캐시 확인
            if query.use_cache:
                cache_key = query.get_cache_key()
                cached_result = cache.get(cache_key)
                
                if cached_result is not None:
                    cache_hit = True
                    execution_time = (timezone.now() - start_time).total_seconds()
                    
                    # 캐시 히트 메트릭
                    track_system_event(EventType.CACHE_HIT, {
                        'query_type': query_type.__name__,
                        'cache_key': cache_key[:50]  # 키 길이 제한
                    })
                    
                    return QueryResult(
                        query_id=query.query_id,
                        query_type=QueryType.CACHED,
                        data=cached_result,
                        cache_hit=True,
                        execution_time=execution_time
                    )
                else:
                    # 캐시 미스 메트릭
                    track_system_event(EventType.CACHE_MISS, {
                        'query_type': query_type.__name__,
                        'cache_key': cache_key[:50]
                    })
            
            # 미들웨어 실행
            for middleware in self._middleware:
                middleware(query)
            
            # 조회 실행
            result = handler.handle(query)
            
            # 실행 시간 계산
            execution_time = (timezone.now() - start_time).total_seconds()
            result.execution_time = execution_time
            
            # 결과 캐시 저장
            if query.use_cache and not cache_hit:
                cache_key = query.get_cache_key()
                cache_timeout = query.get_cache_timeout()
                cache.set(cache_key, result.data, timeout=cache_timeout)
            
            # 메트릭 추적
            track_system_event(EventType.API_REQUEST, {
                'query_type': query_type.__name__,
                'cache_hit': cache_hit,
                'execution_time': execution_time
            })
            
            logger.info(f"Query executed: {query_type.__name__} [{'cache' if cache_hit else 'db'}] in {execution_time:.3f}s")
            
            return result
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Query execution failed: {query_type.__name__} - {error_message}")
            
            track_system_event(EventType.API_ERROR, {
                'query_type': query_type.__name__,
                'error_message': error_message
            })
            
            raise


# 이벤트 저장소 (Event Sourcing을 위한 기본 구조)
class Event:
    """도메인 이벤트"""
    
    def __init__(self, aggregate_id: str, event_type: str, data: Dict[str, Any], user_id: Optional[int] = None):
        self.event_id = str(uuid.uuid4())
        self.aggregate_id = aggregate_id
        self.event_type = event_type
        self.data = data
        self.user_id = user_id
        self.timestamp = timezone.now()
        self.version = 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_id': self.event_id,
            'aggregate_id': self.aggregate_id,
            'event_type': self.event_type,
            'data': self.data,
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat(),
            'version': self.version
        }


class EventStore:
    """이벤트 저장소"""
    
    def __init__(self):
        self.events: List[Event] = []
        self._snapshots: Dict[str, Any] = {}
    
    def append_event(self, event: Event):
        """이벤트 추가"""
        self.events.append(event)
        logger.debug(f"Event stored: {event.event_type} for {event.aggregate_id}")
    
    def get_events(self, aggregate_id: str, from_version: int = 1) -> List[Event]:
        """집계 ID에 대한 이벤트 조회"""
        return [
            event for event in self.events 
            if event.aggregate_id == aggregate_id and event.version >= from_version
        ]
    
    def save_snapshot(self, aggregate_id: str, snapshot: Any, version: int):
        """스냅샷 저장"""
        self._snapshots[aggregate_id] = {
            'data': snapshot,
            'version': version,
            'timestamp': timezone.now()
        }
    
    def get_snapshot(self, aggregate_id: str) -> Optional[Dict[str, Any]]:
        """스냅샷 조회"""
        return self._snapshots.get(aggregate_id)


# 글로벌 인스턴스
command_bus = CommandBus()
query_bus = QueryBus()
event_store = EventStore()


# 데코레이터들
def command_handler(command_type: Type[Command]):
    """명령 핸들러 등록 데코레이터"""
    def decorator(handler_class):
        handler_instance = handler_class()
        command_bus.register_handler(command_type, handler_instance)
        return handler_class
    return decorator


def query_handler(query_type: Type[Query]):
    """조회 핸들러 등록 데코레이터"""
    def decorator(handler_class):
        handler_instance = handler_class()
        query_bus.register_handler(query_type, handler_instance)
        return handler_class
    return decorator


# 미들웨어들
def logging_middleware(command_or_query: Union[Command, Query]):
    """로깅 미들웨어"""
    logger.debug(f"Processing: {command_or_query.__class__.__name__} - {command_or_query.to_dict()}")


def auth_middleware(command_or_query: Union[Command, Query]):
    """인증 미들웨어"""
    if hasattr(command_or_query, 'user_id') and command_or_query.user_id:
        try:
            user = User.objects.get(id=command_or_query.user_id)
            if not user.is_active:
                raise PermissionError(f"User {command_or_query.user_id} is not active")
        except User.DoesNotExist:
            raise PermissionError(f"User {command_or_query.user_id} does not exist")


def validation_middleware(command_or_query: Union[Command, Query]):
    """유효성 검사 미들웨어"""
    if isinstance(command_or_query, Command):
        if not command_or_query.validate():
            raise ValueError("Command validation failed")


# 미들웨어 등록
command_bus.add_middleware(logging_middleware)
command_bus.add_middleware(auth_middleware)
command_bus.add_middleware(validation_middleware)

query_bus.add_middleware(logging_middleware)
query_bus.add_middleware(auth_middleware)


# 유틸리티 함수들
def dispatch_command(command: Command) -> CommandResult:
    """명령 실행 편의 함수"""
    return command_bus.dispatch(command)


def dispatch_query(query: Query[T]) -> QueryResult[T]:
    """조회 실행 편의 함수"""
    return query_bus.dispatch(query)


class CQRSMixin:
    """CQRS 패턴을 위한 믹스인"""
    
    def dispatch_command(self, command: Command) -> CommandResult:
        """명령 실행"""
        return command_bus.dispatch(command)
    
    def dispatch_query(self, query: Query[T]) -> QueryResult[T]:
        """조회 실행"""
        return query_bus.dispatch(query)


# 성능 모니터링
class CQRSMetrics:
    """CQRS 메트릭 수집기"""
    
    @staticmethod
    def get_command_stats() -> Dict[str, Any]:
        """명령 통계"""
        # Redis에서 명령 통계 조회
        stats = {}
        for command_type in command_bus._handlers.keys():
            key = f"cqrs:command:{command_type.__name__}"
            stats[command_type.__name__] = {
                'total_count': cache.get(f"{key}:count", 0),
                'success_count': cache.get(f"{key}:success", 0),
                'failure_count': cache.get(f"{key}:failure", 0),
                'avg_execution_time': cache.get(f"{key}:avg_time", 0.0)
            }
        return stats
    
    @staticmethod
    def get_query_stats() -> Dict[str, Any]:
        """조회 통계"""
        stats = {}
        for query_type in query_bus._handlers.keys():
            key = f"cqrs:query:{query_type.__name__}"
            stats[query_type.__name__] = {
                'total_count': cache.get(f"{key}:count", 0),
                'cache_hit_count': cache.get(f"{key}:cache_hit", 0),
                'cache_miss_count': cache.get(f"{key}:cache_miss", 0),
                'avg_execution_time': cache.get(f"{key}:avg_time", 0.0)
            }
        return stats
    
    @staticmethod
    def get_overall_stats() -> Dict[str, Any]:
        """전체 CQRS 통계"""
        return {
            'commands': CQRSMetrics.get_command_stats(),
            'queries': CQRSMetrics.get_query_stats(),
            'registered_handlers': {
                'commands': len(command_bus._handlers),
                'queries': len(query_bus._handlers)
            }
        }
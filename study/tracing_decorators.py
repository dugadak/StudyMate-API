"""
Study 앱용 분산 추적 데코레이터

학습 관련 비즈니스 로직에 특화된 추적 데코레이터들을 제공합니다.
"""

from functools import wraps
from typing import Optional, Dict, Any
import logging

from django.conf import settings
from django.contrib.auth import get_user_model

from studymate_api.distributed_tracing import (
    studymate_tracer, 
    trace_function, 
    trace_ai_request,
    trace_database_query,
    trace_cache_operation
)

logger = logging.getLogger(__name__)
User = get_user_model()


def trace_study_operation(operation_name: str, include_user: bool = True, 
                         include_subject: bool = False):
    """학습 작업 추적 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            span_name = f"study.{operation_name}"
            
            with studymate_tracer.create_span(span_name) as span:
                try:
                    # 사용자 정보 추가
                    if include_user and args:
                        user_id = None
                        # 첫 번째 인자가 사용자 ID인 경우
                        if isinstance(args[0], int):
                            user_id = args[0]
                        # 첫 번째 인자가 User 객체인 경우
                        elif hasattr(args[0], 'id'):
                            user_id = args[0].id
                        # kwargs에서 user 또는 user_id 찾기
                        elif 'user' in kwargs:
                            user_id = kwargs['user'].id if hasattr(kwargs['user'], 'id') else kwargs['user']
                        elif 'user_id' in kwargs:
                            user_id = kwargs['user_id']
                        
                        if user_id:
                            studymate_tracer.add_user_context(span, user_id)
                    
                    # 과목 정보 추가
                    if include_subject:
                        subject_id = kwargs.get('subject_id') or kwargs.get('subject', {}).get('id')
                        if subject_id:
                            studymate_tracer.add_business_context(span, subject_id=subject_id)
                    
                    # 함수 실행
                    result = func(*args, **kwargs)
                    
                    # 결과에 따른 추가 정보
                    if hasattr(result, 'id'):
                        span.set_attribute(f"{operation_name}.result_id", result.id)
                    
                    return result
                    
                except Exception as e:
                    span.record_exception(e)
                    raise
        
        return wrapper
    return decorator


def trace_ai_generation(provider: str, model: str = None):
    """AI 콘텐츠 생성 추적 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 모델명 추출
            model_name = model or kwargs.get('model', 'default')
            
            with trace_ai_request(provider, model_name, 'content_generation') as span:
                try:
                    # 입력 텍스트 길이 기록
                    if 'text' in kwargs:
                        span.set_attribute("ai.input_length", len(kwargs['text']))
                    
                    # 요청 타입 기록
                    if 'request_type' in kwargs:
                        span.set_attribute("ai.request_type", kwargs['request_type'])
                    
                    result = func(*args, **kwargs)
                    
                    # 응답 정보 기록
                    if isinstance(result, dict):
                        if 'content' in result:
                            span.set_attribute("ai.output_length", len(result['content']))
                        if 'tokens_used' in result:
                            span.set_attribute("ai.tokens_used", result['tokens_used'])
                        if 'cost' in result:
                            span.set_attribute("ai.cost", result['cost'])
                    
                    return result
                    
                except Exception as e:
                    span.record_exception(e)
                    span.set_attribute("ai.error", str(e))
                    raise
        
        return wrapper
    return decorator


def trace_quiz_operation(operation_type: str):
    """퀴즈 작업 추적 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            span_name = f"quiz.{operation_type}"
            
            with studymate_tracer.create_span(span_name) as span:
                try:
                    # 퀴즈 ID 추가
                    quiz_id = kwargs.get('quiz_id') or kwargs.get('quiz', {}).get('id')
                    if quiz_id:
                        studymate_tracer.add_business_context(span, quiz_id=quiz_id)
                    
                    # 사용자 정보 추가
                    user_id = kwargs.get('user_id') or kwargs.get('user', {}).get('id')
                    if user_id:
                        studymate_tracer.add_user_context(span, user_id)
                    
                    # 퀴즈 메타데이터 추가
                    if 'difficulty' in kwargs:
                        span.set_attribute("quiz.difficulty", kwargs['difficulty'])
                    
                    if 'question_count' in kwargs:
                        span.set_attribute("quiz.question_count", kwargs['question_count'])
                    
                    result = func(*args, **kwargs)
                    
                    # 결과 정보 추가
                    if isinstance(result, dict):
                        if 'score' in result:
                            span.set_attribute("quiz.score", result['score'])
                        if 'correct_answers' in result:
                            span.set_attribute("quiz.correct_answers", result['correct_answers'])
                        if 'completion_time' in result:
                            span.set_attribute("quiz.completion_time", result['completion_time'])
                    
                    return result
                    
                except Exception as e:
                    span.record_exception(e)
                    raise
        
        return wrapper
    return decorator


def trace_study_session(session_type: str = "learning"):
    """학습 세션 추적 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            span_name = f"session.{session_type}"
            
            with studymate_tracer.create_span(span_name) as span:
                try:
                    # 세션 정보 추가
                    session_id = kwargs.get('session_id')
                    if session_id:
                        studymate_tracer.add_user_context(span, kwargs.get('user_id'), session_id)
                    
                    # 학습 주제 정보
                    subject_id = kwargs.get('subject_id')
                    if subject_id:
                        studymate_tracer.add_business_context(
                            span, 
                            subject_id=subject_id, 
                            operation_type=session_type
                        )
                    
                    result = func(*args, **kwargs)
                    
                    # 세션 결과 정보
                    if isinstance(result, dict):
                        if 'duration' in result:
                            span.set_attribute("session.duration", result['duration'])
                        if 'activities_completed' in result:
                            span.set_attribute("session.activities_completed", result['activities_completed'])
                        if 'focus_score' in result:
                            span.set_attribute("session.focus_score", result['focus_score'])
                    
                    return result
                    
                except Exception as e:
                    span.record_exception(e)
                    raise
        
        return wrapper
    return decorator


def trace_database_operation(table_name: str, operation: str = "query"):
    """데이터베이스 작업 추적 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with trace_database_query(operation, table_name) as span:
                try:
                    # 쿼리 파라미터 정보 (민감한 정보 제외)
                    if 'filters' in kwargs and isinstance(kwargs['filters'], dict):
                        safe_filters = {k: v for k, v in kwargs['filters'].items() 
                                      if k not in ['password', 'token', 'secret']}
                        span.set_attribute("db.filters", str(safe_filters))
                    
                    result = func(*args, **kwargs)
                    
                    # 결과 정보
                    if hasattr(result, 'count'):
                        span.set_attribute("db.result_count", result.count())
                    elif isinstance(result, (list, tuple)):
                        span.set_attribute("db.result_count", len(result))
                    
                    return result
                    
                except Exception as e:
                    span.record_exception(e)
                    raise
        
        return wrapper
    return decorator


def trace_cache_access(cache_key_pattern: str, operation: str = "get"):
    """캐시 접근 추적 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 실제 캐시 키 생성
            cache_key = cache_key_pattern.format(**kwargs) if kwargs else cache_key_pattern
            
            with trace_cache_operation(operation, cache_key) as span:
                try:
                    result = func(*args, **kwargs)
                    
                    # 캐시 히트/미스 정보
                    if operation == "get":
                        hit = result is not None
                        span.set_attribute("cache.hit", hit)
                        if hit:
                            span.set_attribute("cache.data_size", len(str(result)))
                    
                    return result
                    
                except Exception as e:
                    span.record_exception(e)
                    raise
        
        return wrapper
    return decorator


def trace_personalization_operation(operation_type: str):
    """개인화 작업 추적 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            span_name = f"personalization.{operation_type}"
            
            with studymate_tracer.create_span(span_name) as span:
                try:
                    # 사용자 정보
                    user_id = kwargs.get('user_id') or kwargs.get('user', {}).get('id')
                    if user_id:
                        studymate_tracer.add_user_context(span, user_id)
                    
                    # 개인화 타입
                    span.set_attribute("personalization.type", operation_type)
                    
                    result = func(*args, **kwargs)
                    
                    # 개인화 결과
                    if isinstance(result, dict):
                        if 'learning_style' in result:
                            span.set_attribute("personalization.learning_style", result['learning_style'])
                        if 'confidence_score' in result:
                            span.set_attribute("personalization.confidence", result['confidence_score'])
                        if 'recommendations_count' in result:
                            span.set_attribute("personalization.recommendations_count", result['recommendations_count'])
                    
                    return result
                    
                except Exception as e:
                    span.record_exception(e)
                    raise
        
        return wrapper
    return decorator
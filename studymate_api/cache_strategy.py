"""
Advanced caching strategy for StudyMate API

This module provides enhanced caching strategies for improved performance.
"""

from typing import Any, Optional, Callable, Dict, List
from django.core.cache import cache
from django.conf import settings
from functools import wraps
import hashlib
import json
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


class CacheStrategy:
    """캐싱 전략을 관리하는 클래스"""
    
    # 캐시 TTL 설정 (초 단위)
    TTL_SHORT = 60 * 5  # 5분
    TTL_MEDIUM = 60 * 30  # 30분
    TTL_LONG = 60 * 60 * 2  # 2시간
    TTL_EXTRA_LONG = 60 * 60 * 24  # 24시간
    
    @staticmethod
    def get_cache_key(prefix: str, **kwargs) -> str:
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
        
        if len(param_str) > 200:
            # 긴 키는 해시로 단축
            param_hash = hashlib.md5(param_str.encode()).hexdigest()
            return f"{settings.CACHE_KEY_PREFIX}:{prefix}:{param_hash}"
        
        return f"{settings.CACHE_KEY_PREFIX}:{prefix}:{param_str}"
    
    @staticmethod
    def invalidate_pattern(pattern: str):
        """
        패턴과 일치하는 캐시 무효화
        
        Args:
            pattern: 무효화할 캐시 키 패턴
        """
        # Redis를 사용하는 경우
        if hasattr(cache, '_cache'):
            redis_client = cache._cache.get_client()
            keys = redis_client.keys(f"{settings.CACHE_KEY_PREFIX}:{pattern}*")
            if keys:
                redis_client.delete(*keys)
                logger.info(f"Invalidated {len(keys)} cache keys matching pattern: {pattern}")


class SmartCache:
    """스마트 캐싱 데코레이터"""
    
    def __init__(self, 
                 ttl: int = CacheStrategy.TTL_MEDIUM,
                 key_prefix: str = None,
                 vary_on_user: bool = False,
                 vary_on_params: List[str] = None,
                 condition: Callable = None):
        """
        Args:
            ttl: 캐시 유효 시간 (초)
            key_prefix: 캐시 키 접두사
            vary_on_user: 사용자별로 캐시 분리 여부
            vary_on_params: 캐시를 분리할 매개변수 목록
            condition: 캐싱 조건 함수
        """
        self.ttl = ttl
        self.key_prefix = key_prefix
        self.vary_on_user = vary_on_user
        self.vary_on_params = vary_on_params or []
        self.condition = condition
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 캐싱 조건 확인
            if self.condition and not self.condition(*args, **kwargs):
                return func(*args, **kwargs)
            
            # 캐시 키 생성
            cache_key_parts = {}
            
            # 함수 이름 기반 키
            if self.key_prefix:
                cache_key_parts['prefix'] = self.key_prefix
            else:
                cache_key_parts['prefix'] = f"{func.__module__}.{func.__name__}"
            
            # 사용자별 캐시
            if self.vary_on_user:
                request = args[0] if args else kwargs.get('request')
                if request and hasattr(request, 'user') and request.user.is_authenticated:
                    cache_key_parts['user_id'] = request.user.id
            
            # 매개변수별 캐시
            for param in self.vary_on_params:
                if param in kwargs:
                    cache_key_parts[param] = kwargs[param]
            
            cache_key = CacheStrategy.get_cache_key(**cache_key_parts)
            
            # 캐시에서 조회
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_result
            
            # 함수 실행 및 캐싱
            result = func(*args, **kwargs)
            cache.set(cache_key, result, self.ttl)
            logger.debug(f"Cache miss and set: {cache_key}")
            
            return result
        
        wrapper.invalidate = lambda **kwargs: CacheStrategy.invalidate_pattern(
            self.key_prefix or f"{func.__module__}.{func.__name__}"
        )
        
        return wrapper


class LayeredCache:
    """다층 캐싱 시스템"""
    
    def __init__(self):
        self.l1_cache = {}  # 메모리 캐시 (매우 빠름)
        self.l1_max_size = 1000
        self.l1_ttl = 60  # 1분
    
    def get(self, key: str, l2_getter: Callable = None) -> Any:
        """
        다층 캐시에서 값 조회
        
        Args:
            key: 캐시 키
            l2_getter: L2 캐시에서 값을 가져오는 함수
            
        Returns:
            캐시된 값 또는 None
        """
        # L1 캐시 확인
        if key in self.l1_cache:
            value, timestamp = self.l1_cache[key]
            import time
            if time.time() - timestamp < self.l1_ttl:
                logger.debug(f"L1 cache hit: {key}")
                return value
            else:
                del self.l1_cache[key]
        
        # L2 캐시 (Redis) 확인
        value = cache.get(key)
        if value is not None:
            logger.debug(f"L2 cache hit: {key}")
            self._set_l1(key, value)
            return value
        
        # 캐시 미스 - getter 함수 실행
        if l2_getter:
            value = l2_getter()
            if value is not None:
                self.set(key, value)
            return value
        
        return None
    
    def set(self, key: str, value: Any, ttl: int = CacheStrategy.TTL_MEDIUM):
        """
        다층 캐시에 값 설정
        
        Args:
            key: 캐시 키
            value: 캐시할 값
            ttl: 캐시 유효 시간
        """
        # L1 캐시 설정
        self._set_l1(key, value)
        
        # L2 캐시 설정
        cache.set(key, value, ttl)
        logger.debug(f"Set layered cache: {key}")
    
    def _set_l1(self, key: str, value: Any):
        """L1 캐시 설정"""
        import time
        
        # 캐시 크기 제한
        if len(self.l1_cache) >= self.l1_max_size:
            # 가장 오래된 항목 제거 (간단한 LRU)
            oldest_key = min(self.l1_cache.keys(), 
                           key=lambda k: self.l1_cache[k][1])
            del self.l1_cache[oldest_key]
        
        self.l1_cache[key] = (value, time.time())
    
    def invalidate(self, key: str):
        """캐시 무효화"""
        # L1 캐시 제거
        if key in self.l1_cache:
            del self.l1_cache[key]
        
        # L2 캐시 제거
        cache.delete(key)
        logger.debug(f"Invalidated cache: {key}")


# 전역 레이어드 캐시 인스턴스
layered_cache = LayeredCache()


class QueryCache:
    """데이터베이스 쿼리 결과 캐싱"""
    
    @staticmethod
    def cached_queryset(queryset, cache_key: str, ttl: int = CacheStrategy.TTL_MEDIUM):
        """
        QuerySet 결과 캐싱
        
        Args:
            queryset: Django QuerySet
            cache_key: 캐시 키
            ttl: 캐시 유효 시간
            
        Returns:
            캐시된 쿼리 결과
        """
        # 캐시에서 조회
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"Query cache hit: {cache_key}")
            return cached_data
        
        # 쿼리 실행 및 캐싱
        # select_related와 prefetch_related 최적화 확인
        if hasattr(queryset, '_prefetch_related_lookups'):
            logger.debug(f"Prefetch lookups: {queryset._prefetch_related_lookups}")
        
        # 쿼리 실행
        data = list(queryset)
        
        # 결과 캐싱
        cache.set(cache_key, data, ttl)
        logger.debug(f"Query cache miss and set: {cache_key}")
        
        return data
    
    @staticmethod
    def cached_aggregate(queryset, aggregation: Dict, cache_key: str, ttl: int = CacheStrategy.TTL_LONG):
        """
        집계 쿼리 결과 캐싱
        
        Args:
            queryset: Django QuerySet
            aggregation: 집계 함수 딕셔너리
            cache_key: 캐시 키
            ttl: 캐시 유효 시간
            
        Returns:
            캐시된 집계 결과
        """
        # 캐시에서 조회
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"Aggregate cache hit: {cache_key}")
            return cached_data
        
        # 집계 실행 및 캐싱
        data = queryset.aggregate(**aggregation)
        cache.set(cache_key, data, ttl)
        logger.debug(f"Aggregate cache miss and set: {cache_key}")
        
        return data


class CacheWarmup:
    """캐시 예열 유틸리티"""
    
    @staticmethod
    def warmup_user_data(user_id: int):
        """
        사용자 데이터 캐시 예열
        
        Args:
            user_id: 사용자 ID
        """
        from study.models import StudySummary, StudyProgress
        
        # 사용자의 최근 요약 캐싱
        summaries_key = CacheStrategy.get_cache_key('user_summaries', user_id=user_id)
        summaries = StudySummary.objects.filter(
            user_id=user_id
        ).select_related('subject').order_by('-generated_at')[:10]
        cache.set(summaries_key, list(summaries), CacheStrategy.TTL_LONG)
        
        # 사용자의 학습 진도 캐싱
        progress_key = CacheStrategy.get_cache_key('user_progress', user_id=user_id)
        progress = StudyProgress.objects.filter(
            user_id=user_id
        ).select_related('subject')
        cache.set(progress_key, list(progress), CacheStrategy.TTL_LONG)
        
        logger.info(f"Warmed up cache for user {user_id}")
    
    @staticmethod
    def warmup_popular_subjects():
        """인기 과목 데이터 캐시 예열"""
        from study.models import Subject
        
        # 인기 과목 캐싱
        popular_key = CacheStrategy.get_cache_key('popular_subjects')
        popular_subjects = Subject.objects.filter(
            is_active=True
        ).order_by('-total_learners')[:20]
        cache.set(popular_key, list(popular_subjects), CacheStrategy.TTL_EXTRA_LONG)
        
        logger.info("Warmed up cache for popular subjects")


# 캐시 무효화 신호 처리
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


def setup_cache_invalidation():
    """캐시 무효화 신호 설정"""
    from study.models import StudySummary, Subject, StudyProgress
    
    @receiver([post_save, post_delete], sender=StudySummary)
    def invalidate_summary_cache(sender, instance, **kwargs):
        """요약 캐시 무효화"""
        user_key = CacheStrategy.get_cache_key('user_summaries', user_id=instance.user_id)
        cache.delete(user_key)
        logger.debug(f"Invalidated summary cache for user {instance.user_id}")
    
    @receiver([post_save, post_delete], sender=Subject)
    def invalidate_subject_cache(sender, instance, **kwargs):
        """과목 캐시 무효화"""
        CacheStrategy.invalidate_pattern('popular_subjects')
        CacheStrategy.invalidate_pattern(f'subject_{instance.id}')
        logger.debug(f"Invalidated subject cache for {instance.id}")
    
    @receiver([post_save, post_delete], sender=StudyProgress)
    def invalidate_progress_cache(sender, instance, **kwargs):
        """진도 캐시 무효화"""
        progress_key = CacheStrategy.get_cache_key('user_progress', user_id=instance.user_id)
        cache.delete(progress_key)
        logger.debug(f"Invalidated progress cache for user {instance.user_id}")
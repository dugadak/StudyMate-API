"""
StudyMate API 고급 캐싱 시스템

이 모듈은 다음 기능을 제공합니다:
- 태그 기반 캐시 무효화
- 지능형 캐시 예열
- 계층적 캐시 관리
- 캐시 성능 모니터링
- 자동 캐시 최적화
"""

import time
import json
import hashlib
import logging
from typing import Any, Dict, List, Optional, Set, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, OrderedDict
from threading import Lock, RLock
import asyncio
from concurrent.futures import ThreadPoolExecutor

from django.core.cache import cache
from django.core.cache.backends.base import BaseCache
from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """캐시 엔트리 메타데이터"""
    key: str
    value: Any
    tags: Set[str]
    created_at: datetime
    ttl: int
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    size_bytes: int = 0


@dataclass
class CacheStats:
    """캐시 성능 통계"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    total_size: int = 0
    avg_access_time: float = 0.0


class TaggedCache:
    """태그 기반 캐시 관리자"""
    
    def __init__(self, cache_backend: BaseCache = None):
        self.cache = cache_backend or cache
        self.tag_registry: Dict[str, Set[str]] = defaultdict(set)
        self.key_tags: Dict[str, Set[str]] = defaultdict(set)
        self.stats = CacheStats()
        self._lock = RLock()
        
        # 태그 레지스트리 키
        self.tag_registry_key = "cache_tag_registry"
        self.key_tags_key = "cache_key_tags"
        
        # 태그 정보 로드
        self._load_tag_registry()
    
    def _load_tag_registry(self):
        """태그 레지스트리 로드"""
        try:
            registry_data = self.cache.get(self.tag_registry_key, {})
            key_tags_data = self.cache.get(self.key_tags_key, {})
            
            self.tag_registry = defaultdict(set)
            for tag, keys in registry_data.items():
                self.tag_registry[tag] = set(keys)
            
            self.key_tags = defaultdict(set)
            for key, tags in key_tags_data.items():
                self.key_tags[key] = set(tags)
                
        except Exception as e:
            logger.warning(f"태그 레지스트리 로드 실패: {e}")
            self.tag_registry = defaultdict(set)
            self.key_tags = defaultdict(set)
    
    def _save_tag_registry(self):
        """태그 레지스트리 저장"""
        try:
            registry_data = {
                tag: list(keys) for tag, keys in self.tag_registry.items()
            }
            key_tags_data = {
                key: list(tags) for key, tags in self.key_tags.items()
            }
            
            self.cache.set(self.tag_registry_key, registry_data, timeout=86400)  # 24시간
            self.cache.set(self.key_tags_key, key_tags_data, timeout=86400)
            
        except Exception as e:
            logger.error(f"태그 레지스트리 저장 실패: {e}")
    
    def set(self, key: str, value: Any, tags: List[str] = None, timeout: int = None) -> bool:
        """태그와 함께 캐시 설정"""
        start_time = time.time()
        
        try:
            with self._lock:
                # 캐시 설정
                success = self.cache.set(key, value, timeout=timeout)
                
                if success and tags:
                    # 태그 등록
                    tag_set = set(tags)
                    self.key_tags[key] = tag_set
                    
                    for tag in tag_set:
                        self.tag_registry[tag].add(key)
                    
                    # 태그 레지스트리 저장
                    self._save_tag_registry()
                
                # 통계 업데이트
                self.stats.sets += 1
                
                return success
                
        except Exception as e:
            logger.error(f"캐시 설정 실패 - key: {key}, error: {e}")
            return False
        finally:
            access_time = time.time() - start_time
            self._update_access_time(access_time)
    
    def get(self, key: str, default: Any = None) -> Any:
        """캐시에서 값 조회"""
        start_time = time.time()
        
        try:
            value = self.cache.get(key, default)
            
            # 통계 업데이트
            if value is not default:
                self.stats.hits += 1
            else:
                self.stats.misses += 1
            
            return value
            
        except Exception as e:
            logger.error(f"캐시 조회 실패 - key: {key}, error: {e}")
            self.stats.misses += 1
            return default
        finally:
            access_time = time.time() - start_time
            self._update_access_time(access_time)
    
    def delete(self, key: str) -> bool:
        """캐시 키 삭제"""
        try:
            with self._lock:
                # 캐시에서 삭제
                success = self.cache.delete(key)
                
                # 태그에서 키 제거
                if key in self.key_tags:
                    tags = self.key_tags[key]
                    for tag in tags:
                        if tag in self.tag_registry:
                            self.tag_registry[tag].discard(key)
                            if not self.tag_registry[tag]:
                                del self.tag_registry[tag]
                    
                    del self.key_tags[key]
                    self._save_tag_registry()
                
                # 통계 업데이트
                self.stats.deletes += 1
                
                return success
                
        except Exception as e:
            logger.error(f"캐시 삭제 실패 - key: {key}, error: {e}")
            return False
    
    def invalidate_tag(self, tag: str) -> int:
        """태그로 캐시 무효화"""
        try:
            with self._lock:
                if tag not in self.tag_registry:
                    return 0
                
                keys_to_delete = list(self.tag_registry[tag])
                deleted_count = 0
                
                for key in keys_to_delete:
                    if self.delete(key):
                        deleted_count += 1
                
                logger.info(f"태그 '{tag}'로 {deleted_count}개 캐시 무효화")
                return deleted_count
                
        except Exception as e:
            logger.error(f"태그 무효화 실패 - tag: {tag}, error: {e}")
            return 0
    
    def invalidate_tags(self, tags: List[str]) -> int:
        """여러 태그로 캐시 무효화"""
        total_deleted = 0
        for tag in tags:
            total_deleted += self.invalidate_tag(tag)
        return total_deleted
    
    def get_keys_by_tag(self, tag: str) -> Set[str]:
        """태그로 키 목록 조회"""
        return self.tag_registry.get(tag, set()).copy()
    
    def get_tags_by_key(self, key: str) -> Set[str]:
        """키로 태그 목록 조회"""
        return self.key_tags.get(key, set()).copy()
    
    def _update_access_time(self, access_time: float):
        """접근 시간 통계 업데이트"""
        total_operations = self.stats.hits + self.stats.misses + self.stats.sets
        if total_operations > 0:
            self.stats.avg_access_time = (
                (self.stats.avg_access_time * (total_operations - 1) + access_time) 
                / total_operations
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        hit_rate = 0.0
        total_reads = self.stats.hits + self.stats.misses
        if total_reads > 0:
            hit_rate = self.stats.hits / total_reads
        
        return {
            'hits': self.stats.hits,
            'misses': self.stats.misses,
            'sets': self.stats.sets,
            'deletes': self.stats.deletes,
            'hit_rate': hit_rate,
            'avg_access_time': self.stats.avg_access_time,
            'total_tags': len(self.tag_registry),
            'total_keys': len(self.key_tags),
        }


class SmartCacheStrategy:
    """지능형 캐싱 전략"""
    
    def __init__(self):
        self.tagged_cache = TaggedCache()
        self.warming_strategies = {}
        self.access_patterns = defaultdict(list)
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # 캐시 전략 설정
        self.strategies = {
            'user_profile': {
                'ttl': 3600,  # 1시간
                'tags': ['user', 'profile'],
                'warm_on_login': True,
                'preload_related': ['preferences', 'subscription'],
            },
            'study_content': {
                'ttl': 7200,  # 2시간
                'tags': ['study', 'content'],
                'warm_on_access': True,
                'popular_threshold': 10,
            },
            'quiz_results': {
                'ttl': 1800,  # 30분
                'tags': ['quiz', 'results'],
                'invalidate_on_update': True,
            },
            'ai_responses': {
                'ttl': 86400,  # 24시간
                'tags': ['ai', 'responses'],
                'cache_expensive_only': True,
                'min_generation_time': 2.0,
            },
            'analytics': {
                'ttl': 3600,  # 1시간
                'tags': ['analytics', 'stats'],
                'batch_update': True,
                'refresh_schedule': '*/15 * * * *',  # 15분마다
            }
        }
    
    def get_cache_key(self, prefix: str, **kwargs) -> str:
        """캐시 키 생성"""
        key_parts = [prefix]
        
        # 정렬된 키-값 쌍으로 일관된 키 생성
        for key, value in sorted(kwargs.items()):
            if isinstance(value, (dict, list)):
                value = json.dumps(value, sort_keys=True)
            key_parts.append(f"{key}:{value}")
        
        key_string = ":".join(str(part) for part in key_parts)
        
        # 키가 너무 긴 경우 해시 사용
        if len(key_string) > 200:
            key_hash = hashlib.md5(key_string.encode()).hexdigest()
            return f"{prefix}:hash:{key_hash}"
        
        return key_string
    
    def cache_with_strategy(self, strategy_name: str, key_suffix: str, 
                          value_func: Callable, **kwargs) -> Any:
        """전략에 따른 캐싱"""
        if strategy_name not in self.strategies:
            logger.warning(f"알 수 없는 캐시 전략: {strategy_name}")
            return value_func()
        
        strategy = self.strategies[strategy_name]
        cache_key = self.get_cache_key(strategy_name, suffix=key_suffix, **kwargs)
        
        # 캐시에서 조회
        cached_value = self.tagged_cache.get(cache_key)
        if cached_value is not None:
            self._record_access(strategy_name, cache_key)
            return cached_value
        
        # 캐시 미스 - 값 생성
        start_time = time.time()
        value = value_func()
        generation_time = time.time() - start_time
        
        # 캐싱 조건 확인
        should_cache = True
        
        if strategy.get('cache_expensive_only'):
            min_time = strategy.get('min_generation_time', 1.0)
            should_cache = generation_time >= min_time
        
        if should_cache and value is not None:
            self.tagged_cache.set(
                cache_key,
                value,
                tags=strategy['tags'],
                timeout=strategy['ttl']
            )
        
        self._record_access(strategy_name, cache_key, generation_time)
        return value
    
    def warm_cache(self, strategy_name: str, warm_data: List[Dict[str, Any]]):
        """캐시 예열"""
        if strategy_name not in self.strategies:
            return
        
        strategy = self.strategies[strategy_name]
        
        def warm_single_item(item_data):
            try:
                cache_key = self.get_cache_key(strategy_name, **item_data['key_data'])
                
                if self.tagged_cache.get(cache_key) is None:
                    value = item_data['value_func']()
                    
                    self.tagged_cache.set(
                        cache_key,
                        value,
                        tags=strategy['tags'],
                        timeout=strategy['ttl']
                    )
                    
                    logger.debug(f"캐시 예열 완료: {cache_key}")
                    
            except Exception as e:
                logger.error(f"캐시 예열 실패: {e}")
        
        # 병렬로 캐시 예열
        futures = []
        for item_data in warm_data:
            future = self.executor.submit(warm_single_item, item_data)
            futures.append(future)
        
        # 모든 작업 완료 대기
        for future in futures:
            try:
                future.result(timeout=30)
            except Exception as e:
                logger.error(f"캐시 예열 작업 실패: {e}")
        
        logger.info(f"캐시 예열 완료: {strategy_name}, {len(warm_data)}개 항목")
    
    def auto_warm_popular_content(self):
        """인기 콘텐츠 자동 예열"""
        try:
            # 접근 패턴 분석
            popular_items = self._analyze_access_patterns()
            
            for strategy_name, items in popular_items.items():
                if items:
                    self.warm_cache(strategy_name, items)
                    
        except Exception as e:
            logger.error(f"자동 캐시 예열 실패: {e}")
    
    def _record_access(self, strategy_name: str, cache_key: str, 
                      generation_time: float = None):
        """접근 패턴 기록"""
        access_record = {
            'timestamp': timezone.now(),
            'cache_key': cache_key,
            'generation_time': generation_time,
        }
        
        self.access_patterns[strategy_name].append(access_record)
        
        # 오래된 기록 정리 (최근 1000개만 유지)
        if len(self.access_patterns[strategy_name]) > 1000:
            self.access_patterns[strategy_name] = \
                self.access_patterns[strategy_name][-1000:]
    
    def _analyze_access_patterns(self) -> Dict[str, List[Dict[str, Any]]]:
        """접근 패턴 분석하여 인기 항목 반환"""
        popular_items = defaultdict(list)
        
        for strategy_name, accesses in self.access_patterns.items():
            if not accesses:
                continue
            
            strategy = self.strategies[strategy_name]
            threshold = strategy.get('popular_threshold', 5)
            
            # 최근 24시간 데이터만 분석
            recent_accesses = [
                access for access in accesses
                if access['timestamp'] > timezone.now() - timedelta(hours=24)
            ]
            
            # 키별 접근 횟수 계산
            key_counts = defaultdict(int)
            for access in recent_accesses:
                key_counts[access['cache_key']] += 1
            
            # 인기 항목 선별
            for cache_key, count in key_counts.items():
                if count >= threshold:
                    # 실제 데이터 로딩 함수는 별도 구현 필요
                    popular_items[strategy_name].append({
                        'key_data': self._parse_cache_key(cache_key),
                        'value_func': lambda: None,  # 실제 로딩 함수로 교체
                        'access_count': count,
                    })
        
        return popular_items
    
    def _parse_cache_key(self, cache_key: str) -> Dict[str, Any]:
        """캐시 키를 파싱하여 원본 데이터 추출"""
        # 간단한 구현 - 실제로는 더 정교한 파싱 필요
        parts = cache_key.split(':')
        if len(parts) >= 2:
            return {'parsed_key': cache_key}
        return {}
    
    def invalidate_user_cache(self, user_id: int):
        """사용자 관련 캐시 무효화"""
        tags_to_invalidate = [
            f"user:{user_id}",
            f"profile:{user_id}",
            f"study_user:{user_id}",
            f"quiz_user:{user_id}",
        ]
        
        total_deleted = 0
        for tag in tags_to_invalidate:
            deleted = self.tagged_cache.invalidate_tag(tag)
            total_deleted += deleted
        
        logger.info(f"사용자 {user_id} 캐시 {total_deleted}개 무효화")
        return total_deleted
    
    def invalidate_content_cache(self, content_type: str, content_id: int):
        """콘텐츠 관련 캐시 무효화"""
        tags_to_invalidate = [
            f"{content_type}:{content_id}",
            f"{content_type}_list",
            "analytics",
        ]
        
        total_deleted = self.tagged_cache.invalidate_tags(tags_to_invalidate)
        logger.info(f"{content_type} {content_id} 캐시 {total_deleted}개 무효화")
        return total_deleted
    
    def get_cache_health(self) -> Dict[str, Any]:
        """캐시 시스템 상태 확인"""
        stats = self.tagged_cache.get_stats()
        
        health_status = {
            'status': 'healthy',
            'statistics': stats,
            'strategies': list(self.strategies.keys()),
            'access_patterns': {
                name: len(patterns) 
                for name, patterns in self.access_patterns.items()
            },
            'warnings': [],
        }
        
        # 성능 경고 확인
        if stats['hit_rate'] < 0.7:
            health_status['warnings'].append(
                f"낮은 캐시 히트율: {stats['hit_rate']:.2%}"
            )
        
        if stats['avg_access_time'] > 0.1:
            health_status['warnings'].append(
                f"높은 캐시 접근 시간: {stats['avg_access_time']:.3f}초"
            )
        
        return health_status


# 전역 캐시 매니저 인스턴스
smart_cache = SmartCacheStrategy()


# Django 시그널 핸들러
@receiver(post_save)
def invalidate_cache_on_save(sender, instance, **kwargs):
    """모델 저장 시 관련 캐시 무효화"""
    model_name = sender._meta.model_name
    
    try:
        if hasattr(instance, 'pk') and instance.pk:
            smart_cache.invalidate_content_cache(model_name, instance.pk)
            
            # 사용자 관련 모델인 경우 사용자 캐시도 무효화
            if hasattr(instance, 'user_id'):
                smart_cache.invalidate_user_cache(instance.user_id)
            elif hasattr(instance, 'user') and hasattr(instance.user, 'pk'):
                smart_cache.invalidate_user_cache(instance.user.pk)
                
    except Exception as e:
        logger.error(f"캐시 무효화 실패 - {model_name}: {e}")


@receiver(post_delete)
def invalidate_cache_on_delete(sender, instance, **kwargs):
    """모델 삭제 시 관련 캐시 무효화"""
    model_name = sender._meta.model_name
    
    try:
        if hasattr(instance, 'pk') and instance.pk:
            smart_cache.invalidate_content_cache(model_name, instance.pk)
            
            # 사용자 관련 모델인 경우 사용자 캐시도 무효화
            if hasattr(instance, 'user_id'):
                smart_cache.invalidate_user_cache(instance.user_id)
            elif hasattr(instance, 'user') and hasattr(instance.user, 'pk'):
                smart_cache.invalidate_user_cache(instance.user.pk)
                
    except Exception as e:
        logger.error(f"캐시 무효화 실패 - {model_name}: {e}")


# 헬퍼 함수들
def cache_user_profile(user_id: int, value_func: Callable) -> Any:
    """사용자 프로필 캐싱"""
    return smart_cache.cache_with_strategy(
        'user_profile',
        f"user:{user_id}",
        value_func,
        user_id=user_id
    )


def cache_study_content(subject_id: int, difficulty: str, value_func: Callable) -> Any:
    """학습 콘텐츠 캐싱"""
    return smart_cache.cache_with_strategy(
        'study_content',
        f"subject:{subject_id}:difficulty:{difficulty}",
        value_func,
        subject_id=subject_id,
        difficulty=difficulty
    )


def cache_quiz_results(user_id: int, quiz_id: int, value_func: Callable) -> Any:
    """퀴즈 결과 캐싱"""
    return smart_cache.cache_with_strategy(
        'quiz_results',
        f"user:{user_id}:quiz:{quiz_id}",
        value_func,
        user_id=user_id,
        quiz_id=quiz_id
    )


def cache_ai_response(prompt_hash: str, model: str, value_func: Callable) -> Any:
    """AI 응답 캐싱"""
    return smart_cache.cache_with_strategy(
        'ai_responses',
        f"prompt:{prompt_hash}:model:{model}",
        value_func,
        prompt_hash=prompt_hash,
        model=model
    )


def cache_analytics(metric_type: str, date_range: str, value_func: Callable) -> Any:
    """분석 데이터 캐싱"""
    return smart_cache.cache_with_strategy(
        'analytics',
        f"metric:{metric_type}:range:{date_range}",
        value_func,
        metric_type=metric_type,
        date_range=date_range
    )
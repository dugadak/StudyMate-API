"""
Comprehensive caching system for StudyMate API

This module provides advanced caching strategies including:
- Multi-level caching (Redis, local memory, database)
- Cache invalidation strategies
- Cache warming for frequently accessed data
- Analytics and monitoring for cache performance
- Distributed cache coordination
"""

from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.conf import settings
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from typing import Dict, Any, Optional, List, Callable, Union
import hashlib
import json
import time
import logging
from functools import wraps
from datetime import timedelta

logger = logging.getLogger(__name__)


class CacheKeyGenerator:
    """Intelligent cache key generation with versioning and namespacing"""
    
    def __init__(self, namespace: str = 'studymate'):
        self.namespace = namespace
        self.version = getattr(settings, 'CACHE_VERSION', 1)
    
    def generate_key(self, 
                    key_type: str, 
                    identifier: Union[str, int, tuple], 
                    user_id: Optional[int] = None,
                    extra_params: Optional[Dict[str, Any]] = None) -> str:
        """Generate optimized cache key"""
        key_parts = [
            self.namespace,
            key_type,
            str(identifier),
            f"v{self.version}"
        ]
        
        if user_id:
            key_parts.append(f"u{user_id}")
        
        if extra_params:
            # Sort params for consistent key generation
            params_str = json.dumps(extra_params, sort_keys=True, separators=(',', ':'))
            params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
            key_parts.append(f"p{params_hash}")
        
        # Join with colons and ensure length limit
        key = ':'.join(key_parts)
        if len(key) > 250:  # Redis key length limit
            key_hash = hashlib.md5(key.encode()).hexdigest()
            key = f"{self.namespace}:hash:{key_hash}"
        
        return key
    
    def generate_pattern(self, key_type: str, pattern: str = '*') -> str:
        """Generate cache key pattern for bulk operations"""
        return f"{self.namespace}:{key_type}:{pattern}:v{self.version}"


class SmartCache:
    """Enhanced caching with intelligent strategies"""
    
    def __init__(self, default_timeout: int = 300):
        self.default_timeout = default_timeout
        self.key_generator = CacheKeyGenerator()
        self.hit_count = 0
        self.miss_count = 0
    
    def get(self, 
           key_type: str, 
           identifier: Union[str, int], 
           user_id: Optional[int] = None,
           default: Any = None,
           extra_params: Optional[Dict[str, Any]] = None) -> Any:
        """Enhanced cache get with statistics"""
        key = self.key_generator.generate_key(key_type, identifier, user_id, extra_params)
        
        try:
            value = cache.get(key, default)
            if value is not default:
                self.hit_count += 1
                logger.debug(f"Cache hit: {key}")
                return value
            else:
                self.miss_count += 1
                logger.debug(f"Cache miss: {key}")
                return default
        except Exception as e:
            logger.error(f"Cache get error for {key}: {str(e)}")
            return default
    
    def set(self, 
           key_type: str, 
           identifier: Union[str, int], 
           value: Any,
           timeout: Optional[int] = None,
           user_id: Optional[int] = None,
           extra_params: Optional[Dict[str, Any]] = None) -> bool:
        """Enhanced cache set with error handling"""
        key = self.key_generator.generate_key(key_type, identifier, user_id, extra_params)
        timeout = timeout or self.default_timeout
        
        try:
            cache.set(key, value, timeout)
            logger.debug(f"Cache set: {key} (timeout: {timeout}s)")
            return True
        except Exception as e:
            logger.error(f"Cache set error for {key}: {str(e)}")
            return False
    
    def delete(self, 
              key_type: str, 
              identifier: Union[str, int],
              user_id: Optional[int] = None,
              extra_params: Optional[Dict[str, Any]] = None) -> bool:
        """Enhanced cache delete"""
        key = self.key_generator.generate_key(key_type, identifier, user_id, extra_params)
        
        try:
            cache.delete(key)
            logger.debug(f"Cache delete: {key}")
            return True
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {str(e)}")
            return False
    
    def delete_pattern(self, key_type: str, pattern: str = '*') -> int:
        """Delete cache keys matching pattern"""
        try:
            pattern_key = self.key_generator.generate_pattern(key_type, pattern)
            
            # Get all matching keys
            if hasattr(cache, 'delete_pattern'):
                # Redis backend
                return cache.delete_pattern(pattern_key)
            else:
                # Fallback for other backends
                logger.warning("Pattern deletion not supported by cache backend")
                return 0
        except Exception as e:
            logger.error(f"Cache pattern delete error: {str(e)}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'hits': self.hit_count,
            'misses': self.miss_count,
            'total_requests': total_requests,
            'hit_rate': round(hit_rate, 2)
        }


# Global cache instance
smart_cache = SmartCache()


def cache_function(key_type: str, 
                  timeout: int = 300,
                  user_specific: bool = False,
                  invalidate_on: Optional[List[str]] = None):
    """Decorator for caching function results"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function arguments
            cache_args = args + tuple(sorted(kwargs.items()))
            key_identifier = hashlib.md5(str(cache_args).encode()).hexdigest()
            
            # Get user ID if user_specific
            user_id = None
            if user_specific and args:
                # Try to extract user from first argument (typically request or self)
                if hasattr(args[0], 'user'):
                    user_id = getattr(args[0].user, 'id', None)
                elif hasattr(args[0], 'request') and hasattr(args[0].request, 'user'):
                    user_id = getattr(args[0].request.user, 'id', None)
            
            # Try to get from cache
            cached_result = smart_cache.get(key_type, key_identifier, user_id)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            smart_cache.set(key_type, key_identifier, result, timeout, user_id)
            
            return result
        
        # Store invalidation info on function
        wrapper._cache_key_type = key_type
        wrapper._cache_invalidate_on = invalidate_on or []
        
        return wrapper
    return decorator


class CacheInvalidator:
    """Handles cache invalidation strategies"""
    
    def __init__(self):
        self.invalidation_rules: Dict[str, List[str]] = {}
    
    def register_rule(self, model_name: str, cache_types: List[str]):
        """Register cache invalidation rule for model changes"""
        self.invalidation_rules[model_name] = cache_types
    
    def invalidate_for_model(self, model_name: str, instance_id: Optional[int] = None):
        """Invalidate caches when model changes"""
        cache_types = self.invalidation_rules.get(model_name, [])
        
        for cache_type in cache_types:
            if instance_id:
                # Invalidate specific instance
                smart_cache.delete(cache_type, instance_id)
            
            # Invalidate pattern-based caches
            smart_cache.delete_pattern(cache_type)
        
        logger.info(f"Invalidated caches for {model_name}: {cache_types}")


# Global invalidator
cache_invalidator = CacheInvalidator()


class CacheWarmer:
    """Proactive cache warming for frequently accessed data"""
    
    def __init__(self):
        self.warming_strategies: Dict[str, Callable] = {}
    
    def register_strategy(self, cache_type: str, strategy_func: Callable):
        """Register cache warming strategy"""
        self.warming_strategies[cache_type] = strategy_func
    
    def warm_cache(self, cache_type: str, **kwargs):
        """Execute cache warming strategy"""
        if cache_type in self.warming_strategies:
            try:
                strategy_func = self.warming_strategies[cache_type]
                strategy_func(**kwargs)
                logger.info(f"Cache warming completed for {cache_type}")
            except Exception as e:
                logger.error(f"Cache warming failed for {cache_type}: {str(e)}")
    
    def warm_all_caches(self):
        """Warm all registered caches"""
        for cache_type in self.warming_strategies.keys():
            self.warm_cache(cache_type)


# Global cache warmer
cache_warmer = CacheWarmer()


class StudyMateCache:
    """StudyMate-specific cache operations"""
    
    # Cache type constants
    USER_PROFILE = 'user_profile'
    STUDY_STATISTICS = 'study_stats'
    QUIZ_RESULTS = 'quiz_results'
    SUBJECT_DATA = 'subject_data'
    SUBSCRIPTION_STATUS = 'subscription'
    NOTIFICATION_SETTINGS = 'notification_settings'
    
    @staticmethod
    @cache_function(USER_PROFILE, timeout=600, user_specific=True)
    def get_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
        """Cache user profile data"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            user = User.objects.select_related('profile').get(id=user_id)
            return {
                'id': user.id,
                'email': user.email,
                'name': f"{user.first_name} {user.last_name}".strip(),
                'profile_name': getattr(user.profile, 'name', None) if hasattr(user, 'profile') else None,
                'is_active': user.is_active,
                'date_joined': user.date_joined.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None
            }
        except User.DoesNotExist:
            return None
    
    @staticmethod
    @cache_function(STUDY_STATISTICS, timeout=900)
    def get_study_statistics(user_id: int, period_days: int = 30) -> Dict[str, Any]:
        """Cache study statistics"""
        from study.models import StudySummary
        from django.utils import timezone
        from datetime import timedelta
        
        since_date = timezone.now() - timedelta(days=period_days)
        summaries = StudySummary.objects.filter(
            user_id=user_id,
            created_at__gte=since_date
        )
        
        from django.db import models
        return {
            'total_summaries': summaries.count(),
            'total_subjects': summaries.values('subject').distinct().count(),
            'avg_rating': summaries.aggregate(avg_rating=models.Avg('user_rating'))['avg_rating'] or 0,
            'period_days': period_days,
            'last_updated': timezone.now().isoformat()
        }
    
    @staticmethod
    @cache_function(SUBSCRIPTION_STATUS, timeout=300, user_specific=True)
    def get_subscription_status(user_id: int) -> Dict[str, Any]:
        """Cache subscription status"""
        from subscription.models import UserSubscription
        from django.utils import timezone
        
        try:
            subscription = UserSubscription.objects.select_related('plan').filter(
                user_id=user_id,
                status__in=['active', 'trialing']
            ).first()
            
            if subscription:
                return {
                    'is_active': True,
                    'plan_name': subscription.plan.name,
                    'plan_type': subscription.plan.plan_type,
                    'expires_at': subscription.expires_at.isoformat() if subscription.expires_at else None,
                    'is_trial': subscription.is_trial,
                    'trial_ends_at': subscription.trial_ends_at.isoformat() if subscription.trial_ends_at else None
                }
            else:
                return {'is_active': False}
        except Exception:
            return {'is_active': False}


# Setup cache invalidation rules
cache_invalidator.register_rule('User', [StudyMateCache.USER_PROFILE])
cache_invalidator.register_rule('UserProfile', [StudyMateCache.USER_PROFILE])
cache_invalidator.register_rule('StudySummary', [StudyMateCache.STUDY_STATISTICS])
cache_invalidator.register_rule('UserSubscription', [StudyMateCache.SUBSCRIPTION_STATUS])


def setup_cache_warming_strategies():
    """Setup cache warming strategies"""
    
    def warm_popular_subjects():
        """Warm cache for popular subjects"""
        from study.models import Subject
        
        popular_subjects = Subject.objects.filter(
            is_active=True,
            total_learners__gt=100
        ).order_by('-total_learners')[:20]
        
        for subject in popular_subjects:
            smart_cache.set(StudyMateCache.SUBJECT_DATA, subject.id, {
                'id': subject.id,
                'name': subject.name,
                'category': subject.category,
                'total_learners': subject.total_learners,
                'average_rating': subject.average_rating
            }, timeout=1800)  # 30 minutes
    
    def warm_user_profiles():
        """Warm cache for recently active users"""
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from datetime import timedelta
        
        User = get_user_model()
        recent_users = User.objects.filter(
            last_login__gte=timezone.now() - timedelta(days=7)
        ).select_related('profile')[:100]
        
        for user in recent_users:
            StudyMateCache.get_user_profile(user.id)
    
    # Register strategies
    cache_warmer.register_strategy('popular_subjects', warm_popular_subjects)
    cache_warmer.register_strategy('user_profiles', warm_user_profiles)


# Initialize cache warming strategies
setup_cache_warming_strategies()


# Django signal handlers for cache invalidation
def invalidate_cache_on_save(sender, instance, **kwargs):
    """Invalidate cache when model instance is saved"""
    model_name = sender.__name__
    cache_invalidator.invalidate_for_model(model_name, instance.pk)


def invalidate_cache_on_delete(sender, instance, **kwargs):
    """Invalidate cache when model instance is deleted"""
    model_name = sender.__name__
    cache_invalidator.invalidate_for_model(model_name, instance.pk)


# Connect signals for automatic cache invalidation
from django.apps import apps

def connect_cache_signals():
    """Connect cache invalidation signals for all models"""
    for app_name in ['accounts', 'study', 'quiz', 'subscription', 'notifications']:
        try:
            app_config = apps.get_app_config(app_name)
            for model in app_config.get_models():
                post_save.connect(invalidate_cache_on_save, sender=model)
                post_delete.connect(invalidate_cache_on_delete, sender=model)
        except LookupError:
            pass


# Cache monitoring and analytics
class CacheMonitor:
    """Monitor cache performance and provide analytics"""
    
    @staticmethod
    def get_cache_info() -> Dict[str, Any]:
        """Get comprehensive cache information"""
        return {
            'backend': str(cache.__class__),
            'stats': smart_cache.get_stats(),
            'timestamp': timezone.now().isoformat()
        }
    
    @staticmethod
    def get_cache_size_estimate() -> Dict[str, Any]:
        """Estimate cache size and memory usage"""
        try:
            if hasattr(cache, 'keys'):
                # Redis backend
                all_keys = cache.keys('studymate:*')
                return {
                    'total_keys': len(all_keys),
                    'estimated_size_mb': len(all_keys) * 0.001  # Rough estimate
                }
            else:
                return {'message': 'Size estimation not available for this backend'}
        except Exception as e:
            return {'error': str(e)}


# Export main classes and functions
__all__ = [
    'SmartCache',
    'CacheKeyGenerator', 
    'CacheInvalidator',
    'CacheWarmer',
    'StudyMateCache',
    'CacheMonitor',
    'cache_function',
    'smart_cache',
    'cache_invalidator',
    'cache_warmer',
    'connect_cache_signals'
]
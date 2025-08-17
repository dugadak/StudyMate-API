"""
Enhanced base serializers with performance optimizations for StudyMate API

This module provides optimized base serializers that include:
- Selective field serialization based on context
- Optimized queryset handling with select_related and prefetch_related
- Caching for expensive computed fields
- Field-level permissions and dynamic field exclusion
- Performance monitoring and metrics
"""

from rest_framework import serializers
from django.core.cache import cache
from django.db.models import Prefetch
from typing import Dict, Any, List, Optional, Set
import hashlib
import time
import logging

logger = logging.getLogger(__name__)


class OptimizedModelSerializer(serializers.ModelSerializer):
    """
    Enhanced ModelSerializer with performance optimizations
    
    Features:
    - Selective field serialization based on context
    - Automatic queryset optimization
    - Field-level caching for expensive operations
    - Performance monitoring
    """
    
    # Define fields that should be cached (override in subclasses)
    cached_fields: Set[str] = set()
    
    # Define fields for different contexts (override in subclasses)
    list_fields: Optional[List[str]] = None
    detail_fields: Optional[List[str]] = None
    
    # Define related fields for queryset optimization
    select_related_fields: List[str] = []
    prefetch_related_fields: List[str] = []
    
    def __init__(self, *args, **kwargs):
        # Extract context before calling super
        context = kwargs.get('context', {})
        self.request = context.get('request')
        
        # Optimize fields based on context
        self._optimize_fields_for_context(kwargs)
        
        super().__init__(*args, **kwargs)
        
        # Track serialization performance
        self._start_time = time.time()
    
    def _optimize_fields_for_context(self, kwargs):
        """Optimize fields based on request context"""
        if not self.request:
            return
        
        view_action = getattr(self.request, 'resolver_match', None)
        if not view_action:
            return
        
        action = getattr(view_action, 'func', None)
        if hasattr(action, 'cls'):
            view_action_name = getattr(action.cls, 'action', None)
        else:
            view_action_name = None
        
        # Use list fields for list views, detail fields for detail views
        if view_action_name == 'list' and self.list_fields:
            kwargs['fields'] = self.list_fields
        elif view_action_name in ['retrieve', 'update', 'partial_update'] and self.detail_fields:
            kwargs['fields'] = self.detail_fields
        
        # Handle query parameter field selection
        if self.request and hasattr(self.request, 'query_params'):
            fields_param = self.request.query_params.get('fields')
            if fields_param:
                requested_fields = [f.strip() for f in fields_param.split(',')]
                # Only include fields that exist in the serializer
                valid_fields = set(requested_fields) & set(self.get_field_names())
                if valid_fields:
                    kwargs['fields'] = list(valid_fields)
    
    def get_field_names(self):
        """Get all available field names"""
        if hasattr(self.Meta, 'fields'):
            if self.Meta.fields == '__all__':
                return [field.name for field in self.Meta.model._meta.get_fields()]
            return self.Meta.fields
        return []
    
    def to_representation(self, instance):
        """Enhanced representation with caching and performance monitoring"""
        # Generate cache key for cached fields
        cache_keys = {}
        for field_name in self.cached_fields:
            if field_name in self.fields:
                cache_key = self._generate_cache_key(instance, field_name)
                cached_value = cache.get(cache_key)
                if cached_value is not None:
                    cache_keys[field_name] = cached_value
        
        # Get base representation
        data = super().to_representation(instance)
        
        # Apply cached values
        for field_name, cached_value in cache_keys.items():
            data[field_name] = cached_value
        
        # Cache expensive computed fields
        for field_name in self.cached_fields:
            if field_name in data and field_name not in cache_keys:
                cache_key = self._generate_cache_key(instance, field_name)
                cache.set(cache_key, data[field_name], timeout=300)  # 5 minutes
        
        # Log performance metrics
        self._log_performance_metrics(instance)
        
        return data
    
    def _generate_cache_key(self, instance, field_name: str) -> str:
        """Generate cache key for field"""
        model_name = instance.__class__.__name__.lower()
        instance_id = getattr(instance, 'pk', 'no_pk')
        updated_at = getattr(instance, 'updated_at', None)
        
        # Include updated_at in cache key for cache invalidation
        timestamp = updated_at.timestamp() if updated_at else ''
        
        key_data = f"{model_name}:{instance_id}:{field_name}:{timestamp}"
        return f"serializer_cache:{hashlib.md5(key_data.encode()).hexdigest()}"
    
    def _log_performance_metrics(self, instance):
        """Log serialization performance metrics"""
        if hasattr(self, '_start_time'):
            duration = (time.time() - self._start_time) * 1000  # milliseconds
            
            if duration > 100:  # Log slow serializations
                logger.warning(
                    f"Slow serialization: {self.__class__.__name__} "
                    f"for {instance.__class__.__name__}({instance.pk}) "
                    f"took {duration:.2f}ms"
                )
    
    @classmethod
    def optimize_queryset(cls, queryset):
        """Optimize queryset with select_related and prefetch_related"""
        if cls.select_related_fields:
            queryset = queryset.select_related(*cls.select_related_fields)
        
        if cls.prefetch_related_fields:
            queryset = queryset.prefetch_related(*cls.prefetch_related_fields)
        
        return queryset


class ListOnlySerializer(OptimizedModelSerializer):
    """Serializer optimized for list views with minimal fields"""
    
    def __init__(self, *args, **kwargs):
        # Remove detail fields for list views
        if hasattr(self.Meta, 'list_fields'):
            kwargs['fields'] = self.Meta.list_fields
        super().__init__(*args, **kwargs)


class DetailOnlySerializer(OptimizedModelSerializer):
    """Serializer optimized for detail views with all fields"""
    
    def __init__(self, *args, **kwargs):
        # Include all fields for detail views
        if hasattr(self.Meta, 'detail_fields'):
            kwargs['fields'] = self.Meta.detail_fields
        super().__init__(*args, **kwargs)


class TimestampMixin:
    """Mixin for adding optimized timestamp fields"""
    
    created_at_display = serializers.SerializerMethodField()
    updated_at_display = serializers.SerializerMethodField()
    
    def get_created_at_display(self, obj):
        """Get human-readable created_at"""
        if hasattr(obj, 'created_at') and obj.created_at:
            return obj.created_at.strftime('%Y-%m-%d %H:%M:%S')
        return None
    
    def get_updated_at_display(self, obj):
        """Get human-readable updated_at"""
        if hasattr(obj, 'updated_at') and obj.updated_at:
            return obj.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        return None


class UserRelatedMixin:
    """Mixin for serializers with user relationships"""
    
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_full_name = serializers.SerializerMethodField()
    
    def get_user_full_name(self, obj):
        """Get user's full name"""
        if hasattr(obj, 'user') and obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email
        return None


class PaginationOptimizedSerializer(OptimizedModelSerializer):
    """Serializer optimized for paginated responses"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Remove expensive fields for paginated lists
        if self.context.get('paginated', False):
            expensive_fields = getattr(self.Meta, 'expensive_fields', [])
            for field_name in expensive_fields:
                if field_name in self.fields:
                    del self.fields[field_name]


class BulkSerializerMixin:
    """Mixin for optimizing bulk operations"""
    
    def __init__(self, *args, **kwargs):
        self.is_bulk = kwargs.pop('bulk', False)
        super().__init__(*args, **kwargs)
        
        if self.is_bulk:
            # Remove expensive fields for bulk operations
            bulk_excluded_fields = getattr(self.Meta, 'bulk_excluded_fields', [])
            for field_name in bulk_excluded_fields:
                if field_name in self.fields:
                    del self.fields[field_name]


class CachedMethodField(serializers.SerializerMethodField):
    """SerializerMethodField with caching support"""
    
    def __init__(self, method_name=None, cache_timeout=300, **kwargs):
        self.cache_timeout = cache_timeout
        super().__init__(method_name, **kwargs)
    
    def to_representation(self, value):
        """Cached representation"""
        # Generate cache key
        method = getattr(self.parent, self.method_name)
        cache_key = f"method_field:{self.parent.__class__.__name__}:{value.pk}:{self.method_name}"
        
        # Try to get from cache
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        # Compute and cache result
        result = method(value)
        cache.set(cache_key, result, timeout=self.cache_timeout)
        
        return result


class AnalyticsSerializerMixin:
    """Mixin for adding analytics data to serializers"""
    
    analytics_data = serializers.SerializerMethodField()
    
    def get_analytics_data(self, obj):
        """Get analytics data for object"""
        # This is a placeholder - implement specific analytics in subclasses
        return {
            'views': getattr(obj, 'view_count', 0),
            'interactions': getattr(obj, 'interaction_count', 0),
            'last_accessed': getattr(obj, 'last_accessed_at', None)
        }


class PerformanceMonitoringMixin:
    """Mixin for monitoring serializer performance"""
    
    def __init__(self, *args, **kwargs):
        self._perf_start = time.time()
        super().__init__(*args, **kwargs)
    
    def to_representation(self, instance):
        start_time = time.time()
        data = super().to_representation(instance)
        duration = (time.time() - start_time) * 1000
        
        # Add performance metadata if requested
        if self.context.get('include_performance', False):
            data['_performance'] = {
                'serialization_time_ms': round(duration, 2),
                'field_count': len(data)
            }
        
        return data


# Export commonly used classes
__all__ = [
    'OptimizedModelSerializer',
    'ListOnlySerializer', 
    'DetailOnlySerializer',
    'TimestampMixin',
    'UserRelatedMixin',
    'PaginationOptimizedSerializer',
    'BulkSerializerMixin',
    'CachedMethodField',
    'AnalyticsSerializerMixin',
    'PerformanceMonitoringMixin'
]
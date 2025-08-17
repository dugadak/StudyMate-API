"""
Enhanced viewset mixins with performance optimizations for StudyMate API

This module provides optimized viewset mixins that include:
- Automatic queryset optimization based on serializer configuration
- Selective field loading based on request parameters
- Response caching for GET requests
- Performance monitoring and logging
- Bulk operation support
"""

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.core.cache import cache
from django.db.models import QuerySet, Prefetch
from django.utils import timezone
from typing import Dict, Any, Optional, List
import hashlib
import time
import logging

logger = logging.getLogger(__name__)


class OptimizedQuerysetMixin:
    """Mixin for automatic queryset optimization"""
    
    def get_queryset(self):
        """Optimize queryset based on serializer configuration"""
        queryset = super().get_queryset()
        
        # Get serializer class
        serializer_class = self.get_serializer_class()
        
        # Apply queryset optimization if available
        if hasattr(serializer_class, 'optimize_queryset'):
            queryset = serializer_class.optimize_queryset(queryset)
        
        return queryset
    
    def get_serializer_context(self):
        """Enhanced serializer context with optimization hints"""
        context = super().get_serializer_context()
        
        # Add pagination flag for optimized serialization
        if hasattr(self, 'paginate_queryset'):
            context['paginated'] = True
        
        # Add performance monitoring flag if requested
        if self.request and self.request.query_params.get('debug') == 'performance':
            context['include_performance'] = True
        
        return context


class SelectiveFieldsMixin:
    """Mixin for selective field loading based on request parameters"""
    
    def get_serializer(self, *args, **kwargs):
        """Enhanced serializer with selective fields"""
        # Check for fields parameter
        if self.request and hasattr(self.request, 'query_params'):
            fields_param = self.request.query_params.get('fields')
            if fields_param:
                # Validate and set fields
                requested_fields = [f.strip() for f in fields_param.split(',')]
                kwargs['fields'] = requested_fields
        
        return super().get_serializer(*args, **kwargs)


class CachedResponseMixin:
    """Mixin for caching GET responses"""
    
    cache_timeout = 300  # 5 minutes default
    cache_key_prefix = 'api_response'
    
    def dispatch(self, request, *args, **kwargs):
        """Dispatch with response caching for GET requests"""
        # Only cache GET requests
        if request.method != 'GET':
            return super().dispatch(request, *args, **kwargs)
        
        # Generate cache key
        cache_key = self._generate_cache_key(request, *args, **kwargs)
        
        # Try to get cached response
        cached_response = cache.get(cache_key)
        if cached_response is not None:
            logger.debug(f"Cache hit for {cache_key}")
            return Response(cached_response)
        
        # Get fresh response
        response = super().dispatch(request, *args, **kwargs)
        
        # Cache successful responses
        if response.status_code == status.HTTP_200_OK:
            cache.set(cache_key, response.data, timeout=self.cache_timeout)
            logger.debug(f"Cached response for {cache_key}")
        
        return response
    
    def _generate_cache_key(self, request, *args, **kwargs) -> str:
        """Generate cache key for request"""
        # Include view name, action, query params, and user
        view_name = self.__class__.__name__
        action_name = getattr(self, 'action', 'unknown')
        
        # Include relevant query parameters
        query_params = dict(request.query_params)
        
        # Include user ID for user-specific data
        user_id = request.user.id if request.user.is_authenticated else 'anonymous'
        
        # Create key components
        key_components = [
            view_name,
            action_name,
            str(user_id),
            str(sorted(query_params.items())),
            str(kwargs)
        ]
        
        # Generate hash
        key_string = '|'.join(key_components)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        
        return f"{self.cache_key_prefix}:{key_hash}"


class PerformanceMonitoringMixin:
    """Mixin for monitoring API performance"""
    
    def dispatch(self, request, *args, **kwargs):
        """Dispatch with performance monitoring"""
        start_time = time.time()
        
        # Get response
        response = super().dispatch(request, *args, **kwargs)
        
        # Calculate duration
        duration = (time.time() - start_time) * 1000  # milliseconds
        
        # Log slow requests
        if duration > 1000:  # > 1 second
            logger.warning(
                f"Slow API request: {request.method} {request.path} "
                f"took {duration:.2f}ms"
            )
        elif duration > 500:  # > 500ms
            logger.info(
                f"API request: {request.method} {request.path} "
                f"took {duration:.2f}ms"
            )
        
        # Add performance headers in debug mode
        if request.query_params.get('debug') == 'performance':
            response['X-Response-Time'] = f"{duration:.2f}ms"
            response['X-Timestamp'] = timezone.now().isoformat()
        
        return response


class BulkOperationMixin:
    """Mixin for bulk operations"""
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Bulk create objects"""
        serializer = self.get_serializer(data=request.data, many=True, bulk=True)
        serializer.is_valid(raise_exception=True)
        
        # Perform bulk create
        instances = serializer.save()
        
        # Return created objects
        response_serializer = self.get_serializer(instances, many=True)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['patch'])
    def bulk_update(self, request):
        """Bulk update objects"""
        # Extract IDs and data
        bulk_data = request.data
        if not isinstance(bulk_data, list):
            return Response(
                {'error': 'Expected list of objects'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update objects
        updated_objects = []
        for item in bulk_data:
            if 'id' not in item:
                continue
            
            try:
                instance = self.get_queryset().get(id=item['id'])
                serializer = self.get_serializer(
                    instance, 
                    data=item, 
                    partial=True,
                    bulk=True
                )
                serializer.is_valid(raise_exception=True)
                updated_objects.append(serializer.save())
            except self.queryset.model.DoesNotExist:
                continue
        
        # Return updated objects
        response_serializer = self.get_serializer(updated_objects, many=True)
        return Response(response_serializer.data)
    
    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        """Bulk delete objects"""
        ids = request.data.get('ids', [])
        if not ids:
            return Response(
                {'error': 'No IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Delete objects
        deleted_count = self.get_queryset().filter(id__in=ids).delete()[0]
        
        return Response({
            'deleted_count': deleted_count,
            'message': f'Successfully deleted {deleted_count} objects'
        })


class FilterOptimizationMixin:
    """Mixin for optimizing filtering operations"""
    
    def filter_queryset(self, queryset):
        """Optimize queryset filtering"""
        # Apply parent filtering
        queryset = super().filter_queryset(queryset)
        
        # Add index hints for common filters
        if hasattr(self, 'filterset_class') and self.filterset_class:
            # Get active filters
            filterset = self.filterset_class(
                self.request.query_params,
                queryset=queryset,
                request=self.request
            )
            
            # Log slow filters
            start_time = time.time()
            queryset = filterset.qs
            duration = (time.time() - start_time) * 1000
            
            if duration > 100:  # > 100ms
                logger.warning(
                    f"Slow filter operation on {self.__class__.__name__} "
                    f"took {duration:.2f}ms"
                )
        
        return queryset


class OptimizedModelViewSet(
    OptimizedQuerysetMixin,
    SelectiveFieldsMixin,
    CachedResponseMixin,
    PerformanceMonitoringMixin,
    BulkOperationMixin,
    FilterOptimizationMixin,
    viewsets.ModelViewSet
):
    """Fully optimized ModelViewSet with all performance enhancements"""
    
    # Default cache timeout (can be overridden)
    cache_timeout = 300
    
    def get_serializer_class(self):
        """Dynamic serializer selection based on action"""
        # Use list serializer for list actions
        if self.action == 'list' and hasattr(self, 'list_serializer_class'):
            return self.list_serializer_class
        
        # Use detail serializer for detail actions
        if self.action in ['retrieve', 'update', 'partial_update'] and hasattr(self, 'detail_serializer_class'):
            return self.detail_serializer_class
        
        return super().get_serializer_class()
    
    @action(detail=False, methods=['get'])
    def performance_stats(self, request):
        """Get performance statistics for this viewset"""
        return Response({
            'model': self.queryset.model.__name__,
            'total_objects': self.get_queryset().count(),
            'cache_timeout': self.cache_timeout,
            'optimizations_enabled': [
                'queryset_optimization',
                'selective_fields',
                'response_caching',
                'performance_monitoring',
                'bulk_operations',
                'filter_optimization'
            ]
        })


class ReadOnlyOptimizedViewSet(
    OptimizedQuerysetMixin,
    SelectiveFieldsMixin,
    CachedResponseMixin,
    PerformanceMonitoringMixin,
    FilterOptimizationMixin,
    viewsets.ReadOnlyModelViewSet
):
    """Optimized read-only ViewSet for high-performance read operations"""
    
    # Longer cache timeout for read-only data
    cache_timeout = 900  # 15 minutes


# Export classes
__all__ = [
    'OptimizedQuerysetMixin',
    'SelectiveFieldsMixin', 
    'CachedResponseMixin',
    'PerformanceMonitoringMixin',
    'BulkOperationMixin',
    'FilterOptimizationMixin',
    'OptimizedModelViewSet',
    'ReadOnlyOptimizedViewSet'
]
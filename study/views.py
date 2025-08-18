from rest_framework import viewsets, generics, status, permissions, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.utils import timezone
from django.db import models
from django.db.models import Q, Count, Avg, Sum, Max, F
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from studymate_api.schema import (
    study_schema, COMMON_PARAMETERS, APIExamples,
    StandardResponseSerializer, ErrorResponseSerializer, get_paginated_response_schema
)
from studymate_api.advanced_cache import (
    smart_cache, cache_study_content, cache_ai_response, cache_user_profile
)
from studymate_api.personalization import (
    get_personalized_content_recommendations, 
    update_learning_pattern,
    get_adaptive_difficulty
)
from studymate_api.metrics import (
    track_user_event, track_business_event, EventType
)
from typing import Dict, Any, Optional
import logging
import hashlib

from .models import Subject, StudySettings, StudySummary, StudyProgress, StudyGoal
from .serializers import (
    SubjectSerializer, StudySettingsSerializer, 
    StudySummarySerializer, StudyProgressSerializer, StudyGoalSerializer,
    StudySummaryDetailSerializer, SubjectCreateSerializer
)
from .services import StudySummaryService, StudyProgressService
from .filters import StudySummaryFilter, StudyProgressFilter
from .pagination import StudyPagination

logger = logging.getLogger(__name__)


@study_schema(
    summary="과목 관리",
    description="학습 과목 조회, 생성, 수정, 삭제를 관리합니다."
)
class SubjectViewSet(viewsets.ModelViewSet):
    """Enhanced Subject ViewSet with filtering and statistics"""
    
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'tags', 'keywords']
    ordering_fields = ['name', 'total_learners', 'average_rating', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        """Get filtered and optimized queryset with caching"""
        # Create cache key based on query parameters
        cache_key_params = {
            'category': self.request.query_params.get('category'),
            'difficulty': self.request.query_params.get('difficulty'),
            'premium_only': self.request.query_params.get('premium_only'),
            'subscribed_only': self.request.query_params.get('subscribed_only'),
            'user_id': self.request.user.id if self.request.query_params.get('subscribed_only') else None
        }
        
        def get_queryset_func():
            queryset = Subject.objects.filter(is_active=True)
            
            # Filter by category
            category = self.request.query_params.get('category')
            if category:
                queryset = queryset.filter(category=category)
            
            # Filter by difficulty
            difficulty = self.request.query_params.get('difficulty')
            if difficulty:
                queryset = queryset.filter(default_difficulty=difficulty)
            
            # Filter by premium requirement
            premium_only = self.request.query_params.get('premium_only')
            if premium_only and premium_only.lower() == 'true':
                queryset = queryset.filter(requires_premium=True)
            elif premium_only and premium_only.lower() == 'false':
                queryset = queryset.filter(requires_premium=False)
            
            # Filter subscribed subjects only
            subscribed_only = self.request.query_params.get('subscribed_only')
            if subscribed_only and subscribed_only.lower() == 'true':
                queryset = queryset.filter(
                    user_settings__user=self.request.user
                ).distinct()
            
            return queryset
        
        # Use study content caching
        filter_hash = hashlib.md5(str(cache_key_params).encode()).hexdigest()
        queryset = cache_study_content(
            subject_id=0,  # 0 for subject list
            difficulty=filter_hash,
            value_func=get_queryset_func
        )
        
        if not isinstance(queryset, models.QuerySet):
            # If cached value is not a QuerySet, fallback to normal queryset
            queryset = get_queryset_func()
        
        return queryset.annotate(
            user_summary_count=Count(
                'summaries',
                filter=Q(summaries__user=self.request.user)
            )
        )
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action"""
        if self.action == 'create':
            return SubjectCreateSerializer
        return SubjectSerializer
    
    def get_permissions(self):
        """Get permissions based on action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]
    
    @study_schema(
        summary="과목 통계 조회",
        description="""
        특정 과목의 상세 통계 정보를 조회합니다.
        
        - 전체 학습자 수
        - 평균 평점
        - 사용자별 학습 진행 상황
        - 최근 활동 통계
        """,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'user_stats': {
                                'type': 'object',
                                'properties': {
                                    'user_summaries_count': {'type': 'integer'},
                                    'user_average_rating': {'type': 'number'},
                                    'user_study_time': {'type': 'integer'},
                                    'last_activity': {'type': 'string'}
                                }
                            },
                            'global_stats': {
                                'type': 'object',
                                'properties': {
                                    'total_learners': {'type': 'integer'},
                                    'total_summaries': {'type': 'integer'},
                                    'average_rating': {'type': 'number'},
                                    'recent_activity': {'type': 'integer'}
                                }
                            }
                        }
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                '과목 통계 응답',
                value={
                    'success': True,
                    'data': {
                        'user_stats': {
                            'user_summaries_count': 15,
                            'user_average_rating': 4.2,
                            'user_study_time': 240,
                            'last_activity': '2024-01-01T12:00:00Z'
                        },
                        'global_stats': {
                            'total_learners': 1245,
                            'total_summaries': 5680,
                            'average_rating': 4.5,
                            'recent_activity': 89
                        }
                    }
                },
                response_only=True
            )
        ]
    )
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get detailed subject statistics"""
        subject = self.get_object()
        
        # Get user-specific statistics
        user_stats = {
            'user_summaries_count': StudySummary.objects.filter(
                user=request.user, subject=subject
            ).count(),
            'user_read_summaries': StudySummary.objects.filter(
                user=request.user, subject=subject, is_read=True
            ).count(),
            'user_average_rating': StudySummary.objects.filter(
                user=request.user, subject=subject, user_rating__isnull=False
            ).aggregate(avg_rating=Avg('user_rating'))['avg_rating'] or 0.0,
            'has_settings': StudySettings.objects.filter(
                user=request.user, subject=subject
            ).exists()
        }
        
        # Combine with subject statistics
        stats = subject.get_statistics()
        stats.update(user_stats)
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def categories(self, request):
        """Get available categories with counts"""
        categories = Subject.objects.filter(is_active=True).values(
            'category'
        ).annotate(
            count=Count('id'),
            display_name=models.F('category')
        ).order_by('category')
        
        # Add display names
        category_choices = dict(Subject.CATEGORY_CHOICES)
        for cat in categories:
            cat['display_name'] = category_choices.get(cat['category'], cat['category'])
        
        return Response(list(categories))
    
    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get popular subjects"""
        limit = int(request.query_params.get('limit', 10))
        
        popular_subjects = Subject.objects.filter(
            is_active=True
        ).order_by(
            '-total_learners', '-average_rating'
        )[:limit]
        
        serializer = self.get_serializer(popular_subjects, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="개인화된 과목 추천",
        description="사용자의 학습 스타일과 선호도를 기반으로 과목을 추천합니다.",
        parameters=[
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="추천 개수 제한 (기본값: 5)"
            )
        ]
    )
    @action(detail=False, methods=['get'])
    def personalized_recommendations(self, request):
        """개인화된 과목 추천"""
        try:
            limit = int(request.query_params.get('limit', 5))
            
            # 개인화 추천 엔진 사용
            recommendations = get_personalized_content_recommendations(
                request.user.id, 
                subject_id=None,  # 모든 과목 대상
                limit=limit
            )
            
            # 추천된 과목 ID 추출
            recommended_subject_ids = []
            for rec in recommendations:
                if rec.content_id.startswith('subject_'):
                    subject_id = int(rec.content_id.replace('subject_', ''))
                    recommended_subject_ids.append(subject_id)
            
            # 실제 과목 객체 조회
            if recommended_subject_ids:
                subjects = Subject.objects.filter(
                    id__in=recommended_subject_ids, 
                    is_active=True
                ).order_by(
                    models.Case(*[
                        models.When(id=subject_id, then=pos) 
                        for pos, subject_id in enumerate(recommended_subject_ids)
                    ])
                )
                
                serializer = self.get_serializer(subjects, many=True)
                
                # 추천 이유도 함께 제공
                subject_data = serializer.data
                for i, subject in enumerate(subject_data):
                    if i < len(recommendations):
                        subject['personalization_reason'] = recommendations[i].personalization_reason
                        subject['relevance_score'] = recommendations[i].relevance_score
                
                return Response({
                    'recommendations': subject_data,
                    'total_count': len(subject_data),
                    'personalization_applied': True
                })
            else:
                # 추천이 없는 경우 인기 과목 반환
                fallback_subjects = Subject.objects.filter(
                    is_active=True
                ).order_by('-total_learners')[:limit]
                
                serializer = self.get_serializer(fallback_subjects, many=True)
                return Response({
                    'recommendations': serializer.data,
                    'total_count': len(serializer.data),
                    'personalization_applied': False,
                    'fallback_reason': '개인화 데이터 부족으로 인기 과목을 추천합니다.'
                })
                
        except Exception as e:
            logger.error(f"개인화 추천 실패 - 사용자 {request.user.id}: {e}")
            return Response({
                'error': '추천 생성 중 오류가 발생했습니다.',
                'error_type': 'system_error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class StudySettingsViewSet(viewsets.ModelViewSet):
    """Enhanced StudySettings ViewSet with validation and optimization"""
    
    serializer_class = StudySettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['subject__category', 'difficulty_level', 'preferred_ai_model']
    ordering_fields = ['created_at', 'last_used_at', 'updated_at']
    ordering = ['-last_used_at']
    
    def get_queryset(self):
        """Get user's study settings with related data"""
        return StudySettings.objects.filter(
            user=self.request.user
        ).select_related('subject').prefetch_related(
            'subject__summaries'
        )
    
    def perform_create(self, serializer):
        """Create settings and update subject learner count"""
        settings = serializer.save(user=self.request.user)
        
        # Increment subject learner count
        settings.subject.increment_learner_count()
        
        logger.info(f"Study settings created for user {self.request.user.email}, "
                   f"subject {settings.subject.name}")
    
    def perform_update(self, serializer):
        """Update settings and mark as used"""
        settings = serializer.save()
        settings.update_last_used()
        
        logger.info(f"Study settings updated for user {self.request.user.email}, "
                   f"subject {settings.subject.name}")
    
    @action(detail=True, methods=['post'])
    def test_notification_time(self, request, pk=None):
        """Test if notification time is valid"""
        settings = self.get_object()
        time_str = request.data.get('time')
        
        if not time_str:
            return Response(
                {'error': '시간을 입력해주세요.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            hour, minute = time_str.split(':')
            hour, minute = int(hour), int(minute)
            
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
            
            return Response({
                'valid': True,
                'formatted_time': f"{hour:02d}:{minute:02d}",
                'message': '유효한 시간 형식입니다.'
            })
            
        except (ValueError, AttributeError):
            return Response({
                'valid': False,
                'error': '잘못된 시간 형식입니다. HH:MM 형식으로 입력해주세요.'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def ai_config(self, request, pk=None):
        """Get AI generation configuration"""
        settings = self.get_object()
        return Response(settings.get_ai_generation_config())
    
    @action(detail=False, methods=['get'])
    def bulk_update_notification_times(self, request):
        """Bulk update notification times for all user settings"""
        times = request.query_params.getlist('times')
        
        if not times:
            return Response(
                {'error': '알림 시간을 입력해주세요.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        updated_count = 0
        for settings in self.get_queryset():
            settings.notification_times = times
            settings.save(update_fields=['notification_times'])
            updated_count += 1
        
        return Response({
            'message': f'{updated_count}개의 설정이 업데이트되었습니다.',
            'updated_count': updated_count
        })


class StudySummaryViewSet(viewsets.ModelViewSet):
    """Enhanced StudySummary ViewSet with filtering and interactions"""
    
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = StudySummaryFilter
    search_fields = ['title', 'content', 'topics_covered', 'tags']
    ordering_fields = ['generated_at', 'user_rating', 'reading_time']
    ordering = ['-generated_at']
    pagination_class = StudyPagination
    
    def get_queryset(self):
        """Get user's summaries with optimized queries"""
        queryset = StudySummary.objects.filter(
            user=self.request.user
        ).select_related('subject').prefetch_related('related_summaries')
        
        # Filter by read status
        read_status = self.request.query_params.get('read_status')
        if read_status == 'read':
            queryset = queryset.filter(is_read=True)
        elif read_status == 'unread':
            queryset = queryset.filter(is_read=False)
        
        # Filter by bookmark status
        bookmarked = self.request.query_params.get('bookmarked')
        if bookmarked and bookmarked.lower() == 'true':
            queryset = queryset.filter(is_bookmarked=True)
        
        # Filter by rating
        min_rating = self.request.query_params.get('min_rating')
        if min_rating:
            try:
                queryset = queryset.filter(user_rating__gte=int(min_rating))
            except ValueError:
                pass
        
        return queryset
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action"""
        if self.action == 'retrieve':
            return StudySummaryDetailSerializer
        return StudySummarySerializer
    
    def get_permissions(self):
        """Only allow reading, rating, and bookmarking"""
        if self.action in ['create', 'destroy']:
            return [permissions.IsAdminUser()]
        elif self.action in ['update', 'partial_update']:
            # Only allow updating rating, feedback, and bookmark status
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]
    
    def update(self, request, *args, **kwargs):
        """Limited update - only rating, feedback, and bookmark"""
        instance = self.get_object()
        allowed_fields = ['user_rating', 'user_feedback', 'is_bookmarked']
        
        # Filter request data to only allowed fields
        filtered_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        serializer = self.get_serializer(instance, data=filtered_data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Mark summary as read with enhanced tracking"""
        summary = self.get_object()
        reading_time = request.data.get('reading_time')
        
        if summary.is_read:
            return Response(
                {'message': '이미 읽음 처리된 요약입니다.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark as read with reading time
        summary.mark_as_read(reading_time)
        
        # Update progress with topics
        topics = summary.topics_covered if summary.topics_covered else []
        StudyProgressService.update_progress(
            user=request.user,
            subject=summary.subject,
            action_type='summary_read',
            topics=topics
        )
        
        logger.info(f"Summary marked as read by user {request.user.email}: {summary.title}")
        
        return Response({
            'message': '읽음 처리되었습니다.',
            'reading_stats': summary.get_reading_stats()
        })
    
    @action(detail=True, methods=['post'])
    def toggle_bookmark(self, request, pk=None):
        """Toggle bookmark status"""
        summary = self.get_object()
        is_bookmarked = summary.toggle_bookmark()
        
        logger.info(f"Summary bookmark toggled by user {request.user.email}: "
                   f"{summary.title} -> {is_bookmarked}")
        
        return Response({
            'is_bookmarked': is_bookmarked,
            'message': '북마크되었습니다.' if is_bookmarked else '북마크가 해제되었습니다.'
        })
    
    @action(detail=True, methods=['post'])
    def rate(self, request, pk=None):
        """Rate summary with feedback"""
        summary = self.get_object()
        rating = request.data.get('rating')
        feedback = request.data.get('feedback', '')
        
        if not rating or not isinstance(rating, int) or not (1 <= rating <= 5):
            return Response(
                {'error': '1-5 사이의 평점을 입력해주세요.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not summary.is_read:
            return Response(
                {'error': '읽은 요약만 평점을 줄 수 있습니다.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        summary.set_rating(rating, feedback)
        
        logger.info(f"Summary rated by user {request.user.email}: "
                   f"{summary.title} -> {rating}/5")
        
        return Response({
            'message': '평점이 등록되었습니다.',
            'rating': rating,
            'feedback': feedback
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get user's summary statistics"""
        queryset = self.get_queryset()
        
        stats = {
            'total_summaries': queryset.count(),
            'read_summaries': queryset.filter(is_read=True).count(),
            'unread_summaries': queryset.filter(is_read=False).count(),
            'bookmarked_summaries': queryset.filter(is_bookmarked=True).count(),
            'rated_summaries': queryset.filter(user_rating__isnull=False).count(),
            'average_rating_given': queryset.filter(
                user_rating__isnull=False
            ).aggregate(avg_rating=Avg('user_rating'))['avg_rating'] or 0.0,
            'total_reading_time': queryset.filter(
                reading_time__isnull=False
            ).aggregate(total_time=Sum('reading_time'))['total_time'] or 0,
            'subjects_studied': queryset.values('subject').distinct().count(),
            'recent_activity': queryset.filter(
                generated_at__gte=timezone.now() - timezone.timedelta(days=7)
            ).count()
        }
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def bookmarks(self, request):
        """Get bookmarked summaries"""
        bookmarked = self.get_queryset().filter(is_bookmarked=True)
        
        page = self.paginate_queryset(bookmarked)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(bookmarked, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent summaries"""
        days = int(request.query_params.get('days', 7))
        since_date = timezone.now() - timezone.timedelta(days=days)
        
        recent_summaries = self.get_queryset().filter(
            generated_at__gte=since_date
        )
        
        serializer = self.get_serializer(recent_summaries, many=True)
        return Response(serializer.data)


class StudyProgressViewSet(viewsets.ModelViewSet):
    """Enhanced StudyProgress ViewSet with analytics and insights"""
    
    serializer_class = StudyProgressSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = StudyProgressFilter
    ordering_fields = ['current_streak', 'total_summaries_read', 'last_activity_date']
    ordering = ['-last_activity_date']
    
    def get_queryset(self):
        """Get user's progress with related data"""
        return StudyProgress.objects.filter(
            user=self.request.user
        ).select_related('subject')
    
    def get_permissions(self):
        """Limited write permissions"""
        if self.action in ['create', 'destroy']:
            return [permissions.IsAdminUser()]
        elif self.action in ['update', 'partial_update']:
            # Only allow updating goals
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]
    
    def update(self, request, *args, **kwargs):
        """Limited update - only goals and preferences"""
        instance = self.get_object()
        allowed_fields = ['weekly_goal', 'monthly_goal', 'preferred_study_hours']
        
        filtered_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        serializer = self.get_serializer(instance, data=filtered_data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get comprehensive progress overview"""
        overview_data = StudyProgressService.get_comprehensive_progress(request.user)
        return Response(overview_data)
    
    @action(detail=True, methods=['get'])
    def weekly_report(self, request, pk=None):
        """Get weekly progress report"""
        progress = self.get_object()
        weekly_data = progress.get_weekly_progress()
        
        return Response({
            'subject': progress.subject.name,
            'weekly_progress': weekly_data,
            'insights': progress.get_learning_insights()
        })
    
    @action(detail=True, methods=['get'])
    def learning_insights(self, request, pk=None):
        """Get detailed learning insights"""
        progress = self.get_object()
        insights = progress.get_learning_insights()
        
        # Add recommendations
        recommendations = []
        
        if insights['study_consistency'] < 3:
            recommendations.append("연속 학습일을 늘려보세요. 꾸준한 학습이 중요합니다.")
        
        if insights['performance_trend'] < 3.0:
            recommendations.append("학습 내용의 난이도를 조정해보세요.")
        
        if insights['weekly_frequency'] < 3:
            recommendations.append("주간 학습 빈도를 높여보세요.")
        
        insights['recommendations'] = recommendations
        
        return Response(insights)
    
    @action(detail=False, methods=['get'])
    def leaderboard(self, request):
        """Get user's ranking among friends or global"""
        user_progress = self.get_queryset()
        
        # Calculate user's total stats
        user_total_summaries = sum(p.total_summaries_read for p in user_progress)
        user_max_streak = max((p.current_streak for p in user_progress), default=0)
        
        # Get ranking data (simplified)
        ranking_data = {
            'user_summaries': user_total_summaries,
            'user_max_streak': user_max_streak,
            'subjects_count': user_progress.count(),
            'rank_by_summaries': 'N/A',  # Would need global comparison
            'rank_by_streak': 'N/A',     # Would need global comparison
            'percentile': 'N/A'          # Would need global comparison
        }
        
        return Response(ranking_data)
    
    @action(detail=True, methods=['post'])
    def update_goals(self, request, pk=None):
        """Update study goals"""
        progress = self.get_object()
        weekly_goal = request.data.get('weekly_goal')
        monthly_goal = request.data.get('monthly_goal')
        
        if weekly_goal is not None:
            if not isinstance(weekly_goal, int) or weekly_goal < 1:
                return Response(
                    {'error': '주간 목표는 1 이상이어야 합니다.'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            progress.weekly_goal = weekly_goal
        
        if monthly_goal is not None:
            if not isinstance(monthly_goal, int) or monthly_goal < 1:
                return Response(
                    {'error': '월간 목표는 1 이상이어야 합니다.'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            progress.monthly_goal = monthly_goal
        
        progress.save(update_fields=['weekly_goal', 'monthly_goal'])
        
        return Response({
            'message': '목표가 업데이트되었습니다.',
            'weekly_goal': progress.weekly_goal,
            'monthly_goal': progress.monthly_goal
        })


class StudyGoalViewSet(viewsets.ModelViewSet):
    """StudyGoal ViewSet for managing user study goals"""
    
    serializer_class = StudyGoalSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['goal_type', 'status', 'subject']
    ordering_fields = ['start_date', 'end_date', 'created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get user's study goals"""
        return StudyGoal.objects.filter(
            user=self.request.user
        ).select_related('subject')
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark goal as completed"""
        goal = self.get_object()
        
        if goal.status == 'completed':
            return Response(
                {'error': '이미 완료된 목표입니다.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not goal.is_completed():
            return Response(
                {'error': '목표 달성 조건이 충족되지 않았습니다.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        goal.status = 'completed'
        goal.completed_at = timezone.now()
        goal.save(update_fields=['status', 'completed_at'])
        
        return Response({
            'message': '목표가 완료되었습니다!',
            'completed_at': goal.completed_at.isoformat(),
            'progress': goal.calculate_progress()
        })
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active goals"""
        active_goals = self.get_queryset().filter(status='active')
        serializer = self.get_serializer(active_goals, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def completed(self, request):
        """Get completed goals"""
        completed_goals = self.get_queryset().filter(status='completed')
        serializer = self.get_serializer(completed_goals, many=True)
        return Response(serializer.data)


class GenerateSummaryView(generics.GenericAPIView):
    """Enhanced Summary Generation View with better error handling"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Generate study summary with comprehensive validation"""
        subject_id = request.data.get('subject_id')
        custom_prompt = request.data.get('custom_prompt')
        
        # Validation
        if not subject_id:
            return Response({
                'error': '과목을 선택해주세요.',
                'field': 'subject_id'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            subject_id = int(subject_id)
        except (ValueError, TypeError):
            return Response({
                'error': '올바른 과목 ID를 입력해주세요.',
                'field': 'subject_id'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if subject exists
        try:
            subject = Subject.objects.get(id=subject_id, is_active=True)
        except Subject.DoesNotExist:
            return Response({
                'error': '존재하지 않거나 비활성화된 과목입니다.',
                'field': 'subject_id'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check premium requirements
        if subject.requires_premium and not request.user.profile.is_premium:
            return Response({
                'error': '프리미엄 구독이 필요한 과목입니다.',
                'requires_premium': True
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            # Generate summary with advanced caching
            summary_service = StudySummaryService()
            start_time = timezone.now()
            
            # Create cache key for AI response
            prompt_data = {
                'subject_id': subject_id,
                'custom_prompt': custom_prompt or '',
                'user_preferences': request.user.learning_language if hasattr(request.user, 'learning_language') else 'ko'
            }
            prompt_hash = hashlib.md5(str(prompt_data).encode()).hexdigest()
            
            # Try to get from AI response cache first
            def generate_summary_func():
                return summary_service.generate_summary(
                    user=request.user,
                    subject_id=subject_id,
                    custom_prompt=custom_prompt
                )
            
            summary = cache_ai_response(
                prompt_hash=prompt_hash,
                model='openai',  # or get from settings
                value_func=generate_summary_func
            )
            
            generation_time = (timezone.now() - start_time).total_seconds()
            
            # Log successful generation
            logger.info(f"Summary generated successfully for user {request.user.email}, "
                       f"subject {subject.name}, time: {generation_time:.2f}s")
            
            # Track summary generation event
            track_user_event(EventType.SUMMARY_GENERATED, request.user.id, {
                'subject_id': subject_id,
                'subject_name': subject.name,
                'generation_time': generation_time,
                'custom_prompt_used': bool(custom_prompt)
            })
            
            # Increment subject summary count
            subject.increment_summary_count()
            
            # Update learning pattern with new activity
            try:
                activity_data = {
                    'activity_type': 'summary_generation',
                    'duration': int(generation_time / 60),  # 분 단위
                    'completion_rate': 1.0,  # 완료됨
                    'content_type': 'text',
                    'subject_id': subject_id,
                    'difficulty': getattr(summary, 'difficulty_level', 'intermediate'),
                    'performance_score': 0.8,  # 기본 성과 점수
                }
                update_learning_pattern(request.user.id, activity_data)
            except Exception as pattern_error:
                logger.warning(f"학습 패턴 업데이트 실패: {pattern_error}")
            
            return Response({
                'summary': StudySummarySerializer(summary, context={'request': request}).data,
                'message': '학습 요약이 생성되었습니다.',
                'generation_time': generation_time,
                'subject_name': subject.name
            }, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            # User-related errors (limits, validation)
            logger.warning(f"User error in summary generation for {request.user.email}: {str(e)}")
            return Response({
                'error': str(e),
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            # System errors
            logger.error(f"System error in summary generation for {request.user.email}: {str(e)}")
            return Response({
                'error': '요약 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
                'error_type': 'system_error',
                'details': str(e) if request.user.is_staff else None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get(self, request):
        """Get generation limits and usage info"""
        try:
            # Get user's usage statistics
            summary_service = StudySummaryService()
            usage_stats = summary_service.get_usage_statistics(request.user)
            
            # Get today's usage
            today = timezone.now().date()
            today_summaries = StudySummary.objects.filter(
                user=request.user,
                generated_at__date=today
            ).count()
            
            # Get user's daily limit (from most permissive settings)
            max_daily_limit = StudySettings.objects.filter(
                user=request.user
            ).aggregate(
                max_limit=models.Max('daily_summary_count')
            )['max_limit'] or 3
            
            return Response({
                'daily_usage': today_summaries,
                'daily_limit': max_daily_limit,
                'remaining_today': max(0, max_daily_limit - today_summaries),
                'usage_stats': usage_stats,
                'can_generate': today_summaries < max_daily_limit
            })
            
        except Exception as e:
            logger.error(f"Error getting generation info for {request.user.email}: {str(e)}")
            return Response({
                'error': '사용량 정보를 가져오는 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class StudyAnalyticsView(generics.GenericAPIView):
    """Study Analytics and Insights View"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get comprehensive study analytics"""
        try:
            # Time range
            days = int(request.query_params.get('days', 30))
            since_date = timezone.now() - timezone.timedelta(days=days)
            
            # User summaries in time range
            summaries = StudySummary.objects.filter(
                user=request.user,
                generated_at__gte=since_date
            ).select_related('subject')
            
            # User progress data
            progress_data = StudyProgress.objects.filter(
                user=request.user
            ).select_related('subject')
            
            # Calculate analytics
            analytics = {
                'time_range_days': days,
                'summary_analytics': {
                    'total_generated': summaries.count(),
                    'total_read': summaries.filter(is_read=True).count(),
                    'average_rating': summaries.filter(
                        user_rating__isnull=False
                    ).aggregate(avg=Avg('user_rating'))['avg'] or 0.0,
                    'subjects_studied': summaries.values('subject').distinct().count(),
                    'by_difficulty': {
                        level: summaries.filter(difficulty_level=level).count()
                        for level, _ in StudySummary.DIFFICULTY_CHOICES
                    },
                    'by_subject': [
                        {
                            'subject': s['subject__name'],
                            'count': s['count']
                        }
                        for s in summaries.values('subject__name').annotate(
                            count=Count('id')
                        ).order_by('-count')[:10]
                    ]
                },
                'progress_analytics': {
                    'total_subjects': progress_data.count(),
                    'max_streak': max((p.current_streak for p in progress_data), default=0),
                    'total_topics': len(set(
                        topic for p in progress_data for topic in p.topics_learned
                    )),
                    'subjects_with_goals': StudyGoal.objects.filter(
                        user=request.user, status='active'
                    ).count()
                },
                'insights': []
            }
            
            # Generate insights
            if analytics['summary_analytics']['total_generated'] > 0:
                read_rate = (analytics['summary_analytics']['total_read'] / 
                           analytics['summary_analytics']['total_generated']) * 100
                
                if read_rate < 50:
                    analytics['insights'].append({
                        'type': 'warning',
                        'message': f'읽기 완료율이 {read_rate:.1f}%입니다. 생성된 요약을 더 많이 읽어보세요.'
                    })
                elif read_rate > 80:
                    analytics['insights'].append({
                        'type': 'success',
                        'message': f'훌륭한 읽기 완료율 {read_rate:.1f}%를 유지하고 있습니다!'
                    })
            
            if analytics['progress_analytics']['max_streak'] > 7:
                analytics['insights'].append({
                    'type': 'success',
                    'message': f'연속 {analytics["progress_analytics"]["max_streak"]}일 학습! 꾸준함이 돋보입니다.'
                })
            elif analytics['progress_analytics']['max_streak'] < 3:
                analytics['insights'].append({
                    'type': 'info',
                    'message': '꾸준한 학습을 위해 매일 조금씩이라도 공부해보세요.'
                })
            
            return Response(analytics)
            
        except Exception as e:
            logger.error(f"Error getting analytics for {request.user.email}: {str(e)}")
            return Response({
                'error': '분석 데이터를 가져오는 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

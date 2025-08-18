from rest_framework import viewsets, generics, status, permissions, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.utils import timezone
from django.db import models, transaction
from django.db.models import Q, Count, Avg, Sum, Max, F
from django_filters.rest_framework import DjangoFilterBackend
from typing import Dict, Any, Optional, List
import logging
import random

from .models import (
    Quiz, QuizChoice, QuizAttempt, QuizSession, 
    QuizProgress, QuizCategory
)
from .serializers import (
    QuizSerializer, QuizDetailSerializer, QuizListSerializer, QuizCreateSerializer,
    QuizChoiceSerializer, QuizAttemptSerializer, QuizSessionSerializer,
    QuizProgressSerializer, QuizCategorySerializer, QuizStatisticsSerializer,
    QuizSessionSummarySerializer
)
from .filters import QuizFilter, QuizAttemptFilter, QuizSessionFilter
from .pagination import QuizPagination
from study.models import Subject
from studymate_api.metrics import (
    track_user_event, track_business_event, EventType
)

logger = logging.getLogger(__name__)


class QuizViewSet(viewsets.ModelViewSet):
    """Enhanced Quiz ViewSet with comprehensive functionality"""
    
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = QuizFilter
    search_fields = ['title', 'question', 'explanation', 'tags', 'topics_covered']
    ordering_fields = ['created_at', 'difficulty_level', 'points', 'success_rate', 'total_attempts']
    ordering = ['-created_at']
    pagination_class = QuizPagination
    
    def get_queryset(self):
        """Get filtered and optimized queryset"""
        queryset = Quiz.objects.filter(
            is_active=True,
            status='active'
        ).select_related('subject').prefetch_related('choices')
        
        # Filter by subject
        subject_id = self.request.query_params.get('subject')
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        
        # Filter by difficulty
        difficulty = self.request.query_params.get('difficulty')
        if difficulty:
            queryset = queryset.filter(difficulty_level=difficulty)
        
        # Filter by quiz type
        quiz_type = self.request.query_params.get('quiz_type')
        if quiz_type:
            queryset = queryset.filter(quiz_type=quiz_type)
        
        # Filter by user's capability (attempted/not attempted)
        attempted_filter = self.request.query_params.get('attempted')
        if attempted_filter:
            user_attempted_quizzes = QuizAttempt.objects.filter(
                user=self.request.user
            ).values_list('quiz_id', flat=True)
            
            if attempted_filter.lower() == 'true':
                queryset = queryset.filter(id__in=user_attempted_quizzes)
            elif attempted_filter.lower() == 'false':
                queryset = queryset.exclude(id__in=user_attempted_quizzes)
        
        # Filter premium content based on user subscription
        if not self.request.user.profile.is_premium:
            queryset = queryset.filter(requires_premium=False)
        
        return queryset.annotate(
            user_attempts_count=Count(
                'attempts',
                filter=Q(attempts__user=self.request.user)
            )
        )
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action"""
        if self.action == 'list':
            return QuizListSerializer
        elif self.action == 'retrieve':
            return QuizDetailSerializer
        elif self.action == 'create':
            return QuizCreateSerializer
        return QuizSerializer
    
    def get_permissions(self):
        """Get permissions based on action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]
    
    @action(detail=True, methods=['post'])
    def attempt(self, request, pk=None):
        """Submit answer for a quiz"""
        quiz = self.get_object()
        
        # Check if user can attempt this quiz
        if not quiz.allow_multiple_attempts:
            if QuizAttempt.objects.filter(user=request.user, quiz=quiz).exists():
                return Response(
                    {'error': '이 퀴즈는 중복 시도가 허용되지 않습니다.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Create attempt
        attempt_serializer = QuizAttemptSerializer(
            data=request.data,
            context={'request': request}
        )
        attempt_serializer.is_valid(raise_exception=True)
        attempt = attempt_serializer.save(quiz=quiz)
        
        # Update or create progress
        progress, created = QuizProgress.objects.get_or_create(
            user=request.user,
            subject=quiz.subject,
            defaults={'current_difficulty': quiz.difficulty_level}
        )
        progress.update_progress(attempt)
        
        # Prepare response with feedback
        response_data = {
            'attempt': attempt_serializer.data,
            'is_correct': attempt.is_correct,
            'explanation': quiz.explanation,
            'points_earned': attempt.total_points
        }
        
        if attempt.is_correct:
            response_data['message'] = '정답입니다!'
            response_data['bonus_info'] = {
                'time_bonus': attempt.bonus_points,
                'difficulty_bonus': 0  # Calculate if needed
            }
        else:
            response_data['message'] = '오답입니다. 해설을 확인해보세요.'
            correct_choices = quiz.get_correct_choices()
            response_data['correct_answers'] = [
                choice.choice_text for choice in correct_choices
            ]
        
        logger.info(f"Quiz attempt: {request.user.email} -> {quiz.title} ({'정답' if attempt.is_correct else '오답'})")
        
        # Track quiz attempt event
        track_user_event(EventType.QUIZ_ATTEMPTED, request.user.id, {
            'quiz_id': quiz.id,
            'quiz_title': quiz.title[:100],
            'quiz_type': quiz.quiz_type,
            'difficulty_level': quiz.difficulty_level,
            'is_correct': attempt.is_correct,
            'time_spent': attempt.time_spent_seconds,
            'points_earned': attempt.total_points
        })
        
        # Track completion if answer is correct
        if attempt.is_correct:
            track_user_event(EventType.QUIZ_COMPLETED, request.user.id, {
                'quiz_id': quiz.id,
                'quiz_title': quiz.title[:100],
                'difficulty_level': quiz.difficulty_level,
                'points_earned': attempt.total_points,
                'time_spent': attempt.time_spent_seconds
            })
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def hints(self, request, pk=None):
        """Get hints for a quiz"""
        quiz = self.get_object()
        hints = quiz.get_hints_list()
        
        # Track hint usage if part of an attempt
        session_id = request.query_params.get('session_id')
        if session_id:
            try:
                session = QuizSession.objects.get(id=session_id, user=request.user)
                # Could track hint usage here
            except QuizSession.DoesNotExist:
                pass
        
        return Response({
            'hints': hints,
            'hint_count': len(hints)
        })
    
    @action(detail=True, methods=['get'])
    def choices(self, request, pk=None):
        """Get quiz choices (optionally shuffled)"""
        quiz = self.get_object()
        shuffle = request.query_params.get('shuffle', 'true').lower() == 'true'
        
        choices = quiz.get_choices(shuffle=shuffle)
        serializer = QuizChoiceSerializer(choices, many=True)
        
        return Response({
            'choices': serializer.data,
            'shuffle_enabled': quiz.shuffle_choices
        })
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get detailed quiz statistics"""
        quiz = self.get_object()
        
        # Basic statistics
        stats = quiz.get_statistics()
        
        # User-specific statistics
        user_attempts = QuizAttempt.objects.filter(
            user=request.user,
            quiz=quiz
        )
        
        user_stats = {
            'user_attempts': user_attempts.count(),
            'user_correct': user_attempts.filter(is_correct=True).count(),
            'user_best_time': None,
            'user_average_time': None,
            'user_last_attempt': None
        }
        
        if user_attempts.exists():
            times = [a.time_spent_seconds for a in user_attempts if a.time_spent_seconds]
            if times:
                user_stats['user_best_time'] = min(times)
                user_stats['user_average_time'] = sum(times) / len(times)
            
            last_attempt = user_attempts.order_by('-attempted_at').first()
            user_stats['user_last_attempt'] = {
                'attempted_at': last_attempt.attempted_at,
                'is_correct': last_attempt.is_correct,
                'time_spent': last_attempt.time_spent_seconds
            }
        
        # Choice analytics (for staff only)
        choice_analytics = []
        if request.user.is_staff:
            for choice in quiz.choices.all():
                choice_analytics.append({
                    'choice_text': choice.choice_text,
                    'is_correct': choice.is_correct,
                    'selection_count': choice.selection_count,
                    'selection_percentage': choice.selection_percentage
                })
        
        return Response({
            'quiz_statistics': stats,
            'user_statistics': user_stats,
            'choice_analytics': choice_analytics
        })
    
    @action(detail=False, methods=['get'])
    def recommended(self, request):
        """Get recommended quizzes for user"""
        user_progress = QuizProgress.objects.filter(user=request.user)
        
        # Get user's preferred difficulty and subjects
        difficulty_levels = ['beginner', 'intermediate', 'advanced', 'expert']
        user_difficulties = list(user_progress.values_list('current_difficulty', flat=True))
        preferred_difficulty = max(user_difficulties, key=user_difficulties.count) if user_difficulties else 'beginner'
        
        # Get subjects user has studied
        studied_subjects = user_progress.values_list('subject_id', flat=True)
        
        # Build recommendation queryset
        recommendations = Quiz.objects.filter(
            is_active=True,
            status='active'
        ).exclude(
            id__in=QuizAttempt.objects.filter(user=request.user).values_list('quiz_id', flat=True)
        )
        
        # Prioritize user's subjects and difficulty
        subject_weight = Q(subject_id__in=studied_subjects)
        difficulty_weight = Q(difficulty_level=preferred_difficulty)
        
        recommendations = recommendations.annotate(
            recommendation_score=models.Case(
                models.When(subject_weight & difficulty_weight, then=models.Value(3)),
                models.When(subject_weight, then=models.Value(2)),
                models.When(difficulty_weight, then=models.Value(1)),
                default=models.Value(0),
                output_field=models.IntegerField()
            )
        ).order_by('-recommendation_score', '-success_rate')[:20]
        
        serializer = QuizListSerializer(recommendations, many=True, context={'request': request})
        
        return Response({
            'recommended_quizzes': serializer.data,
            'recommendation_basis': {
                'preferred_difficulty': preferred_difficulty,
                'studied_subjects_count': len(studied_subjects)
            }
        })
    
    @action(detail=False, methods=['get'])
    def random(self, request):
        """Get random quiz for practice"""
        subject_id = request.query_params.get('subject')
        difficulty = request.query_params.get('difficulty')
        
        queryset = self.get_queryset()
        
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        if difficulty:
            queryset = queryset.filter(difficulty_level=difficulty)
        
        # Exclude already attempted quizzes if requested
        exclude_attempted = request.query_params.get('exclude_attempted', 'false').lower() == 'true'
        if exclude_attempted:
            attempted_quiz_ids = QuizAttempt.objects.filter(
                user=request.user
            ).values_list('quiz_id', flat=True)
            queryset = queryset.exclude(id__in=attempted_quiz_ids)
        
        quiz_count = queryset.count()
        if quiz_count == 0:
            return Response(
                {'message': '조건에 맞는 퀴즈가 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get random quiz
        random_index = random.randint(0, quiz_count - 1)
        random_quiz = queryset[random_index]
        
        serializer = QuizDetailSerializer(random_quiz, context={'request': request})
        return Response(serializer.data)


class QuizAttemptViewSet(viewsets.ModelViewSet):
    """Quiz Attempt ViewSet for tracking user attempts"""
    
    serializer_class = QuizAttemptSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = QuizAttemptFilter
    ordering_fields = ['attempted_at', 'is_correct', 'points_earned']
    ordering = ['-attempted_at']
    pagination_class = QuizPagination
    
    def get_queryset(self):
        """Get user's quiz attempts with related data"""
        return QuizAttempt.objects.filter(
            user=self.request.user
        ).select_related('quiz', 'quiz__subject', 'selected_choice')
    
    def get_permissions(self):
        """Only allow reading and creating attempts"""
        if self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get user's attempt statistics"""
        attempts = self.get_queryset()
        
        total_attempts = attempts.count()
        correct_attempts = attempts.filter(is_correct=True).count()
        total_points = attempts.aggregate(total=Sum('points_earned'))['total'] or 0
        
        stats = {
            'total_attempts': total_attempts,
            'correct_attempts': correct_attempts,
            'accuracy': (correct_attempts / total_attempts) * 100 if total_attempts > 0 else 0,
            'total_points': total_points,
            'average_points': total_points / total_attempts if total_attempts > 0 else 0
        }
        
        # Statistics by difficulty
        by_difficulty = {}
        for difficulty, _ in Quiz.DIFFICULTY_CHOICES:
            difficulty_attempts = attempts.filter(quiz__difficulty_level=difficulty)
            difficulty_count = difficulty_attempts.count()
            difficulty_correct = difficulty_attempts.filter(is_correct=True).count()
            
            by_difficulty[difficulty] = {
                'total': difficulty_count,
                'correct': difficulty_correct,
                'accuracy': (difficulty_correct / difficulty_count) * 100 if difficulty_count > 0 else 0
            }
        
        # Recent performance (last 10 attempts)
        recent_attempts = attempts[:10]
        recent_performance = [
            {
                'quiz_title': attempt.quiz.title,
                'is_correct': attempt.is_correct,
                'points': attempt.total_points,
                'attempted_at': attempt.attempted_at
            }
            for attempt in recent_attempts
        ]
        
        return Response({
            'overall_statistics': stats,
            'by_difficulty': by_difficulty,
            'recent_performance': recent_performance
        })
    
    @action(detail=True, methods=['post'])
    def rate_difficulty(self, request, pk=None):
        """Rate the difficulty of an attempt"""
        attempt = self.get_object()
        rating = request.data.get('difficulty_rating')
        feedback = request.data.get('feedback', '')
        
        if not rating or not (1 <= int(rating) <= 5):
            return Response(
                {'error': '난이도 평점은 1-5 사이의 값이어야 합니다.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        attempt.difficulty_rating = int(rating)
        attempt.feedback = feedback
        attempt.save(update_fields=['difficulty_rating', 'feedback'])
        
        # Update quiz difficulty rating
        attempt.quiz.update_difficulty_rating(float(rating))
        
        return Response({
            'message': '난이도 평점이 등록되었습니다.',
            'difficulty_rating': attempt.difficulty_rating
        })


class QuizSessionViewSet(viewsets.ModelViewSet):
    """Quiz Session ViewSet for managing quiz sessions"""
    
    serializer_class = QuizSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = QuizSessionFilter
    ordering_fields = ['started_at', 'completed_at', 'score_percentage']
    ordering = ['-started_at']
    pagination_class = QuizPagination
    
    def get_queryset(self):
        """Get user's quiz sessions"""
        return QuizSession.objects.filter(
            user=self.request.user
        ).select_related('subject')
    
    def get_permissions(self):
        """Limited write permissions"""
        if self.action in ['destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start or resume a quiz session"""
        session = self.get_object()
        
        if session.status == 'completed':
            return Response(
                {'error': '이미 완료된 세션입니다.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if session.status == 'paused':
            session.resume_session()
            return Response({
                'message': '세션이 재개되었습니다.',
                'status': session.status
            })
        
        # Session is already active
        return Response({
            'message': '세션이 진행 중입니다.',
            'status': session.status,
            'remaining_questions': session.remaining_questions
        })
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause a quiz session"""
        session = self.get_object()
        
        if session.status != 'active':
            return Response(
                {'error': '진행 중인 세션만 일시정지할 수 있습니다.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        session.pause_session()
        
        return Response({
            'message': '세션이 일시정지되었습니다.',
            'status': session.status
        })
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete a quiz session"""
        session = self.get_object()
        
        if session.status == 'completed':
            return Response(
                {'error': '이미 완료된 세션입니다.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        session.complete_session()
        
        # Update progress
        progress, created = QuizProgress.objects.get_or_create(
            user=request.user,
            subject=session.subject
        )
        progress.total_sessions += 1
        progress.save(update_fields=['total_sessions'])
        
        # Generate session summary
        summary_serializer = QuizSessionSummarySerializer(session)
        
        return Response({
            'message': '세션이 완료되었습니다.',
            'session_summary': summary_serializer.data,
            'recommendations': {
                'next_difficulty': session.get_recommended_next_difficulty(),
                'continue_studying': session.score_percentage < 80,
                'review_topics': session.topics_covered if session.score_percentage < 60 else []
            }
        })
    
    @action(detail=True, methods=['get'])
    def next_quiz(self, request, pk=None):
        """Get next quiz for the session"""
        session = self.get_object()
        
        if session.status != 'active':
            return Response(
                {'error': '활성 상태의 세션만 퀴즈를 제공할 수 있습니다.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if session.remaining_questions <= 0:
            return Response(
                {'message': '목표 문제 수에 도달했습니다. 세션을 완료해주세요.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get available quizzes for this session
        available_quizzes = Quiz.objects.filter(
            subject=session.subject,
            is_active=True,
            status='active'
        )
        
        # Apply difficulty filter if set
        if session.difficulty_level:
            available_quizzes = available_quizzes.filter(
                difficulty_level=session.difficulty_level
            )
        
        # Exclude already attempted quizzes in this session
        session_quiz_ids = session.attempts.values_list('quiz_id', flat=True)
        available_quizzes = available_quizzes.exclude(id__in=session_quiz_ids)
        
        if not available_quizzes.exists():
            return Response(
                {'message': '더 이상 출제할 수 있는 퀴즈가 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Select random quiz
        quiz = random.choice(available_quizzes)
        serializer = QuizDetailSerializer(quiz, context={'request': request})
        
        return Response({
            'quiz': serializer.data,
            'session_info': {
                'remaining_questions': session.remaining_questions,
                'current_score': session.score_percentage,
                'time_spent': (timezone.now() - session.started_at).total_seconds() / 60
            }
        })
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get user's active sessions"""
        active_sessions = self.get_queryset().filter(
            status__in=['active', 'paused']
        )
        
        serializer = self.get_serializer(active_sessions, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        """Get user's session history with summaries"""
        completed_sessions = self.get_queryset().filter(
            status='completed'
        ).order_by('-completed_at')
        
        page = self.paginate_queryset(completed_sessions)
        if page is not None:
            serializer = QuizSessionSummarySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = QuizSessionSummarySerializer(completed_sessions, many=True)
        return Response(serializer.data)


class QuizProgressViewSet(viewsets.ReadOnlyModelViewSet):
    """Quiz Progress ViewSet for tracking user progress"""
    
    serializer_class = QuizProgressSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['total_points_earned', 'current_streak', 'last_activity_date']
    ordering = ['-last_activity_date']
    
    def get_queryset(self):
        """Get user's quiz progress"""
        return QuizProgress.objects.filter(
            user=self.request.user
        ).select_related('subject')
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get comprehensive progress overview"""
        progress_data = self.get_queryset()
        
        total_overview = {
            'total_subjects': progress_data.count(),
            'total_quizzes_attempted': sum(p.total_quizzes_attempted for p in progress_data),
            'total_quizzes_correct': sum(p.total_quizzes_correct for p in progress_data),
            'total_points_earned': sum(p.total_points_earned for p in progress_data),
            'max_streak': max((p.current_streak for p in progress_data), default=0),
            'average_accuracy': 0,
            'total_study_time_hours': 0,
            'subjects_progress': []
        }
        
        if total_overview['total_quizzes_attempted'] > 0:
            total_overview['average_accuracy'] = (
                total_overview['total_quizzes_correct'] / 
                total_overview['total_quizzes_attempted']
            ) * 100
        
        total_study_seconds = sum(p.total_study_time.total_seconds() for p in progress_data)
        total_overview['total_study_time_hours'] = total_study_seconds / 3600
        
        for progress in progress_data:
            subject_data = {
                'subject_name': progress.subject.name,
                'current_difficulty': progress.get_current_difficulty_display(),
                'accuracy': progress.overall_accuracy,
                'total_points': progress.total_points_earned,
                'current_streak': progress.current_streak,
                'last_activity': progress.last_activity_date
            }
            total_overview['subjects_progress'].append(subject_data)
        
        return Response(total_overview)
    
    @action(detail=True, methods=['get'])
    def insights(self, request, pk=None):
        """Get detailed learning insights for subject"""
        progress = self.get_object()
        insights = progress.get_recommendations()
        
        # Add more detailed insights
        detailed_insights = {
            'recommendations': insights,
            'strengths': [],
            'areas_for_improvement': [],
            'study_patterns': {},
            'achievement_progress': {}
        }
        
        # Analyze strengths and weaknesses
        if progress.overall_accuracy >= 80:
            detailed_insights['strengths'].append('높은 정답률 유지')
        if progress.current_streak >= 10:
            detailed_insights['strengths'].append('우수한 연속 정답 기록')
        
        if progress.overall_accuracy < 60:
            detailed_insights['areas_for_improvement'].append('정답률 향상 필요')
        if progress.current_streak < 3:
            detailed_insights['areas_for_improvement'].append('꾸준한 학습 습관 형성 필요')
        
        # Study patterns
        if progress.recent_performance:
            recent_accuracy = sum(
                1 for p in progress.recent_performance[:10] if p['is_correct']
            ) / min(len(progress.recent_performance), 10)
            
            detailed_insights['study_patterns'] = {
                'recent_accuracy': recent_accuracy * 100,
                'improvement_trend': recent_accuracy > (progress.overall_accuracy / 100),
                'consistency_score': min(progress.current_streak / 20, 1.0)
            }
        
        return Response(detailed_insights)


class QuizCategoryViewSet(viewsets.ModelViewSet):
    """Quiz Category ViewSet for managing categories"""
    
    serializer_class = QuizCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['order', 'name', 'created_at']
    ordering = ['order', 'name']
    
    def get_queryset(self):
        """Get active categories"""
        return QuizCategory.objects.filter(is_active=True)
    
    def get_permissions(self):
        """Admin only for create/update/delete"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get category tree structure"""
        categories = self.get_queryset().filter(parent__isnull=True)
        
        def build_tree(category):
            children = category.subcategories.filter(is_active=True).order_by('order', 'name')
            return {
                'id': category.id,
                'name': category.name,
                'icon': category.icon,
                'color_code': category.color_code,
                'quiz_count': category.get_quiz_count(),
                'children': [build_tree(child) for child in children]
            }
        
        tree = [build_tree(cat) for cat in categories]
        
        return Response({'categories': tree})


class QuizAnalyticsView(generics.GenericAPIView):
    """Quiz Analytics and Statistics View"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get comprehensive quiz analytics"""
        user = request.user
        days = int(request.query_params.get('days', 30))
        since_date = timezone.now() - timezone.timedelta(days=days)
        
        # User's quiz attempts in time range
        attempts = QuizAttempt.objects.filter(
            user=user,
            attempted_at__gte=since_date
        ).select_related('quiz', 'quiz__subject')
        
        # Basic statistics
        total_attempts = attempts.count()
        correct_attempts = attempts.filter(is_correct=True).count()
        total_points = attempts.aggregate(total=Sum('points_earned'))['total'] or 0
        
        analytics = {
            'time_range_days': days,
            'overview': {
                'total_attempts': total_attempts,
                'correct_attempts': correct_attempts,
                'accuracy': (correct_attempts / total_attempts) * 100 if total_attempts > 0 else 0,
                'total_points': total_points,
                'unique_quizzes': attempts.values('quiz').distinct().count(),
                'subjects_studied': attempts.values('quiz__subject').distinct().count()
            },
            'by_difficulty': {},
            'by_subject': [],
            'by_quiz_type': {},
            'daily_activity': [],
            'insights': []
        }
        
        # Statistics by difficulty
        for difficulty, display_name in Quiz.DIFFICULTY_CHOICES:
            difficulty_attempts = attempts.filter(quiz__difficulty_level=difficulty)
            count = difficulty_attempts.count()
            correct = difficulty_attempts.filter(is_correct=True).count()
            
            analytics['by_difficulty'][difficulty] = {
                'display_name': display_name,
                'total': count,
                'correct': correct,
                'accuracy': (correct / count) * 100 if count > 0 else 0
            }
        
        # Statistics by subject
        subject_stats = attempts.values(
            'quiz__subject__name'
        ).annotate(
            total=Count('id'),
            correct=Count('id', filter=Q(is_correct=True)),
            points=Sum('points_earned')
        ).order_by('-total')[:10]
        
        analytics['by_subject'] = [
            {
                'subject': stat['quiz__subject__name'],
                'total': stat['total'],
                'correct': stat['correct'],
                'accuracy': (stat['correct'] / stat['total']) * 100,
                'points': stat['points'] or 0
            }
            for stat in subject_stats
        ]
        
        # Statistics by quiz type
        for quiz_type, display_name in Quiz.QUIZ_TYPE_CHOICES:
            type_attempts = attempts.filter(quiz__quiz_type=quiz_type)
            count = type_attempts.count()
            correct = type_attempts.filter(is_correct=True).count()
            
            analytics['by_quiz_type'][quiz_type] = {
                'display_name': display_name,
                'total': count,
                'correct': correct,
                'accuracy': (correct / count) * 100 if count > 0 else 0
            }
        
        # Generate insights
        if analytics['overview']['accuracy'] >= 85:
            analytics['insights'].append({
                'type': 'success',
                'message': f"우수한 정답률 {analytics['overview']['accuracy']:.1f}%를 유지하고 있습니다!"
            })
        elif analytics['overview']['accuracy'] < 60:
            analytics['insights'].append({
                'type': 'warning',
                'message': f"정답률이 {analytics['overview']['accuracy']:.1f}%입니다. 더 많은 연습이 필요해 보입니다."
            })
        
        if analytics['overview']['total_attempts'] < 10:
            analytics['insights'].append({
                'type': 'info',
                'message': "더 많은 퀴즈를 풀어보세요. 꾸준한 연습이 실력 향상의 지름길입니다."
            })
        
        return Response(analytics)


class QuizRecommendationView(generics.GenericAPIView):
    """Quiz Recommendation Engine"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get personalized quiz recommendations"""
        user = request.user
        
        # Get user's progress and preferences
        user_progress = QuizProgress.objects.filter(user=user)
        recent_attempts = QuizAttempt.objects.filter(
            user=user
        ).order_by('-attempted_at')[:20]
        
        recommendations = {
            'adaptive_quizzes': [],
            'review_quizzes': [],
            'challenge_quizzes': [],
            'new_topics': [],
            'recommendation_reasons': []
        }
        
        # Adaptive recommendations based on performance
        if user_progress.exists():
            for progress in user_progress:
                if progress.overall_accuracy >= 85:
                    # User is doing well, recommend harder content
                    difficulty_levels = ['beginner', 'intermediate', 'advanced', 'expert']
                    current_index = difficulty_levels.index(progress.current_difficulty)
                    if current_index < len(difficulty_levels) - 1:
                        next_difficulty = difficulty_levels[current_index + 1]
                        
                        challenge_quizzes = Quiz.objects.filter(
                            subject=progress.subject,
                            difficulty_level=next_difficulty,
                            is_active=True
                        ).exclude(
                            id__in=QuizAttempt.objects.filter(user=user).values_list('quiz_id', flat=True)
                        )[:5]
                        
                        for quiz in challenge_quizzes:
                            recommendations['challenge_quizzes'].append({
                                'id': quiz.id,
                                'title': quiz.title,
                                'difficulty': quiz.get_difficulty_level_display(),
                                'points': quiz.points,
                                'reason': f"{progress.subject.name}에서 우수한 성과를 보이고 있어 더 어려운 문제를 추천합니다."
                            })
                
                elif progress.overall_accuracy < 70:
                    # User needs review
                    if progress.weak_topics:
                        review_quizzes = Quiz.objects.filter(
                            subject=progress.subject,
                            difficulty_level=progress.current_difficulty,
                            topics_covered__overlap=progress.weak_topics,
                            is_active=True
                        )[:5]
                        
                        for quiz in review_quizzes:
                            recommendations['review_quizzes'].append({
                                'id': quiz.id,
                                'title': quiz.title,
                                'topics': quiz.topics_covered,
                                'reason': "취약한 주제를 보강하기 위한 복습 문제입니다."
                            })
        
        # New topic recommendations
        attempted_subjects = set(user_progress.values_list('subject_id', flat=True))
        all_subjects = Subject.objects.filter(is_active=True)
        
        for subject in all_subjects:
            if subject.id not in attempted_subjects:
                intro_quizzes = Quiz.objects.filter(
                    subject=subject,
                    difficulty_level='beginner',
                    is_active=True
                )[:3]
                
                if intro_quizzes.exists():
                    recommendations['new_topics'].append({
                        'subject_id': subject.id,
                        'subject_name': subject.name,
                        'intro_quizzes': [
                            {
                                'id': quiz.id,
                                'title': quiz.title,
                                'points': quiz.points
                            }
                            for quiz in intro_quizzes
                        ],
                        'reason': f"{subject.name} 분야를 새롭게 시작해보세요."
                    })
        
        return Response(recommendations)
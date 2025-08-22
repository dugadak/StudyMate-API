from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.db.models import Sum, Avg, Count, Q, F
from datetime import datetime, timedelta
from typing import Dict, List, Any

from .models import Dashboard, StudyPattern, DailyGoal
from .serializers import (
    DashboardSerializer, StudyPatternSerializer,
    DailyGoalSerializer, UpdateGoalSerializer, StatsOverviewSerializer
)


class DashboardViewSet(viewsets.ViewSet):
    """홈 대시보드 관련 API"""
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """대시보드 메인 데이터 조회"""
        user = request.user
        dashboard, created = Dashboard.objects.get_or_create(user=user)
        
        # 오늘의 목표 확인 및 생성
        today = timezone.now().date()
        daily_goal, _ = DailyGoal.objects.get_or_create(
            user=user,
            date=today,
            defaults={
                'target_minutes': dashboard.daily_goal_minutes,
                'target_quizzes': 5
            }
        )
        
        # 대시보드 데이터 시리얼라이즈
        dashboard_data = DashboardSerializer(dashboard).data
        goal_data = DailyGoalSerializer(daily_goal).data
        
        return Response({
            'dashboard': dashboard_data,
            'today_goal': goal_data,
            'user_info': {
                'email': user.email,
                'username': user.username,
                'is_premium': hasattr(user, 'subscription') and user.subscription.is_active
            }
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """통계 개요 조회"""
        user = request.user
        period = request.query_params.get('period', '7')  # 7, 30, all
        
        # 기간 설정
        today = timezone.now().date()
        if period == '7':
            start_date = today - timedelta(days=7)
        elif period == '30':
            start_date = today - timedelta(days=30)
        else:
            start_date = None
        
        # 학습 패턴 조회
        patterns_query = StudyPattern.objects.filter(user=user)
        if start_date:
            patterns_query = patterns_query.filter(date__gte=start_date)
        
        patterns = patterns_query.order_by('-date', '-hour')
        
        # 패턴 분석
        pattern_data = []
        for pattern in patterns[:100]:  # 최대 100개
            pattern_data.append({
                'date': pattern.date,
                'hour': pattern.hour,
                'minutes': pattern.study_minutes,
                'quizzes': pattern.quiz_count,
                'accuracy': float(pattern.accuracy_rate) if pattern.accuracy_rate else 0,
                'focus': pattern.focus_score
            })
        
        # 추세 분석
        daily_stats = patterns_query.values('date').annotate(
            total_minutes=Sum('study_minutes'),
            total_quizzes=Sum('quiz_count'),
            avg_accuracy=Avg('accuracy_rate'),
            avg_focus=Avg('focus_score')
        ).order_by('date')
        
        trends = {
            'daily_minutes': [{'date': s['date'], 'value': s['total_minutes']} for s in daily_stats],
            'daily_quizzes': [{'date': s['date'], 'value': s['total_quizzes']} for s in daily_stats],
            'daily_accuracy': [{'date': s['date'], 'value': float(s['avg_accuracy'] or 0)} for s in daily_stats],
        }
        
        # 집중 시간 분석 (시간대별)
        hourly_stats = patterns_query.values('hour').annotate(
            total_minutes=Sum('study_minutes'),
            avg_focus=Avg('focus_score')
        ).order_by('hour')
        
        focus_time = {
            'best_hours': list(hourly_stats.order_by('-total_minutes')[:3].values('hour', 'total_minutes')),
            'hourly_distribution': list(hourly_stats.values('hour', 'total_minutes', 'avg_focus'))
        }
        
        # 히트맵 데이터 생성
        heatmap_data = []
        for pattern in patterns_query.values('date', 'hour', 'study_minutes'):
            intensity = min(100, pattern['study_minutes'] * 2)  # 50분 = 100% 강도
            heatmap_data.append({
                'date': pattern['date'],
                'hour': pattern['hour'],
                'intensity': intensity
            })
        
        return Response({
            'patterns': pattern_data,
            'trends': trends,
            'focus_time': focus_time,
            'heatmap': heatmap_data
        })
    
    @action(detail=False, methods=['post'])
    def update_goal(self, request):
        """일일 목표 업데이트"""
        serializer = UpdateGoalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user
        today = timezone.now().date()
        
        # 대시보드 목표 업데이트
        dashboard, _ = Dashboard.objects.get_or_create(user=user)
        dashboard.daily_goal_minutes = serializer.validated_data['target_minutes']
        dashboard.save()
        
        # 오늘 목표 업데이트
        daily_goal, _ = DailyGoal.objects.get_or_create(
            user=user,
            date=today
        )
        daily_goal.target_minutes = serializer.validated_data['target_minutes']
        daily_goal.target_quizzes = serializer.validated_data['target_quizzes']
        daily_goal.save()
        
        return Response({
            'message': '목표가 업데이트되었습니다.',
            'goal': DailyGoalSerializer(daily_goal).data
        })
    
    @action(detail=False, methods=['post'])
    def log_activity(self, request):
        """학습 활동 기록"""
        activity_type = request.data.get('type')  # 'study' or 'quiz'
        minutes = request.data.get('minutes', 0)
        quiz_score = request.data.get('quiz_score', None)
        
        user = request.user
        today = timezone.now().date()
        current_hour = timezone.now().hour
        
        # 대시보드 업데이트
        dashboard, _ = Dashboard.objects.get_or_create(user=user)
        
        if activity_type == 'study':
            dashboard.total_study_minutes += minutes
            dashboard.daily_completed_minutes += minutes
            dashboard.update_streak()
        elif activity_type == 'quiz':
            dashboard.total_quizzes_taken += 1
            if quiz_score is not None:
                # 평균 정답률 업데이트 (단순 이동평균)
                weight = 0.9 if dashboard.total_quizzes_taken > 1 else 0
                dashboard.average_accuracy = (
                    dashboard.average_accuracy * weight + quiz_score * (1 - weight)
                )
            dashboard.last_quiz_date = today
        
        dashboard.save()
        
        # 학습 패턴 기록
        pattern, created = StudyPattern.objects.get_or_create(
            user=user,
            date=today,
            hour=current_hour,
            defaults={'study_minutes': 0, 'quiz_count': 0}
        )
        
        if activity_type == 'study':
            pattern.study_minutes += minutes
        elif activity_type == 'quiz':
            pattern.quiz_count += 1
            if quiz_score is not None:
                if pattern.accuracy_rate:
                    pattern.accuracy_rate = (pattern.accuracy_rate + quiz_score) / 2
                else:
                    pattern.accuracy_rate = quiz_score
        
        pattern.save()
        
        # 일일 목표 업데이트
        daily_goal, _ = DailyGoal.objects.get_or_create(
            user=user,
            date=today,
            defaults={
                'target_minutes': dashboard.daily_goal_minutes,
                'target_quizzes': 5
            }
        )
        
        if activity_type == 'study':
            daily_goal.completed_minutes += minutes
        elif activity_type == 'quiz':
            daily_goal.completed_quizzes += 1
        
        daily_goal.check_achievement()
        
        return Response({
            'message': '활동이 기록되었습니다.',
            'dashboard': DashboardSerializer(dashboard).data,
            'goal': DailyGoalSerializer(daily_goal).data
        })
from rest_framework import serializers
from .models import Dashboard, StudyPattern, DailyGoal
from django.utils import timezone
from datetime import datetime, timedelta
from typing import Dict, List, Any


class DashboardSerializer(serializers.ModelSerializer):
    """대시보드 시리얼라이저"""
    
    progress_percentage = serializers.SerializerMethodField()
    weekly_stats = serializers.SerializerMethodField()
    
    class Meta:
        model = Dashboard
        fields = [
            'streak_days',
            'total_study_minutes',
            'total_quizzes_taken',
            'average_accuracy',
            'achievement_score',
            'daily_completed_minutes',
            'daily_goal_minutes',
            'progress_percentage',
            'weekly_stats',
            'last_study_date',
            'last_quiz_date',
        ]
        read_only_fields = fields
    
    def get_progress_percentage(self, obj) -> int:
        """오늘의 진도율 계산"""
        return obj.get_progress_percentage()
    
    def get_weekly_stats(self, obj) -> Dict[str, Any]:
        """주간 통계 계산"""
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        
        patterns = StudyPattern.objects.filter(
            user=obj.user,
            date__gte=week_ago,
            date__lte=today
        )
        
        total_minutes = sum(p.study_minutes for p in patterns)
        total_quizzes = sum(p.quiz_count for p in patterns)
        avg_accuracy = 0
        if patterns:
            accuracies = [p.accuracy_rate for p in patterns if p.accuracy_rate]
            if accuracies:
                avg_accuracy = sum(accuracies) / len(accuracies)
        
        return {
            'total_minutes': total_minutes,
            'total_quizzes': total_quizzes,
            'average_accuracy': float(avg_accuracy),
            'study_days': patterns.values('date').distinct().count()
        }


class StudyPatternSerializer(serializers.ModelSerializer):
    """학습 패턴 시리얼라이저"""
    
    class Meta:
        model = StudyPattern
        fields = [
            'date',
            'hour',
            'study_minutes',
            'quiz_count',
            'accuracy_rate',
            'focus_score'
        ]
        read_only_fields = fields


class HeatmapDataSerializer(serializers.Serializer):
    """히트맵 데이터 시리얼라이저"""
    
    date = serializers.DateField()
    hour = serializers.IntegerField()
    intensity = serializers.IntegerField()
    
    class Meta:
        fields = ['date', 'hour', 'intensity']


class StatsOverviewSerializer(serializers.Serializer):
    """통계 개요 시리얼라이저"""
    
    patterns = serializers.ListField(
        child=serializers.DictField(),
        help_text="학습 패턴 데이터"
    )
    trends = serializers.DictField(help_text="학습 추세 데이터")
    focus_time = serializers.DictField(help_text="집중 시간 분석")
    heatmap = serializers.ListField(
        child=HeatmapDataSerializer(),
        help_text="히트맵 데이터"
    )


class DailyGoalSerializer(serializers.ModelSerializer):
    """일일 목표 시리얼라이저"""
    
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = DailyGoal
        fields = [
            'id',
            'date',
            'target_minutes',
            'target_quizzes',
            'completed_minutes',
            'completed_quizzes',
            'is_achieved',
            'progress_percentage'
        ]
    
    def get_progress_percentage(self, obj) -> Dict[str, int]:
        """목표별 달성률 계산"""
        minutes_progress = 0
        quizzes_progress = 0
        
        if obj.target_minutes > 0:
            minutes_progress = min(100, int((obj.completed_minutes / obj.target_minutes) * 100))
        if obj.target_quizzes > 0:
            quizzes_progress = min(100, int((obj.completed_quizzes / obj.target_quizzes) * 100))
        
        return {
            'minutes': minutes_progress,
            'quizzes': quizzes_progress,
            'overall': min(minutes_progress, quizzes_progress)
        }


class UpdateGoalSerializer(serializers.Serializer):
    """목표 업데이트 시리얼라이저"""
    
    target_minutes = serializers.IntegerField(min_value=5, max_value=480)
    target_quizzes = serializers.IntegerField(min_value=1, max_value=50)
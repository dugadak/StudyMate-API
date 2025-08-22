from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Sum, Avg, Count
from datetime import timedelta

from .models import UserStatistics, PeerComparison
from home.models import StudyPattern


class StatsOverviewView(APIView):
    """전체 통계 API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """전체 통계 조회"""
        user = request.user
        stats, created = UserStatistics.objects.get_or_create(user=user)
        
        return Response({
            'total_study_hours': stats.total_study_hours,
            'total_quizzes': stats.total_quizzes,
            'total_correct': stats.total_correct,
            'overall_accuracy': float(stats.overall_accuracy),
            'subject_stats': stats.subject_stats,
            'peer_percentile': stats.peer_percentile
        })


class StatsPeriodView(APIView):
    """기간별 통계 API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """기간별 통계 조회"""
        user = request.user
        period = request.query_params.get('period', '7')  # 7, 30, all
        
        today = timezone.now().date()
        if period == '7':
            start_date = today - timedelta(days=7)
        elif period == '30':
            start_date = today - timedelta(days=30)
        else:
            start_date = None
        
        # 학습 패턴 집계
        patterns_query = StudyPattern.objects.filter(user=user)
        if start_date:
            patterns_query = patterns_query.filter(date__gte=start_date)
        
        stats = patterns_query.aggregate(
            total_minutes=Sum('study_minutes'),
            total_quizzes=Sum('quiz_count'),
            avg_accuracy=Avg('accuracy_rate')
        )
        
        return Response({
            'period': period,
            'total_study_minutes': stats['total_minutes'] or 0,
            'total_quizzes': stats['total_quizzes'] or 0,
            'average_accuracy': float(stats['avg_accuracy'] or 0),
            'study_days': patterns_query.values('date').distinct().count()
        })


class StatsStrengthsView(APIView):
    """강약점 분석 API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """강약점 자동 파악"""
        user = request.user
        stats, created = UserStatistics.objects.get_or_create(user=user)
        
        # 강약점 업데이트
        stats.update_strength_weakness()
        
        return Response({
            'strengths': stats.strengths,
            'weaknesses': stats.weaknesses,
            'subject_performance': stats.subject_stats
        })


class StatsPeerComparisonView(APIView):
    """또래 비교 API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """또래 대비 성과 비교"""
        user = request.user
        stats, created = UserStatistics.objects.get_or_create(user=user)
        
        # 사용자 연령대 및 학력 추정 (프로필 기반)
        age_group = "20-25"  # 기본값
        education_level = "대학생"  # 기본값
        
        # 또래 비교 데이터 조회
        peer_data, created = PeerComparison.objects.get_or_create(
            age_group=age_group,
            education_level=education_level,
            defaults={
                'avg_study_hours': 20,
                'avg_accuracy': 70,
                'avg_quiz_count': 50
            }
        )
        
        # 백분위 계산
        user_score = (stats.total_study_hours / 10) + stats.overall_accuracy
        peer_avg_score = (peer_data.avg_study_hours / 10) + float(peer_data.avg_accuracy)
        
        if peer_avg_score > 0:
            percentile = min(100, max(0, int((user_score / peer_avg_score) * 50)))
        else:
            percentile = 50
        
        # 백분위 저장
        stats.peer_percentile = percentile
        stats.save()
        
        return Response({
            'your_stats': {
                'study_hours': stats.total_study_hours,
                'accuracy': float(stats.overall_accuracy),
                'quiz_count': stats.total_quizzes
            },
            'peer_average': {
                'study_hours': peer_data.avg_study_hours,
                'accuracy': float(peer_data.avg_accuracy),
                'quiz_count': peer_data.avg_quiz_count
            },
            'percentile': percentile,
            'message': f"상위 {100 - percentile}% 입니다."
        })
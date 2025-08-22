from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from typing import Dict, Any


class UserStatistics(models.Model):
    """사용자 통계 종합"""
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='statistics'
    )
    
    # 전체 통계
    total_study_hours = models.FloatField(default=0, help_text="총 학습 시간(시간)")
    total_quizzes = models.PositiveIntegerField(default=0, help_text="총 퀴즈 수")
    total_correct = models.PositiveIntegerField(default=0, help_text="총 정답 수")
    overall_accuracy = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="전체 정답률")
    
    # 과목별 통계
    subject_stats = models.JSONField(default=dict, help_text="과목별 통계")
    
    # 강약점 분석
    strengths = models.JSONField(default=list, help_text="강점 분야")
    weaknesses = models.JSONField(default=list, help_text="약점 분야")
    
    # 또래 비교
    peer_percentile = models.PositiveIntegerField(default=50, help_text="또래 대비 백분위")
    
    # 타임스탬프
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'stats_user_statistics'
        verbose_name = '사용자 통계'
        verbose_name_plural = '사용자 통계'
    
    def __str__(self):
        return f"{self.user.email} 통계"
    
    def update_strength_weakness(self):
        """강약점 업데이트"""
        if not self.subject_stats:
            return
        
        # 과목별 정답률 계산
        subject_accuracies = []
        for subject, stats in self.subject_stats.items():
            if stats.get('total_questions', 0) > 0:
                accuracy = stats.get('correct', 0) / stats['total_questions']
                subject_accuracies.append((subject, accuracy))
        
        # 정렬
        subject_accuracies.sort(key=lambda x: x[1], reverse=True)
        
        # 강점과 약점 식별
        if len(subject_accuracies) >= 3:
            self.strengths = [s[0] for s in subject_accuracies[:3] if s[1] >= 0.7]
            self.weaknesses = [s[0] for s in subject_accuracies[-3:] if s[1] < 0.5]
        
        self.save()


class PeerComparison(models.Model):
    """또래 비교 데이터"""
    
    age_group = models.CharField(max_length=20, help_text="연령대 (예: 20-25)")
    education_level = models.CharField(max_length=50, help_text="학력 수준")
    
    # 평균 통계
    avg_study_hours = models.FloatField(default=0, help_text="평균 학습 시간")
    avg_accuracy = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="평균 정답률")
    avg_quiz_count = models.PositiveIntegerField(default=0, help_text="평균 퀴즈 수")
    
    # 분포
    percentile_data = models.JSONField(default=dict, help_text="백분위 분포 데이터")
    
    # 업데이트 정보
    sample_size = models.PositiveIntegerField(default=0, help_text="샘플 크기")
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'stats_peer_comparison'
        unique_together = [['age_group', 'education_level']]
        indexes = [
            models.Index(fields=['age_group', 'education_level']),
        ]
        verbose_name = '또래 비교'
        verbose_name_plural = '또래 비교'
    
    def __str__(self):
        return f"{self.age_group} - {self.education_level}"
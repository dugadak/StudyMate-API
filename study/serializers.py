from rest_framework import serializers
from django.core.cache import cache
from django.utils import timezone
from django.db import models
from typing import Dict, Any, List, Optional
import logging

from .models import (
    Subject, StudySettings, StudySummary, StudyProgress, StudyGoal
)

logger = logging.getLogger(__name__)


class SubjectSerializer(serializers.ModelSerializer):
    """Enhanced Subject serializer with statistics and metadata"""
    
    statistics = serializers.SerializerMethodField()
    is_subscribed = serializers.SerializerMethodField()
    user_progress = serializers.SerializerMethodField()
    popular_tags = serializers.SerializerMethodField()
    
    class Meta:
        model = Subject
        fields = [
            'id', 'name', 'description', 'category', 'default_difficulty',
            'icon', 'color_code', 'total_learners', 'total_summaries',
            'average_rating', 'is_active', 'requires_premium',
            'tags', 'keywords', 'statistics', 'is_subscribed',
            'user_progress', 'popular_tags', 'created_at'
        ]
        read_only_fields = [
            'id', 'total_learners', 'total_summaries', 'average_rating',
            'statistics', 'is_subscribed', 'user_progress', 'popular_tags',
            'created_at'
        ]
    
    def get_statistics(self, obj: Subject) -> Dict[str, Any]:
        """Get subject statistics"""
        return obj.get_statistics()
    
    def get_is_subscribed(self, obj: Subject) -> bool:
        """Check if current user has study settings for this subject"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        return StudySettings.objects.filter(
            user=request.user,
            subject=obj
        ).exists()
    
    def get_user_progress(self, obj: Subject) -> Optional[Dict[str, Any]]:
        """Get user's progress for this subject"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        
        try:
            progress = StudyProgress.objects.get(user=request.user, subject=obj)
            return {
                'total_summaries_read': progress.total_summaries_read,
                'current_streak': progress.current_streak,
                'completion_rate': progress.completion_rate,
                'last_activity': progress.last_activity_date.isoformat() if progress.last_activity_date else None
            }
        except StudyProgress.DoesNotExist:
            return None
    
    def get_popular_tags(self, obj: Subject) -> List[str]:
        """Get most popular tags for this subject"""
        # Cache popular tags for performance
        cache_key = f"subject_popular_tags_{obj.id}"
        popular_tags = cache.get(cache_key)
        
        if popular_tags is None:
            # Get tags from recent summaries (simplified)
            popular_tags = obj.tags[:5] if obj.tags else []
            cache.set(cache_key, popular_tags, 3600)  # Cache for 1 hour
        
        return popular_tags


class StudySettingsSerializer(serializers.ModelSerializer):
    """Enhanced StudySettings serializer with validation and preferences"""
    
    subject = SubjectSerializer(read_only=True)
    subject_id = serializers.IntegerField(write_only=True)
    ai_generation_config = serializers.SerializerMethodField()
    is_study_day_today = serializers.SerializerMethodField()
    next_notification_time = serializers.SerializerMethodField()
    
    class Meta:
        model = StudySettings
        fields = [
            'id', 'subject', 'subject_id', 'difficulty_level',
            'current_knowledge', 'learning_goal', 'preferred_depth',
            'learning_style', 'content_type_preference',
            'daily_summary_count', 'notification_times', 'study_days',
            'preferred_study_duration', 'include_examples', 'include_quizzes',
            'language_preference', 'preferred_ai_model', 'custom_prompt_template',
            'ai_generation_config', 'is_study_day_today', 'next_notification_time',
            'created_at', 'updated_at', 'last_used_at'
        ]
        read_only_fields = [
            'id', 'ai_generation_config', 'is_study_day_today',
            'next_notification_time', 'created_at', 'updated_at', 'last_used_at'
        ]
        extra_kwargs = {
            'current_knowledge': {'min_length': 10, 'max_length': 1000},
            'learning_goal': {'min_length': 10, 'max_length': 1000},
            'custom_prompt_template': {'max_length': 2000},
        }
    
    def get_ai_generation_config(self, obj: StudySettings) -> Dict[str, Any]:
        """Get AI generation configuration"""
        return obj.get_ai_generation_config()
    
    def get_is_study_day_today(self, obj: StudySettings) -> bool:
        """Check if today is a study day"""
        return obj.is_study_day_today()
    
    def get_next_notification_time(self, obj: StudySettings) -> Optional[str]:
        """Get next notification time today"""
        current_time = timezone.now().strftime('%H:%M')
        notification_times = obj.get_notification_times_list()
        
        for time_str in sorted(notification_times):
            if time_str > current_time:
                return time_str
        
        # If no more notifications today, return first one tomorrow
        return notification_times[0] if notification_times else None
    
    def validate_notification_times(self, value: List[str]) -> List[str]:
        """Validate notification times format and range"""
        if not isinstance(value, list):
            raise serializers.ValidationError("알림 시간은 리스트 형태여야 합니다.")
        
        if len(value) > 10:
            raise serializers.ValidationError("알림 시간은 최대 10개까지 설정할 수 있습니다.")
        
        validated_times = []
        for time_str in value:
            try:
                hour, minute = time_str.split(':')
                hour, minute = int(hour), int(minute)
                
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError
                
                # Normalize format
                normalized_time = f"{hour:02d}:{minute:02d}"
                if normalized_time not in validated_times:
                    validated_times.append(normalized_time)
                    
            except (ValueError, AttributeError):
                raise serializers.ValidationError(f"잘못된 시간 형식입니다: {time_str}")
        
        return sorted(validated_times)
    
    def validate_study_days(self, value: List[str]) -> List[str]:
        """Validate study days"""
        if not isinstance(value, list):
            raise serializers.ValidationError("학습 요일은 리스트 형태여야 합니다.")
        
        valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        invalid_days = [day for day in value if day not in valid_days]
        
        if invalid_days:
            raise serializers.ValidationError(f"잘못된 요일입니다: {invalid_days}")
        
        if len(value) == 0:
            raise serializers.ValidationError("최소 하나의 학습 요일을 선택해야 합니다.")
        
        return list(set(value))  # Remove duplicates
    
    def validate_subject_id(self, value: int) -> int:
        """Validate subject exists and is active"""
        try:
            subject = Subject.objects.get(id=value)
            if not subject.is_active:
                raise serializers.ValidationError("비활성화된 과목입니다.")
            return value
        except Subject.DoesNotExist:
            raise serializers.ValidationError("존재하지 않는 과목입니다.")
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Cross-field validation"""
        # Check if user already has settings for this subject (for create)
        if not self.instance:  # Creating new settings
            user = self.context['request'].user
            subject_id = attrs.get('subject_id')
            
            if StudySettings.objects.filter(user=user, subject_id=subject_id).exists():
                raise serializers.ValidationError({
                    'subject_id': '이미 이 과목에 대한 설정이 존재합니다.'
                })
        
        # Validate difficulty progression
        difficulty_order = ['beginner', 'intermediate', 'advanced', 'expert']
        current_level = attrs.get('difficulty_level', self.instance.difficulty_level if self.instance else 'beginner')
        preferred_depth = attrs.get('preferred_depth', self.instance.preferred_depth if self.instance else 'intermediate')
        
        if difficulty_order.index(preferred_depth) < difficulty_order.index(current_level):
            raise serializers.ValidationError({
                'preferred_depth': '선호 깊이는 현재 수준보다 높거나 같아야 합니다.'
            })
        
        return attrs
    
    def create(self, validated_data: Dict[str, Any]) -> StudySettings:
        """Create study settings with user"""
        validated_data['user'] = self.context['request'].user
        
        # Update last used timestamp
        settings = StudySettings.objects.create(**validated_data)
        settings.update_last_used()
        
        logger.info(f"Study settings created for user {settings.user.email}, subject {settings.subject.name}")
        return settings
    
    def update(self, instance: StudySettings, validated_data: Dict[str, Any]) -> StudySettings:
        """Update study settings and mark as used"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.update_last_used()
        instance.save()
        
        logger.info(f"Study settings updated for user {instance.user.email}, subject {instance.subject.name}")
        return instance


class StudySummarySerializer(serializers.ModelSerializer):
    """Enhanced StudySummary serializer with interaction data"""
    
    subject = SubjectSerializer(read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    reading_stats = serializers.SerializerMethodField()
    related_count = serializers.SerializerMethodField()
    estimated_reading_time = serializers.SerializerMethodField()
    content_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = StudySummary
        fields = [
            'id', 'user_email', 'subject', 'title', 'content', 'content_preview',
            'content_type', 'difficulty_level', 'ai_model_used', 'generation_time',
            'token_count', 'is_read', 'read_at', 'reading_time', 'user_rating',
            'user_feedback', 'is_bookmarked', 'topics_covered', 'tags',
            'reading_stats', 'related_count', 'estimated_reading_time',
            'generated_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user_email', 'ai_model_used', 'generation_time', 'token_count',
            'reading_stats', 'related_count', 'estimated_reading_time',
            'generated_at', 'updated_at'
        ]
        extra_kwargs = {
            'user_rating': {'min_value': 1, 'max_value': 5},
            'user_feedback': {'max_length': 1000},
        }
    
    def get_reading_stats(self, obj: StudySummary) -> Dict[str, Any]:
        """Get reading statistics"""
        return obj.get_reading_stats()
    
    def get_related_count(self, obj: StudySummary) -> int:
        """Get count of related summaries"""
        return obj.related_summaries.count()
    
    def get_estimated_reading_time(self, obj: StudySummary) -> int:
        """Estimate reading time in minutes"""
        # Average reading speed: 200 words per minute
        word_count = len(obj.content.split())
        return max(1, word_count // 200)
    
    def get_content_preview(self, obj: StudySummary) -> str:
        """Get content preview for list views"""
        if len(obj.content) <= 200:
            return obj.content
        return obj.content[:200] + "..."
    
    def validate_user_rating(self, value: Optional[int]) -> Optional[int]:
        """Validate user rating"""
        if value is not None and not (1 <= value <= 5):
            raise serializers.ValidationError("평점은 1-5 사이의 값이어야 합니다.")
        return value
    
    def validate_topics_covered(self, value: List[str]) -> List[str]:
        """Validate topics covered"""
        if not isinstance(value, list):
            raise serializers.ValidationError("주제는 리스트 형태여야 합니다.")
        
        if len(value) > 20:
            raise serializers.ValidationError("주제는 최대 20개까지 설정할 수 있습니다.")
        
        # Clean and validate topics
        cleaned_topics = []
        for topic in value:
            if isinstance(topic, str) and len(topic.strip()) > 0:
                cleaned_topic = topic.strip()[:100]  # Limit length
                if cleaned_topic not in cleaned_topics:
                    cleaned_topics.append(cleaned_topic)
        
        return cleaned_topics
    
    def validate_tags(self, value: List[str]) -> List[str]:
        """Validate tags"""
        if not isinstance(value, list):
            raise serializers.ValidationError("태그는 리스트 형태여야 합니다.")
        
        if len(value) > 10:
            raise serializers.ValidationError("태그는 최대 10개까지 설정할 수 있습니다.")
        
        # Clean and validate tags
        cleaned_tags = []
        for tag in value:
            if isinstance(tag, str) and len(tag.strip()) > 0:
                cleaned_tag = tag.strip().lower()[:50]  # Normalize and limit length
                if cleaned_tag not in cleaned_tags:
                    cleaned_tags.append(cleaned_tag)
        
        return cleaned_tags


class StudyProgressSerializer(serializers.ModelSerializer):
    """Enhanced StudyProgress serializer with insights and analytics"""
    
    subject = SubjectSerializer(read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    weekly_progress = serializers.SerializerMethodField()
    learning_insights = serializers.SerializerMethodField()
    achievement_summary = serializers.SerializerMethodField()
    study_pattern = serializers.SerializerMethodField()
    
    class Meta:
        model = StudyProgress
        fields = [
            'id', 'user_email', 'subject', 'topics_learned', 'mastery_levels',
            'total_summaries_read', 'total_quizzes_completed', 'total_study_time',
            'current_streak', 'longest_streak', 'study_frequency',
            'average_rating_given', 'completion_rate', 'weekly_goal', 'monthly_goal',
            'preferred_study_hours', 'study_session_count', 'average_session_duration',
            'badges_earned', 'milestones_reached', 'weekly_progress',
            'learning_insights', 'achievement_summary', 'study_pattern',
            'last_activity_date', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user_email', 'total_summaries_read', 'total_quizzes_completed',
            'total_study_time', 'current_streak', 'longest_streak', 'study_frequency',
            'average_rating_given', 'completion_rate', 'study_session_count',
            'average_session_duration', 'badges_earned', 'milestones_reached',
            'weekly_progress', 'learning_insights', 'achievement_summary',
            'study_pattern', 'last_activity_date', 'created_at', 'updated_at'
        ]
    
    def get_weekly_progress(self, obj: StudyProgress) -> Dict[str, Any]:
        """Get weekly progress data"""
        return obj.get_weekly_progress()
    
    def get_learning_insights(self, obj: StudyProgress) -> Dict[str, Any]:
        """Get learning insights"""
        return obj.get_learning_insights()
    
    def get_achievement_summary(self, obj: StudyProgress) -> Dict[str, Any]:
        """Get achievement summary"""
        return {
            'total_badges': len(obj.badges_earned),
            'total_milestones': len(obj.milestones_reached),
            'recent_badges': obj.badges_earned[-3:] if obj.badges_earned else [],
            'recent_milestones': obj.milestones_reached[-3:] if obj.milestones_reached else [],
        }
    
    def get_study_pattern(self, obj: StudyProgress) -> Dict[str, Any]:
        """Get study pattern analysis"""
        return {
            'preferred_hours': obj.preferred_study_hours[:3] if obj.preferred_study_hours else [],
            'average_session_minutes': obj.average_session_duration,
            'total_sessions': obj.study_session_count,
            'consistency_score': min(obj.current_streak / 30.0, 1.0),  # Normalized to 0-1
            'weekly_frequency': obj.study_frequency,
        }


class StudyGoalSerializer(serializers.ModelSerializer):
    """StudyGoal serializer with progress tracking"""
    
    subject = SubjectSerializer(read_only=True)
    subject_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    progress = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = StudyGoal
        fields = [
            'id', 'subject', 'subject_id', 'title', 'description',
            'goal_type', 'status', 'target_summaries', 'target_quizzes',
            'target_study_time', 'current_summaries', 'current_quizzes',
            'current_study_time', 'start_date', 'end_date', 'completed_at',
            'progress', 'days_remaining', 'is_completed', 'progress_percentage',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'current_summaries', 'current_quizzes', 'current_study_time',
            'completed_at', 'progress', 'days_remaining', 'is_completed',
            'progress_percentage', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'title': {'min_length': 3, 'max_length': 200},
            'description': {'max_length': 1000},
        }
    
    def get_progress(self, obj: StudyGoal) -> Dict[str, float]:
        """Get goal progress"""
        return obj.calculate_progress()
    
    def get_days_remaining(self, obj: StudyGoal) -> int:
        """Get days remaining"""
        return obj.days_remaining()
    
    def get_is_completed(self, obj: StudyGoal) -> bool:
        """Check if goal is completed"""
        return obj.is_completed()
    
    def get_progress_percentage(self, obj: StudyGoal) -> float:
        """Get overall progress percentage"""
        progress = obj.calculate_progress()
        if not progress:
            return 0.0
        
        return sum(progress.values()) / len(progress)
    
    def validate_subject_id(self, value: Optional[int]) -> Optional[int]:
        """Validate subject if provided"""
        if value is not None:
            try:
                subject = Subject.objects.get(id=value)
                if not subject.is_active:
                    raise serializers.ValidationError("비활성화된 과목입니다.")
            except Subject.DoesNotExist:
                raise serializers.ValidationError("존재하지 않는 과목입니다.")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Cross-field validation"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date and start_date >= end_date:
            raise serializers.ValidationError({
                'end_date': '종료일은 시작일보다 늦어야 합니다.'
            })
        
        # At least one target should be set
        if not any([
            attrs.get('target_summaries', 0) > 0,
            attrs.get('target_quizzes', 0) > 0,
            attrs.get('target_study_time') and attrs.get('target_study_time').total_seconds() > 0
        ]):
            raise serializers.ValidationError(
                "최소 하나의 목표(요약, 퀴즈, 학습시간)를 설정해야 합니다."
            )
        
        return attrs
    
    def create(self, validated_data: Dict[str, Any]) -> StudyGoal:
        """Create study goal"""
        validated_data['user'] = self.context['request'].user
        goal = StudyGoal.objects.create(**validated_data)
        
        logger.info(f"Study goal created: {goal.title} for user {goal.user.email}")
        return goal


class StudySummaryDetailSerializer(StudySummarySerializer):
    """Detailed serializer for StudySummary with related summaries"""
    
    related_summaries = serializers.SerializerMethodField()
    user_can_rate = serializers.SerializerMethodField()
    subject_statistics = serializers.SerializerMethodField()
    
    class Meta(StudySummarySerializer.Meta):
        fields = StudySummarySerializer.Meta.fields + [
            'related_summaries', 'user_can_rate', 'subject_statistics'
        ]
    
    def get_related_summaries(self, obj: StudySummary) -> List[Dict[str, Any]]:
        """Get related summaries"""
        related = obj.related_summaries.filter(
            user=obj.user
        ).select_related('subject')[:5]
        
        return [{
            'id': summary.id,
            'title': summary.title,
            'subject_name': summary.subject.name,
            'difficulty_level': summary.difficulty_level,
            'generated_at': summary.generated_at.isoformat(),
        } for summary in related]
    
    def get_user_can_rate(self, obj: StudySummary) -> bool:
        """Check if user can rate this summary"""
        request = self.context.get('request')
        return (
            request and 
            request.user.is_authenticated and 
            request.user == obj.user and
            obj.is_read
        )
    
    def get_subject_statistics(self, obj: StudySummary) -> Dict[str, Any]:
        """Get subject-related statistics for this user"""
        user_summaries = StudySummary.objects.filter(
            user=obj.user,
            subject=obj.subject
        )
        
        return {
            'total_summaries': user_summaries.count(),
            'read_summaries': user_summaries.filter(is_read=True).count(),
            'rated_summaries': user_summaries.filter(user_rating__isnull=False).count(),
            'average_rating': user_summaries.filter(
                user_rating__isnull=False
            ).aggregate(
                avg_rating=models.Avg('user_rating')
            )['avg_rating'] or 0.0,
            'bookmarked_summaries': user_summaries.filter(is_bookmarked=True).count(),
        }


class SubjectCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating subjects (admin only)"""
    
    class Meta:
        model = Subject
        fields = [
            'name', 'description', 'category', 'default_difficulty',
            'icon', 'color_code', 'requires_premium', 'tags', 'keywords'
        ]
        extra_kwargs = {
            'name': {'min_length': 2, 'max_length': 100},
            'description': {'max_length': 1000},
            'icon': {'max_length': 50},
            'color_code': {'max_length': 7},
        }
    
    def validate_name(self, value: str) -> str:
        """Validate subject name uniqueness"""
        value = value.strip()
        if Subject.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("이미 존재하는 과목명입니다.")
        return value
    
    def validate_color_code(self, value: str) -> str:
        """Validate hex color code"""
        if value and not value.startswith('#'):
            value = '#' + value
        
        if value and len(value) != 7:
            raise serializers.ValidationError("올바른 HEX 컬러 코드 형식이 아닙니다. (#FFFFFF)")
        
        return value
    
    def validate_tags(self, value: List[str]) -> List[str]:
        """Validate and clean tags"""
        if not isinstance(value, list):
            return []
        
        cleaned_tags = []
        for tag in value[:20]:  # Limit to 20 tags
            if isinstance(tag, str) and len(tag.strip()) > 0:
                cleaned_tag = tag.strip().lower()[:50]
                if cleaned_tag not in cleaned_tags:
                    cleaned_tags.append(cleaned_tag)
        
        return cleaned_tags
    
    def validate_keywords(self, value: List[str]) -> List[str]:
        """Validate and clean keywords"""
        if not isinstance(value, list):
            return []
        
        cleaned_keywords = []
        for keyword in value[:30]:  # Limit to 30 keywords
            if isinstance(keyword, str) and len(keyword.strip()) > 0:
                cleaned_keyword = keyword.strip().lower()[:100]
                if cleaned_keyword not in cleaned_keywords:
                    cleaned_keywords.append(cleaned_keyword)
        
        return cleaned_keywords
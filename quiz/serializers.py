from rest_framework import serializers
from django.core.cache import cache
from django.utils import timezone
from django.db import models
from typing import Dict, Any, List, Optional
import logging

from .models import (
    Quiz, QuizChoice, QuizAttempt, QuizSession, 
    QuizProgress, QuizCategory
)
from study.models import Subject

logger = logging.getLogger(__name__)


class QuizChoiceSerializer(serializers.ModelSerializer):
    """Quiz Choice serializer with analytics"""
    
    selection_percentage = serializers.ReadOnlyField()
    
    class Meta:
        model = QuizChoice
        fields = [
            'id', 'choice_text', 'is_correct', 'order', 'explanation',
            'selection_count', 'selection_percentage', 'created_at'
        ]
        read_only_fields = [
            'id', 'selection_count', 'selection_percentage', 'created_at'
        ]
        extra_kwargs = {
            'choice_text': {'min_length': 1, 'max_length': 1000},
            'explanation': {'max_length': 2000},
        }
    
    def validate_order(self, value: int) -> int:
        """Validate choice order"""
        if value < 0:
            raise serializers.ValidationError("순서는 0 이상이어야 합니다.")
        return value


class QuizChoiceCreateSerializer(QuizChoiceSerializer):
    """Serializer for creating quiz choices without analytics"""
    
    class Meta(QuizChoiceSerializer.Meta):
        fields = [
            'choice_text', 'is_correct', 'order', 'explanation'
        ]


class QuizSerializer(serializers.ModelSerializer):
    """Enhanced Quiz serializer with comprehensive features"""
    
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    choices = QuizChoiceSerializer(many=True, read_only=True)
    success_rate = serializers.ReadOnlyField()
    estimated_time_minutes = serializers.ReadOnlyField()
    statistics = serializers.SerializerMethodField()
    hints_list = serializers.SerializerMethodField()
    can_attempt = serializers.SerializerMethodField()
    user_attempts_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Quiz
        fields = [
            'id', 'subject', 'subject_name', 'title', 'question', 'quiz_type',
            'difficulty_level', 'status', 'explanation', 'related_knowledge',
            'hints_list', 'tags', 'topics_covered', 'estimated_time_seconds',
            'estimated_time_minutes', 'points', 'is_active', 'requires_premium',
            'allow_multiple_attempts', 'shuffle_choices', 'ai_generated',
            'choices', 'success_rate', 'statistics', 'can_attempt',
            'user_attempts_count', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'subject_name', 'total_attempts', 'correct_attempts',
            'average_time_spent', 'difficulty_rating', 'last_attempted_at',
            'success_rate', 'estimated_time_minutes', 'statistics',
            'can_attempt', 'user_attempts_count', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'title': {'min_length': 3, 'max_length': 200},
            'question': {'min_length': 10},
            'explanation': {'min_length': 10},
            'related_knowledge': {'max_length': 2000},
            'generation_prompt': {'max_length': 2000},
        }
    
    def get_statistics(self, obj: Quiz) -> Dict[str, Any]:
        """Get quiz statistics"""
        return obj.get_statistics()
    
    def get_hints_list(self, obj: Quiz) -> List[str]:
        """Get hints list"""
        return obj.get_hints_list()
    
    def get_can_attempt(self, obj: Quiz) -> bool:
        """Check if current user can attempt this quiz"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        # Check if quiz allows multiple attempts
        if obj.allow_multiple_attempts:
            return True
        
        # Check if user has already attempted this quiz
        return not QuizAttempt.objects.filter(
            user=request.user,
            quiz=obj
        ).exists()
    
    def get_user_attempts_count(self, obj: Quiz) -> int:
        """Get user's attempt count for this quiz"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
        
        return QuizAttempt.objects.filter(
            user=request.user,
            quiz=obj
        ).count()
    
    def validate_tags(self, value: List[str]) -> List[str]:
        """Validate and clean tags"""
        if not isinstance(value, list):
            return []
        
        cleaned_tags = []
        for tag in value[:10]:  # Limit to 10 tags
            if isinstance(tag, str) and len(tag.strip()) > 0:
                cleaned_tag = tag.strip().lower()[:50]
                if cleaned_tag not in cleaned_tags:
                    cleaned_tags.append(cleaned_tag)
        
        return cleaned_tags
    
    def validate_topics_covered(self, value: List[str]) -> List[str]:
        """Validate topics covered"""
        if not isinstance(value, list):
            return []
        
        cleaned_topics = []
        for topic in value[:15]:  # Limit to 15 topics
            if isinstance(topic, str) and len(topic.strip()) > 0:
                cleaned_topic = topic.strip()[:100]
                if cleaned_topic not in cleaned_topics:
                    cleaned_topics.append(cleaned_topic)
        
        return cleaned_topics
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Cross-field validation"""
        quiz_type = attrs.get('quiz_type')
        
        # Validate estimated time
        estimated_time = attrs.get('estimated_time_seconds', 60)
        if estimated_time < 10:
            raise serializers.ValidationError({
                'estimated_time_seconds': '예상 소요 시간은 최소 10초 이상이어야 합니다.'
            })
        
        # Validate points
        points = attrs.get('points', 10)
        if points < 1:
            raise serializers.ValidationError({
                'points': '배점은 최소 1점 이상이어야 합니다.'
            })
        
        return attrs


class QuizCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating quizzes with choices"""
    
    choices = QuizChoiceCreateSerializer(many=True, required=True)
    
    class Meta:
        model = Quiz
        fields = [
            'subject', 'title', 'question', 'quiz_type', 'difficulty_level',
            'explanation', 'related_knowledge', 'hints', 'tags', 'topics_covered',
            'estimated_time_seconds', 'points', 'requires_premium',
            'allow_multiple_attempts', 'shuffle_choices', 'choices'
        ]
        extra_kwargs = {
            'title': {'min_length': 3, 'max_length': 200},
            'question': {'min_length': 10},
            'explanation': {'min_length': 10},
        }
    
    def validate_choices(self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate quiz choices"""
        if not value:
            raise serializers.ValidationError("퀴즈에는 최소 1개의 선택지가 필요합니다.")
        
        if len(value) > 10:
            raise serializers.ValidationError("선택지는 최대 10개까지 가능합니다.")
        
        quiz_type = self.initial_data.get('quiz_type', 'multiple_choice')
        
        if quiz_type == 'multiple_choice':
            if len(value) < 2:
                raise serializers.ValidationError("객관식 문제는 최소 2개의 선택지가 필요합니다.")
            
            correct_count = sum(1 for choice in value if choice.get('is_correct', False))
            if correct_count == 0:
                raise serializers.ValidationError("최소 1개의 정답 선택지가 필요합니다.")
            if correct_count > 1:
                raise serializers.ValidationError("객관식 문제는 정답이 1개여야 합니다.")
        
        elif quiz_type == 'true_false':
            if len(value) != 2:
                raise serializers.ValidationError("True/False 문제는 정확히 2개의 선택지가 필요합니다.")
            
            correct_count = sum(1 for choice in value if choice.get('is_correct', False))
            if correct_count != 1:
                raise serializers.ValidationError("True/False 문제는 정답이 1개여야 합니다.")
        
        elif quiz_type in ['short_answer', 'fill_blank']:
            correct_count = sum(1 for choice in value if choice.get('is_correct', False))
            if correct_count == 0:
                raise serializers.ValidationError("최소 1개의 정답이 필요합니다.")
        
        return value
    
    def create(self, validated_data: Dict[str, Any]) -> Quiz:
        """Create quiz with choices"""
        choices_data = validated_data.pop('choices')
        quiz = Quiz.objects.create(**validated_data)
        
        for i, choice_data in enumerate(choices_data):
            choice_data['order'] = choice_data.get('order', i)
            QuizChoice.objects.create(quiz=quiz, **choice_data)
        
        logger.info(f"Quiz created: {quiz.title} with {len(choices_data)} choices")
        return quiz


class QuizDetailSerializer(QuizSerializer):
    """Detailed quiz serializer with additional information"""
    
    user_last_attempt = serializers.SerializerMethodField()
    related_quizzes = serializers.SerializerMethodField()
    choice_analytics = serializers.SerializerMethodField()
    
    class Meta(QuizSerializer.Meta):
        fields = QuizSerializer.Meta.fields + [
            'user_last_attempt', 'related_quizzes', 'choice_analytics',
            'total_attempts', 'correct_attempts', 'average_time_spent',
            'difficulty_rating'
        ]
    
    def get_user_last_attempt(self, obj: Quiz) -> Optional[Dict[str, Any]]:
        """Get user's last attempt for this quiz"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        
        last_attempt = QuizAttempt.objects.filter(
            user=request.user,
            quiz=obj
        ).order_by('-attempted_at').first()
        
        if last_attempt:
            return {
                'attempted_at': last_attempt.attempted_at,
                'is_correct': last_attempt.is_correct,
                'points_earned': last_attempt.total_points,
                'time_spent': last_attempt.time_spent_seconds
            }
        
        return None
    
    def get_related_quizzes(self, obj: Quiz) -> List[Dict[str, Any]]:
        """Get related quizzes"""
        related = Quiz.objects.filter(
            subject=obj.subject,
            difficulty_level=obj.difficulty_level,
            is_active=True
        ).exclude(id=obj.id)[:5]
        
        return [
            {
                'id': quiz.id,
                'title': quiz.title,
                'quiz_type': quiz.get_quiz_type_display(),
                'success_rate': quiz.success_rate
            }
            for quiz in related
        ]
    
    def get_choice_analytics(self, obj: Quiz) -> List[Dict[str, Any]]:
        """Get choice selection analytics"""
        if not self.context.get('request', {}).user.is_staff:
            return []
        
        return [
            {
                'choice_id': choice.id,
                'choice_text': choice.choice_text[:50],
                'is_correct': choice.is_correct,
                'selection_count': choice.selection_count,
                'selection_percentage': choice.selection_percentage
            }
            for choice in obj.choices.all()
        ]


class QuizAttemptSerializer(serializers.ModelSerializer):
    """Quiz Attempt serializer with comprehensive tracking"""
    
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    quiz_type = serializers.CharField(source='quiz.get_quiz_type_display', read_only=True)
    subject_name = serializers.CharField(source='quiz.subject.name', read_only=True)
    total_points = serializers.ReadOnlyField()
    time_spent_seconds = serializers.ReadOnlyField()
    hints_used_list = serializers.SerializerMethodField()
    
    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'quiz', 'quiz_title', 'quiz_type', 'subject_name',
            'user_answer', 'selected_choice', 'is_correct', 'started_at',
            'attempted_at', 'time_spent', 'time_spent_seconds', 'difficulty_rating',
            'feedback', 'hints_used_list', 'points_earned', 'bonus_points',
            'total_points'
        ]
        read_only_fields = [
            'id', 'quiz_title', 'quiz_type', 'subject_name', 'attempted_at',
            'time_spent_seconds', 'points_earned', 'bonus_points', 'total_points'
        ]
        extra_kwargs = {
            'user_answer': {'min_length': 1},
            'feedback': {'max_length': 1000},
            'difficulty_rating': {'min_value': 1, 'max_value': 5},
        }
    
    def get_hints_used_list(self, obj: QuizAttempt) -> List[str]:
        """Get hints used list"""
        return obj.get_hints_used_list()
    
    def validate_difficulty_rating(self, value: Optional[int]) -> Optional[int]:
        """Validate difficulty rating"""
        if value is not None and not (1 <= value <= 5):
            raise serializers.ValidationError("난이도 평점은 1-5 사이의 값이어야 합니다.")
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Cross-field validation"""
        quiz = attrs.get('quiz')
        selected_choice = attrs.get('selected_choice')
        user_answer = attrs.get('user_answer')
        
        # Validate choice selection for multiple choice questions
        if quiz and quiz.quiz_type == 'multiple_choice':
            if not selected_choice:
                raise serializers.ValidationError({
                    'selected_choice': '객관식 문제는 선택지를 선택해야 합니다.'
                })
            
            if selected_choice.quiz != quiz:
                raise serializers.ValidationError({
                    'selected_choice': '선택지가 해당 퀴즈에 속하지 않습니다.'
                })
        
        # Validate answer for non-multiple choice questions
        if quiz and quiz.quiz_type != 'multiple_choice':
            if not user_answer or not user_answer.strip():
                raise serializers.ValidationError({
                    'user_answer': '답안을 입력해야 합니다.'
                })
        
        return attrs
    
    def create(self, validated_data: Dict[str, Any]) -> QuizAttempt:
        """Create attempt with automatic answer checking"""
        user = self.context['request'].user
        quiz = validated_data['quiz']
        user_answer = validated_data['user_answer']
        
        # Check if user can attempt this quiz
        if not quiz.allow_multiple_attempts:
            if QuizAttempt.objects.filter(user=user, quiz=quiz).exists():
                raise serializers.ValidationError("이 퀴즈는 중복 시도가 허용되지 않습니다.")
        
        # Auto-check answer
        is_correct = quiz.check_answer(user_answer)
        validated_data['is_correct'] = is_correct
        validated_data['user'] = user
        
        # Set started_at if not provided
        if 'started_at' not in validated_data:
            validated_data['started_at'] = timezone.now()
        
        # Get IP and User Agent from request
        request = self.context.get('request')
        if request:
            validated_data['ip_address'] = self.get_client_ip(request)
            validated_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
        
        attempt = QuizAttempt.objects.create(**validated_data)
        
        logger.info(f"Quiz attempt created: {user.email} -> {quiz.title} ({'정답' if is_correct else '오답'})")
        
        return attempt
    
    def get_client_ip(self, request) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class QuizSessionSerializer(serializers.ModelSerializer):
    """Quiz Session serializer with comprehensive tracking"""
    
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    score_percentage = serializers.ReadOnlyField()
    points_percentage = serializers.ReadOnlyField()
    duration_minutes = serializers.SerializerMethodField()
    remaining_questions = serializers.ReadOnlyField()
    performance_summary = serializers.SerializerMethodField()
    is_time_limit_exceeded = serializers.SerializerMethodField()
    
    class Meta:
        model = QuizSession
        fields = [
            'id', 'subject', 'subject_name', 'session_type', 'difficulty_level',
            'target_questions', 'time_limit', 'total_questions', 'answered_questions',
            'correct_answers', 'total_points', 'max_possible_points', 'status',
            'started_at', 'completed_at', 'score_percentage', 'points_percentage',
            'duration_minutes', 'remaining_questions', 'average_time_per_question',
            'topics_covered', 'performance_summary', 'is_time_limit_exceeded'
        ]
        read_only_fields = [
            'id', 'subject_name', 'total_questions', 'answered_questions',
            'correct_answers', 'total_points', 'max_possible_points',
            'completed_at', 'score_percentage', 'points_percentage',
            'duration_minutes', 'remaining_questions', 'average_time_per_question',
            'topics_covered', 'performance_summary', 'is_time_limit_exceeded'
        ]
        extra_kwargs = {
            'target_questions': {'min_value': 1, 'max_value': 100},
        }
    
    def get_duration_minutes(self, obj: QuizSession) -> Optional[float]:
        """Get session duration in minutes"""
        if obj.duration:
            return obj.duration.total_seconds() / 60
        return None
    
    def get_performance_summary(self, obj: QuizSession) -> Dict[str, Any]:
        """Get performance summary"""
        return obj.get_performance_summary()
    
    def get_is_time_limit_exceeded(self, obj: QuizSession) -> bool:
        """Check if time limit is exceeded"""
        if not obj.time_limit or obj.status != 'active':
            return False
        
        elapsed_time = timezone.now() - obj.started_at - obj.total_pause_time
        return elapsed_time > obj.time_limit
    
    def validate_target_questions(self, value: int) -> int:
        """Validate target questions"""
        if value < 1:
            raise serializers.ValidationError("목표 문제 수는 최소 1개 이상이어야 합니다.")
        if value > 100:
            raise serializers.ValidationError("목표 문제 수는 최대 100개까지 가능합니다.")
        return value
    
    def validate_time_limit(self, value: Optional[any]) -> Optional[any]:
        """Validate time limit"""
        if value and value.total_seconds() < 60:
            raise serializers.ValidationError("제한 시간은 최소 1분 이상이어야 합니다.")
        if value and value.total_seconds() > 14400:  # 4 hours
            raise serializers.ValidationError("제한 시간은 최대 4시간까지 가능합니다.")
        return value
    
    def create(self, validated_data: Dict[str, Any]) -> QuizSession:
        """Create quiz session"""
        validated_data['user'] = self.context['request'].user
        session = QuizSession.objects.create(**validated_data)
        
        logger.info(f"Quiz session created: {session.user.email} -> {session.subject.name}")
        return session


class QuizProgressSerializer(serializers.ModelSerializer):
    """Quiz Progress serializer with analytics and insights"""
    
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    overall_accuracy = serializers.ReadOnlyField()
    recommendations = serializers.SerializerMethodField()
    recent_activity = serializers.SerializerMethodField()
    achievement_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = QuizProgress
        fields = [
            'id', 'subject', 'subject_name', 'total_quizzes_attempted',
            'total_quizzes_correct', 'total_sessions', 'total_points_earned',
            'current_streak', 'longest_streak', 'difficulty_levels_mastered',
            'current_difficulty', 'total_study_time', 'average_session_duration',
            'recent_performance', 'weak_topics', 'strong_topics',
            'badges_earned', 'milestones_reached', 'overall_accuracy',
            'recommendations', 'recent_activity', 'achievement_summary',
            'last_activity_date', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'subject_name', 'total_quizzes_attempted', 'total_quizzes_correct',
            'total_sessions', 'total_points_earned', 'current_streak',
            'longest_streak', 'total_study_time', 'average_session_duration',
            'recent_performance', 'overall_accuracy', 'recommendations',
            'recent_activity', 'achievement_summary', 'last_activity_date',
            'created_at', 'updated_at'
        ]
    
    def get_recommendations(self, obj: QuizProgress) -> Dict[str, Any]:
        """Get learning recommendations"""
        return obj.get_recommendations()
    
    def get_recent_activity(self, obj: QuizProgress) -> Dict[str, Any]:
        """Get recent activity summary"""
        recent_performance = obj.recent_performance[:5]
        
        if not recent_performance:
            return {
                'total_attempts': 0,
                'correct_attempts': 0,
                'accuracy': 0.0,
                'total_points': 0,
                'average_time': 0.0
            }
        
        total_attempts = len(recent_performance)
        correct_attempts = sum(1 for p in recent_performance if p['is_correct'])
        total_points = sum(p['points'] for p in recent_performance)
        total_time = sum(p['time_spent'] for p in recent_performance if p['time_spent'])
        
        return {
            'total_attempts': total_attempts,
            'correct_attempts': correct_attempts,
            'accuracy': (correct_attempts / total_attempts) * 100 if total_attempts > 0 else 0.0,
            'total_points': total_points,
            'average_time': total_time / total_attempts if total_attempts > 0 and total_time > 0 else 0.0
        }
    
    def get_achievement_summary(self, obj: QuizProgress) -> Dict[str, Any]:
        """Get achievement summary"""
        return {
            'total_badges': len(obj.badges_earned),
            'total_milestones': len(obj.milestones_reached),
            'recent_badges': obj.badges_earned[-3:] if obj.badges_earned else [],
            'recent_milestones': obj.milestones_reached[-3:] if obj.milestones_reached else [],
        }


class QuizCategorySerializer(serializers.ModelSerializer):
    """Quiz Category serializer with hierarchy support"""
    
    full_path = serializers.ReadOnlyField()
    quiz_count = serializers.SerializerMethodField()
    subcategories = serializers.SerializerMethodField()
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    
    class Meta:
        model = QuizCategory
        fields = [
            'id', 'name', 'description', 'parent', 'parent_name', 'icon',
            'color_code', 'is_active', 'order', 'full_path', 'quiz_count',
            'subcategories', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'parent_name', 'full_path', 'quiz_count', 'subcategories',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'name': {'min_length': 2, 'max_length': 100},
            'description': {'max_length': 1000},
            'color_code': {'max_length': 7},
        }
    
    def get_quiz_count(self, obj: QuizCategory) -> int:
        """Get quiz count for category"""
        return obj.get_quiz_count()
    
    def get_subcategories(self, obj: QuizCategory) -> List[Dict[str, Any]]:
        """Get subcategories"""
        subcategories = obj.subcategories.filter(is_active=True).order_by('order', 'name')
        return [
            {
                'id': sub.id,
                'name': sub.name,
                'icon': sub.icon,
                'color_code': sub.color_code,
                'quiz_count': sub.get_quiz_count()
            }
            for sub in subcategories
        ]
    
    def validate_name(self, value: str) -> str:
        """Validate category name uniqueness"""
        value = value.strip()
        
        # Check for uniqueness within the same parent
        parent = self.initial_data.get('parent')
        queryset = QuizCategory.objects.filter(name__iexact=value, parent=parent)
        
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
        
        if queryset.exists():
            raise serializers.ValidationError("같은 상위 카테고리 내에서 중복된 이름입니다.")
        
        return value
    
    def validate_color_code(self, value: str) -> str:
        """Validate hex color code"""
        if value and not value.startswith('#'):
            value = '#' + value
        
        if value and len(value) != 7:
            raise serializers.ValidationError("올바른 HEX 컬러 코드 형식이 아닙니다. (#FFFFFF)")
        
        return value


class QuizListSerializer(serializers.ModelSerializer):
    """Simplified quiz serializer for list views"""
    
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    success_rate = serializers.ReadOnlyField()
    estimated_time_minutes = serializers.ReadOnlyField()
    can_attempt = serializers.SerializerMethodField()
    
    class Meta:
        model = Quiz
        fields = [
            'id', 'subject_name', 'title', 'quiz_type', 'difficulty_level',
            'points', 'estimated_time_minutes', 'success_rate', 'total_attempts',
            'requires_premium', 'can_attempt', 'created_at'
        ]
    
    def get_can_attempt(self, obj: Quiz) -> bool:
        """Check if current user can attempt this quiz"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        if obj.allow_multiple_attempts:
            return True
        
        return not QuizAttempt.objects.filter(
            user=request.user,
            quiz=obj
        ).exists()


class QuizStatisticsSerializer(serializers.Serializer):
    """Serializer for quiz statistics and analytics"""
    
    total_quizzes = serializers.IntegerField(read_only=True)
    total_attempts = serializers.IntegerField(read_only=True)
    overall_accuracy = serializers.FloatField(read_only=True)
    average_score = serializers.FloatField(read_only=True)
    total_study_time = serializers.FloatField(read_only=True)
    
    by_difficulty = serializers.DictField(read_only=True)
    by_subject = serializers.ListField(read_only=True)
    by_quiz_type = serializers.DictField(read_only=True)
    
    recent_activity = serializers.DictField(read_only=True)
    progress_trends = serializers.ListField(read_only=True)
    achievements = serializers.DictField(read_only=True)
    
    recommendations = serializers.DictField(read_only=True)


class QuizSessionSummarySerializer(serializers.ModelSerializer):
    """Summary serializer for completed quiz sessions"""
    
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    score_percentage = serializers.ReadOnlyField()
    duration_minutes = serializers.SerializerMethodField()
    recommended_next_difficulty = serializers.SerializerMethodField()
    
    class Meta:
        model = QuizSession
        fields = [
            'id', 'subject_name', 'session_type', 'difficulty_level',
            'total_questions', 'correct_answers', 'total_points',
            'score_percentage', 'duration_minutes', 'topics_covered',
            'recommended_next_difficulty', 'completed_at'
        ]
    
    def get_duration_minutes(self, obj: QuizSession) -> Optional[float]:
        """Get session duration in minutes"""
        if obj.duration:
            return round(obj.duration.total_seconds() / 60, 1)
        return None
    
    def get_recommended_next_difficulty(self, obj: QuizSession) -> str:
        """Get recommended next difficulty"""
        return obj.get_recommended_next_difficulty()
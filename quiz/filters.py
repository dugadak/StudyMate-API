import django_filters
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .models import Quiz, QuizAttempt, QuizSession, QuizProgress
from study.models import Subject


class QuizFilter(django_filters.FilterSet):
    """Enhanced filters for Quiz"""
    
    subject = django_filters.ModelChoiceFilter(
        queryset=Subject.objects.filter(is_active=True),
        field_name='subject'
    )
    difficulty_level = django_filters.ChoiceFilter(
        choices=Quiz.DIFFICULTY_CHOICES
    )
    quiz_type = django_filters.ChoiceFilter(
        choices=Quiz.QUIZ_TYPE_CHOICES
    )
    status = django_filters.ChoiceFilter(
        choices=Quiz.STATUS_CHOICES
    )
    requires_premium = django_filters.BooleanFilter()
    ai_generated = django_filters.BooleanFilter()
    min_points = django_filters.NumberFilter(
        field_name='points',
        lookup_expr='gte'
    )
    max_points = django_filters.NumberFilter(
        field_name='points',
        lookup_expr='lte'
    )
    min_success_rate = django_filters.NumberFilter(
        method='filter_min_success_rate',
        label='Minimum success rate'
    )
    created_after = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte'
    )
    created_before = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte'
    )
    tags = django_filters.CharFilter(
        method='filter_tags',
        label='Contains tags (comma-separated)'
    )
    topics = django_filters.CharFilter(
        method='filter_topics',
        label='Contains topics (comma-separated)'
    )
    
    class Meta:
        model = Quiz
        fields = []
    
    def filter_min_success_rate(self, queryset, name, value):
        """Filter quizzes with minimum success rate"""
        if value is not None:
            return queryset.extra(
                where=["CASE WHEN total_attempts > 0 THEN (correct_attempts * 100.0 / total_attempts) ELSE 0 END >= %s"],
                params=[value]
            )
        return queryset
    
    def filter_tags(self, queryset, name, value):
        """Filter by tags"""
        if value:
            tags = [tag.strip().lower() for tag in value.split(',') if tag.strip()]
            if tags:
                query = Q()
                for tag in tags:
                    query |= Q(tags__icontains=tag)
                return queryset.filter(query)
        return queryset
    
    def filter_topics(self, queryset, name, value):
        """Filter by topics covered"""
        if value:
            topics = [topic.strip() for topic in value.split(',') if topic.strip()]
            if topics:
                query = Q()
                for topic in topics:
                    query |= Q(topics_covered__icontains=topic)
                return queryset.filter(query)
        return queryset


class QuizAttemptFilter(django_filters.FilterSet):
    """Enhanced filters for QuizAttempt"""
    
    quiz = django_filters.ModelChoiceFilter(
        queryset=Quiz.objects.filter(is_active=True),
        field_name='quiz'
    )
    subject = django_filters.ModelChoiceFilter(
        queryset=Subject.objects.filter(is_active=True),
        field_name='quiz__subject'
    )
    is_correct = django_filters.BooleanFilter()
    difficulty_level = django_filters.ChoiceFilter(
        field_name='quiz__difficulty_level',
        choices=Quiz.DIFFICULTY_CHOICES
    )
    quiz_type = django_filters.ChoiceFilter(
        field_name='quiz__quiz_type',
        choices=Quiz.QUIZ_TYPE_CHOICES
    )
    min_points = django_filters.NumberFilter(
        field_name='points_earned',
        lookup_expr='gte'
    )
    has_rating = django_filters.BooleanFilter(
        method='filter_has_rating',
        label='Has difficulty rating'
    )
    attempted_after = django_filters.DateTimeFilter(
        field_name='attempted_at',
        lookup_expr='gte'
    )
    attempted_before = django_filters.DateTimeFilter(
        field_name='attempted_at',
        lookup_expr='lte'
    )
    recent_days = django_filters.NumberFilter(
        method='filter_recent_days',
        label='Attempted within last N days'
    )
    session = django_filters.ModelChoiceFilter(
        queryset=QuizSession.objects.all(),
        field_name='session'
    )
    
    class Meta:
        model = QuizAttempt
        fields = []
    
    def filter_has_rating(self, queryset, name, value):
        """Filter attempts that have difficulty ratings"""
        if value:
            return queryset.filter(difficulty_rating__isnull=False)
        else:
            return queryset.filter(difficulty_rating__isnull=True)
    
    def filter_recent_days(self, queryset, name, value):
        """Filter attempts within last N days"""
        if value and value > 0:
            since_date = timezone.now() - timedelta(days=value)
            return queryset.filter(attempted_at__gte=since_date)
        return queryset


class QuizSessionFilter(django_filters.FilterSet):
    """Enhanced filters for QuizSession"""
    
    subject = django_filters.ModelChoiceFilter(
        queryset=Subject.objects.filter(is_active=True),
        field_name='subject'
    )
    session_type = django_filters.ChoiceFilter(
        choices=QuizSession.SESSION_TYPE_CHOICES
    )
    status = django_filters.ChoiceFilter(
        choices=QuizSession.STATUS_CHOICES
    )
    difficulty_level = django_filters.ChoiceFilter(
        choices=Quiz.DIFFICULTY_CHOICES
    )
    min_score = django_filters.NumberFilter(
        method='filter_min_score',
        label='Minimum score percentage'
    )
    started_after = django_filters.DateTimeFilter(
        field_name='started_at',
        lookup_expr='gte'
    )
    started_before = django_filters.DateTimeFilter(
        field_name='started_at',
        lookup_expr='lte'
    )
    completed_after = django_filters.DateTimeFilter(
        field_name='completed_at',
        lookup_expr='gte'
    )
    completed_before = django_filters.DateTimeFilter(
        field_name='completed_at',
        lookup_expr='lte'
    )
    min_questions = django_filters.NumberFilter(
        field_name='total_questions',
        lookup_expr='gte'
    )
    recent_days = django_filters.NumberFilter(
        method='filter_recent_days',
        label='Started within last N days'
    )
    
    class Meta:
        model = QuizSession
        fields = []
    
    def filter_min_score(self, queryset, name, value):
        """Filter sessions with minimum score percentage"""
        if value is not None:
            return queryset.extra(
                where=["CASE WHEN total_questions > 0 THEN (correct_answers * 100.0 / total_questions) ELSE 0 END >= %s"],
                params=[value]
            )
        return queryset
    
    def filter_recent_days(self, queryset, name, value):
        """Filter sessions started within last N days"""
        if value and value > 0:
            since_date = timezone.now() - timedelta(days=value)
            return queryset.filter(started_at__gte=since_date)
        return queryset
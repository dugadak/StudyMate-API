import django_filters
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .models import StudySummary, StudyProgress, Subject


class StudySummaryFilter(django_filters.FilterSet):
    """Enhanced filters for StudySummary"""
    
    subject = django_filters.ModelChoiceFilter(
        queryset=Subject.objects.filter(is_active=True),
        field_name='subject'
    )
    difficulty_level = django_filters.ChoiceFilter(
        choices=StudySummary.DIFFICULTY_CHOICES
    )
    content_type = django_filters.ChoiceFilter(
        choices=StudySummary.CONTENT_TYPE_CHOICES
    )
    is_read = django_filters.BooleanFilter()
    is_bookmarked = django_filters.BooleanFilter()
    has_rating = django_filters.BooleanFilter(
        method='filter_has_rating',
        label='Has user rating'
    )
    min_rating = django_filters.NumberFilter(
        field_name='user_rating',
        lookup_expr='gte'
    )
    max_rating = django_filters.NumberFilter(
        field_name='user_rating',
        lookup_expr='lte'
    )
    generated_after = django_filters.DateTimeFilter(
        field_name='generated_at',
        lookup_expr='gte'
    )
    generated_before = django_filters.DateTimeFilter(
        field_name='generated_at',
        lookup_expr='lte'
    )
    recent_days = django_filters.NumberFilter(
        method='filter_recent_days',
        label='Generated within last N days'
    )
    ai_model = django_filters.CharFilter(
        field_name='ai_model_used',
        lookup_expr='icontains'
    )
    topics = django_filters.CharFilter(
        method='filter_topics',
        label='Contains topics (comma-separated)'
    )
    tags = django_filters.CharFilter(
        method='filter_tags',
        label='Contains tags (comma-separated)'
    )
    
    class Meta:
        model = StudySummary
        fields = []
    
    def filter_has_rating(self, queryset, name, value):
        """Filter summaries that have user ratings"""
        if value:
            return queryset.filter(user_rating__isnull=False)
        else:
            return queryset.filter(user_rating__isnull=True)
    
    def filter_recent_days(self, queryset, name, value):
        """Filter summaries generated within last N days"""
        if value and value > 0:
            since_date = timezone.now() - timedelta(days=value)
            return queryset.filter(generated_at__gte=since_date)
        return queryset
    
    def filter_topics(self, queryset, name, value):
        """Filter by topics contained in summary"""
        if value:
            topics = [topic.strip() for topic in value.split(',') if topic.strip()]
            if topics:
                query = Q()
                for topic in topics:
                    query |= Q(topics_covered__icontains=topic)
                return queryset.filter(query)
        return queryset
    
    def filter_tags(self, queryset, name, value):
        """Filter by tags contained in summary"""
        if value:
            tags = [tag.strip().lower() for tag in value.split(',') if tag.strip()]
            if tags:
                query = Q()
                for tag in tags:
                    query |= Q(tags__icontains=tag)
                return queryset.filter(query)
        return queryset


class StudyProgressFilter(django_filters.FilterSet):
    """Enhanced filters for StudyProgress"""
    
    subject = django_filters.ModelChoiceFilter(
        queryset=Subject.objects.filter(is_active=True),
        field_name='subject'
    )
    min_streak = django_filters.NumberFilter(
        field_name='current_streak',
        lookup_expr='gte'
    )
    max_streak = django_filters.NumberFilter(
        field_name='current_streak',
        lookup_expr='lte'
    )
    min_summaries = django_filters.NumberFilter(
        field_name='total_summaries_read',
        lookup_expr='gte'
    )
    min_quizzes = django_filters.NumberFilter(
        field_name='total_quizzes_completed',
        lookup_expr='gte'
    )
    active_since = django_filters.DateFilter(
        field_name='last_activity_date',
        lookup_expr='gte'
    )
    inactive_days = django_filters.NumberFilter(
        method='filter_inactive_days',
        label='Inactive for N days'
    )
    has_weekly_goal = django_filters.BooleanFilter(
        method='filter_has_weekly_goal',
        label='Has weekly goal set'
    )
    meets_weekly_goal = django_filters.BooleanFilter(
        method='filter_meets_weekly_goal',
        label='Meeting weekly goal'
    )
    completion_rate_min = django_filters.NumberFilter(
        field_name='completion_rate',
        lookup_expr='gte'
    )
    topics_learned = django_filters.CharFilter(
        method='filter_topics_learned',
        label='Contains learned topics (comma-separated)'
    )
    badges = django_filters.CharFilter(
        method='filter_badges',
        label='Has badges (comma-separated)'
    )
    
    class Meta:
        model = StudyProgress
        fields = []
    
    def filter_inactive_days(self, queryset, name, value):
        """Filter progress for users inactive for N days"""
        if value and value > 0:
            cutoff_date = timezone.now().date() - timedelta(days=value)
            return queryset.filter(last_activity_date__lt=cutoff_date)
        return queryset
    
    def filter_has_weekly_goal(self, queryset, name, value):
        """Filter progress with weekly goals"""
        if value:
            return queryset.filter(weekly_goal__gt=0)
        else:
            return queryset.filter(weekly_goal=0)
    
    def filter_meets_weekly_goal(self, queryset, name, value):
        """Filter progress meeting weekly goal"""
        if value:
            # This would need custom logic to calculate weekly progress
            # For now, return queryset as-is
            pass
        return queryset
    
    def filter_topics_learned(self, queryset, name, value):
        """Filter by topics learned"""
        if value:
            topics = [topic.strip() for topic in value.split(',') if topic.strip()]
            if topics:
                query = Q()
                for topic in topics:
                    query |= Q(topics_learned__icontains=topic)
                return queryset.filter(query)
        return queryset
    
    def filter_badges(self, queryset, name, value):
        """Filter by badges earned"""
        if value:
            badges = [badge.strip() for badge in value.split(',') if badge.strip()]
            if badges:
                query = Q()
                for badge in badges:
                    query |= Q(badges_earned__icontains=badge)
                return queryset.filter(query)
        return queryset


class SubjectFilter(django_filters.FilterSet):
    """Enhanced filters for Subject"""
    
    category = django_filters.ChoiceFilter(
        choices=Subject.CATEGORY_CHOICES
    )
    default_difficulty = django_filters.ChoiceFilter(
        choices=Subject.DIFFICULTY_CHOICES
    )
    requires_premium = django_filters.BooleanFilter()
    is_active = django_filters.BooleanFilter()
    min_learners = django_filters.NumberFilter(
        field_name='total_learners',
        lookup_expr='gte'
    )
    min_summaries = django_filters.NumberFilter(
        field_name='total_summaries',
        lookup_expr='gte'
    )
    min_rating = django_filters.NumberFilter(
        field_name='average_rating',
        lookup_expr='gte'
    )
    tags = django_filters.CharFilter(
        method='filter_tags',
        label='Contains tags (comma-separated)'
    )
    keywords = django_filters.CharFilter(
        method='filter_keywords',
        label='Contains keywords (comma-separated)'
    )
    
    class Meta:
        model = Subject
        fields = []
    
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
    
    def filter_keywords(self, queryset, name, value):
        """Filter by keywords"""
        if value:
            keywords = [keyword.strip().lower() for keyword in value.split(',') if keyword.strip()]
            if keywords:
                query = Q()
                for keyword in keywords:
                    query |= Q(keywords__icontains=keyword)
                return queryset.filter(query)
        return queryset
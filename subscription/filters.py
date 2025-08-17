import django_filters
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import (
    SubscriptionPlan, UserSubscription, UsageCredit, 
    Payment, Discount, DiscountUsage
)


class SubscriptionPlanFilter(django_filters.FilterSet):
    """Enhanced filters for SubscriptionPlan"""
    
    plan_type = django_filters.ChoiceFilter(
        choices=SubscriptionPlan.PLAN_TYPES
    )
    billing_interval = django_filters.ChoiceFilter(
        choices=SubscriptionPlan.BILLING_INTERVALS
    )
    min_price = django_filters.NumberFilter(
        field_name='price',
        lookup_expr='gte'
    )
    max_price = django_filters.NumberFilter(
        field_name='price',
        lookup_expr='lte'
    )
    has_trial = django_filters.BooleanFilter(
        method='filter_has_trial',
        label='Has trial period'
    )
    has_discount = django_filters.BooleanFilter(
        method='filter_has_discount',
        label='Has discount'
    )
    features = django_filters.CharFilter(
        method='filter_features',
        label='Has features (comma-separated)'
    )
    
    class Meta:
        model = SubscriptionPlan
        fields = ['is_active', 'is_popular', 'is_promotional']
    
    def filter_has_trial(self, queryset, name, value):
        """Filter plans with trial period"""
        if value:
            return queryset.filter(trial_days__gt=0)
        else:
            return queryset.filter(trial_days=0)
    
    def filter_has_discount(self, queryset, name, value):
        """Filter plans with discount"""
        if value:
            return queryset.filter(
                original_price__isnull=False,
                original_price__gt=F('price')
            )
        else:
            return queryset.filter(
                Q(original_price__isnull=True) |
                Q(original_price__lte=F('price'))
            )
    
    def filter_features(self, queryset, name, value):
        """Filter by features"""
        if value:
            features = [feature.strip() for feature in value.split(',') if feature.strip()]
            for feature in features:
                queryset = queryset.filter(features__has_key=feature)
            return queryset
        return queryset


class UserSubscriptionFilter(django_filters.FilterSet):
    """Enhanced filters for UserSubscription"""
    
    status = django_filters.ChoiceFilter(
        choices=UserSubscription.STATUS_CHOICES
    )
    plan_type = django_filters.ChoiceFilter(
        field_name='plan__plan_type',
        choices=SubscriptionPlan.PLAN_TYPES
    )
    billing_interval = django_filters.ChoiceFilter(
        field_name='plan__billing_interval',
        choices=SubscriptionPlan.BILLING_INTERVALS
    )
    expires_soon = django_filters.BooleanFilter(
        method='filter_expires_soon',
        label='Expires within 7 days'
    )
    in_trial = django_filters.BooleanFilter(
        method='filter_in_trial',
        label='Currently in trial'
    )
    started_after = django_filters.DateTimeFilter(
        field_name='started_at',
        lookup_expr='gte'
    )
    started_before = django_filters.DateTimeFilter(
        field_name='started_at',
        lookup_expr='lte'
    )
    expires_after = django_filters.DateTimeFilter(
        field_name='expires_at',
        lookup_expr='gte'
    )
    expires_before = django_filters.DateTimeFilter(
        field_name='expires_at',
        lookup_expr='lte'
    )
    has_discount = django_filters.BooleanFilter(
        method='filter_has_discount',
        label='Has discount applied'
    )
    
    class Meta:
        model = UserSubscription
        fields = ['is_recurring', 'auto_renew']
    
    def filter_expires_soon(self, queryset, name, value):
        """Filter subscriptions expiring soon"""
        if value:
            soon_date = timezone.now() + timedelta(days=7)
            return queryset.filter(
                expires_at__isnull=False,
                expires_at__lte=soon_date,
                status__in=['active', 'trialing']
            )
        return queryset
    
    def filter_in_trial(self, queryset, name, value):
        """Filter subscriptions in trial"""
        if value:
            return queryset.filter(
                status='trialing',
                trial_ends_at__isnull=False,
                trial_ends_at__gt=timezone.now()
            )
        else:
            return queryset.exclude(
                status='trialing',
                trial_ends_at__isnull=False,
                trial_ends_at__gt=timezone.now()
            )
    
    def filter_has_discount(self, queryset, name, value):
        """Filter subscriptions with discount"""
        if value:
            return queryset.filter(discount_applied__gt=0)
        else:
            return queryset.filter(discount_applied=0)


class UsageCreditFilter(django_filters.FilterSet):
    """Enhanced filters for UsageCredit"""
    
    credit_type = django_filters.ChoiceFilter(
        choices=UsageCredit.CREDIT_TYPES
    )
    reset_period = django_filters.ChoiceFilter(
        choices=[('daily', '일간'), ('weekly', '주간'), ('monthly', '월간')]
    )
    is_expired = django_filters.BooleanFilter(
        method='filter_is_expired',
        label='Is expired'
    )
    low_credits = django_filters.BooleanFilter(
        method='filter_low_credits',
        label='Low credits (less than 20%)'
    )
    has_daily_limit = django_filters.BooleanFilter(
        method='filter_has_daily_limit',
        label='Has daily limit'
    )
    plan_type = django_filters.ChoiceFilter(
        field_name='source_subscription__plan__plan_type',
        choices=SubscriptionPlan.PLAN_TYPES
    )
    
    class Meta:
        model = UsageCredit
        fields = ['is_unlimited']
    
    def filter_is_expired(self, queryset, name, value):
        """Filter expired credits"""
        now = timezone.now()
        if value:
            return queryset.filter(
                expires_at__isnull=False,
                expires_at__lt=now
            )
        else:
            return queryset.filter(
                Q(expires_at__isnull=True) |
                Q(expires_at__gte=now)
            )
    
    def filter_low_credits(self, queryset, name, value):
        """Filter credits that are running low"""
        if value:
            # This would require a custom SQL query in production
            # For now, we'll use a simple filter
            return queryset.extra(
                where=[
                    "(total_credits + bonus_credits - used_credits) <= (total_credits + bonus_credits) * 0.2"
                ]
            ).exclude(is_unlimited=True)
        return queryset
    
    def filter_has_daily_limit(self, queryset, name, value):
        """Filter credits with daily limits"""
        if value:
            return queryset.filter(daily_limit__isnull=False)
        else:
            return queryset.filter(daily_limit__isnull=True)


class PaymentFilter(django_filters.FilterSet):
    """Enhanced filters for Payment"""
    
    status = django_filters.ChoiceFilter(
        choices=Payment.STATUS_CHOICES
    )
    payment_method = django_filters.ChoiceFilter(
        choices=Payment.PAYMENT_METHODS
    )
    currency = django_filters.CharFilter()
    min_amount = django_filters.NumberFilter(
        field_name='amount',
        lookup_expr='gte'
    )
    max_amount = django_filters.NumberFilter(
        field_name='amount',
        lookup_expr='lte'
    )
    is_refunded = django_filters.BooleanFilter(
        method='filter_is_refunded',
        label='Has refunds'
    )
    plan_type = django_filters.ChoiceFilter(
        field_name='subscription__plan__plan_type',
        choices=SubscriptionPlan.PLAN_TYPES
    )
    created_after = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte'
    )
    created_before = django_filters.DateTimeFilter(
        field_name='created_at',
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
    recent_days = django_filters.NumberFilter(
        method='filter_recent_days',
        label='Payments within last N days'
    )
    
    class Meta:
        model = Payment
        fields = []
    
    def filter_is_refunded(self, queryset, name, value):
        """Filter payments with refunds"""
        if value:
            return queryset.filter(refund_amount__gt=0)
        else:
            return queryset.filter(refund_amount=0)
    
    def filter_recent_days(self, queryset, name, value):
        """Filter payments within last N days"""
        if value and value > 0:
            since_date = timezone.now() - timedelta(days=value)
            return queryset.filter(created_at__gte=since_date)
        return queryset


class DiscountFilter(django_filters.FilterSet):
    """Enhanced filters for Discount"""
    
    discount_type = django_filters.ChoiceFilter(
        choices=Discount.DISCOUNT_TYPES
    )
    is_valid_now = django_filters.BooleanFilter(
        method='filter_is_valid_now',
        label='Currently valid'
    )
    is_expired = django_filters.BooleanFilter(
        method='filter_is_expired',
        label='Is expired'
    )
    is_used_up = django_filters.BooleanFilter(
        method='filter_is_used_up',
        label='Usage limit reached'
    )
    min_value = django_filters.NumberFilter(
        field_name='value',
        lookup_expr='gte'
    )
    max_value = django_filters.NumberFilter(
        field_name='value',
        lookup_expr='lte'
    )
    usage_count = django_filters.NumberFilter(
        field_name='current_uses'
    )
    created_after = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte'
    )
    created_before = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte'
    )
    valid_from_after = django_filters.DateTimeFilter(
        field_name='valid_from',
        lookup_expr='gte'
    )
    valid_until_before = django_filters.DateTimeFilter(
        field_name='valid_until',
        lookup_expr='lte'
    )
    
    class Meta:
        model = Discount
        fields = ['is_active']
    
    def filter_is_valid_now(self, queryset, name, value):
        """Filter currently valid discounts"""
        now = timezone.now()
        if value:
            return queryset.filter(
                is_active=True,
                valid_from__lte=now,
                valid_until__gte=now
            ).filter(
                Q(max_uses__isnull=True) |
                Q(current_uses__lt=F('max_uses'))
            )
        else:
            return queryset.filter(
                Q(is_active=False) |
                Q(valid_from__gt=now) |
                Q(valid_until__lt=now) |
                (Q(max_uses__isnull=False) & Q(current_uses__gte=F('max_uses')))
            )
    
    def filter_is_expired(self, queryset, name, value):
        """Filter expired discounts"""
        now = timezone.now()
        if value:
            return queryset.filter(valid_until__lt=now)
        else:
            return queryset.filter(valid_until__gte=now)
    
    def filter_is_used_up(self, queryset, name, value):
        """Filter discounts that reached usage limit"""
        if value:
            return queryset.filter(
                max_uses__isnull=False,
                current_uses__gte=F('max_uses')
            )
        else:
            return queryset.filter(
                Q(max_uses__isnull=True) |
                Q(current_uses__lt=F('max_uses'))
            )


class DiscountUsageFilter(django_filters.FilterSet):
    """Enhanced filters for DiscountUsage"""
    
    discount_code = django_filters.CharFilter(
        field_name='discount__code',
        lookup_expr='icontains'
    )
    discount_type = django_filters.ChoiceFilter(
        field_name='discount__discount_type',
        choices=Discount.DISCOUNT_TYPES
    )
    user_email = django_filters.CharFilter(
        field_name='user__email',
        lookup_expr='icontains'
    )
    min_discount = django_filters.NumberFilter(
        field_name='amount_discounted',
        lookup_expr='gte'
    )
    max_discount = django_filters.NumberFilter(
        field_name='amount_discounted',
        lookup_expr='lte'
    )
    has_payment = django_filters.BooleanFilter(
        method='filter_has_payment',
        label='Has associated payment'
    )
    used_after = django_filters.DateTimeFilter(
        field_name='used_at',
        lookup_expr='gte'
    )
    used_before = django_filters.DateTimeFilter(
        field_name='used_at',
        lookup_expr='lte'
    )
    recent_days = django_filters.NumberFilter(
        method='filter_recent_days',
        label='Used within last N days'
    )
    
    class Meta:
        model = DiscountUsage
        fields = []
    
    def filter_has_payment(self, queryset, name, value):
        """Filter usages with associated payments"""
        if value:
            return queryset.filter(payment__isnull=False)
        else:
            return queryset.filter(payment__isnull=True)
    
    def filter_recent_days(self, queryset, name, value):
        """Filter usages within last N days"""
        if value and value > 0:
            since_date = timezone.now() - timedelta(days=value)
            return queryset.filter(used_at__gte=since_date)
        return queryset
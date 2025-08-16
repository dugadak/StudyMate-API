from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class SubscriptionPlan(models.Model):
    PLAN_TYPES = [
        ('quiz_10', '퀴즈 10회권'),
        ('quiz_100', '퀴즈 100회권'),
        ('summary_5', '하루 5번 요약정보 제공'),
        ('summary_10', '하루 10번 요약정보 제공'),
        ('time_change_5', '고정시간 변경권 5회'),
        ('time_change_10', '고정시간 변경권 10회'),
        ('pro_monthly', '프로플랜 월 구독'),
    ]
    
    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    duration_days = models.IntegerField(null=True, blank=True, help_text="구독 기간 (일), null이면 일회성")
    features = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.price}원"


class UserSubscription(models.Model):
    STATUS_CHOICES = [
        ('active', '활성'),
        ('expired', '만료'),
        ('cancelled', '취소'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    stripe_subscription_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_recurring = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.plan.name}"

    def is_active(self):
        if self.status != 'active':
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    def save(self, *args, **kwargs):
        if not self.expires_at and self.plan.duration_days:
            self.expires_at = timezone.now() + timedelta(days=self.plan.duration_days)
        super().save(*args, **kwargs)


class UsageCredit(models.Model):
    CREDIT_TYPES = [
        ('quiz', '퀴즈'),
        ('summary', '요약정보'),
        ('time_change', '시간변경'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='usage_credits')
    credit_type = models.CharField(max_length=20, choices=CREDIT_TYPES)
    total_credits = models.IntegerField(default=0)
    used_credits = models.IntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    source_subscription = models.ForeignKey(UserSubscription, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'credit_type']

    def __str__(self):
        return f"{self.user.email} - {self.get_credit_type_display()}: {self.remaining_credits}/{self.total_credits}"

    @property
    def remaining_credits(self):
        return self.total_credits - self.used_credits

    def can_use_credit(self):
        if self.remaining_credits <= 0:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    def use_credit(self, amount=1):
        if self.can_use_credit() and self.remaining_credits >= amount:
            self.used_credits += amount
            self.save()
            return True
        return False


class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', '대기중'),
        ('completed', '완료'),
        ('failed', '실패'),
        ('refunded', '환불'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subscription = models.ForeignKey(UserSubscription, on_delete=models.CASCADE)
    stripe_payment_intent_id = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.amount}원 ({self.get_status_display()})"

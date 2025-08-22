from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from datetime import timedelta
from typing import Dict, Any, Optional
import logging
import stripe

logger = logging.getLogger(__name__)


class SubscriptionPlan(models.Model):
    """Enhanced Subscription Plan model with comprehensive features"""
    
    PLAN_TYPES = [
        ('quiz_10', '퀴즈 10회권'),
        ('quiz_100', '퀴즈 100회권'),
        ('quiz_unlimited', '퀴즈 무제한'),
        ('summary_5', '하루 5번 요약정보 제공'),
        ('summary_10', '하루 10번 요약정보 제공'),
        ('summary_unlimited', '요약정보 무제한'),
        ('time_change_5', '고정시간 변경권 5회'),
        ('time_change_10', '고정시간 변경권 10회'),
        ('basic_monthly', '베이직 월 구독'),
        ('pro_monthly', '프로 월 구독'),
        ('premium_monthly', '프리미엄 월 구독'),
        ('basic_yearly', '베이직 연 구독'),
        ('pro_yearly', '프로 연 구독'),
        ('premium_yearly', '프리미엄 연 구독'),
    ]
    
    BILLING_INTERVALS = [
        ('one_time', '일회성'),
        ('monthly', '월간'),
        ('quarterly', '분기'),
        ('yearly', '연간'),
    ]
    
    name = models.CharField(max_length=100, db_index=True)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES, unique=True, db_index=True)
    stripe_price_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    stripe_product_id = models.CharField(max_length=100, blank=True, null=True)
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    original_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="할인 전 원가"
    )
    description = models.TextField()
    short_description = models.CharField(max_length=200, blank=True)
    billing_interval = models.CharField(
        max_length=20, 
        choices=BILLING_INTERVALS, 
        default='one_time'
    )
    duration_days = models.IntegerField(
        null=True, 
        blank=True, 
        validators=[MinValueValidator(1)],
        help_text="구독 기간 (일), null이면 일회성"
    )
    features = models.JSONField(default=dict, help_text="플랜 기능 정의")
    limits = models.JSONField(default=dict, help_text="사용량 제한")
    is_active = models.BooleanField(default=True, db_index=True)
    is_popular = models.BooleanField(default=False, help_text="인기 플랜 표시")
    is_promotional = models.BooleanField(default=False, help_text="프로모션 플랜")
    max_users = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="최대 사용자 수 제한"
    )
    trial_days = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="무료 체험 기간 (일)"
    )
    order = models.IntegerField(default=0, help_text="정렬 순서")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'price']
        indexes = [
            models.Index(fields=['plan_type', 'is_active']),
            models.Index(fields=['billing_interval', 'is_active']),
            models.Index(fields=['price', 'is_active']),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} - {self.price}원"
    
    def clean(self) -> None:
        """Model validation"""
        super().clean()
        
        if self.billing_interval != 'one_time' and not self.duration_days:
            raise ValidationError("반복 구독은 duration_days가 필요합니다.")
        
        if self.original_price and self.original_price <= self.price:
            raise ValidationError("할인 후 가격이 원가보다 높을 수 없습니다.")
    
    @property
    def discount_percentage(self) -> float:
        """Calculate discount percentage"""
        if not self.original_price or self.original_price <= self.price:
            return 0.0
        return float((self.original_price - self.price) / self.original_price * 100)
    
    @property
    def is_recurring(self) -> bool:
        """Check if plan is recurring"""
        return self.billing_interval != 'one_time'
    
    def get_credits_for_type(self, credit_type: str) -> int:
        """Get credit amount for specific type"""
        return self.limits.get(credit_type, 0)
    
    def has_feature(self, feature: str) -> bool:
        """Check if plan has specific feature"""
        return self.features.get(feature, False)
    
    def create_stripe_price(self) -> Optional[str]:
        """Create Stripe price for this plan"""
        if not stripe.api_key or self.stripe_price_id:
            return self.stripe_price_id
        
        try:
            # Create or get product
            if not self.stripe_product_id:
                product = stripe.Product.create(
                    name=self.name,
                    description=self.description,
                    metadata={'plan_type': self.plan_type}
                )
                self.stripe_product_id = product.id
                self.save(update_fields=['stripe_product_id'])
            
            # Create price
            price_data = {
                'unit_amount': int(self.price * 100),  # Convert to cents
                'currency': 'krw',
                'product': self.stripe_product_id,
                'metadata': {'plan_type': self.plan_type}
            }
            
            if self.is_recurring:
                interval_mapping = {
                    'monthly': 'month',
                    'quarterly': 'month',
                    'yearly': 'year'
                }
                
                price_data['recurring'] = {
                    'interval': interval_mapping.get(self.billing_interval, 'month')
                }
                
                if self.billing_interval == 'quarterly':
                    price_data['recurring']['interval_count'] = 3
            
            stripe_price = stripe.Price.create(**price_data)
            self.stripe_price_id = stripe_price.id
            self.save(update_fields=['stripe_price_id'])
            
            logger.info(f"Created Stripe price for plan {self.name}: {stripe_price.id}")
            return stripe_price.id
            
        except Exception as e:
            logger.error(f"Failed to create Stripe price for plan {self.name}: {str(e)}")
            return None


class UserSubscription(models.Model):
    """Enhanced User Subscription model with comprehensive tracking"""
    
    STATUS_CHOICES = [
        ('trialing', '체험 중'),
        ('active', '활성'),
        ('past_due', '결제 연체'),
        ('canceled', '취소'),
        ('unpaid', '미결제'),
        ('expired', '만료'),
        ('paused', '일시정지'),
    ]
    
    CANCELLATION_REASONS = [
        ('user_request', '사용자 요청'),
        ('payment_failed', '결제 실패'),
        ('admin_action', '관리자 조치'),
        ('fraud', '부정 사용'),
        ('other', '기타'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='subscriptions',
        db_index=True
    )
    plan = models.ForeignKey(
        SubscriptionPlan, 
        on_delete=models.PROTECT,
        related_name='subscriptions'
    )
    stripe_subscription_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        unique=True,
        db_index=True
    )
    stripe_customer_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        db_index=True
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='active',
        db_index=True
    )
    started_at = models.DateTimeField(auto_now_add=True, db_index=True, null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(
        max_length=20,
        choices=CANCELLATION_REASONS,
        blank=True,
        null=True
    )
    cancellation_note = models.TextField(blank=True)
    is_recurring = models.BooleanField(default=False)
    auto_renew = models.BooleanField(default=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    billing_cycle_anchor = models.DateTimeField(null=True, blank=True)
    quantity = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    discount_applied = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="할인율 (퍼센트)"
    )
    metadata = models.JSONField(default=dict, help_text="추가 메타데이터")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['plan', 'status']),
            models.Index(fields=['is_recurring', 'status']),
        ]
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.plan.name} ({self.get_status_display()})"
    
    def clean(self) -> None:
        """Model validation"""
        super().clean()
        
        if self.canceled_at and self.status not in ['canceled', 'expired']:
            raise ValidationError("취소된 구독은 canceled 또는 expired 상태여야 합니다.")
        
        if self.trial_ends_at and self.trial_ends_at <= timezone.now() and self.status == 'trialing':
            raise ValidationError("체험 기간이 만료된 구독은 trialing 상태일 수 없습니다.")
    
    def save(self, *args, **kwargs) -> None:
        """Enhanced save with automatic field population"""
        # Set expiration date for non-recurring subscriptions
        if not self.expires_at and self.plan.duration_days and not self.is_recurring:
            self.expires_at = timezone.now() + timedelta(days=self.plan.duration_days)
        
        # Set trial end date
        if not self.trial_ends_at and self.plan.trial_days > 0:
            self.trial_ends_at = timezone.now() + timedelta(days=self.plan.trial_days)
            self.status = 'trialing'
        
        # Set recurring flag based on plan
        if self.plan.is_recurring:
            self.is_recurring = True
        
        super().save(*args, **kwargs)
    
    @property
    def is_active(self) -> bool:
        """Check if subscription is currently active"""
        if self.status not in ['active', 'trialing']:
            return False
        
        now = timezone.now()
        
        # Check trial period
        if self.status == 'trialing' and self.trial_ends_at and now > self.trial_ends_at:
            return False
        
        # Check expiration
        if self.expires_at and now > self.expires_at:
            return False
        
        return True
    
    @property
    def is_trial(self) -> bool:
        """Check if subscription is in trial period"""
        return (
            self.status == 'trialing' and 
            self.trial_ends_at and 
            timezone.now() <= self.trial_ends_at
        )
    
    @property
    def days_remaining(self) -> Optional[int]:
        """Get days remaining in subscription"""
        if not self.expires_at:
            return None
        
        remaining = self.expires_at - timezone.now()
        return max(0, remaining.days)
    
    @property
    def trial_days_remaining(self) -> Optional[int]:
        """Get trial days remaining"""
        if not self.trial_ends_at or not self.is_trial:
            return None
        
        remaining = self.trial_ends_at - timezone.now()
        return max(0, remaining.days)
    
    def cancel(self, reason: str = 'user_request', note: str = '') -> bool:
        """Cancel subscription"""
        try:
            self.status = 'canceled'
            self.canceled_at = timezone.now()
            self.cancellation_reason = reason
            self.cancellation_note = note
            self.auto_renew = False
            
            # Cancel in Stripe if applicable
            if self.stripe_subscription_id:
                try:
                    stripe.Subscription.modify(
                        self.stripe_subscription_id,
                        cancel_at_period_end=True
                    )
                    logger.info(f"Canceled Stripe subscription: {self.stripe_subscription_id}")
                except Exception as e:
                    logger.error(f"Failed to cancel Stripe subscription {self.stripe_subscription_id}: {str(e)}")
            
            self.save()
            logger.info(f"Canceled subscription for user {self.user.email}, reason: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel subscription {self.id}: {str(e)}")
            return False
    
    def pause(self) -> bool:
        """Pause subscription"""
        if self.status not in ['active', 'trialing']:
            return False
        
        try:
            self.status = 'paused'
            self.save()
            
            # Pause in Stripe if applicable
            if self.stripe_subscription_id:
                try:
                    stripe.Subscription.modify(
                        self.stripe_subscription_id,
                        pause_collection={'behavior': 'mark_uncollectible'}
                    )
                except Exception as e:
                    logger.error(f"Failed to pause Stripe subscription {self.stripe_subscription_id}: {str(e)}")
            
            logger.info(f"Paused subscription for user {self.user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to pause subscription {self.id}: {str(e)}")
            return False
    
    def resume(self) -> bool:
        """Resume paused subscription"""
        if self.status != 'paused':
            return False
        
        try:
            self.status = 'active'
            self.save()
            
            # Resume in Stripe if applicable
            if self.stripe_subscription_id:
                try:
                    stripe.Subscription.modify(
                        self.stripe_subscription_id,
                        pause_collection=''
                    )
                except Exception as e:
                    logger.error(f"Failed to resume Stripe subscription {self.stripe_subscription_id}: {str(e)}")
            
            logger.info(f"Resumed subscription for user {self.user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to resume subscription {self.id}: {str(e)}")
            return False
    
    def get_effective_price(self) -> Decimal:
        """Get effective price after discount"""
        base_price = self.plan.price * self.quantity
        if self.discount_applied > 0:
            discount_amount = base_price * (self.discount_applied / 100)
            return base_price - discount_amount
        return base_price
    
    def sync_with_stripe(self) -> bool:
        """Sync subscription status with Stripe"""
        if not self.stripe_subscription_id:
            return False
        
        try:
            stripe_sub = stripe.Subscription.retrieve(self.stripe_subscription_id)
            
            status_mapping = {
                'trialing': 'trialing',
                'active': 'active',
                'past_due': 'past_due',
                'canceled': 'canceled',
                'unpaid': 'unpaid',
            }
            
            self.status = status_mapping.get(stripe_sub.status, self.status)
            self.current_period_start = timezone.datetime.fromtimestamp(
                stripe_sub.current_period_start, tz=timezone.utc
            )
            self.current_period_end = timezone.datetime.fromtimestamp(
                stripe_sub.current_period_end, tz=timezone.utc
            )
            
            if stripe_sub.trial_end:
                self.trial_ends_at = timezone.datetime.fromtimestamp(
                    stripe_sub.trial_end, tz=timezone.utc
                )
            
            if stripe_sub.canceled_at:
                self.canceled_at = timezone.datetime.fromtimestamp(
                    stripe_sub.canceled_at, tz=timezone.utc
                )
            
            self.save()
            logger.info(f"Synced subscription {self.id} with Stripe")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync subscription {self.id} with Stripe: {str(e)}")
            return False


class UsageCredit(models.Model):
    """Enhanced Usage Credit model with comprehensive tracking"""
    
    CREDIT_TYPES = [
        ('quiz', '퀴즈'),
        ('summary', '요약정보'),
        ('time_change', '시간변경'),
        ('ai_generation', 'AI 생성'),
        ('premium_feature', '프리미엄 기능'),
        ('export', '내보내기'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='usage_credits',
        db_index=True
    )
    credit_type = models.CharField(max_length=20, choices=CREDIT_TYPES, db_index=True)
    total_credits = models.IntegerField(
        default=0, 
        validators=[MinValueValidator(0)]
    )
    used_credits = models.IntegerField(
        default=0, 
        validators=[MinValueValidator(0)]
    )
    bonus_credits = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="보너스 크레딧"
    )
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    source_subscription = models.ForeignKey(
        UserSubscription, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='credits'
    )
    is_unlimited = models.BooleanField(
        default=False,
        help_text="무제한 사용 가능"
    )
    reset_period = models.CharField(
        max_length=20,
        choices=[('daily', '일간'), ('weekly', '주간'), ('monthly', '월간')],
        null=True,
        blank=True,
        help_text="크레딧 초기화 주기"
    )
    last_reset_at = models.DateTimeField(null=True, blank=True)
    daily_limit = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="일일 사용 제한"
    )
    daily_used = models.IntegerField(default=0)
    last_daily_reset = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'credit_type', 'source_subscription']
        indexes = [
            models.Index(fields=['user', 'credit_type']),
            models.Index(fields=['expires_at', 'credit_type']),
            models.Index(fields=['is_unlimited', 'credit_type']),
        ]
    
    def __str__(self) -> str:
        if self.is_unlimited:
            return f"{self.user.email} - {self.get_credit_type_display()}: 무제한"
        return f"{self.user.email} - {self.get_credit_type_display()}: {self.remaining_credits}/{self.total_credits}"
    
    def clean(self) -> None:
        """Model validation"""
        super().clean()
        
        if self.used_credits > self.total_credits and not self.is_unlimited:
            raise ValidationError("사용한 크레딧이 총 크레딧보다 클 수 없습니다.")
        
        if self.daily_used > self.daily_limit and self.daily_limit:
            raise ValidationError("일일 사용량이 제한을 초과했습니다.")
    
    @property
    def remaining_credits(self) -> int:
        """Get remaining credits"""
        if self.is_unlimited:
            return 999999  # Represent unlimited as large number
        return max(0, self.total_credits + self.bonus_credits - self.used_credits)
    
    @property
    def daily_remaining(self) -> Optional[int]:
        """Get remaining daily credits"""
        if not self.daily_limit:
            return None
        return max(0, self.daily_limit - self.daily_used)
    
    def can_use_credit(self, amount: int = 1) -> bool:
        """Check if credits can be used"""
        # Check if unlimited
        if self.is_unlimited:
            return True
        
        # Check if expired
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        
        # Check remaining credits
        if self.remaining_credits < amount:
            return False
        
        # Check daily limit
        if self.daily_limit and self.daily_remaining is not None:
            if self.daily_remaining < amount:
                return False
        
        return True
    
    def use_credit(self, amount: int = 1, force: bool = False) -> bool:
        """Use credits with validation"""
        if not force and not self.can_use_credit(amount):
            return False
        
        if not self.is_unlimited:
            self.used_credits += amount
        
        # Update daily usage
        if self.daily_limit:
            today = timezone.now().date()
            if self.last_daily_reset != today:
                self.daily_used = 0
                self.last_daily_reset = today
            
            self.daily_used += amount
        
        self.save(update_fields=['used_credits', 'daily_used', 'last_daily_reset', 'updated_at'])
        
        logger.info(f"Used {amount} {self.credit_type} credits for user {self.user.email}")
        return True
    
    def add_credits(self, amount: int, bonus: bool = False) -> None:
        """Add credits to the account"""
        if bonus:
            self.bonus_credits += amount
        else:
            self.total_credits += amount
        
        self.save(update_fields=['total_credits', 'bonus_credits', 'updated_at'])
        logger.info(f"Added {amount} {'bonus ' if bonus else ''}{self.credit_type} credits for user {self.user.email}")
    
    def reset_credits(self) -> None:
        """Reset credits based on reset period"""
        if not self.reset_period:
            return
        
        now = timezone.now()
        should_reset = False
        
        if self.reset_period == 'daily':
            if not self.last_reset_at or self.last_reset_at.date() < now.date():
                should_reset = True
        elif self.reset_period == 'weekly':
            if not self.last_reset_at or (now - self.last_reset_at).days >= 7:
                should_reset = True
        elif self.reset_period == 'monthly':
            if not self.last_reset_at or (
                self.last_reset_at.month != now.month or 
                self.last_reset_at.year != now.year
            ):
                should_reset = True
        
        if should_reset:
            self.used_credits = 0
            self.last_reset_at = now
            self.save(update_fields=['used_credits', 'last_reset_at', 'updated_at'])
            logger.info(f"Reset {self.credit_type} credits for user {self.user.email}")
    
    @classmethod
    def get_user_credits(cls, user, credit_type: str) -> 'UsageCredit':
        """Get or create user credits for specific type"""
        credit, created = cls.objects.get_or_create(
            user=user,
            credit_type=credit_type,
            defaults={
                'total_credits': 0,
                'used_credits': 0
            }
        )
        
        if not created:
            credit.reset_credits()  # Check for auto-reset
        
        return credit


class Payment(models.Model):
    """Enhanced Payment model with comprehensive tracking"""
    
    STATUS_CHOICES = [
        ('pending', '대기중'),
        ('processing', '처리중'),
        ('requires_payment_method', '결제수단 필요'),
        ('requires_confirmation', '확인 필요'),
        ('requires_action', '추가 작업 필요'),
        ('canceled', '취소'),
        ('succeeded', '성공'),
        ('failed', '실패'),
        ('refunded', '환불'),
        ('partially_refunded', '부분 환불'),
    ]
    
    PAYMENT_METHODS = [
        ('card', '카드'),
        ('bank_transfer', '계좌이체'),
        ('virtual_account', '가상계좌'),
        ('mobile', '휴대폰'),
        ('kakaopay', '카카오페이'),
        ('naverpay', '네이버페이'),
        ('payco', '페이코'),
        ('samsung_pay', '삼성페이'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='payments',
        db_index=True
    )
    subscription = models.ForeignKey(
        UserSubscription, 
        on_delete=models.CASCADE,
        related_name='payments',
        null=True,
        blank=True
    )
    stripe_payment_intent_id = models.CharField(
        max_length=100, 
        unique=True, 
        null=True, 
        blank=True,
        db_index=True
    )
    stripe_invoice_id = models.CharField(
        max_length=100, 
        null=True, 
        blank=True,
        db_index=True
    )
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=3, default='KRW')
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS,
        default='card'
    )
    status = models.CharField(
        max_length=30, 
        choices=STATUS_CHOICES, 
        default='pending',
        db_index=True
    )
    failure_reason = models.TextField(blank=True, null=True)
    failure_code = models.CharField(max_length=50, blank=True, null=True)
    refund_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    refund_reason = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, help_text="추가 결제 정보")
    receipt_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['subscription', 'status']),
        ]
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.amount}{self.currency} ({self.get_status_display()})"
    
    def clean(self) -> None:
        """Model validation"""
        super().clean()
        
        if self.refund_amount > self.amount:
            raise ValidationError("환불 금액이 결제 금액보다 클 수 없습니다.")
        
        if self.status == 'refunded' and self.refund_amount == 0:
            raise ValidationError("환불된 결제는 환불 금액이 있어야 합니다.")
    
    @property
    def is_successful(self) -> bool:
        """Check if payment was successful"""
        return self.status == 'succeeded'
    
    @property
    def is_refundable(self) -> bool:
        """Check if payment can be refunded"""
        return (
            self.status == 'succeeded' and 
            self.refund_amount < self.amount
        )
    
    @property
    def refundable_amount(self) -> Decimal:
        """Get amount that can still be refunded"""
        return self.amount - self.refund_amount
    
    def process_refund(self, amount: Decimal, reason: str = '') -> bool:
        """Process refund for this payment"""
        if not self.is_refundable or amount > self.refundable_amount:
            return False
        
        try:
            # Process refund in Stripe if applicable
            if self.stripe_payment_intent_id:
                try:
                    refund = stripe.Refund.create(
                        payment_intent=self.stripe_payment_intent_id,
                        amount=int(amount * 100),  # Convert to cents
                        reason='requested_by_customer',
                        metadata={'reason': reason}
                    )
                    logger.info(f"Created Stripe refund: {refund.id}")
                except Exception as e:
                    logger.error(f"Failed to create Stripe refund: {str(e)}")
                    return False
            
            # Update payment record
            self.refund_amount += amount
            self.refund_reason = reason
            self.refunded_at = timezone.now()
            
            if self.refund_amount >= self.amount:
                self.status = 'refunded'
            else:
                self.status = 'partially_refunded'
            
            self.save()
            logger.info(f"Processed refund of {amount} for payment {self.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process refund for payment {self.id}: {str(e)}")
            return False
    
    def sync_with_stripe(self) -> bool:
        """Sync payment status with Stripe"""
        if not self.stripe_payment_intent_id:
            return False
        
        try:
            payment_intent = stripe.PaymentIntent.retrieve(self.stripe_payment_intent_id)
            
            status_mapping = {
                'requires_payment_method': 'requires_payment_method',
                'requires_confirmation': 'requires_confirmation',
                'requires_action': 'requires_action',
                'processing': 'processing',
                'canceled': 'canceled',
                'succeeded': 'succeeded',
            }
            
            self.status = status_mapping.get(payment_intent.status, self.status)
            
            if payment_intent.status == 'succeeded' and not self.completed_at:
                self.completed_at = timezone.now()
            elif payment_intent.status in ['canceled', 'requires_payment_method'] and not self.failed_at:
                self.failed_at = timezone.now()
                if payment_intent.last_payment_error:
                    self.failure_reason = payment_intent.last_payment_error.message
                    self.failure_code = payment_intent.last_payment_error.code
            
            self.save()
            logger.info(f"Synced payment {self.id} with Stripe")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync payment {self.id} with Stripe: {str(e)}")
            return False


class Discount(models.Model):
    """Discount and promotion model"""
    
    DISCOUNT_TYPES = [
        ('percentage', '퍼센트'),
        ('fixed_amount', '고정 금액'),
        ('free_trial', '무료 체험'),
    ]
    
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES)
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    max_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="최대 할인 금액 (퍼센트 할인 시)"
    )
    applicable_plans = models.ManyToManyField(
        SubscriptionPlan,
        blank=True,
        help_text="적용 가능한 플랜 (비어있으면 모든 플랜)"
    )
    min_purchase_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="최소 구매 금액"
    )
    max_uses = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="최대 사용 횟수"
    )
    max_uses_per_user = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="사용자당 최대 사용 횟수"
    )
    current_uses = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    valid_from = models.DateTimeField(db_index=True)
    valid_until = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code', 'is_active']),
            models.Index(fields=['valid_from', 'valid_until']),
        ]
    
    def __str__(self) -> str:
        return f"{self.code} - {self.name}"
    
    def clean(self) -> None:
        """Model validation"""
        super().clean()
        
        if self.valid_until <= self.valid_from:
            raise ValidationError("종료일이 시작일보다 늦어야 합니다.")
        
        if self.discount_type == 'percentage' and self.value > 100:
            raise ValidationError("퍼센트 할인은 100%를 초과할 수 없습니다.")
    
    def is_valid(self, user=None, plan=None, amount=None) -> tuple[bool, str]:
        """Check if discount is valid for given conditions"""
        now = timezone.now()
        
        # Check if active
        if not self.is_active:
            return False, "할인 코드가 비활성화되었습니다."
        
        # Check date range
        if now < self.valid_from:
            return False, "할인 코드가 아직 유효하지 않습니다."
        
        if now > self.valid_until:
            return False, "할인 코드가 만료되었습니다."
        
        # Check usage limits
        if self.max_uses and self.current_uses >= self.max_uses:
            return False, "할인 코드 사용 한도에 도달했습니다."
        
        # Check per-user usage limit
        if user and self.max_uses_per_user:
            user_uses = DiscountUsage.objects.filter(
                discount=self,
                user=user
            ).count()
            if user_uses >= self.max_uses_per_user:
                return False, "사용자별 할인 코드 사용 한도에 도달했습니다."
        
        # Check applicable plans
        if plan and self.applicable_plans.exists():
            if not self.applicable_plans.filter(id=plan.id).exists():
                return False, "이 플랜에는 적용할 수 없는 할인 코드입니다."
        
        # Check minimum purchase amount
        if amount and self.min_purchase_amount:
            if amount < self.min_purchase_amount:
                return False, f"최소 구매 금액 {self.min_purchase_amount}원 이상이어야 합니다."
        
        return True, "유효한 할인 코드입니다."
    
    def calculate_discount(self, amount: Decimal) -> Decimal:
        """Calculate discount amount"""
        if self.discount_type == 'percentage':
            discount = amount * (self.value / 100)
            if self.max_discount_amount:
                discount = min(discount, self.max_discount_amount)
            return discount
        elif self.discount_type == 'fixed_amount':
            return min(self.value, amount)
        
        return Decimal('0.00')
    
    def use_discount(self, user, amount: Decimal) -> bool:
        """Use the discount and record usage"""
        try:
            # Create usage record
            DiscountUsage.objects.create(
                discount=self,
                user=user,
                amount_discounted=self.calculate_discount(amount)
            )
            
            # Increment usage count
            self.current_uses += 1
            self.save(update_fields=['current_uses'])
            
            logger.info(f"Used discount {self.code} for user {user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to use discount {self.code}: {str(e)}")
            return False


class DiscountUsage(models.Model):
    """Track discount usage"""
    
    discount = models.ForeignKey(
        Discount,
        on_delete=models.CASCADE,
        related_name='usages'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='discount_usages'
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='discount_usages'
    )
    amount_discounted = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    used_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-used_at']
        indexes = [
            models.Index(fields=['discount', 'user']),
            models.Index(fields=['user', 'used_at']),
        ]
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.discount.code} ({self.amount_discounted}원 할인)"
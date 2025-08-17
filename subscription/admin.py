from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.http import HttpResponseRedirect
from django.contrib import messages
from decimal import Decimal
from typing import Any
import logging

from .models import (
    SubscriptionPlan, UserSubscription, UsageCredit, 
    Payment, Discount, DiscountUsage
)

logger = logging.getLogger(__name__)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    """Enhanced Subscription Plan admin with comprehensive management"""
    
    list_display = [
        'name', 'plan_type', 'price_display', 'billing_interval',
        'trial_days', 'is_active', 'is_popular', 'subscriber_count', 'order'
    ]
    list_filter = [
        'billing_interval', 'is_active', 'is_popular', 'is_promotional',
        'created_at'
    ]
    search_fields = ['name', 'plan_type', 'description']
    list_editable = ['order', 'is_active', 'is_popular']
    readonly_fields = [
        'stripe_price_id', 'stripe_product_id', 'discount_percentage',
        'subscriber_count', 'revenue_generated', 'created_at', 'updated_at'
    ]
    ordering = ['order', 'price']
    
    fieldsets = (
        ('기본 정보', {
            'fields': (
                'name', 'plan_type', 'short_description', 'description'
            )
        }),
        ('가격 정보', {
            'fields': (
                'price', 'original_price', 'discount_percentage',
                'billing_interval', 'duration_days'
            )
        }),
        ('기능 및 제한', {
            'fields': (
                'features', 'limits', 'max_users', 'trial_days'
            )
        }),
        ('표시 설정', {
            'fields': (
                'is_active', 'is_popular', 'is_promotional', 'order'
            )
        }),
        ('Stripe 연동', {
            'fields': (
                'stripe_price_id', 'stripe_product_id'
            ),
            'classes': ['collapse']
        }),
        ('통계', {
            'fields': (
                'subscriber_count', 'revenue_generated'
            ),
            'classes': ['collapse']
        }),
        ('시스템 정보', {
            'fields': (
                'created_at', 'updated_at'
            ),
            'classes': ['collapse']
        }),
    )
    
    actions = [
        'activate_plans', 'deactivate_plans', 'mark_popular', 
        'unmark_popular', 'create_stripe_prices'
    ]
    
    def price_display(self, obj):
        """Display price with discount info"""
        if obj.original_price and obj.original_price > obj.price:
            return format_html(
                '<span style="text-decoration: line-through; color: #999;">{}</span> '
                '<strong style="color: #e74c3c;">{}</strong> '
                '<span style="color: #27ae60;">(-{:.0f}%)</span>',
                f"{obj.original_price:,}원",
                f"{obj.price:,}원",
                obj.discount_percentage
            )
        return f"{obj.price:,}원"
    price_display.short_description = '가격'
    price_display.admin_order_field = 'price'
    
    def subscriber_count(self, obj):
        """Display current subscriber count"""
        count = obj.subscriptions.filter(status__in=['active', 'trialing']).count()
        return format_html('<strong>{}</strong>명', count)
    subscriber_count.short_description = '구독자 수'
    
    def revenue_generated(self, obj):
        """Display total revenue generated"""
        revenue = obj.subscriptions.filter(
            payments__status='succeeded'
        ).aggregate(
            total=models.Sum('payments__amount')
        )['total'] or Decimal('0.00')
        
        return format_html('<strong>{:,}</strong>원', revenue)
    revenue_generated.short_description = '총 수익'
    
    def activate_plans(self, request, queryset):
        """Bulk activate plans"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated}개의 플랜이 활성화되었습니다.')
    activate_plans.short_description = '선택된 플랜 활성화'
    
    def deactivate_plans(self, request, queryset):
        """Bulk deactivate plans"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated}개의 플랜이 비활성화되었습니다.')
    deactivate_plans.short_description = '선택된 플랜 비활성화'
    
    def mark_popular(self, request, queryset):
        """Mark plans as popular"""
        updated = queryset.update(is_popular=True)
        self.message_user(request, f'{updated}개의 플랜이 인기 플랜으로 설정되었습니다.')
    mark_popular.short_description = '인기 플랜으로 표시'
    
    def unmark_popular(self, request, queryset):
        """Unmark plans as popular"""
        updated = queryset.update(is_popular=False)
        self.message_user(request, f'{updated}개의 플랜이 인기 플랜에서 제외되었습니다.')
    unmark_popular.short_description = '인기 플랜 표시 해제'
    
    def create_stripe_prices(self, request, queryset):
        """Create Stripe prices for selected plans"""
        created_count = 0
        failed_count = 0
        
        for plan in queryset:
            if plan.create_stripe_price():
                created_count += 1
            else:
                failed_count += 1
        
        if created_count > 0:
            self.message_user(
                request, 
                f'{created_count}개의 Stripe 가격이 생성되었습니다.',
                messages.SUCCESS
            )
        
        if failed_count > 0:
            self.message_user(
                request,
                f'{failed_count}개의 Stripe 가격 생성에 실패했습니다.',
                messages.WARNING
            )
    create_stripe_prices.short_description = 'Stripe 가격 생성'


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    """Enhanced User Subscription admin with comprehensive tracking"""
    
    list_display = [
        'user_email', 'plan_name', 'status_display', 'billing_info',
        'subscription_period', 'effective_price_display', 'started_at'
    ]
    list_filter = [
        'status', 'plan__plan_type', 'is_recurring', 'auto_renew',
        'plan__billing_interval', 'started_at', 'expires_at'
    ]
    search_fields = [
        'user__email', 'user__first_name', 'user__last_name', 
        'plan__name', 'stripe_subscription_id'
    ]
    readonly_fields = [
        'stripe_subscription_id', 'stripe_customer_id', 'started_at',
        'is_active', 'is_trial', 'days_remaining', 'trial_days_remaining',
        'effective_price', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'started_at'
    ordering = ['-started_at']
    
    fieldsets = (
        ('구독 정보', {
            'fields': (
                'user', 'plan', 'status', 'quantity'
            )
        }),
        ('기간 정보', {
            'fields': (
                'started_at', 'expires_at', 'trial_ends_at',
                'current_period_start', 'current_period_end'
            )
        }),
        ('결제 정보', {
            'fields': (
                'is_recurring', 'auto_renew', 'discount_applied', 'effective_price'
            )
        }),
        ('취소 정보', {
            'fields': (
                'canceled_at', 'cancellation_reason', 'cancellation_note'
            ),
            'classes': ['collapse']
        }),
        ('Stripe 연동', {
            'fields': (
                'stripe_subscription_id', 'stripe_customer_id'
            ),
            'classes': ['collapse']
        }),
        ('상태 정보', {
            'fields': (
                'is_active', 'is_trial', 'days_remaining', 'trial_days_remaining'
            ),
            'classes': ['collapse']
        }),
        ('메타데이터', {
            'fields': (
                'metadata',
            ),
            'classes': ['collapse']
        }),
        ('시스템 정보', {
            'fields': (
                'created_at', 'updated_at'
            ),
            'classes': ['collapse']
        }),
    )
    
    actions = [
        'cancel_subscriptions', 'pause_subscriptions', 'resume_subscriptions',
        'sync_with_stripe'
    ]
    
    def user_email(self, obj):
        """Display user email with link"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:auth_user_change', args=[obj.user.id]),
            obj.user.email
        )
    user_email.short_description = '사용자'
    user_email.admin_order_field = 'user__email'
    
    def plan_name(self, obj):
        """Display plan name with link"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:subscription_subscriptionplan_change', args=[obj.plan.id]),
            obj.plan.name
        )
    plan_name.short_description = '플랜'
    plan_name.admin_order_field = 'plan__name'
    
    def status_display(self, obj):
        """Display status with color coding"""
        status_colors = {
            'active': 'green',
            'trialing': 'blue',
            'canceled': 'red',
            'expired': 'gray',
            'past_due': 'orange',
            'paused': 'purple'
        }
        
        color = status_colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = '상태'
    status_display.admin_order_field = 'status'
    
    def billing_info(self, obj):
        """Display billing information"""
        info = []
        if obj.is_recurring:
            info.append('정기결제')
        if obj.auto_renew:
            info.append('자동갱신')
        if obj.discount_applied > 0:
            info.append(f'{obj.discount_applied}% 할인')
        
        return ' | '.join(info) if info else '-'
    billing_info.short_description = '결제 정보'
    
    def subscription_period(self, obj):
        """Display subscription period"""
        if obj.is_trial:
            return format_html(
                '<span style="color: blue;">체험 중 ({}일 남음)</span>',
                obj.trial_days_remaining or 0
            )
        elif obj.expires_at:
            days_left = obj.days_remaining
            if days_left is not None:
                if days_left <= 7:
                    color = 'red'
                elif days_left <= 30:
                    color = 'orange'
                else:
                    color = 'green'
                
                return format_html(
                    '<span style="color: {};">{} ~ {} ({}일 남음)</span>',
                    color,
                    obj.started_at.strftime('%Y-%m-%d'),
                    obj.expires_at.strftime('%Y-%m-%d'),
                    days_left
                )
        
        return f"{obj.started_at.strftime('%Y-%m-%d')} ~ 무제한"
    subscription_period.short_description = '구독 기간'
    
    def effective_price_display(self, obj):
        """Display effective price"""
        price = obj.get_effective_price()
        return format_html('<strong>{:,}</strong>원', price)
    effective_price_display.short_description = '실제 결제금액'
    
    def cancel_subscriptions(self, request, queryset):
        """Bulk cancel subscriptions"""
        canceled_count = 0
        failed_count = 0
        
        for subscription in queryset:
            if subscription.status not in ['canceled', 'expired']:
                if subscription.cancel(reason='admin_action'):
                    canceled_count += 1
                else:
                    failed_count += 1
        
        if canceled_count > 0:
            self.message_user(
                request,
                f'{canceled_count}개의 구독이 취소되었습니다.',
                messages.SUCCESS
            )
        
        if failed_count > 0:
            self.message_user(
                request,
                f'{failed_count}개의 구독 취소에 실패했습니다.',
                messages.WARNING
            )
    cancel_subscriptions.short_description = '선택된 구독 취소'
    
    def pause_subscriptions(self, request, queryset):
        """Bulk pause subscriptions"""
        paused_count = 0
        failed_count = 0
        
        for subscription in queryset:
            if subscription.status in ['active', 'trialing']:
                if subscription.pause():
                    paused_count += 1
                else:
                    failed_count += 1
        
        if paused_count > 0:
            self.message_user(
                request,
                f'{paused_count}개의 구독이 일시정지되었습니다.',
                messages.SUCCESS
            )
        
        if failed_count > 0:
            self.message_user(
                request,
                f'{failed_count}개의 구독 일시정지에 실패했습니다.',
                messages.WARNING
            )
    pause_subscriptions.short_description = '선택된 구독 일시정지'
    
    def resume_subscriptions(self, request, queryset):
        """Bulk resume subscriptions"""
        resumed_count = 0
        failed_count = 0
        
        for subscription in queryset:
            if subscription.status == 'paused':
                if subscription.resume():
                    resumed_count += 1
                else:
                    failed_count += 1
        
        if resumed_count > 0:
            self.message_user(
                request,
                f'{resumed_count}개의 구독이 재개되었습니다.',
                messages.SUCCESS
            )
        
        if failed_count > 0:
            self.message_user(
                request,
                f'{failed_count}개의 구독 재개에 실패했습니다.',
                messages.WARNING
            )
    resume_subscriptions.short_description = '선택된 구독 재개'
    
    def sync_with_stripe(self, request, queryset):
        """Sync subscriptions with Stripe"""
        synced_count = 0
        failed_count = 0
        
        for subscription in queryset:
            if subscription.stripe_subscription_id:
                if subscription.sync_with_stripe():
                    synced_count += 1
                else:
                    failed_count += 1
        
        if synced_count > 0:
            self.message_user(
                request,
                f'{synced_count}개의 구독이 Stripe와 동기화되었습니다.',
                messages.SUCCESS
            )
        
        if failed_count > 0:
            self.message_user(
                request,
                f'{failed_count}개의 구독 동기화에 실패했습니다.',
                messages.WARNING
            )
    sync_with_stripe.short_description = 'Stripe와 동기화'


@admin.register(UsageCredit)
class UsageCreditAdmin(admin.ModelAdmin):
    """Enhanced Usage Credit admin"""
    
    list_display = [
        'user_email', 'credit_type_display', 'credit_status', 
        'usage_percentage_display', 'source_display', 'expires_at'
    ]
    list_filter = [
        'credit_type', 'is_unlimited', 'reset_period', 
        'source_subscription__plan__plan_type', 'expires_at'
    ]
    search_fields = [
        'user__email', 'user__first_name', 'user__last_name'
    ]
    readonly_fields = [
        'remaining_credits', 'daily_remaining', 'usage_percentage',
        'created_at', 'updated_at'
    ]
    ordering = ['user__email', 'credit_type']
    
    fieldsets = (
        ('사용자 정보', {
            'fields': (
                'user', 'credit_type'
            )
        }),
        ('크레딧 정보', {
            'fields': (
                'total_credits', 'used_credits', 'bonus_credits', 
                'remaining_credits', 'is_unlimited'
            )
        }),
        ('일일 제한', {
            'fields': (
                'daily_limit', 'daily_used', 'daily_remaining', 'last_daily_reset'
            )
        }),
        ('리셋 설정', {
            'fields': (
                'reset_period', 'last_reset_at'
            )
        }),
        ('만료 및 소스', {
            'fields': (
                'expires_at', 'source_subscription'
            )
        }),
        ('시스템 정보', {
            'fields': (
                'created_at', 'updated_at'
            ),
            'classes': ['collapse']
        }),
    )
    
    actions = ['reset_usage', 'add_bonus_credits', 'extend_expiry']
    
    def user_email(self, obj):
        """Display user email"""
        return obj.user.email
    user_email.short_description = '사용자'
    user_email.admin_order_field = 'user__email'
    
    def credit_type_display(self, obj):
        """Display credit type"""
        return obj.get_credit_type_display()
    credit_type_display.short_description = '크레딧 타입'
    credit_type_display.admin_order_field = 'credit_type'
    
    def credit_status(self, obj):
        """Display credit status"""
        if obj.is_unlimited:
            return format_html('<span style="color: gold; font-weight: bold;">무제한</span>')
        
        remaining = obj.remaining_credits
        total = obj.total_credits + obj.bonus_credits
        
        if remaining <= 0:
            color = 'red'
            status = '소진'
        elif remaining <= total * 0.2:
            color = 'orange'
            status = '부족'
        else:
            color = 'green'
            status = '충분'
        
        return format_html(
            '<span style="color: {};">{} / {} ({})</span>',
            color, remaining, total, status
        )
    credit_status.short_description = '크레딧 상태'
    
    def usage_percentage_display(self, obj):
        """Display usage percentage"""
        if obj.is_unlimited:
            return '-'
        
        total = obj.total_credits + obj.bonus_credits
        if total == 0:
            return '0%'
        
        percentage = (obj.used_credits / total) * 100
        
        if percentage >= 80:
            color = 'red'
        elif percentage >= 60:
            color = 'orange'
        else:
            color = 'green'
        
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, percentage
        )
    usage_percentage_display.short_description = '사용률'
    
    def source_display(self, obj):
        """Display credit source"""
        if obj.source_subscription:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:subscription_usersubscription_change', 
                       args=[obj.source_subscription.id]),
                obj.source_subscription.plan.name
            )
        return '직접 추가'
    source_display.short_description = '소스'
    
    def reset_usage(self, request, queryset):
        """Reset credit usage"""
        for credit in queryset:
            credit.used_credits = 0
            credit.daily_used = 0
            credit.save()
        
        self.message_user(
            request,
            f'{queryset.count()}개의 크레딧 사용량이 초기화되었습니다.'
        )
    reset_usage.short_description = '사용량 초기화'
    
    def add_bonus_credits(self, request, queryset):
        """Add bonus credits"""
        # This would typically be done through a form
        amount = 10  # Default amount
        
        for credit in queryset:
            credit.add_credits(amount, bonus=True)
        
        self.message_user(
            request,
            f'{queryset.count()}개의 크레딧에 {amount}개의 보너스가 추가되었습니다.'
        )
    add_bonus_credits.short_description = '보너스 크레딧 추가 (10개)'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Enhanced Payment admin with comprehensive tracking"""
    
    list_display = [
        'user_email', 'subscription_plan_name', 'amount_display',
        'payment_method_display', 'status_display', 'created_at'
    ]
    list_filter = [
        'status', 'payment_method', 'currency', 'subscription__plan__plan_type',
        'created_at', 'completed_at'
    ]
    search_fields = [
        'user__email', 'stripe_payment_intent_id', 'stripe_invoice_id',
        'subscription__plan__name'
    ]
    readonly_fields = [
        'stripe_payment_intent_id', 'stripe_invoice_id', 'is_successful',
        'is_refundable', 'refundable_amount', 'receipt_url',
        'created_at', 'completed_at', 'failed_at', 'refunded_at'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('결제 정보', {
            'fields': (
                'user', 'subscription', 'amount', 'currency', 'payment_method'
            )
        }),
        ('상태', {
            'fields': (
                'status', 'is_successful', 'failure_reason', 'failure_code'
            )
        }),
        ('환불 정보', {
            'fields': (
                'refund_amount', 'refund_reason', 'is_refundable', 'refundable_amount'
            )
        }),
        ('Stripe 연동', {
            'fields': (
                'stripe_payment_intent_id', 'stripe_invoice_id', 'receipt_url'
            ),
            'classes': ['collapse']
        }),
        ('시간 정보', {
            'fields': (
                'created_at', 'completed_at', 'failed_at', 'refunded_at'
            ),
            'classes': ['collapse']
        }),
        ('메타데이터', {
            'fields': (
                'metadata',
            ),
            'classes': ['collapse']
        }),
    )
    
    actions = ['process_refunds', 'sync_with_stripe']
    
    def user_email(self, obj):
        """Display user email"""
        return obj.user.email
    user_email.short_description = '사용자'
    user_email.admin_order_field = 'user__email'
    
    def subscription_plan_name(self, obj):
        """Display subscription plan name"""
        if obj.subscription:
            return obj.subscription.plan.name
        return '-'
    subscription_plan_name.short_description = '구독 플랜'
    
    def amount_display(self, obj):
        """Display amount with currency"""
        return format_html(
            '<strong>{:,}</strong> {}',
            obj.amount, obj.currency
        )
    amount_display.short_description = '금액'
    amount_display.admin_order_field = 'amount'
    
    def payment_method_display(self, obj):
        """Display payment method"""
        return obj.get_payment_method_display()
    payment_method_display.short_description = '결제 수단'
    payment_method_display.admin_order_field = 'payment_method'
    
    def status_display(self, obj):
        """Display status with color coding"""
        status_colors = {
            'succeeded': 'green',
            'pending': 'orange',
            'failed': 'red',
            'canceled': 'gray',
            'refunded': 'purple',
            'partially_refunded': 'blue'
        }
        
        color = status_colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = '상태'
    status_display.admin_order_field = 'status'
    
    def process_refunds(self, request, queryset):
        """Process refunds for selected payments"""
        refunded_count = 0
        failed_count = 0
        
        for payment in queryset:
            if payment.is_refundable:
                if payment.process_refund(payment.refundable_amount, '관리자 환불'):
                    refunded_count += 1
                else:
                    failed_count += 1
        
        if refunded_count > 0:
            self.message_user(
                request,
                f'{refunded_count}개의 결제가 환불되었습니다.',
                messages.SUCCESS
            )
        
        if failed_count > 0:
            self.message_user(
                request,
                f'{failed_count}개의 환불 처리에 실패했습니다.',
                messages.WARNING
            )
    process_refunds.short_description = '전액 환불 처리'
    
    def sync_with_stripe(self, request, queryset):
        """Sync payments with Stripe"""
        synced_count = 0
        failed_count = 0
        
        for payment in queryset:
            if payment.stripe_payment_intent_id:
                if payment.sync_with_stripe():
                    synced_count += 1
                else:
                    failed_count += 1
        
        if synced_count > 0:
            self.message_user(
                request,
                f'{synced_count}개의 결제가 Stripe와 동기화되었습니다.',
                messages.SUCCESS
            )
        
        if failed_count > 0:
            self.message_user(
                request,
                f'{failed_count}개의 결제 동기화에 실패했습니다.',
                messages.WARNING
            )
    sync_with_stripe.short_description = 'Stripe와 동기화'


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    """Enhanced Discount admin"""
    
    list_display = [
        'code', 'name', 'discount_type_display', 'value_display',
        'usage_status', 'validity_period', 'is_active'
    ]
    list_filter = [
        'discount_type', 'is_active', 'valid_from', 'valid_until',
        'created_at'
    ]
    search_fields = ['code', 'name', 'description']
    readonly_fields = [
        'current_uses', 'usage_percentage', 'total_discount_amount', 
        'created_at', 'updated_at'
    ]
    filter_horizontal = ['applicable_plans']
    
    fieldsets = (
        ('기본 정보', {
            'fields': (
                'code', 'name', 'description'
            )
        }),
        ('할인 설정', {
            'fields': (
                'discount_type', 'value', 'max_discount_amount'
            )
        }),
        ('적용 조건', {
            'fields': (
                'applicable_plans', 'min_purchase_amount'
            )
        }),
        ('사용 제한', {
            'fields': (
                'max_uses', 'max_uses_per_user', 'current_uses'
            )
        }),
        ('유효 기간', {
            'fields': (
                'is_active', 'valid_from', 'valid_until'
            )
        }),
        ('통계', {
            'fields': (
                'usage_percentage', 'total_discount_amount'
            ),
            'classes': ['collapse']
        }),
        ('시스템 정보', {
            'fields': (
                'created_at', 'updated_at'
            ),
            'classes': ['collapse']
        }),
    )
    
    actions = ['activate_discounts', 'deactivate_discounts', 'extend_validity']
    
    def discount_type_display(self, obj):
        """Display discount type"""
        return obj.get_discount_type_display()
    discount_type_display.short_description = '할인 타입'
    discount_type_display.admin_order_field = 'discount_type'
    
    def value_display(self, obj):
        """Display discount value"""
        if obj.discount_type == 'percentage':
            return f"{obj.value}%"
        else:
            return f"{obj.value:,}원"
    value_display.short_description = '할인 값'
    value_display.admin_order_field = 'value'
    
    def usage_status(self, obj):
        """Display usage status"""
        if obj.max_uses:
            percentage = (obj.current_uses / obj.max_uses) * 100
            
            if percentage >= 100:
                color = 'red'
                status = '사용완료'
            elif percentage >= 80:
                color = 'orange'
                status = '거의완료'
            else:
                color = 'green'
                status = '사용가능'
            
            return format_html(
                '<span style="color: {};">{}/{} ({})</span>',
                color, obj.current_uses, obj.max_uses, status
            )
        else:
            return format_html(
                '<span style="color: green;">{} (무제한)</span>',
                obj.current_uses
            )
    usage_status.short_description = '사용 현황'
    
    def validity_period(self, obj):
        """Display validity period"""
        now = timezone.now()
        
        if now < obj.valid_from:
            return format_html(
                '<span style="color: blue;">시작 예정 ({})</span>',
                obj.valid_from.strftime('%Y-%m-%d')
            )
        elif now > obj.valid_until:
            return format_html(
                '<span style="color: red;">만료됨 ({})</span>',
                obj.valid_until.strftime('%Y-%m-%d')
            )
        else:
            days_left = (obj.valid_until - now).days
            
            if days_left <= 3:
                color = 'red'
            elif days_left <= 7:
                color = 'orange'
            else:
                color = 'green'
            
            return format_html(
                '<span style="color: {};">유효 ({}일 남음)</span>',
                color, days_left
            )
    validity_period.short_description = '유효 기간'
    
    def usage_percentage(self, obj):
        """Calculate usage percentage"""
        if not obj.max_uses:
            return 0
        return (obj.current_uses / obj.max_uses) * 100
    usage_percentage.short_description = '사용률 (%)'
    
    def total_discount_amount(self, obj):
        """Calculate total discount amount"""
        total = obj.usages.aggregate(
            total=models.Sum('amount_discounted')
        )['total'] or Decimal('0.00')
        
        return format_html('<strong>{:,}</strong>원', total)
    total_discount_amount.short_description = '총 할인 금액'
    
    def activate_discounts(self, request, queryset):
        """Activate discounts"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated}개의 할인이 활성화되었습니다.')
    activate_discounts.short_description = '선택된 할인 활성화'
    
    def deactivate_discounts(self, request, queryset):
        """Deactivate discounts"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated}개의 할인이 비활성화되었습니다.')
    deactivate_discounts.short_description = '선택된 할인 비활성화'


@admin.register(DiscountUsage)
class DiscountUsageAdmin(admin.ModelAdmin):
    """Discount Usage admin"""
    
    list_display = [
        'discount_code', 'user_email', 'amount_discounted_display',
        'payment_info', 'used_at'
    ]
    list_filter = [
        'discount__discount_type', 'used_at'
    ]
    search_fields = [
        'discount__code', 'user__email', 'payment__stripe_payment_intent_id'
    ]
    readonly_fields = ['used_at']
    ordering = ['-used_at']
    
    def discount_code(self, obj):
        """Display discount code"""
        return obj.discount.code
    discount_code.short_description = '할인 코드'
    discount_code.admin_order_field = 'discount__code'
    
    def user_email(self, obj):
        """Display user email"""
        return obj.user.email
    user_email.short_description = '사용자'
    user_email.admin_order_field = 'user__email'
    
    def amount_discounted_display(self, obj):
        """Display discounted amount"""
        return format_html('<strong>{:,}</strong>원', obj.amount_discounted)
    amount_discounted_display.short_description = '할인 금액'
    amount_discounted_display.admin_order_field = 'amount_discounted'
    
    def payment_info(self, obj):
        """Display payment information"""
        if obj.payment:
            return format_html(
                '<a href="{}">{} ({})</a>',
                reverse('admin:subscription_payment_change', args=[obj.payment.id]),
                f"{obj.payment.amount:,}원",
                obj.payment.get_status_display()
            )
        return '-'
    payment_info.short_description = '결제 정보'


# Admin site customization
admin.site.site_header = "StudyMate 구독 관리"
admin.site.site_title = "StudyMate Subscription Admin"
admin.site.index_title = "구독 관리 대시보드"
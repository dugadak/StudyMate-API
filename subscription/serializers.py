from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from typing import Dict, Any, Optional
import logging
import stripe

from .models import (
    SubscriptionPlan, UserSubscription, UsageCredit, 
    Payment, Discount, DiscountUsage
)

logger = logging.getLogger(__name__)
User = get_user_model()


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Enhanced Subscription Plan serializer"""
    
    discount_percentage = serializers.ReadOnlyField()
    is_recurring = serializers.ReadOnlyField()
    effective_price = serializers.SerializerMethodField()
    features_display = serializers.SerializerMethodField()
    limits_display = serializers.SerializerMethodField()
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'name', 'plan_type', 'price', 'original_price', 
            'discount_percentage', 'description', 'short_description',
            'billing_interval', 'duration_days', 'features', 'limits',
            'is_active', 'is_popular', 'is_promotional', 'trial_days',
            'is_recurring', 'effective_price', 'features_display', 
            'limits_display', 'order', 'created_at'
        ]
        read_only_fields = [
            'id', 'stripe_price_id', 'stripe_product_id', 'created_at', 'updated_at'
        ]
    
    def get_effective_price(self, obj) -> Decimal:
        """Get effective price (considering discounts)"""
        return obj.price
    
    def get_features_display(self, obj) -> Dict[str, Any]:
        """Get formatted features for display"""
        features = obj.features or {}
        display_features = {}
        
        feature_labels = {
            'unlimited_quiz': '무제한 퀴즈',
            'unlimited_summary': '무제한 요약',
            'ai_generation': 'AI 생성 기능',
            'export_data': '데이터 내보내기',
            'priority_support': '우선 지원',
            'advanced_analytics': '고급 분석',
            'custom_study_plans': '맞춤 학습 계획',
            'offline_access': '오프라인 접근',
        }
        
        for key, value in features.items():
            display_features[feature_labels.get(key, key)] = value
        
        return display_features
    
    def get_limits_display(self, obj) -> Dict[str, Any]:
        """Get formatted limits for display"""
        limits = obj.limits or {}
        display_limits = {}
        
        limit_labels = {
            'quiz': '퀴즈 횟수',
            'summary': '요약 횟수',
            'time_change': '시간 변경',
            'ai_generation': 'AI 생성',
            'export': '내보내기',
        }
        
        for key, value in limits.items():
            label = limit_labels.get(key, key)
            if value == -1:
                display_limits[label] = '무제한'
            else:
                display_limits[label] = f"{value}회"
        
        return display_limits
    
    def validate(self, attrs):
        """Enhanced validation"""
        # Validate billing interval and duration
        billing_interval = attrs.get('billing_interval')
        duration_days = attrs.get('duration_days')
        
        if billing_interval != 'one_time' and not duration_days:
            raise serializers.ValidationError(
                "반복 구독은 duration_days가 필요합니다."
            )
        
        # Validate price and original price
        price = attrs.get('price')
        original_price = attrs.get('original_price')
        
        if original_price and original_price <= price:
            raise serializers.ValidationError(
                "할인 후 가격이 원가보다 높을 수 없습니다."
            )
        
        return attrs


class SubscriptionPlanListSerializer(serializers.ModelSerializer):
    """Simplified serializer for plan listing"""
    
    discount_percentage = serializers.ReadOnlyField()
    is_recurring = serializers.ReadOnlyField()
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'name', 'plan_type', 'price', 'original_price',
            'discount_percentage', 'short_description', 'billing_interval',
            'is_popular', 'is_promotional', 'trial_days', 'is_recurring'
        ]


class UserSubscriptionSerializer(serializers.ModelSerializer):
    """Enhanced User Subscription serializer"""
    
    plan = SubscriptionPlanSerializer(read_only=True)
    plan_id = serializers.IntegerField(write_only=True)
    is_active = serializers.ReadOnlyField()
    is_trial = serializers.ReadOnlyField()
    days_remaining = serializers.ReadOnlyField()
    trial_days_remaining = serializers.ReadOnlyField()
    effective_price = serializers.ReadOnlyField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    cancellation_reason_display = serializers.CharField(
        source='get_cancellation_reason_display', 
        read_only=True
    )
    
    class Meta:
        model = UserSubscription
        fields = [
            'id', 'plan', 'plan_id', 'status', 'status_display',
            'started_at', 'expires_at', 'trial_ends_at', 'canceled_at',
            'cancellation_reason', 'cancellation_reason_display',
            'cancellation_note', 'is_recurring', 'auto_renew',
            'current_period_start', 'current_period_end', 'quantity',
            'discount_applied', 'is_active', 'is_trial', 
            'days_remaining', 'trial_days_remaining', 'effective_price',
            'metadata', 'created_at'
        ]
        read_only_fields = [
            'id', 'user', 'stripe_subscription_id', 'stripe_customer_id',
            'started_at', 'canceled_at', 'current_period_start',
            'current_period_end', 'billing_cycle_anchor', 'created_at', 'updated_at'
        ]
    
    def validate_plan_id(self, value):
        """Validate plan selection"""
        try:
            plan = SubscriptionPlan.objects.get(id=value, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("유효하지 않은 구독 플랜입니다.")
        
        return value
    
    def validate_quantity(self, value):
        """Validate quantity"""
        if value < 1:
            raise serializers.ValidationError("수량은 1 이상이어야 합니다.")
        
        return value
    
    def validate_discount_applied(self, value):
        """Validate discount percentage"""
        if value < 0 or value > 100:
            raise serializers.ValidationError("할인율은 0-100% 사이여야 합니다.")
        
        return value
    
    def create(self, validated_data):
        """Create subscription with plan"""
        plan_id = validated_data.pop('plan_id')
        plan = SubscriptionPlan.objects.get(id=plan_id)
        
        subscription = UserSubscription.objects.create(
            plan=plan,
            **validated_data
        )
        
        # Create usage credits based on plan limits
        for credit_type, amount in plan.limits.items():
            if amount > 0:
                UsageCredit.objects.create(
                    user=subscription.user,
                    credit_type=credit_type,
                    total_credits=amount,
                    source_subscription=subscription,
                    is_unlimited=amount == -1
                )
        
        logger.info(f"Created subscription for user {subscription.user.email}: {plan.name}")
        return subscription


class UserSubscriptionSummarySerializer(serializers.ModelSerializer):
    """Summary serializer for subscription overview"""
    
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_type = serializers.CharField(source='plan.plan_type', read_only=True)
    is_active = serializers.ReadOnlyField()
    days_remaining = serializers.ReadOnlyField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = UserSubscription
        fields = [
            'id', 'plan_name', 'plan_type', 'status', 'status_display',
            'is_active', 'days_remaining', 'started_at', 'expires_at'
        ]


class UsageCreditSerializer(serializers.ModelSerializer):
    """Enhanced Usage Credit serializer"""
    
    credit_type_display = serializers.CharField(source='get_credit_type_display', read_only=True)
    remaining_credits = serializers.ReadOnlyField()
    daily_remaining = serializers.ReadOnlyField()
    subscription_plan_name = serializers.CharField(
        source='source_subscription.plan.name', 
        read_only=True
    )
    usage_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = UsageCredit
        fields = [
            'id', 'credit_type', 'credit_type_display', 'total_credits',
            'used_credits', 'bonus_credits', 'remaining_credits',
            'is_unlimited', 'daily_limit', 'daily_used', 'daily_remaining',
            'expires_at', 'subscription_plan_name', 'usage_percentage',
            'reset_period', 'last_reset_at', 'created_at'
        ]
        read_only_fields = [
            'id', 'user', 'used_credits', 'daily_used', 'last_daily_reset',
            'last_reset_at', 'created_at', 'updated_at'
        ]
    
    def get_usage_percentage(self, obj) -> float:
        """Calculate usage percentage"""
        if obj.is_unlimited or obj.total_credits == 0:
            return 0.0
        
        total_available = obj.total_credits + obj.bonus_credits
        return (obj.used_credits / total_available) * 100 if total_available > 0 else 0.0
    
    def validate_total_credits(self, value):
        """Validate total credits"""
        if value < 0:
            raise serializers.ValidationError("총 크레딧은 0 이상이어야 합니다.")
        
        return value
    
    def validate_bonus_credits(self, value):
        """Validate bonus credits"""
        if value < 0:
            raise serializers.ValidationError("보너스 크레딧은 0 이상이어야 합니다.")
        
        return value


class PaymentSerializer(serializers.ModelSerializer):
    """Enhanced Payment serializer"""
    
    subscription_plan_name = serializers.CharField(
        source='subscription.plan.name', 
        read_only=True
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_display = serializers.CharField(
        source='get_payment_method_display', 
        read_only=True
    )
    is_successful = serializers.ReadOnlyField()
    is_refundable = serializers.ReadOnlyField()
    refundable_amount = serializers.ReadOnlyField()
    
    class Meta:
        model = Payment
        fields = [
            'id', 'subscription', 'subscription_plan_name', 'amount', 'currency',
            'payment_method', 'payment_method_display', 'status', 'status_display',
            'failure_reason', 'failure_code', 'refund_amount', 'refund_reason',
            'receipt_url', 'is_successful', 'is_refundable', 'refundable_amount',
            'created_at', 'completed_at', 'failed_at', 'refunded_at'
        ]
        read_only_fields = [
            'id', 'user', 'stripe_payment_intent_id', 'stripe_invoice_id',
            'failure_reason', 'failure_code', 'refund_amount', 'refund_reason',
            'receipt_url', 'completed_at', 'failed_at', 'refunded_at',
            'created_at', 'metadata'
        ]
    
    def validate_amount(self, value):
        """Validate payment amount"""
        if value <= 0:
            raise serializers.ValidationError("결제 금액은 0보다 커야 합니다.")
        
        return value


class PaymentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating payments"""
    
    plan_id = serializers.IntegerField(write_only=True)
    discount_code = serializers.CharField(write_only=True, required=False)
    payment_method_id = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = Payment
        fields = [
            'plan_id', 'discount_code', 'payment_method_id', 'payment_method',
            'quantity', 'metadata'
        ]
    
    def validate_plan_id(self, value):
        """Validate plan selection"""
        try:
            plan = SubscriptionPlan.objects.get(id=value, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("유효하지 않은 구독 플랜입니다.")
        
        return value
    
    def validate_discount_code(self, value):
        """Validate discount code"""
        if not value:
            return value
        
        try:
            discount = Discount.objects.get(code=value, is_active=True)
            now = timezone.now()
            
            if now < discount.valid_from or now > discount.valid_until:
                raise serializers.ValidationError("유효하지 않은 할인 코드입니다.")
            
        except Discount.DoesNotExist:
            raise serializers.ValidationError("존재하지 않는 할인 코드입니다.")
        
        return value
    
    def create(self, validated_data):
        """Create payment intent with Stripe integration"""
        user = self.context['request'].user
        plan_id = validated_data.pop('plan_id')
        discount_code = validated_data.pop('discount_code', None)
        payment_method_id = validated_data.pop('payment_method_id', None)
        
        plan = SubscriptionPlan.objects.get(id=plan_id)
        quantity = validated_data.get('quantity', 1)
        
        # Calculate amount
        base_amount = plan.price * quantity
        discount_amount = Decimal('0.00')
        
        # Apply discount if provided
        if discount_code:
            try:
                discount = Discount.objects.get(code=discount_code, is_active=True)
                is_valid, message = discount.is_valid(user=user, plan=plan, amount=base_amount)
                
                if is_valid:
                    discount_amount = discount.calculate_discount(base_amount)
                else:
                    raise serializers.ValidationError(f"할인 코드 오류: {message}")
                    
            except Discount.DoesNotExist:
                raise serializers.ValidationError("유효하지 않은 할인 코드입니다.")
        
        final_amount = base_amount - discount_amount
        
        # Create subscription first
        subscription = UserSubscription.objects.create(
            user=user,
            plan=plan,
            quantity=quantity
        )
        
        # Create payment record
        payment = Payment.objects.create(
            user=user,
            subscription=subscription,
            amount=final_amount,
            **validated_data
        )
        
        # Create Stripe payment intent if not recurring
        if not plan.is_recurring:
            try:
                intent = stripe.PaymentIntent.create(
                    amount=int(final_amount * 100),  # Convert to cents
                    currency='krw',
                    payment_method=payment_method_id,
                    confirmation_method='manual',
                    confirm=True,
                    metadata={
                        'user_id': user.id,
                        'subscription_id': subscription.id,
                        'plan_type': plan.plan_type
                    }
                )
                
                payment.stripe_payment_intent_id = intent.id
                payment.save()
                
                logger.info(f"Created Stripe payment intent for user {user.email}: {intent.id}")
                
            except stripe.error.StripeError as e:
                logger.error(f"Stripe payment intent creation failed: {str(e)}")
                payment.status = 'failed'
                payment.failure_reason = str(e)
                payment.save()
        
        return payment


class DiscountSerializer(serializers.ModelSerializer):
    """Enhanced Discount serializer"""
    
    discount_type_display = serializers.CharField(
        source='get_discount_type_display', 
        read_only=True
    )
    usage_count = serializers.SerializerMethodField()
    remaining_uses = serializers.SerializerMethodField()
    applicable_plan_names = serializers.SerializerMethodField()
    
    class Meta:
        model = Discount
        fields = [
            'id', 'code', 'name', 'description', 'discount_type',
            'discount_type_display', 'value', 'max_discount_amount',
            'min_purchase_amount', 'max_uses', 'max_uses_per_user',
            'current_uses', 'usage_count', 'remaining_uses',
            'applicable_plan_names', 'is_active', 'valid_from', 'valid_until',
            'created_at'
        ]
        read_only_fields = ['id', 'current_uses', 'created_at', 'updated_at']
    
    def get_usage_count(self, obj) -> int:
        """Get total usage count"""
        return obj.usages.count()
    
    def get_remaining_uses(self, obj) -> Optional[int]:
        """Get remaining uses"""
        if not obj.max_uses:
            return None
        return max(0, obj.max_uses - obj.current_uses)
    
    def get_applicable_plan_names(self, obj) -> list:
        """Get list of applicable plan names"""
        if not obj.applicable_plans.exists():
            return ["모든 플랜"]
        return list(obj.applicable_plans.values_list('name', flat=True))
    
    def validate_code(self, value):
        """Validate discount code uniqueness"""
        if self.instance:
            # Update case - exclude current instance
            if Discount.objects.exclude(id=self.instance.id).filter(code=value).exists():
                raise serializers.ValidationError("이미 존재하는 할인 코드입니다.")
        else:
            # Create case
            if Discount.objects.filter(code=value).exists():
                raise serializers.ValidationError("이미 존재하는 할인 코드입니다.")
        
        return value.upper()  # Convert to uppercase
    
    def validate(self, attrs):
        """Enhanced validation"""
        valid_from = attrs.get('valid_from')
        valid_until = attrs.get('valid_until')
        discount_type = attrs.get('discount_type')
        value = attrs.get('value')
        
        # Validate date range
        if valid_until and valid_from and valid_until <= valid_from:
            raise serializers.ValidationError("종료일이 시작일보다 늦어야 합니다.")
        
        # Validate percentage discount
        if discount_type == 'percentage' and value > 100:
            raise serializers.ValidationError("퍼센트 할인은 100%를 초과할 수 없습니다.")
        
        return attrs


class DiscountValidationSerializer(serializers.Serializer):
    """Serializer for discount code validation"""
    
    code = serializers.CharField(max_length=50)
    plan_id = serializers.IntegerField(required=False)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    
    def validate_code(self, value):
        """Validate discount code exists"""
        try:
            discount = Discount.objects.get(code=value.upper(), is_active=True)
        except Discount.DoesNotExist:
            raise serializers.ValidationError("유효하지 않은 할인 코드입니다.")
        
        return value.upper()
    
    def validate(self, attrs):
        """Validate discount applicability"""
        code = attrs.get('code')
        plan_id = attrs.get('plan_id')
        amount = attrs.get('amount')
        user = self.context['request'].user
        
        discount = Discount.objects.get(code=code, is_active=True)
        plan = None
        
        if plan_id:
            try:
                plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
            except SubscriptionPlan.DoesNotExist:
                raise serializers.ValidationError("유효하지 않은 구독 플랜입니다.")
        
        # Validate discount
        is_valid, message = discount.is_valid(user=user, plan=plan, amount=amount)
        
        if not is_valid:
            raise serializers.ValidationError(message)
        
        attrs['discount'] = discount
        attrs['plan'] = plan
        return attrs


class DiscountUsageSerializer(serializers.ModelSerializer):
    """Discount Usage serializer"""
    
    discount_code = serializers.CharField(source='discount.code', read_only=True)
    discount_name = serializers.CharField(source='discount.name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = DiscountUsage
        fields = [
            'id', 'discount_code', 'discount_name', 'user_email',
            'amount_discounted', 'used_at'
        ]
        read_only_fields = ['id', 'used_at']


class SubscriptionAnalyticsSerializer(serializers.Serializer):
    """Serializer for subscription analytics"""
    
    total_subscriptions = serializers.IntegerField()
    active_subscriptions = serializers.IntegerField()
    trial_subscriptions = serializers.IntegerField()
    canceled_subscriptions = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    monthly_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    average_subscription_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    churn_rate = serializers.FloatField()
    popular_plans = serializers.ListField()
    revenue_by_plan = serializers.DictField()
    subscription_growth = serializers.ListField()


class SubscriptionCreateSerializer(serializers.Serializer):
    """Serializer for creating subscription with Stripe"""
    
    plan_id = serializers.IntegerField()
    payment_method_id = serializers.CharField()
    discount_code = serializers.CharField(required=False, allow_blank=True)
    quantity = serializers.IntegerField(default=1, min_value=1)
    
    def validate_plan_id(self, value):
        """Validate plan selection"""
        try:
            plan = SubscriptionPlan.objects.get(id=value, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("유효하지 않은 구독 플랜입니다.")
        
        return value
    
    def validate_discount_code(self, value):
        """Validate discount code if provided"""
        if not value:
            return value
        
        try:
            discount = Discount.objects.get(code=value.upper(), is_active=True)
            now = timezone.now()
            
            if now < discount.valid_from or now > discount.valid_until:
                raise serializers.ValidationError("유효하지 않은 할인 코드입니다.")
            
        except Discount.DoesNotExist:
            raise serializers.ValidationError("존재하지 않는 할인 코드입니다.")
        
        return value.upper()
    
    def create(self, validated_data):
        """Create subscription with Stripe integration"""
        user = self.context['request'].user
        plan_id = validated_data['plan_id']
        payment_method_id = validated_data['payment_method_id']
        discount_code = validated_data.get('discount_code')
        quantity = validated_data['quantity']
        
        plan = SubscriptionPlan.objects.get(id=plan_id)
        
        try:
            # Create or get Stripe customer
            if not hasattr(user, 'stripe_customer_id') or not user.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=user.email,
                    name=f"{user.first_name} {user.last_name}".strip(),
                    metadata={'user_id': user.id}
                )
                user.stripe_customer_id = customer.id
                user.save()
            else:
                customer = stripe.Customer.retrieve(user.stripe_customer_id)
            
            # Attach payment method to customer
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer.id
            )
            
            # Set as default payment method
            stripe.Customer.modify(
                customer.id,
                invoice_settings={'default_payment_method': payment_method_id}
            )
            
            # Create subscription data
            subscription_data = {
                'customer': customer.id,
                'items': [{
                    'price': plan.stripe_price_id or plan.create_stripe_price(),
                    'quantity': quantity
                }],
                'payment_behavior': 'default_incomplete',
                'expand': ['latest_invoice.payment_intent'],
                'metadata': {
                    'user_id': user.id,
                    'plan_type': plan.plan_type
                }
            }
            
            # Add trial period if applicable
            if plan.trial_days > 0:
                subscription_data['trial_period_days'] = plan.trial_days
            
            # Apply discount if provided
            if discount_code:
                discount = Discount.objects.get(code=discount_code, is_active=True)
                is_valid, message = discount.is_valid(user=user, plan=plan)
                
                if is_valid:
                    # Create Stripe coupon for discount
                    if discount.discount_type == 'percentage':
                        coupon = stripe.Coupon.create(
                            percent_off=float(discount.value),
                            duration='once',
                            name=discount.name
                        )
                    else:
                        coupon = stripe.Coupon.create(
                            amount_off=int(discount.value * 100),
                            currency='krw',
                            duration='once',
                            name=discount.name
                        )
                    
                    subscription_data['coupon'] = coupon.id
                else:
                    raise serializers.ValidationError(f"할인 코드 오류: {message}")
            
            # Create Stripe subscription
            stripe_subscription = stripe.Subscription.create(**subscription_data)
            
            # Create local subscription record
            subscription = UserSubscription.objects.create(
                user=user,
                plan=plan,
                stripe_subscription_id=stripe_subscription.id,
                stripe_customer_id=customer.id,
                quantity=quantity,
                is_recurring=plan.is_recurring
            )
            
            # Create usage credits based on plan
            for credit_type, amount in plan.limits.items():
                if amount > 0:
                    UsageCredit.objects.create(
                        user=user,
                        credit_type=credit_type,
                        total_credits=amount,
                        source_subscription=subscription,
                        is_unlimited=amount == -1
                    )
            
            # Record discount usage
            if discount_code:
                discount.use_discount(user, plan.price * quantity)
            
            logger.info(f"Created subscription for user {user.email}: {plan.name}")
            
            return {
                'subscription': subscription,
                'stripe_subscription': stripe_subscription,
                'client_secret': stripe_subscription.latest_invoice.payment_intent.client_secret
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe subscription creation failed: {str(e)}")
            raise serializers.ValidationError(f"결제 처리 중 오류가 발생했습니다: {str(e)}")
        except Exception as e:
            logger.error(f"Subscription creation failed: {str(e)}")
            raise serializers.ValidationError(f"구독 생성 중 오류가 발생했습니다: {str(e)}")
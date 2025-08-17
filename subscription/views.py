from rest_framework import viewsets, generics, status, permissions, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.utils import timezone
from django.db import models, transaction
from django.db.models import Q, Count, Sum, Avg, F
from django_filters.rest_framework import DjangoFilterBackend
from decimal import Decimal
from datetime import timedelta, date
from typing import Dict, Any, Optional, List
import logging
import stripe
from django.conf import settings

from .models import (
    SubscriptionPlan, UserSubscription, UsageCredit, 
    Payment, Discount, DiscountUsage
)
from .serializers import (
    SubscriptionPlanSerializer, SubscriptionPlanListSerializer,
    UserSubscriptionSerializer, UserSubscriptionSummarySerializer,
    UsageCreditSerializer, PaymentSerializer, PaymentCreateSerializer,
    DiscountSerializer, DiscountValidationSerializer, DiscountUsageSerializer,
    SubscriptionAnalyticsSerializer, SubscriptionCreateSerializer
)

logger = logging.getLogger(__name__)


class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """Enhanced Subscription Plan ViewSet"""
    
    queryset = SubscriptionPlan.objects.filter(is_active=True)
    permission_classes = [permissions.AllowAny]  # Plans are public
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['plan_type', 'billing_interval', 'is_popular', 'is_promotional']
    ordering_fields = ['price', 'order', 'created_at']
    ordering = ['order', 'price']
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action"""
        if self.action == 'list':
            return SubscriptionPlanListSerializer
        return SubscriptionPlanSerializer
    
    def get_queryset(self):
        """Get filtered queryset with caching"""
        cache_key = f"subscription_plans_{self.request.query_params.urlencode()}"
        plans = cache.get(cache_key)
        
        if plans is None:
            plans = super().get_queryset()
            
            # Filter by billing interval
            billing_interval = self.request.query_params.get('billing_interval')
            if billing_interval:
                plans = plans.filter(billing_interval=billing_interval)
            
            # Filter by features
            features = self.request.query_params.get('features')
            if features:
                feature_list = features.split(',')
                for feature in feature_list:
                    plans = plans.filter(features__has_key=feature.strip())
            
            # Cache for 15 minutes
            cache.set(cache_key, plans, 900)
        
        return plans
    
    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get popular plans"""
        popular_plans = self.get_queryset().filter(is_popular=True)
        serializer = self.get_serializer(popular_plans, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def promotional(self, request):
        """Get promotional plans"""
        promo_plans = self.get_queryset().filter(is_promotional=True)
        serializer = self.get_serializer(promo_plans, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def features(self, request, pk=None):
        """Get detailed plan features"""
        plan = self.get_object()
        
        features = {
            'included_features': plan.features,
            'usage_limits': plan.limits,
            'billing_details': {
                'price': plan.price,
                'billing_interval': plan.get_billing_interval_display(),
                'trial_days': plan.trial_days,
                'is_recurring': plan.is_recurring
            },
            'restrictions': {
                'max_users': plan.max_users,
                'duration_days': plan.duration_days
            }
        }
        
        return Response(features)


class UserSubscriptionViewSet(viewsets.ModelViewSet):
    """Enhanced User Subscription ViewSet"""
    
    serializer_class = UserSubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'plan__plan_type', 'is_recurring']
    ordering_fields = ['created_at', 'expires_at', 'started_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get user's subscriptions"""
        return UserSubscription.objects.filter(
            user=self.request.user
        ).select_related('plan').prefetch_related('credits', 'payments')
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['create']:
            return [permissions.IsAuthenticated()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated()]  # Users can manage their own subscriptions
        return [permissions.IsAuthenticated()]
    
    def perform_create(self, serializer):
        """Create subscription for authenticated user"""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get user's active subscriptions"""
        active_subs = self.get_queryset().filter(
            status__in=['active', 'trialing']
        )
        
        serializer = UserSubscriptionSummarySerializer(active_subs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get user's current/primary subscription"""
        current_sub = self.get_queryset().filter(
            status__in=['active', 'trialing']
        ).order_by('-created_at').first()
        
        if not current_sub:
            return Response(
                {'message': '활성 구독이 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(current_sub)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel subscription"""
        subscription = self.get_object()
        
        if subscription.status in ['canceled', 'expired']:
            return Response(
                {'error': '이미 취소되거나 만료된 구독입니다.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', 'user_request')
        note = request.data.get('note', '')
        
        if subscription.cancel(reason=reason, note=note):
            return Response({
                'message': '구독이 성공적으로 취소되었습니다.',
                'canceled_at': subscription.canceled_at,
                'status': subscription.status
            })
        else:
            return Response(
                {'error': '구독 취소 중 오류가 발생했습니다.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause subscription"""
        subscription = self.get_object()
        
        if subscription.pause():
            return Response({
                'message': '구독이 일시정지되었습니다.',
                'status': subscription.status
            })
        else:
            return Response(
                {'error': '구독 일시정지 중 오류가 발생했습니다.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """Resume paused subscription"""
        subscription = self.get_object()
        
        if subscription.resume():
            return Response({
                'message': '구독이 재개되었습니다.',
                'status': subscription.status
            })
        else:
            return Response(
                {'error': '구독 재개 중 오류가 발생했습니다.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def sync_stripe(self, request, pk=None):
        """Sync subscription with Stripe"""
        subscription = self.get_object()
        
        if subscription.sync_with_stripe():
            serializer = self.get_serializer(subscription)
            return Response({
                'message': 'Stripe와 동기화되었습니다.',
                'subscription': serializer.data
            })
        else:
            return Response(
                {'error': 'Stripe 동기화 중 오류가 발생했습니다.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def usage_summary(self, request):
        """Get user's usage summary across all subscriptions"""
        user = request.user
        credits = UsageCredit.objects.filter(user=user)
        
        summary = {}
        for credit in credits:
            credit_type = credit.get_credit_type_display()
            summary[credit_type] = {
                'total': credit.total_credits + credit.bonus_credits,
                'used': credit.used_credits,
                'remaining': credit.remaining_credits,
                'is_unlimited': credit.is_unlimited,
                'daily_limit': credit.daily_limit,
                'daily_used': credit.daily_used,
                'expires_at': credit.expires_at
            }
        
        return Response(summary)


class UsageCreditViewSet(viewsets.ReadOnlyModelViewSet):
    """Usage Credit ViewSet for tracking user credits"""
    
    serializer_class = UsageCreditSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['credit_type', 'is_unlimited', 'source_subscription']
    ordering_fields = ['created_at', 'expires_at', 'remaining_credits']
    ordering = ['credit_type', '-created_at']
    
    def get_queryset(self):
        """Get user's usage credits"""
        return UsageCredit.objects.filter(
            user=self.request.user
        ).select_related('source_subscription__plan')
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get credits summary by type"""
        credits = self.get_queryset()
        
        summary = {}
        for credit in credits:
            credit_type = credit.credit_type
            if credit_type not in summary:
                summary[credit_type] = {
                    'type_display': credit.get_credit_type_display(),
                    'total_credits': 0,
                    'total_used': 0,
                    'total_remaining': 0,
                    'is_unlimited': False,
                    'sources': []
                }
            
            summary[credit_type]['total_credits'] += credit.total_credits + credit.bonus_credits
            summary[credit_type]['total_used'] += credit.used_credits
            summary[credit_type]['total_remaining'] += credit.remaining_credits
            
            if credit.is_unlimited:
                summary[credit_type]['is_unlimited'] = True
            
            summary[credit_type]['sources'].append({
                'subscription_plan': credit.source_subscription.plan.name if credit.source_subscription else 'Direct',
                'credits': credit.total_credits,
                'bonus': credit.bonus_credits,
                'expires_at': credit.expires_at
            })
        
        return Response(summary)
    
    @action(detail=False, methods=['post'])
    def use_credit(self, request):
        """Use credits for specific type"""
        credit_type = request.data.get('credit_type')
        amount = int(request.data.get('amount', 1))
        
        if not credit_type:
            return Response(
                {'error': '크레딧 타입을 지정해주세요.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get user's credit for this type
        try:
            credit = UsageCredit.get_user_credits(request.user, credit_type)
        except UsageCredit.DoesNotExist:
            return Response(
                {'error': '해당 타입의 크레딧이 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if credit.use_credit(amount):
            return Response({
                'message': f'{amount}개의 {credit.get_credit_type_display()} 크레딧을 사용했습니다.',
                'remaining_credits': credit.remaining_credits
            })
        else:
            return Response(
                {'error': '크레딧이 부족하거나 사용할 수 없습니다.'},
                status=status.HTTP_400_BAD_REQUEST
            )


class PaymentViewSet(viewsets.ModelViewSet):
    """Enhanced Payment ViewSet"""
    
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'payment_method', 'subscription__plan__plan_type']
    ordering_fields = ['created_at', 'amount', 'completed_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get user's payments"""
        return Payment.objects.filter(
            user=self.request.user
        ).select_related('subscription__plan')
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action"""
        if self.action == 'create':
            return PaymentCreateSerializer
        return PaymentSerializer
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]  # Only admins can modify payments
        return [permissions.IsAuthenticated()]
    
    def perform_create(self, serializer):
        """Create payment for authenticated user"""
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def refund(self, request, pk=None):
        """Request refund for payment"""
        payment = self.get_object()
        amount = request.data.get('amount')
        reason = request.data.get('reason', '')
        
        if not amount:
            # Full refund
            amount = payment.refundable_amount
        else:
            amount = Decimal(str(amount))
        
        if payment.process_refund(amount, reason):
            return Response({
                'message': f'{amount}원이 환불 처리되었습니다.',
                'refund_amount': payment.refund_amount,
                'status': payment.status
            })
        else:
            return Response(
                {'error': '환불 처리 중 오류가 발생했습니다.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def sync_stripe(self, request, pk=None):
        """Sync payment with Stripe"""
        payment = self.get_object()
        
        if payment.sync_with_stripe():
            serializer = self.get_serializer(payment)
            return Response({
                'message': 'Stripe와 동기화되었습니다.',
                'payment': serializer.data
            })
        else:
            return Response(
                {'error': 'Stripe 동기화 중 오류가 발생했습니다.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get user's payment statistics"""
        payments = self.get_queryset()
        
        stats = {
            'total_payments': payments.count(),
            'successful_payments': payments.filter(status='succeeded').count(),
            'total_amount': payments.filter(status='succeeded').aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00'),
            'total_refunded': payments.aggregate(
                total=Sum('refund_amount')
            )['total'] or Decimal('0.00'),
            'recent_payments': PaymentSerializer(
                payments[:5], many=True
            ).data
        }
        
        return Response(stats)


class DiscountViewSet(viewsets.ModelViewSet):
    """Enhanced Discount ViewSet"""
    
    serializer_class = DiscountSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'name', 'description']
    filterset_fields = ['discount_type', 'is_active']
    ordering_fields = ['created_at', 'valid_from', 'valid_until']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get discounts based on user permissions"""
        if self.request.user.is_staff:
            return Discount.objects.all()
        else:
            # Regular users can only see active discounts
            return Discount.objects.filter(
                is_active=True,
                valid_from__lte=timezone.now(),
                valid_until__gte=timezone.now()
            )
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        elif self.action in ['validate_discount']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]
    
    @action(detail=False, methods=['post'])
    def validate_discount(self, request):
        """Validate discount code"""
        serializer = DiscountValidationSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        discount = serializer.validated_data['discount']
        plan = serializer.validated_data.get('plan')
        amount = serializer.validated_data.get('amount')
        
        # Calculate discount amount
        discount_amount = Decimal('0.00')
        if amount:
            discount_amount = discount.calculate_discount(amount)
        
        return Response({
            'valid': True,
            'message': '유효한 할인 코드입니다.',
            'discount': {
                'code': discount.code,
                'name': discount.name,
                'type': discount.get_discount_type_display(),
                'value': discount.value,
                'discount_amount': discount_amount,
                'max_discount_amount': discount.max_discount_amount
            }
        })
    
    @action(detail=True, methods=['get'])
    def usage_stats(self, request, pk=None):
        """Get discount usage statistics"""
        discount = self.get_object()
        
        if not request.user.is_staff:
            return Response(
                {'error': '권한이 없습니다.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        usages = DiscountUsage.objects.filter(discount=discount)
        
        stats = {
            'total_uses': usages.count(),
            'remaining_uses': discount.max_uses - discount.current_uses if discount.max_uses else None,
            'total_discount_amount': usages.aggregate(
                total=Sum('amount_discounted')
            )['total'] or Decimal('0.00'),
            'usage_by_date': list(
                usages.extra(
                    select={'date': 'DATE(used_at)'}
                ).values('date').annotate(
                    count=Count('id'),
                    total_discount=Sum('amount_discounted')
                ).order_by('date')
            ),
            'recent_usages': DiscountUsageSerializer(
                usages[:10], many=True
            ).data
        }
        
        return Response(stats)


class SubscriptionAnalyticsView(generics.GenericAPIView):
    """Subscription Analytics and Statistics View"""
    
    permission_classes = [permissions.IsAdminUser]
    serializer_class = SubscriptionAnalyticsSerializer
    
    def get(self, request):
        """Get comprehensive subscription analytics"""
        days = int(request.query_params.get('days', 30))
        since_date = timezone.now() - timedelta(days=days)
        
        # Basic subscription statistics
        total_subscriptions = UserSubscription.objects.count()
        active_subscriptions = UserSubscription.objects.filter(
            status__in=['active', 'trialing']
        ).count()
        trial_subscriptions = UserSubscription.objects.filter(
            status='trialing'
        ).count()
        canceled_subscriptions = UserSubscription.objects.filter(
            status='canceled'
        ).count()
        
        # Revenue statistics
        successful_payments = Payment.objects.filter(
            status='succeeded',
            created_at__gte=since_date
        )
        
        total_revenue = successful_payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        monthly_revenue = successful_payments.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        ).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        avg_subscription_value = successful_payments.aggregate(
            avg=Avg('amount')
        )['avg'] or Decimal('0.00')
        
        # Churn rate calculation
        total_active_start = UserSubscription.objects.filter(
            created_at__lt=since_date,
            status='active'
        ).count()
        
        churn_rate = 0.0
        if total_active_start > 0:
            churned = UserSubscription.objects.filter(
                canceled_at__gte=since_date,
                status='canceled'
            ).count()
            churn_rate = (churned / total_active_start) * 100
        
        # Popular plans
        popular_plans = list(
            UserSubscription.objects.values(
                'plan__name', 'plan__plan_type'
            ).annotate(
                count=Count('id')
            ).order_by('-count')[:5]
        )
        
        # Revenue by plan
        revenue_by_plan = {}
        plan_revenues = successful_payments.values(
            'subscription__plan__name'
        ).annotate(
            revenue=Sum('amount')
        )
        
        for item in plan_revenues:
            plan_name = item['subscription__plan__name']
            if plan_name:
                revenue_by_plan[plan_name] = float(item['revenue'])
        
        # Subscription growth over time
        subscription_growth = []
        for i in range(days, 0, -1):
            date_point = timezone.now() - timedelta(days=i)
            daily_subs = UserSubscription.objects.filter(
                created_at__date=date_point.date()
            ).count()
            
            subscription_growth.append({
                'date': date_point.date().isoformat(),
                'subscriptions': daily_subs
            })
        
        analytics_data = {
            'total_subscriptions': total_subscriptions,
            'active_subscriptions': active_subscriptions,
            'trial_subscriptions': trial_subscriptions,
            'canceled_subscriptions': canceled_subscriptions,
            'total_revenue': total_revenue,
            'monthly_revenue': monthly_revenue,
            'average_subscription_value': avg_subscription_value,
            'churn_rate': churn_rate,
            'popular_plans': popular_plans,
            'revenue_by_plan': revenue_by_plan,
            'subscription_growth': subscription_growth
        }
        
        serializer = self.serializer_class(analytics_data)
        return Response(serializer.data)


class SubscriptionCreateView(generics.CreateAPIView):
    """Create subscription with Stripe integration"""
    
    serializer_class = SubscriptionCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        """Create subscription with comprehensive error handling"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                result = serializer.save()
                
                return Response({
                    'message': '구독이 성공적으로 생성되었습니다.',
                    'subscription_id': result['subscription'].id,
                    'client_secret': result['client_secret'],
                    'requires_action': result['stripe_subscription'].status == 'incomplete'
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"Subscription creation failed for user {request.user.email}: {str(e)}")
            return Response(
                {'error': '구독 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class WebhookView(generics.GenericAPIView):
    """Stripe webhook handler"""
    
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        """Handle Stripe webhooks"""
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        endpoint_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except ValueError:
            logger.error("Invalid payload in Stripe webhook")
            return Response({'error': 'Invalid payload'}, status=400)
        except stripe.error.SignatureVerificationError:
            logger.error("Invalid signature in Stripe webhook")
            return Response({'error': 'Invalid signature'}, status=400)
        
        # Handle the event
        event_type = event['type']
        event_data = event['data']['object']
        
        try:
            if event_type == 'invoice.payment_succeeded':
                self._handle_payment_succeeded(event_data)
            elif event_type == 'invoice.payment_failed':
                self._handle_payment_failed(event_data)
            elif event_type == 'customer.subscription.updated':
                self._handle_subscription_updated(event_data)
            elif event_type == 'customer.subscription.deleted':
                self._handle_subscription_deleted(event_data)
            elif event_type == 'payment_intent.succeeded':
                self._handle_payment_intent_succeeded(event_data)
            else:
                logger.info(f"Unhandled Stripe webhook event: {event_type}")
            
            return Response({'status': 'success'})
            
        except Exception as e:
            logger.error(f"Error processing Stripe webhook {event_type}: {str(e)}")
            return Response({'error': 'Webhook processing failed'}, status=500)
    
    def _handle_payment_succeeded(self, invoice_data):
        """Handle successful payment"""
        subscription_id = invoice_data.get('subscription')
        if subscription_id:
            try:
                subscription = UserSubscription.objects.get(
                    stripe_subscription_id=subscription_id
                )
                subscription.sync_with_stripe()
                logger.info(f"Payment succeeded for subscription {subscription.id}")
            except UserSubscription.DoesNotExist:
                logger.warning(f"Subscription not found for Stripe ID: {subscription_id}")
    
    def _handle_payment_failed(self, invoice_data):
        """Handle failed payment"""
        subscription_id = invoice_data.get('subscription')
        if subscription_id:
            try:
                subscription = UserSubscription.objects.get(
                    stripe_subscription_id=subscription_id
                )
                subscription.status = 'past_due'
                subscription.save()
                logger.info(f"Payment failed for subscription {subscription.id}")
            except UserSubscription.DoesNotExist:
                logger.warning(f"Subscription not found for Stripe ID: {subscription_id}")
    
    def _handle_subscription_updated(self, subscription_data):
        """Handle subscription update"""
        subscription_id = subscription_data.get('id')
        try:
            subscription = UserSubscription.objects.get(
                stripe_subscription_id=subscription_id
            )
            subscription.sync_with_stripe()
            logger.info(f"Subscription updated: {subscription.id}")
        except UserSubscription.DoesNotExist:
            logger.warning(f"Subscription not found for Stripe ID: {subscription_id}")
    
    def _handle_subscription_deleted(self, subscription_data):
        """Handle subscription deletion"""
        subscription_id = subscription_data.get('id')
        try:
            subscription = UserSubscription.objects.get(
                stripe_subscription_id=subscription_id
            )
            subscription.status = 'canceled'
            subscription.canceled_at = timezone.now()
            subscription.save()
            logger.info(f"Subscription canceled: {subscription.id}")
        except UserSubscription.DoesNotExist:
            logger.warning(f"Subscription not found for Stripe ID: {subscription_id}")
    
    def _handle_payment_intent_succeeded(self, payment_intent_data):
        """Handle successful payment intent"""
        payment_intent_id = payment_intent_data.get('id')
        try:
            payment = Payment.objects.get(
                stripe_payment_intent_id=payment_intent_id
            )
            payment.sync_with_stripe()
            logger.info(f"Payment intent succeeded: {payment.id}")
        except Payment.DoesNotExist:
            logger.warning(f"Payment not found for Stripe ID: {payment_intent_id}")


class SubscriptionDashboardView(generics.GenericAPIView):
    """User subscription dashboard"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get user's subscription dashboard data"""
        user = request.user
        
        # Current subscription
        current_subscription = UserSubscription.objects.filter(
            user=user,
            status__in=['active', 'trialing']
        ).select_related('plan').first()
        
        # Usage credits summary
        credits = UsageCredit.objects.filter(user=user)
        credits_summary = {}
        
        for credit in credits:
            credit_type = credit.credit_type
            credits_summary[credit_type] = {
                'type_display': credit.get_credit_type_display(),
                'remaining': credit.remaining_credits,
                'total': credit.total_credits + credit.bonus_credits,
                'is_unlimited': credit.is_unlimited,
                'daily_limit': credit.daily_limit,
                'daily_used': credit.daily_used,
                'expires_at': credit.expires_at
            }
        
        # Recent payments
        recent_payments = Payment.objects.filter(
            user=user
        ).order_by('-created_at')[:5]
        
        # Subscription history
        subscription_history = UserSubscription.objects.filter(
            user=user
        ).order_by('-created_at')[:10]
        
        dashboard_data = {
            'current_subscription': UserSubscriptionSerializer(
                current_subscription
            ).data if current_subscription else None,
            'credits_summary': credits_summary,
            'recent_payments': PaymentSerializer(
                recent_payments, many=True
            ).data,
            'subscription_history': UserSubscriptionSummarySerializer(
                subscription_history, many=True
            ).data,
            'quick_stats': {
                'total_subscriptions': UserSubscription.objects.filter(user=user).count(),
                'total_payments': Payment.objects.filter(user=user, status='succeeded').count(),
                'total_spent': Payment.objects.filter(
                    user=user, status='succeeded'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            }
        }
        
        return Response(dashboard_data)
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router and register viewsets
router = DefaultRouter()
router.register(r'plans', views.SubscriptionPlanViewSet, basename='subscriptionplan')
router.register(r'subscriptions', views.UserSubscriptionViewSet, basename='usersubscription')
router.register(r'credits', views.UsageCreditViewSet, basename='usagecredit')
router.register(r'payments', views.PaymentViewSet, basename='payment')
router.register(r'discounts', views.DiscountViewSet, basename='discount')

# URL patterns
urlpatterns = [
    # Router URLs
    path('', include(router.urls)),
    
    # Plan endpoints
    path('plans/popular/', 
         views.SubscriptionPlanViewSet.as_view({'get': 'popular'}), 
         name='plans-popular'),
    path('plans/promotional/', 
         views.SubscriptionPlanViewSet.as_view({'get': 'promotional'}), 
         name='plans-promotional'),
    path('plans/<int:pk>/features/', 
         views.SubscriptionPlanViewSet.as_view({'get': 'features'}), 
         name='plans-features'),
    
    # Subscription endpoints
    path('subscriptions/active/', 
         views.UserSubscriptionViewSet.as_view({'get': 'active'}), 
         name='subscriptions-active'),
    path('subscriptions/current/', 
         views.UserSubscriptionViewSet.as_view({'get': 'current'}), 
         name='subscriptions-current'),
    path('subscriptions/<int:pk>/cancel/', 
         views.UserSubscriptionViewSet.as_view({'post': 'cancel'}), 
         name='subscriptions-cancel'),
    path('subscriptions/<int:pk>/pause/', 
         views.UserSubscriptionViewSet.as_view({'post': 'pause'}), 
         name='subscriptions-pause'),
    path('subscriptions/<int:pk>/resume/', 
         views.UserSubscriptionViewSet.as_view({'post': 'resume'}), 
         name='subscriptions-resume'),
    path('subscriptions/<int:pk>/sync-stripe/', 
         views.UserSubscriptionViewSet.as_view({'post': 'sync_stripe'}), 
         name='subscriptions-sync-stripe'),
    path('subscriptions/usage-summary/', 
         views.UserSubscriptionViewSet.as_view({'get': 'usage_summary'}), 
         name='subscriptions-usage-summary'),
    
    # Credit endpoints
    path('credits/summary/', 
         views.UsageCreditViewSet.as_view({'get': 'summary'}), 
         name='credits-summary'),
    path('credits/use/', 
         views.UsageCreditViewSet.as_view({'post': 'use_credit'}), 
         name='credits-use'),
    
    # Payment endpoints
    path('payments/<int:pk>/refund/', 
         views.PaymentViewSet.as_view({'post': 'refund'}), 
         name='payments-refund'),
    path('payments/<int:pk>/sync-stripe/', 
         views.PaymentViewSet.as_view({'post': 'sync_stripe'}), 
         name='payments-sync-stripe'),
    path('payments/statistics/', 
         views.PaymentViewSet.as_view({'get': 'statistics'}), 
         name='payments-statistics'),
    
    # Discount endpoints
    path('discounts/validate/', 
         views.DiscountViewSet.as_view({'post': 'validate_discount'}), 
         name='discounts-validate'),
    path('discounts/<int:pk>/usage-stats/', 
         views.DiscountViewSet.as_view({'get': 'usage_stats'}), 
         name='discounts-usage-stats'),
    
    # Analytics and reporting
    path('analytics/', 
         views.SubscriptionAnalyticsView.as_view(), 
         name='subscription-analytics'),
    
    # Subscription creation with Stripe
    path('create-subscription/', 
         views.SubscriptionCreateView.as_view(), 
         name='create-subscription'),
    
    # User dashboard
    path('dashboard/', 
         views.SubscriptionDashboardView.as_view(), 
         name='subscription-dashboard'),
    
    # Stripe webhook
    path('webhook/', 
         views.WebhookView.as_view(), 
         name='stripe-webhook'),
]
from django.urls import path
from .views import (
    StatsOverviewView, StatsPeriodView,
    StatsStrengthsView, StatsPeerComparisonView
)

urlpatterns = [
    path('overview/', StatsOverviewView.as_view(), name='stats-overview'),
    path('period/', StatsPeriodView.as_view(), name='stats-period'),
    path('strengths/', StatsStrengthsView.as_view(), name='stats-strengths'),
    path('peer-comparison/', StatsPeerComparisonView.as_view(), name='stats-peer-comparison'),
]
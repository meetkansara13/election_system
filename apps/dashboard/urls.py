from django.urls import path
from .views import (
    index, SeatsChartView, VoteShareTrendView,
    TurnoutMapView, PredictionConfidenceView, LiveStatsView, CandidateListView, GeoServerMapView
)

urlpatterns = [
    path('', index, name='dashboard'),
    path('api/seats/', SeatsChartView.as_view()),
    path('api/trend/', VoteShareTrendView.as_view()),
    path('api/turnout/', TurnoutMapView.as_view()),
    path('api/confidence/', PredictionConfidenceView.as_view()),
    path('api/stats/', LiveStatsView.as_view()),
    path('api/candidates/', CandidateListView.as_view()),
    path('api/map-layer/', GeoServerMapView.as_view()),
]

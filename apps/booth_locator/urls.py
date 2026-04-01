from django.urls import path
from .views import NearestBoothView, BoothMapView, BoothListView, BoothDetailView

urlpatterns = [
    path('nearest/', NearestBoothView.as_view()),
    path('map/', BoothMapView.as_view()),
    path('list/', BoothListView.as_view()),
    path('<str:booth_id>/', BoothDetailView.as_view()),
]

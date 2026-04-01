from django.urls import path
from .views import TrainModelView, PredictView, BulkPredictView

urlpatterns = [
    path('', PredictView.as_view()),
    path('train/', TrainModelView.as_view()),
    path('bulk/', BulkPredictView.as_view()),
]

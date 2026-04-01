from rest_framework import serializers
from .models import ElectionHistory, PredictionResult


class ElectionHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ElectionHistory
        fields = '__all__'


class PredictionResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = PredictionResult
        fields = '__all__'

from rest_framework import serializers
from .models import PollingBooth, Constituency


class PollingBoothSerializer(serializers.ModelSerializer):
    class Meta:
        model = PollingBooth
        fields = '__all__'


class ConstituencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Constituency
        fields = '__all__'

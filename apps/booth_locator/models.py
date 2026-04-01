from django.db import models


class PollingBooth(models.Model):
    booth_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    address = models.TextField()
    constituency = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    state = models.CharField(max_length=100, default='Gujarat')
    latitude = models.FloatField()
    longitude = models.FloatField()
    total_voters = models.IntegerField(default=0)
    is_accessible = models.BooleanField(default=True)
    has_cctv = models.BooleanField(default=False)

    class Meta:
        ordering = ['constituency', 'booth_id']

    def __str__(self):
        return f"{self.booth_id} - {self.name}"


class Constituency(models.Model):
    name = models.CharField(max_length=100, unique=True)
    district = models.CharField(max_length=100)
    state = models.CharField(max_length=100, default='Gujarat')
    total_voters = models.IntegerField(default=0)

    def __str__(self):
        return self.name

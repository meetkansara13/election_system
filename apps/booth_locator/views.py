from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from geopy.distance import geodesic
import folium
import json
import os

from .models import PollingBooth
from .serializers import PollingBoothSerializer


class NearestBoothView(APIView):
    """
    GET /api/booth/nearest/?lat=23.03&lng=72.58&limit=5
    Returns nearest polling booths sorted by distance.
    """
    def get(self, request):
        try:
            user_lat = float(request.GET.get('lat'))
            user_lng = float(request.GET.get('lng'))
            limit = int(request.GET.get('limit', 5))
        except (TypeError, ValueError):
            return Response({'error': 'lat and lng are required as floats.'}, status=400)

        booths = PollingBooth.objects.all()
        user_coords = (user_lat, user_lng)

        results = []
        for booth in booths:
            booth_coords = (booth.latitude, booth.longitude)
            dist = geodesic(user_coords, booth_coords).km
            results.append({
                'id': booth.id,
                'booth_id': booth.booth_id,
                'name': booth.name,
                'address': booth.address,
                'constituency': booth.constituency,
                'latitude': booth.latitude,
                'longitude': booth.longitude,
                'distance_km': round(dist, 3),
                'total_voters': booth.total_voters,
                'is_accessible': booth.is_accessible,
                'has_cctv': booth.has_cctv,
            })

        results.sort(key=lambda x: x['distance_km'])
        return Response(results[:limit])


class BoothMapView(APIView):
    """
    GET /api/booth/map/?constituency=Maninagar
    Returns folium HTML map with booth pins.
    """
    def get(self, request):
        constituency = request.GET.get('constituency')
        qs = PollingBooth.objects.all()
        if constituency:
            qs = qs.filter(constituency__icontains=constituency)

        if not qs.exists():
            return Response({'error': 'No booths found.'}, status=404)

        center_lat = sum(b.latitude for b in qs) / qs.count()
        center_lng = sum(b.longitude for b in qs) / qs.count()

        m = folium.Map(location=[center_lat, center_lng], zoom_start=13,
                       tiles='CartoDB positron')

        for booth in qs:
            popup_html = f"""
            <div style='font-family:sans-serif;min-width:180px'>
              <b style='font-size:14px'>{booth.name}</b><br>
              <small>ID: {booth.booth_id}</small><br>
              <hr style='margin:4px 0'>
              {booth.address}<br>
              <b>Constituency:</b> {booth.constituency}<br>
              <b>Voters:</b> {booth.total_voters:,}<br>
              {'✅ Accessible' if booth.is_accessible else '❌ Not accessible'}<br>
              {'📷 CCTV' if booth.has_cctv else ''}
            </div>"""

            folium.Marker(
                location=[booth.latitude, booth.longitude],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=booth.name,
                icon=folium.Icon(color='red', icon='info-sign')
            ).add_to(m)

        map_html = m._repr_html_()
        return Response({'map_html': map_html, 'booth_count': qs.count()})


class BoothListView(APIView):
    """GET /api/booth/list/?constituency=X&district=Y"""
    def get(self, request):
        qs = PollingBooth.objects.all()
        constituency = request.GET.get('constituency')
        district = request.GET.get('district')
        if constituency:
            qs = qs.filter(constituency__icontains=constituency)
        if district:
            qs = qs.filter(district__icontains=district)
        serializer = PollingBoothSerializer(qs, many=True)
        return Response(serializer.data)


class BoothDetailView(APIView):
    """GET /api/booth/<booth_id>/"""
    def get(self, request, booth_id):
        try:
            booth = PollingBooth.objects.get(booth_id=booth_id)
            serializer = PollingBoothSerializer(booth)
            return Response(serializer.data)
        except PollingBooth.DoesNotExist:
            return Response({'error': 'Booth not found'}, status=404)

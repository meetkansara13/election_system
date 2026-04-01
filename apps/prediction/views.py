from rest_framework.views import APIView
from rest_framework.response import Response
import os
from django.conf import settings

from .ml_engine import predict_constituency, train_models


def models_exist():
    return os.path.exists(os.path.join(settings.ML_MODELS_DIR, 'winner_clf.pkl'))


class TrainModelView(APIView):
    """POST /api/predict/train/"""
    def post(self, request):
        try:
            use_real = request.data.get('use_real_data', True)
            metrics = train_models(use_real_data=use_real)
            return Response({'status': 'trained', 'metrics': metrics})
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class PredictView(APIView):
    """POST /api/predict/"""
    def post(self, request):
        if not models_exist():
            return Response(
                {'error': 'Models not trained. POST to /api/predict/train/ first.'},
                status=400
            )
        constituency = request.data.get('constituency')
        year = request.data.get('year', 2027)
        candidates = request.data.get('candidates', [])

        if not constituency:
            return Response({'error': 'constituency is required'}, status=400)

        try:
            result = predict_constituency(constituency, year, candidates)
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class BulkPredictView(APIView):
    """POST /api/predict/bulk/"""
    def post(self, request):
        if not models_exist():
            return Response({'error': 'Models not trained.'}, status=400)

        constituencies = request.data.get('constituencies', [])
        year = request.data.get('year', 2027)

        if not constituencies:
            return Response({'error': 'constituencies list is required'}, status=400)

        results = []
        for c in constituencies:
            try:
                results.append(predict_constituency(c, year))
            except Exception as e:
                results.append({'constituency': c, 'error': str(e)})

        summary = {}
        for r in results:
            if 'predicted_winner' in r:
                p = r['predicted_winner']
                summary[p] = summary.get(p, 0) + 1

        return Response({
            'year': year,
            'total_constituencies': len(constituencies),
            'seat_predictions': summary,
            'details': results,
        })
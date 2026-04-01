from django.http import JsonResponse
from rest_framework.authtoken.models import Token


EXEMPT_PATHS = [
    '/api/auth/login/',
    '/api/auth/register/',
    '/admin/',
]


class TokenAuthMiddleware:
    """
    Middleware that enforces token auth on all API endpoints.
    Dashboard and static files are also protected — redirect to login page.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Always allow exempt paths
        if any(path.startswith(p) for p in EXEMPT_PATHS):
            return self.get_response(request)

        # Allow already-authenticated sessions (dashboard HTML)
        if request.user.is_authenticated:
            return self.get_response(request)

        # For API paths, require token
        if path.startswith('/api/'):
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header.startswith('Token '):
                token_key = auth_header.split(' ')[1]
                try:
                    token = Token.objects.select_related('user').get(key=token_key)
                    request.user = token.user
                    return self.get_response(request)
                except Token.DoesNotExist:
                    pass
            return JsonResponse({'detail': 'Authentication required.'}, status=401)

        # For dashboard HTML, redirect to login page
        if path.startswith('/dashboard/'):
            from django.shortcuts import redirect
            return redirect('/login/')

        return self.get_response(request)
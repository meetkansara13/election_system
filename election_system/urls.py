from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

from apps.accounts.views import LoginPageView, LogoutPageView

urlpatterns = [
    # Redirect root based on session state
    path('', lambda r: redirect('/dashboard/' if r.user.is_authenticated else '/login/')),

    # Admin
    path('admin/', admin.site.urls),

    # APIs
    path('api/booth/', include('apps.booth_locator.urls')),
    path('api/predict/', include('apps.prediction.urls')),

    # Dashboard
    path('dashboard/', include('apps.dashboard.urls')),

    # Accounts (API routes)
    path('api/auth/', include('apps.accounts.urls')),

    # 🔥 CLEAN WEB ROUTES
    path('login/', LoginPageView.as_view(), name='login'),
    path('logout/', LogoutPageView.as_view(), name='logout'),
    path('accounts/login/', lambda r: redirect('/login/')),
    path('accounts/logout/', lambda r: redirect('/logout/')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    ProfileView,
    ChangePasswordView,
    UserListView,
    LoginPageView,
    LogoutPageView
)

urlpatterns = [
    # 🔐 API ROUTES
    path('register/', RegisterView.as_view(), name='auth-register'),
    path('login/', LoginView.as_view(), name='auth-login'),
    path('logout/', LogoutView.as_view(), name='auth-logout'),
    path('profile/', ProfileView.as_view(), name='auth-profile'),
    path('change-password/', ChangePasswordView.as_view(), name='auth-change-password'),
    path('users/', UserListView.as_view(), name='auth-users'),

    # 🌐 WEB ROUTES (TEMPLATES)
    path('login-page/', LoginPageView.as_view(), name='login-page'),
    path('logout-page/', LogoutPageView.as_view(), name='logout-page'),
]
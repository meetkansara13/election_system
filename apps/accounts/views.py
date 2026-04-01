from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect
from django.contrib.auth import logout as auth_logout
from rest_framework.permissions import AllowAny
from django.views import View
from django.utils.http import url_has_allowed_host_and_scheme
import threading
from .models import User
from .serializers import (
    RegisterSerializer, LoginSerializer,
    UserSerializer, ChangePasswordSerializer
)


_model_training_lock = threading.Lock()
_model_training_started = False


def trigger_model_training():
    global _model_training_started
    with _model_training_lock:
        if _model_training_started:
            return
        _model_training_started = True

    def _train():
        global _model_training_started
        try:
            from apps.prediction.ml_engine import train_models
            train_models(use_real_data=True)
        except Exception:
            pass
        finally:
            with _model_training_lock:
                _model_training_started = False

    threading.Thread(target=_train, daemon=True).start()


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                'message': 'Account created successfully.',
                'token': token.key,
                'user': UserSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)
            trigger_model_training()
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                'message': 'Login successful.',
                'token': token.key,
                'user': UserSerializer(user).data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            request.user.auth_token.delete()
        except Exception:
            pass
        logout(request)
        return Response({'message': 'Logged out successfully.'})


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            if not user.check_password(serializer.validated_data['old_password']):
                return Response(
                    {'old_password': 'Incorrect password.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            # Re-issue token
            user.auth_token.delete()
            token = Token.objects.create(user=user)
            return Response({'message': 'Password changed.', 'token': token.key})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserListView(APIView):
    """Admin only — list all users."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'admin':
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        users = User.objects.all().order_by('-created_at')
        return Response(UserSerializer(users, many=True).data)
    
class LoginPageView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        return render(request, 'accounts/login.html', {
            'next_url': request.GET.get('next', '/dashboard/'),
        })

    def post(self, request):
        serializer = LoginSerializer(data={
            'email': request.POST.get('email'),
            'password': request.POST.get('password'),
        })
        next_url = request.POST.get('next') or '/dashboard/'
        if not url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            next_url = '/dashboard/'

        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)
            trigger_model_training()
            return redirect(next_url)

        errors = serializer.errors.get('non_field_errors') or ['Login failed.']
        return render(request, 'accounts/login.html', {
            'error_message': errors[0],
            'next_url': next_url,
        })
 
 
class LogoutPageView(View):
    def get(self, request):
        auth_logout(request)
        return render(request, 'accounts/logout.html')

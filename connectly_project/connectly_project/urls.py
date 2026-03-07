from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from posts.views import GoogleLoginAPIView

urlpatterns = [
    path('admin/', admin.site.urls),

    # API routes
    path('api/', include('posts.urls')),

    # JWT
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Google OAuth login via django-allauth
    path('auth/google/login/', GoogleLoginAPIView.as_view(), name='google_login'),
]

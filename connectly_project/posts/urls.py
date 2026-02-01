from django.urls import path
from . import views
from .views import PostDetailView, ProtectedView

urlpatterns = [
    path('users/', views.get_users),
    path('users/create/', views.create_user),

    path('posts/', views.get_posts),
    path('posts/create/', views.create_post),
    path('posts/<int:pk>/', PostDetailView.as_view()),

    path('protected/', ProtectedView.as_view()),
]

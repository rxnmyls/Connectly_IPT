from django.urls import path
from .views import (
    PostDetailView, 
    ProtectedView, 
    UserListCreate, 
    PostListCreate, 
    CommentListCreate,
    PostCommentsView,
    CommentCreateView,
    LikeCreateView,
    feed,
)

urlpatterns = [
    path('users/', UserListCreate.as_view(), name='user-list-create'),
    path('posts/', PostListCreate.as_view(), name='post-list-create'),
    path('comments/', CommentListCreate.as_view(), name='comment-list-create'),
    path('posts/<int:pk>/', PostDetailView.as_view(), name='post-detail'),
    path('posts/<int:pk>/comments/', PostCommentsView.as_view(), name='post-comments'),
    path('posts/<int:pk>/comment/', CommentCreateView.as_view(), name='create-comment'),
    path('posts/<int:pk>/like/', LikeCreateView.as_view(), name='like-post'),
    path('feed/', feed, name='feed'),
    path('protected/', ProtectedView.as_view(), name='protected'),
]

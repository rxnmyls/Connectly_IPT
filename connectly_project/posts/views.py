import os

from django.contrib.auth.models import User as AuthUser
from django.contrib.sites.models import Site
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
import json

from allauth.socialaccount.helpers import complete_social_login
from allauth.socialaccount.models import SocialApp, SocialLogin, SocialToken
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User as LocalUser, Post, Comment, Like
from .serializers import UserSerializer, PostSerializer, CommentSerializer, LikeSerializer
from .permissions import IsPostAuthor

# =========================
# USERS
# =========================

def get_users(request):
    users = AuthUser.objects.all()
    serializer = UserSerializer(users, many=True)
    return JsonResponse(serializer.data, safe=False)


@csrf_exempt
def create_user(request):
    if request.method == "POST":
        data = json.loads(request.body)

        user = AuthUser(
            username=data["username"],
            email=data["email"]
        )

        # PASSWORD HASHING on auth user
        user.set_password(data["password"])
        user.save()

        return JsonResponse(
            {"message": "User created successfully"},
            status=201
        )

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def login_user(request):
    if request.method == "POST":
        data = json.loads(request.body)

        user = authenticate(
            username=data["username"],
            password=data["password"]
        )

        if user:
            return JsonResponse({"message": "Login successful"})
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    return JsonResponse({"error": "Method not allowed"}, status=405)


class GoogleLoginAPIView(APIView):
    """POST /auth/google/login

    Accepts a Google OAuth2 access token (or ID token) and returns a JWT pair.

    The client is expected to obtain the Google token via the frontend Google OAuth flow
    (e.g. Google Sign-In / Google Identity Services) and then send it to this endpoint.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        access_token = request.data.get('access_token') or request.data.get('id_token')
        if not access_token:
            return Response({"detail": "Missing access_token"}, status=status.HTTP_400_BAD_REQUEST)

        # Ensure we've configured a SocialApp for Google.
        app = SocialApp.objects.filter(provider=GoogleOAuth2Adapter.provider_id).first()
        if not app:
            # Optionally create one from env vars if not present.
            client_id = os.environ.get('GOOGLE_CLIENT_ID')
            secret = os.environ.get('GOOGLE_CLIENT_SECRET')
            if client_id and secret:
                app = SocialApp.objects.create(
                    provider=GoogleOAuth2Adapter.provider_id,
                    name='Google',
                    client_id=client_id,
                    secret=secret,
                )
                app.sites.add(Site.objects.get_current())

        if not app:
            return Response(
                {"detail": "Google SocialApp is not configured. Set GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET or configure via the admin."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        token = SocialToken(token=access_token, app=app)
        adapter = GoogleOAuth2Adapter(request)
        login = adapter.complete_login(request, app, token, response={"access_token": access_token})
        login.token = token
        login.state = SocialLogin.state_from_request(request)

        try:
            complete_social_login(request, login)
        except Exception as exc:
            return Response({"detail": "Google login failed", "error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        user = login.user
        if not user.is_active:
            user.is_active = True
            user.save()

        refresh = RefreshToken.for_user(user)
        return Response({"access": str(refresh.access_token), "refresh": str(refresh)})


# =========================
# POSTS (PROTECTED)
# =========================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_posts(request):
    """
     No token → 401
    """
    posts = Post.objects.all()
    serializer = PostSerializer(posts, many=True)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_post(request):
    serializer = PostSerializer(data=request.data)

    if serializer.is_valid():
        # Map authenticated auth.User to posts.User (local user model)
        local_user, _ = LocalUser.objects.get_or_create(
            username=request.user.username,
            defaults={
                'email': getattr(request.user, 'email', '')
            }
        )
        serializer.save(author=local_user)
        return Response(serializer.data, status=201)

    return Response(serializer.errors, status=400)


class PostDetailView(APIView):
    """
    RBAC enforced here
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsPostAuthor]

    def get(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        self.check_object_permissions(request, post)
        serializer = PostSerializer(post)
        return Response(serializer.data)

    def delete(self, request, pk):
        """
        Regular user deleting others' post → 403
        """
        post = get_object_or_404(Post, pk=pk)
        self.check_object_permissions(request, post)
        post.delete()
        return Response({"message": "Post deleted"})


class ProtectedView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"message": "Authenticated!"})


class UserListCreate(APIView):
    def get(self, request):
        users = AuthUser.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)


    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PostListCreate(APIView):
    def get(self, request):
        # Public: no auth required to view posts
        posts = Post.objects.all()
        serializer = PostSerializer(posts, many=True)
        return Response(serializer.data)

    def post(self, request):
        # Require auth to create posts
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication credentials were not provided."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        serializer = PostSerializer(data=request.data)
        if serializer.is_valid():
            # Map authenticated auth.User to posts.User (local user model)
            local_user, _ = LocalUser.objects.get_or_create(
                username=request.user.username,
                defaults={'email': getattr(request.user, 'email', '')}
            )
            serializer.save(author=local_user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def feed(request):
    """GET /feed

    Returns posts sorted by newest first.

    Query params:
      - page (int, required)
      - page_size (int, required)
      - user (optional username to filter by author)
    """

    # Validate pagination parameters (must be integers >= 1)
    try:
        page = int(request.query_params.get('page', 1))
        if page < 1:
            raise ValueError
    except (TypeError, ValueError):
        return Response(
            {"detail": "Invalid page parameter. Must be an integer >= 1."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        page_size = int(request.query_params.get('page_size', 10))
        if page_size < 1:
            raise ValueError
    except (TypeError, ValueError):
        return Response(
            {"detail": "Invalid page_size parameter. Must be an integer >= 1."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    posts_qs = Post.objects.order_by('-created_at')

    username = request.query_params.get('user')
    if username:
        if not AuthUser.objects.filter(username=username).exists():
            return Response(
                {"detail": f"User '{username}' not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        posts_qs = posts_qs.filter(author__username=username)
    elif request.user and request.user.is_authenticated:
        # Optional: if user is logged in and no explicit filter is passed,
        # show that user's posts (user-specific feed). Otherwise, return global feed.
        posts_qs = posts_qs.filter(author__username=request.user.username)

    total = posts_qs.count()
    offset = (page - 1) * page_size
    posts = posts_qs[offset : offset + page_size]

    serializer = PostSerializer(posts, many=True)
    return Response(
        {
            'page': page,
            'page_size': page_size,
            'total': total,
            'results': serializer.data,
        }
    )


class CommentListCreate(APIView):
    def get(self, request):
        comments = Comment.objects.all()
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CommentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PostCommentsView(APIView):
    """
    GET /posts/{id}/comments: Retrieves all comments for a post.
    """
    def get(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        comments = post.comments.all()
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)


class CommentCreateView(APIView):
    """
    POST /posts/{id}/comment: Allows users to comment on a post.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        serializer = CommentSerializer(data=request.data)
        if serializer.is_valid():
            local_user, _ = LocalUser.objects.get_or_create(
                username=request.user.username,
                defaults={'email': getattr(request.user, 'email', '')}
            )
            serializer.save(author=local_user, post=post)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LikeCreateView(APIView):
    """
    POST /posts/{id}/like: Allows users to like a post.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        # Map auth user to local posts.User
        local_user, _ = LocalUser.objects.get_or_create(
            username=request.user.username,
            defaults={'email': getattr(request.user, 'email', '')}
        )

        # Check if user already liked this post
        like = Like.objects.filter(user=local_user, post=post).first()
        
        if like:
            # Unlike the post
            like.delete()
            return Response(
                {"message": "Post unliked"},
                status=status.HTTP_200_OK
            )
        else:
            # Like the post
            like = Like.objects.create(user=local_user, post=post)
            serializer = LikeSerializer(like)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )

from django.contrib.auth.models import User as AuthUser
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
import json

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authtoken.models import Token          # NEW

from google.oauth2 import id_token                         # NEW
from google.auth.transport import requests as google_requests  # NEW

from .models import User as LocalUser, Post, Comment, Like
from .serializers import UserSerializer, PostSerializer, CommentSerializer, LikeSerializer
from .permissions import IsPostAuthor

GOOGLE_CLIENT_ID = "445044362191-78olbucqpcip2v9kr511vqe0p8i0gvj2.apps.googleusercontent.com"                # NEW - replace later

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


# =========================
# GOOGLE OAUTH             # NEW
# =========================

class GoogleLoginView(APIView):
    def post(self, request):
        token = request.data.get("token")

        if not token:
            return Response(
                {"error": "Token is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Verify the token with Google
            google_data = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                GOOGLE_CLIENT_ID
            )

            email = google_data.get("email")
            name = google_data.get("name", "")

            # Find or create user
            user, created = AuthUser.objects.get_or_create(
                username=email,
                defaults={"email": email, "first_name": name}
            )

            # Issue API token
            api_token, _ = Token.objects.get_or_create(user=user)

            return Response({
                "token": api_token.key,
                "user": email,
                "new_account": created
            }, status=status.HTTP_200_OK)

        except ValueError:
            # Invalid or expired Google token
            return Response(
                {"error": "Invalid or expired Google token"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
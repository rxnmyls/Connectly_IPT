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
from rest_framework.authtoken.models import Token

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from .models import User as LocalUser, Post, Comment, Like
from .serializers import UserSerializer, PostSerializer, CommentSerializer, LikeSerializer
from .permissions import IsPostAuthor, IsAdmin

GOOGLE_CLIENT_ID = "445044362191-78olbucqpcip2v9kr511vqe0p8i0gvj2.apps.googleusercontent.com"

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
        local_user, _ = LocalUser.objects.get_or_create(
            username=request.user.username,
            defaults={
                'email': getattr(request.user, 'email', '')
            }
        )
        serializer.save(author=local_user)
        return Response(serializer.data, status=201)

    return Response(serializer.errors, status=400)


def get_local_user(request):
    """Helper: get LocalUser from authenticated request."""  # NEW HELPER
    return LocalUser.objects.filter(
        username=request.user.username
    ).first()


class PostDetailView(APIView):
    """
    RBAC + Privacy enforced here
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        post = get_object_or_404(Post, pk=pk)

        # Privacy check
        if post.privacy == 'private':
            local_user = get_local_user(request)                      # FIXED
            # Debug info to help trace issues
            print(f"[DEBUG] request.user.username: {request.user.username}")
            print(f"[DEBUG] local_user found: {local_user}")
            print(f"[DEBUG] post.author: {post.author}")
            print(f"[DEBUG] match: {local_user == post.author}")

            if local_user is None or post.author != local_user:
                return Response(
                    {"error": "This post is private."},
                    status=status.HTTP_403_FORBIDDEN
                )

        serializer = PostSerializer(post)
        return Response(serializer.data)

    def delete(self, request, pk):
        """
        Admin can delete any post.
        Regular user can only delete their own post → 403
        """
        post = get_object_or_404(Post, pk=pk)

        local_user = get_local_user(request)                          # FIXED

        is_admin = local_user and local_user.role == 'admin'
        is_author = local_user and post.author == local_user

        if not (is_admin or is_author):
            return Response(
                {"error": "You do not have permission to delete this post."},
                status=status.HTTP_403_FORBIDDEN
            )

        post.delete()
        return Response({"message": "Post deleted."})


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
        if request.user and request.user.is_authenticated:
            local_user = get_local_user(request)                      # FIXED
            # Show public posts + user's own private posts
            posts = (
                Post.objects.filter(privacy='public') |
                Post.objects.filter(author=local_user)
            ).distinct().order_by('-created_at')
        else:
            # Guests see public posts only
            posts = Post.objects.filter(
                privacy='public'
            ).order_by('-created_at')

        serializer = PostSerializer(posts, many=True)
        return Response(serializer.data)

    def post(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication credentials were not provided."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        serializer = PostSerializer(data=request.data)
        if serializer.is_valid():
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
        local_user, _ = LocalUser.objects.get_or_create(
            username=request.user.username,
            defaults={'email': getattr(request.user, 'email', '')}
        )

        like = Like.objects.filter(user=local_user, post=post).first()

        if like:
            like.delete()
            return Response(
                {"message": "Post unliked"},
                status=status.HTTP_200_OK
            )
        else:
            like = Like.objects.create(user=local_user, post=post)
            serializer = LikeSerializer(like)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )


# =========================
# GOOGLE OAUTH
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
            google_data = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                GOOGLE_CLIENT_ID
            )

            email = google_data.get("email")
            name = google_data.get("name", "")

            user, created = AuthUser.objects.get_or_create(
                username=email,
                defaults={"email": email, "first_name": name}
            )

            api_token, _ = Token.objects.get_or_create(user=user)

            return Response({
                "token": api_token.key,
                "user": email,
                "new_account": created
            }, status=status.HTTP_200_OK)

        except ValueError:
            return Response(
                {"error": "Invalid or expired Google token"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
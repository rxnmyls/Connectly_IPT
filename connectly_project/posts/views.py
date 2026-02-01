from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
import json

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Post
from .serializers import UserSerializer, PostSerializer
from .permissions import IsPostAuthor


# =========================
# USERS
# =========================

def get_users(request):
    users = User.objects.all()
    serializer = UserSerializer(users, many=True)
    return JsonResponse(serializer.data, safe=False)


@csrf_exempt
def create_user(request):
    if request.method == "POST":
        data = json.loads(request.body)

        user = User(
            username=data["username"],
            email=data["email"]
        )

        #PASSWORD HASHING
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
        serializer.save(author=request.user)
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

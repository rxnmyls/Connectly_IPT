from django.db import models


class User(models.Model):
    ROLE_CHOICES = [                          # NEW
        ('admin', 'Admin'),
        ('user', 'User'),
        ('guest', 'Guest'),
    ]

    username = models.CharField(max_length=100, unique=True)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    role = models.CharField(                  # NEW
        max_length=10,
        choices=ROLE_CHOICES,
        default='user'
    )

    def __str__(self):
        return self.username


class Post(models.Model):
    PRIVACY_CHOICES = [                       # NEW
        ('public', 'Public'),
        ('private', 'Private'),
    ]

    content = models.TextField()
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='posts'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    privacy = models.CharField(               # NEW
        max_length=10,
        choices=PRIVACY_CHOICES,
        default='public'
    )

    def __str__(self):
        return self.content[:50]


class Comment(models.Model):
    text = models.TextField()
    author = models.ForeignKey(User, related_name='comments', on_delete=models.CASCADE)
    post = models.ForeignKey(Post, related_name='comments', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.author.username} on Post {self.post.id}"


class Like(models.Model):
    user = models.ForeignKey(User, related_name='likes', on_delete=models.CASCADE)
    post = models.ForeignKey(Post, related_name='likes', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')

    def __str__(self):
        return f"{self.user.username} liked Post {self.post.id}"
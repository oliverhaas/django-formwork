"""Blog posts grouped by topic, with reader comments."""

from __future__ import annotations

from django.db import models
from django.utils import timezone
from taskmanager.models import Member


class Topic(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "In review"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    STATUS_COLORS = {
        Status.DRAFT: "neutral",
        Status.REVIEW: "warning",
        Status.PUBLISHED: "success",
        Status.ARCHIVED: "secondary",
    }

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    author = models.ForeignKey(Member, on_delete=models.PROTECT, related_name="posts")
    topics = models.ManyToManyField(Topic, blank=True, related_name="posts")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    excerpt = models.CharField(max_length=300, blank=True)
    body = models.TextField()
    cover = models.ImageField(upload_to="posts/", blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    allow_comments = models.BooleanField(default=True)
    reading_minutes = models.PositiveSmallIntegerField(default=3)
    seo_title = models.CharField("SEO title", max_length=70, blank=True)
    seo_description = models.CharField("SEO description", max_length=160, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    name = models.CharField(max_length=80)
    email = models.EmailField()
    body = models.TextField()
    is_approved = models.BooleanField("approved", default=False)
    is_spam = models.BooleanField("spam", default=False)
    ip_address = models.GenericIPAddressField("IP address", null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} on {self.post_id}"

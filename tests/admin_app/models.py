"""Models the admin tests and the admin demo register."""

from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    class Meta:
        app_label = "admin_app"
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        app_label = "admin_app"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Item(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=200)
    slug = models.SlugField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="items")
    tags = models.ManyToManyField(Tag, blank=True, related_name="items")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantity = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    released = models.DateField(null=True, blank=True)
    available_from = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    website = models.URLField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        app_label = "admin_app"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f"/items/{self.pk}/"


class Part(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="parts")
    name = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        app_label = "admin_app"

    def __str__(self):
        return self.name


class Review(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="reviews")
    author = models.CharField(max_length=100)
    rating = models.PositiveSmallIntegerField(choices=[(n, str(n)) for n in range(1, 6)], default=5)
    text = models.TextField(blank=True)

    class Meta:
        app_label = "admin_app"

    def __str__(self):
        return f"{self.author} ({self.rating})"

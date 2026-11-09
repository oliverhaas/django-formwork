from django.db.models import Count
from django.utils import timezone

from django_formwork import admin

from .models import Comment, Post, Topic


class CommentInline(admin.StackedInline):
    model = Comment
    fields = [("name", "email", "created_at"), "body", ("is_approved", "is_spam")]
    readonly_fields = ["created_at"]
    extra = 0


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "post_count"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(num_posts=Count("posts"))

    @admin.display(description="Posts", ordering="num_posts")
    def post_count(self, obj):
        return obj.num_posts


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "status", "published_at", "reading_minutes", "comment_count", "allow_comments"]
    list_select_related = ["author"]
    list_filter = ["status", "topics", "author", "allow_comments", "published_at"]
    list_badges = {"status": Post.STATUS_COLORS}
    list_defer_fields = ["body"]
    search_fields = ["title", "excerpt", "body"]
    date_hierarchy = "published_at"
    prepopulated_fields = {"slug": ["title"]}
    autocomplete_fields = ["author"]
    radio_fields = {"status": admin.HORIZONTAL}
    fieldsets = [
        (None, {"fields": ["title", "slug", ("author", "published_at"), "status", "topics"]}),
        ("Content", {"fields": ["excerpt", "body", "cover", ("reading_minutes", "allow_comments")]}),
        ("SEO", {"fields": ["seo_title", "seo_description"], "classes": ["collapse"]}),
    ]
    inlines = [CommentInline]
    actions = ["publish", "archive"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(num_comments=Count("comments"))

    @admin.display(description="Comments", ordering="num_comments")
    def comment_count(self, obj):
        return obj.num_comments

    @admin.action(description="Publish selected posts", icon="send")
    def publish(self, request, queryset):
        now = timezone.now()
        count = queryset.exclude(status=Post.Status.PUBLISHED).update(status=Post.Status.PUBLISHED, published_at=now)
        self.message_user(request, f"{count} posts published.")

    @admin.action(description="Archive selected posts", icon="archive")
    def archive(self, request, queryset):
        count = queryset.update(status=Post.Status.ARCHIVED)
        self.message_user(request, f"{count} posts archived.")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["name", "post", "created_at", "is_spam", "is_approved"]
    list_select_related = ["post"]
    list_editable = ["is_approved"]
    list_filter = ["is_approved", "is_spam", "created_at"]
    search_fields = ["name", "email", "body", "post__title"]
    date_hierarchy = "created_at"
    autocomplete_fields = ["post"]
    readonly_fields = ["ip_address", "created_at"]
    actions = ["approve", "mark_spam"]

    @admin.action(description="Approve selected comments", icon="check")
    def approve(self, request, queryset):
        count = queryset.update(is_approved=True, is_spam=False)
        self.message_user(request, f"{count} comments approved.")

    @admin.action(description="Mark selected comments as spam", icon="shield-x", danger=True)
    def mark_spam(self, request, queryset):
        count = queryset.update(is_spam=True, is_approved=False)
        self.message_user(request, f"{count} comments marked as spam.")

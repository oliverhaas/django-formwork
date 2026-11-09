from django.db.models import Count, Q

from django_formwork import admin

from .models import Member, Profile, Tag, Task


class AssignedTaskInline(admin.TabularInline):
    model = Task
    fields = ["title", "status", "priority", "due_date"]
    extra = 0
    show_change_link = True


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    icon = "list-checks"
    list_display = ["title", "status", "priority", "assignee", "due_date", "rating"]
    list_filter = ["status", "priority", "assignee", "tags", "due_date"]
    list_badges = {"status": Task.STATUS_COLORS, "priority": Task.PRIORITY_COLORS}
    search_fields = ["title", "description", "assignee__name"]
    date_hierarchy = "due_date"
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["title", "description", ("status", "priority"), ("assignee", "due_date"), "tags"]}),
        ("Review", {"fields": ["rating"]}),
        ("Files", {"fields": ["cover_image", "attachment"], "classes": ["collapse"]}),
        ("History", {"fields": [("created_at", "updated_at")], "classes": ["collapse"]}),
    ]
    actions = ["mark_done"]

    @admin.action(description="Mark selected tasks as done", icon="circle-check")
    def mark_done(self, request, queryset):
        count = queryset.update(status=Task.Status.DONE)
        self.message_user(request, f"{count} tasks marked as done.")


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    icon = "users"
    list_display = ["name", "email", "open_tasks"]
    search_fields = ["name", "email"]
    inlines = [AssignedTaskInline]

    def get_queryset(self, request):
        return (
            super().get_queryset(request).annotate(num_open=Count("tasks", filter=~Q(tasks__status=Task.Status.DONE)))
        )

    @admin.display(description="Open tasks", ordering="num_open")
    def open_tasks(self, obj):
        return obj.num_open


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    icon = "tag"
    list_display = ["name", "color", "task_count"]
    search_fields = ["name"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(num_tasks=Count("tasks"))

    @admin.display(description="Tasks", ordering="num_tasks")
    def task_count(self, obj):
        return obj.num_tasks


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    icon = "user-round"
    list_display = ["full_name", "email", "country"]

    # The example keeps exactly one profile row.
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

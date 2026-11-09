from django.db.models import Count, F, Q
from django.utils import timezone

from django_formwork import admin

from .models import CannedResponse, Reply, Ticket


class ResponseTimeFilter(admin.SimpleListFilter):
    title = "first response"
    parameter_name = "sla"

    def lookups(self, request, model_admin):
        return [("met", "Within target"), ("missed", "Target missed"), ("waiting", "No response yet")]

    def queryset(self, request, queryset):
        target = F("opened_at") + Ticket.FIRST_RESPONSE_TARGET
        if self.value() == "met":
            return queryset.filter(first_response_at__lte=target)
        if self.value() == "missed":
            return queryset.filter(first_response_at__gt=target)
        if self.value() == "waiting":
            return queryset.filter(first_response_at=None)
        return queryset


class ReplyInline(admin.StackedInline):
    model = Reply
    fields = [("author", "is_internal", "created_at"), "body"]
    autocomplete_fields = ["author"]
    extra = 0

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("author")


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    icon = "life-buoy"
    list_display = [
        "__str__",
        "requester",
        "requester__company",
        "status",
        "priority",
        "assignee",
        "opened_at",
        "reply_count",
    ]
    list_select_related = ["requester__company", "assignee"]
    list_filter = [
        "status",
        "priority",
        "channel",
        "assignee",
        ResponseTimeFilter,
        ("satisfaction", admin.EmptyFieldListFilter),
        "opened_at",
    ]
    list_badges = {"status": Ticket.STATUS_COLORS, "priority": Ticket.PRIORITY_COLORS}
    search_fields = ["subject", "requester__email", "requester__last_name", "requester__company__name", "replies__body"]
    date_hierarchy = "opened_at"
    autocomplete_fields = ["requester", "assignee"]
    radio_fields = {"channel": admin.HORIZONTAL}
    readonly_fields = ["opened_at"]
    fieldsets = [
        (None, {"fields": ["subject", ("requester", "assignee"), ("status", "priority"), "channel"]}),
        ("Timing", {"fields": [("opened_at", "first_response_at", "solved_at"), ("time_spent", "satisfaction")]}),
    ]
    inlines = [ReplyInline]
    actions = ["solve", "escalate"]

    def get_queryset(self, request):
        return (
            super().get_queryset(request).annotate(num_replies=Count("replies", filter=Q(replies__is_internal=False)))
        )

    @admin.display(description="Replies", ordering="num_replies")
    def reply_count(self, obj):
        return obj.num_replies

    @admin.action(description="Solve selected tickets", icon="circle-check")
    def solve(self, request, queryset):
        count = queryset.filter(status__in=Ticket.OPEN_STATUSES).update(
            status=Ticket.Status.SOLVED, solved_at=timezone.now()
        )
        self.message_user(request, f"{count} tickets solved.")

    @admin.action(description="Escalate selected tickets", icon="siren")
    def escalate(self, request, queryset):
        count = queryset.filter(status__in=Ticket.OPEN_STATUSES).update(priority=Ticket.Priority.URGENT)
        self.message_user(request, f"{count} tickets escalated to urgent.")


@admin.register(CannedResponse)
class CannedResponseAdmin(admin.ModelAdmin):
    icon = "message-square-text"
    list_display = ["title", "shortcut", "times_used"]
    search_fields = ["title", "body", "shortcut"]
    prepopulated_fields = {"shortcut": ["title"]}

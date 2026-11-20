from django.db import models
from django.db.models import Count, Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import capfirst

from django_formwork import admin
from django_formwork.admin.contenttypes import GenericStackedInline, GenericTabularInline

from .models import Activity, Company, Contact, Deal, FollowUp
from .stats import deal_figures, deal_stats
from .widgets import WebsiteInput


class ContactInline(admin.TabularInline):
    model = Contact
    fields = ["first_name", "last_name", "email", "job_title", "is_primary"]
    extra = 0
    show_change_link = True


class DealInline(admin.TabularInline):
    model = Deal
    fields = ["name", "stage", "value", "currency", "expected_close"]
    extra = 0
    show_change_link = True


class FollowUpInline(GenericTabularInline):
    model = FollowUp
    fields = ["title", "due_at", "owner", "done"]
    extra = 0


class FollowUpStackedInline(GenericStackedInline):
    model = FollowUp
    fields = [("title", "done"), ("due_at", "owner")]
    extra = 0


class ActivityInline(admin.StackedInline):
    model = Activity
    fields = [("kind", "occurred_at", "duration"), "subject", "body", ("contact", "logged_by")]
    extra = 0


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    icon = "building"
    list_display = ["name", "industry", "size", "country", "account_manager", "contact_count", "open_deals"]
    list_filter = ["industry", "size", "country", "account_manager"]
    search_fields = ["name", "website", "contacts__email"]
    choice_description = ["industry", "country"]
    fieldsets = [
        (None, {"fields": ["name", "website", ("industry", "size"), ("country", "account_manager")]}),
        ("Finance", {"fields": ["annual_revenue"]}),
        ("Notes", {"fields": ["notes"], "classes": ["collapse"]}),
    ]
    inlines = [ContactInline, DealInline, FollowUpInline]
    formfield_overrides = {models.URLField: {"widget": WebsiteInput}}

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                num_contacts=Count("contacts", distinct=True),
                num_open_deals=Count("deals", filter=Q(deals__stage__in=Deal.OPEN_STAGES), distinct=True),
            )
        )

    @admin.display(description="Contacts", ordering="num_contacts")
    def contact_count(self, obj):
        return obj.num_contacts

    @admin.display(description="Open deals", ordering="num_open_deals")
    def open_deals(self, obj):
        return obj.num_open_deals


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    icon = "contact"
    list_display = ["__str__", "company", "email", "job_title", "is_primary", "newsletter", "last_contacted"]
    list_filter = ["is_primary", "newsletter", "company__industry", ("last_contacted", admin.EmptyFieldListFilter)]
    search_fields = ["first_name", "last_name", "email", "company__name"]
    choice_description = ["company", "job_title"]
    autocomplete_fields = ["company"]
    import_formats = ("csv", "xlsx")
    import_id_fields = ["email"]
    fields = [
        ("first_name", "last_name"),
        "company",
        ("email", "phone"),
        "job_title",
        ("is_primary", "newsletter"),
        "last_contacted",
    ]
    inlines = [FollowUpStackedInline]


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    icon = "handshake"
    list_display = ["name", "company", "owner", "stage", "value", "currency", "probability", "expected_close"]
    list_filter = ["stage", "owner", "currency", "expected_close", ("company", admin.RelatedOnlyFieldListFilter)]
    list_badges = {"stage": Deal.STAGE_COLORS}
    search_fields = ["name", "company__name", "contact__last_name"]
    date_hierarchy = "expected_close"
    autocomplete_fields = ["company", "contact"]
    readonly_fields = ["created_at"]
    fieldsets = [
        (None, {"fields": ["name", ("company", "contact"), "owner"]}),
        ("Pipeline", {"fields": [("stage", "probability"), ("value", "currency"), ("expected_close", "closed_on")]}),
        ("Lost", {"fields": ["lost_reason"], "classes": ["collapse"]}),
        (None, {"fields": ["created_at"]}),
    ]
    inlines = [FollowUpInline, ActivityInline]
    actions = ["mark_won", "mark_lost"]

    @admin.slot(lazy=True, skeleton="charts/stats_skeleton.html")
    def list_top(self, request, queryset):
        return render_to_string("charts/stats.html", deal_stats(queryset), request)

    def change_top(self, request, obj):
        return render_to_string("charts/figures.html", deal_figures(obj), request)

    @admin.action(description="Mark selected deals as won", icon="trophy")
    def mark_won(self, request, queryset):
        count = queryset.update(stage=Deal.Stage.WON, probability=100, closed_on=timezone.localdate())
        self.message_user(request, f"{count} deals won.")

    @admin.action(description="Mark selected deals as lost", icon="thumbs-down", danger=True)
    def mark_lost(self, request, queryset):
        count = queryset.update(stage=Deal.Stage.LOST, probability=0, closed_on=timezone.localdate())
        self.message_user(request, f"{count} deals lost.")


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    icon = "messages-square"
    list_display = ["subject", "kind", "company", "contact", "logged_by", "occurred_at", "duration"]
    list_filter = ["kind", "logged_by", "occurred_at"]
    list_badges = {"kind": Activity.KIND_COLORS}
    search_fields = ["subject", "body", "company__name"]
    date_hierarchy = "occurred_at"
    autocomplete_fields = ["company", "deal", "contact"]


class RegardingFilter(admin.SimpleListFilter):
    title = "regarding"
    parameter_name = "regarding"

    def lookups(self, request, model_admin):
        return [("company", "Companies"), ("contact", "Contacts"), ("deal", "Deals")]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(content_type__app_label="crm", content_type__model=self.value())
        return queryset


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    icon = "bell"
    list_display = ["title", "regarding_link", "owner", "due_at", "done"]
    list_filter = ["done", RegardingFilter, "owner", "due_at"]
    search_fields = ["title"]
    date_hierarchy = "due_at"
    ordering = ["done", "due_at"]
    fields = ["regarding_link", "title", ("due_at", "owner"), "done"]
    readonly_fields = ["regarding_link"]
    actions = ["mark_done"]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("regarding")

    # A follow-up is added on the company, contact or deal it is about.
    def has_add_permission(self, request):
        return False

    @admin.display(description="Regarding")
    def regarding_link(self, obj):
        if obj.regarding is None:
            return "-"
        ct = obj.content_type
        url = reverse(f"{self.admin_site.name}:{ct.app_label}_{ct.model}_change", args=[obj.object_id])
        return format_html('{}: <a href="{}" class="link link-hover">{}</a>', capfirst(ct.name), url, obj.regarding)

    @admin.action(description="Mark selected follow-ups as done", icon="circle-check")
    def mark_done(self, request, queryset):
        count = queryset.update(done=True)
        self.message_user(request, f"{count} follow-ups marked as done.")

from datetime import timedelta

import django_filters
from django.db.models import Count, Q
from django.utils import timezone

from django_formwork import admin

from .models import Application, Candidate, Interview, Opening


class StaleFilter(admin.SimpleListFilter):
    title = "activity"
    parameter_name = "activity"
    STALE_AFTER = timedelta(days=14)

    def lookups(self, request, model_admin):
        return [("stale", "No move in two weeks"), ("fresh", "Moved recently")]

    def queryset(self, request, queryset):
        cutoff = timezone.now() - self.STALE_AFTER
        active = queryset.exclude(stage__in=[Application.Stage.HIRED, Application.Stage.REJECTED])
        if self.value() == "stale":
            return active.filter(moved_at__lt=cutoff)
        if self.value() == "fresh":
            return active.filter(moved_at__gte=cutoff)
        return queryset


class OpeningApplicationInline(admin.TabularInline):
    model = Application
    fk_name = "opening"
    fields = ["candidate", "stage", "rating", "applied_at"]
    readonly_fields = ["candidate", "applied_at"]
    extra = 0
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("candidate", "opening")


class CandidateApplicationInline(admin.TabularInline):
    model = Application
    fk_name = "candidate"
    fields = ["opening", "stage", "owner", "rating"]
    autocomplete_fields = ["opening", "owner"]
    extra = 0
    show_change_link = True


class InterviewInline(admin.TabularInline):
    model = Interview
    fields = ["kind", "interviewer", "scheduled_at", "duration", "score"]
    autocomplete_fields = ["interviewer"]
    extra = 0


@admin.register(Opening)
class OpeningAdmin(admin.ModelAdmin):
    icon = "briefcase"
    list_display = [
        "title",
        "department",
        "status",
        "workplace",
        "headcount",
        "applicant_count",
        "in_pipeline",
        "opened_on",
    ]
    list_select_related = ["department"]
    list_filter = [
        "status",
        "department",
        "workplace",
        "employment_type",
        django_filters.RangeFilter(field_name="salary_max", label="Salary up to"),
        "opened_on",
    ]
    list_badges = {"status": Opening.STATUS_COLORS}
    list_defer_fields = ["description", "screening_questions"]
    search_fields = ["title", "department__name"]
    date_hierarchy = "opened_on"
    autocomplete_fields = ["department", "hiring_manager"]
    radio_fields = {"workplace": admin.HORIZONTAL}
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "title",
                    ("department", "hiring_manager"),
                    ("status", "headcount"),
                    "workplace",
                    "employment_type",
                ]
            },
        ),
        ("Compensation", {"fields": [("salary_min", "salary_max", "currency")]}),
        ("Timeline", {"fields": [("opened_on", "closes_on")]}),
        ("Posting", {"fields": ["description", "screening_questions"], "classes": ["collapse"]}),
    ]
    inlines = [OpeningApplicationInline]
    save_as = True
    actions = ["publish", "put_on_hold", "close"]

    def get_queryset(self, request):
        closed = [Application.Stage.HIRED, Application.Stage.REJECTED]
        return (
            super()
            .get_queryset(request)
            .annotate(
                num_applications=Count("applications"),
                num_active=Count("applications", filter=~Q(applications__stage__in=closed)),
            )
        )

    @admin.display(description="Applicants", ordering="num_applications")
    def applicant_count(self, obj):
        return obj.num_applications

    @admin.display(description="In pipeline", ordering="num_active")
    def in_pipeline(self, obj):
        return obj.num_active

    @admin.action(description="Publish selected openings", icon="rocket")
    def publish(self, request, queryset):
        count = queryset.filter(status__in=[Opening.Status.DRAFT, Opening.Status.ON_HOLD]).update(
            status=Opening.Status.OPEN
        )
        self.message_user(request, f"{count} openings published.")

    @admin.action(description="Put selected openings on hold", icon="flag")
    def put_on_hold(self, request, queryset):
        count = queryset.filter(status=Opening.Status.OPEN).update(status=Opening.Status.ON_HOLD)
        self.message_user(request, f"{count} openings put on hold.")

    @admin.action(description="Close selected openings", icon="archive", danger=True)
    def close(self, request, queryset):
        count = queryset.exclude(status=Opening.Status.FILLED).update(status=Opening.Status.CLOSED)
        self.message_user(request, f"{count} openings closed.")


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    icon = "users-round"
    list_display = ["__str__", "email", "source", "city", "country", "application_count", "created_at"]
    list_filter = [
        "source",
        "country",
        ("resume", admin.EmptyFieldListFilter),
        ("referred_by", admin.RelatedOnlyFieldListFilter),
        "created_at",
    ]
    search_fields = ["first_name", "last_name", "^email", "city"]
    date_hierarchy = "created_at"
    autocomplete_fields = ["referred_by"]
    import_formats = ("csv", "xlsx", "json")
    import_id_fields = ["email"]
    fieldsets = [
        (None, {"fields": [("first_name", "last_name"), ("email", "phone"), ("city", "country"), "profile_url"]}),
        ("Source", {"fields": [("source", "referred_by"), "created_at"]}),
        ("Documents", {"fields": ["resume", "notes"]}),
    ]
    inlines = [CandidateApplicationInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(num_applications=Count("applications"))

    @admin.display(description="Applications", ordering="num_applications")
    def application_count(self, obj):
        return obj.num_applications


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    icon = "file-user"
    list_display = ["candidate", "opening", "stage", "owner", "rating", "applied_at", "moved_at"]
    list_select_related = ["candidate", "opening", "owner"]
    list_filter = [
        "stage",
        ("opening", admin.RelatedOnlyFieldListFilter),
        "owner",
        StaleFilter,
        ("rating", admin.EmptyFieldListFilter),
        "applied_at",
    ]
    list_badges = {"stage": Application.STAGE_COLORS}
    list_per_page = 50
    show_full_result_count = False
    search_fields = ["candidate__first_name", "candidate__last_name", "candidate__email", "opening__title"]
    date_hierarchy = "applied_at"
    autocomplete_fields = ["candidate", "opening", "owner"]
    radio_fields = {"stage": admin.HORIZONTAL}
    readonly_fields = ["moved_at"]
    fieldsets = [
        (None, {"fields": [("candidate", "opening"), "stage", ("owner", "rating")]}),
        ("Dates", {"fields": [("applied_at", "moved_at")]}),
        ("Rejection", {"fields": ["rejection_reason"], "classes": ["collapse"]}),
    ]
    inlines = [InterviewInline]
    actions = ["advance", "reject"]

    def save_model(self, request, obj, form, change):
        if "stage" in form.changed_data:
            obj.moved_at = timezone.now()
        super().save_model(request, obj, form, change)

    @admin.action(description="Move selected applications to the next stage", icon="arrow-right")
    def advance(self, request, queryset):
        now = timezone.now()
        count = sum(
            queryset.filter(stage=stage).update(stage=after, moved_at=now)
            for stage, after in Application.NEXT_STAGE.items()
        )
        self.message_user(request, f"{count} applications moved on.")

    @admin.action(description="Reject selected applications", icon="circle-x", danger=True)
    def reject(self, request, queryset):
        count = queryset.exclude(stage__in=[Application.Stage.HIRED, Application.Stage.REJECTED]).update(
            stage=Application.Stage.REJECTED, moved_at=timezone.now()
        )
        self.message_user(request, f"{count} applications rejected.")


@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    icon = "calendar-clock"
    list_display = ["__str__", "application", "interviewer", "scheduled_at", "score"]
    list_select_related = ["application__candidate", "application__opening", "interviewer"]
    list_filter = ["kind", "interviewer", ("score", admin.EmptyFieldListFilter), "scheduled_at"]
    search_fields = ["application__candidate__last_name", "application__opening__title", "feedback"]
    date_hierarchy = "scheduled_at"
    autocomplete_fields = ["application", "interviewer"]

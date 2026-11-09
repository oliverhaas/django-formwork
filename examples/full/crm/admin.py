from django.db.models import Count, Q
from django.utils import timezone

from django_formwork import admin

from .models import Activity, Company, Contact, Deal


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
    fieldsets = [
        (None, {"fields": ["name", "website", ("industry", "size"), ("country", "account_manager")]}),
        ("Finance", {"fields": ["annual_revenue"]}),
        ("Notes", {"fields": ["notes"], "classes": ["collapse"]}),
    ]
    inlines = [ContactInline, DealInline]

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
    list_select_related = ["company"]
    list_filter = ["is_primary", "newsletter", "company__industry", ("last_contacted", admin.EmptyFieldListFilter)]
    search_fields = ["first_name", "last_name", "email", "company__name"]
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


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    icon = "handshake"
    list_display = ["name", "company", "owner", "stage", "value", "currency", "probability", "expected_close"]
    list_select_related = ["company", "owner"]
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
    inlines = [ActivityInline]
    actions = ["mark_won", "mark_lost"]

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
    list_select_related = ["company", "contact", "logged_by"]
    list_filter = ["kind", "logged_by", "occurred_at"]
    list_badges = {"kind": Activity.KIND_COLORS}
    search_fields = ["subject", "body", "company__name"]
    date_hierarchy = "occurred_at"
    autocomplete_fields = ["company", "deal", "contact"]

from datetime import timedelta

import django_filters
from django import forms
from django.db.models import Count, F, Q
from django.template.loader import render_to_string
from django.utils import timezone

from django_formwork import admin
from django_formwork.forms import FormworkForm

from .models import Event, Registration, Venue
from .stats import event_figures, event_signups, event_stats


class PostponeForm(FormworkForm):
    days = forms.IntegerField(min_value=1, max_value=365, initial=7, help_text="Start and end move by this many days.")


class WhenFilter(admin.SimpleListFilter):
    title = "when"
    parameter_name = "when"

    def lookups(self, request, model_admin):
        return [("upcoming", "Upcoming"), ("past", "Past")]

    def queryset(self, request, queryset):
        if self.value() == "upcoming":
            return queryset.filter(starts_at__gte=timezone.now())
        if self.value() == "past":
            return queryset.filter(starts_at__lt=timezone.now())
        return queryset


class RegistrationInline(admin.TabularInline):
    model = Registration
    fields = ["contact", "status", "registered_at", "checked_in_at"]
    readonly_fields = ["contact", "registered_at", "checked_in_at"]
    extra = 0
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("contact")


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    icon = "map-pin"
    list_display = ["name", "is_virtual", "city", "country", "capacity", "event_count"]
    list_editable = ["capacity"]
    list_filter = ["is_virtual", "country"]
    search_fields = ["name", "city"]
    fieldsets = [
        (None, {"fields": ["name", "is_virtual", "capacity"]}),
        ("Location", {"fields": [("city", "country"), "address", "url"]}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(num_events=Count("events"))

    @admin.display(description="Events", ordering="num_events")
    def event_count(self, obj):
        return obj.num_events


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    icon = "calendar-days"
    list_display = ["title", "kind", "starts_at", "venue", "host", "price", "seats", "is_published"]
    list_select_related = ["venue", "host"]
    list_editable = ["kind", "starts_at", "venue", "host", "price", "is_published"]
    list_filter = [
        WhenFilter,
        "kind",
        "is_published",
        "venue",
        "host",
        django_filters.RangeFilter(field_name="price", label="Price"),
        "starts_at",
    ]
    list_badges = {"kind": Event.KIND_COLORS}
    list_defer_fields = ["description"]
    search_fields = ["title", "venue__name", "venue__city"]
    date_hierarchy = "starts_at"
    autocomplete_fields = ["venue", "host"]
    prepopulated_fields = {"slug": ["title"]}
    fieldsets = [
        (None, {"fields": ["title", "slug", "kind", ("venue", "host")]}),
        ("Schedule", {"fields": [("starts_at", "ends_at"), ("capacity", "price"), "is_published"]}),
        ("Page", {"fields": ["description", "cover"], "classes": ["collapse"]}),
    ]
    inlines = [RegistrationInline]
    save_as = True
    actions = ["publish", "unpublish", "postpone"]

    def get_queryset(self, request):
        taken = ~Q(registrations__status__in=[Registration.Status.CANCELLED, Registration.Status.WAITLIST])
        return super().get_queryset(request).annotate(num_registrations=Count("registrations", filter=taken))

    @admin.slot(lazy=True, skeleton="events/stats_skeleton.html")
    def list_top(self, request, queryset):
        return render_to_string("events/stats.html", event_stats(queryset), request)

    def change_top(self, request, obj):
        return render_to_string("events/event_figures.html", event_figures(obj), request)

    @admin.slot(lazy=True, skeleton="events/event_signups_skeleton.html")
    def change_bottom(self, request, obj):
        return render_to_string("events/event_signups.html", event_signups(obj), request)

    @admin.display(description="Seats", ordering="num_registrations")
    def seats(self, obj):
        if obj.capacity is None:
            return obj.num_registrations
        return f"{obj.num_registrations} / {obj.capacity}"

    @admin.action(
        description="Publish",
        description_plural="Publish selected events",
        icon="eye",
        help_text="Shows them on the site and opens registration.",
        location=[admin.ActionLocation.CHANGE_LIST, admin.ActionLocation.CHANGE_FORM],
    )
    def publish(self, request, queryset):
        count = queryset.update(is_published=True)
        self.message_user(request, f"{count} events published.")

    @admin.action(
        description="Unpublish",
        description_plural="Unpublish selected events",
        icon="eye-off",
        help_text="Hides them from the site. Registrations stay.",
        confirm="Unpublish %(count)s %(name)s?",
        location=[admin.ActionLocation.CHANGE_LIST, admin.ActionLocation.CHANGE_FORM],
    )
    def unpublish(self, request, queryset):
        count = queryset.update(is_published=False)
        self.message_user(request, f"{count} events unpublished.")

    @admin.action(
        description="Postpone",
        description_plural="Postpone selected events",
        icon="calendar-clock",
        help_text="Moves them by a number of days.",
        form=PostponeForm,
        location=[admin.ActionLocation.CHANGE_LIST, admin.ActionLocation.CHANGE_FORM],
    )
    def postpone(self, request, queryset, form):
        delta = timedelta(days=form.cleaned_data["days"])
        count = queryset.update(starts_at=F("starts_at") + delta, ends_at=F("ends_at") + delta)
        self.message_user(request, f"{count} events postponed by {form.cleaned_data['days']} days.")


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    icon = "ticket"
    list_display = ["contact", "contact__company", "event", "status", "registered_at", "checked_in_at"]
    list_select_related = ["contact__company", "event"]
    list_filter = [
        "status",
        ("event", admin.RelatedOnlyFieldListFilter),
        ("checked_in_at", admin.EmptyFieldListFilter),
        "registered_at",
    ]
    list_badges = {"status": Registration.STATUS_COLORS}
    search_fields = ["contact__first_name", "contact__last_name", "contact__email", "event__title", "=code"]
    date_hierarchy = "registered_at"
    autocomplete_fields = ["event", "contact"]
    readonly_fields = ["code"]
    fields = [("event", "contact"), "status", "code", ("registered_at", "checked_in_at"), "dietary_needs"]
    actions = ["check_in", "cancel"]

    @admin.action(description="Check in selected attendees", icon="badge-check")
    def check_in(self, request, queryset):
        count = queryset.filter(status=Registration.Status.REGISTERED).update(
            status=Registration.Status.ATTENDED, checked_in_at=timezone.now()
        )
        self.message_user(request, f"{count} attendees checked in.")

    @admin.action(description="Cancel selected registrations", icon="ban", danger=True)
    def cancel(self, request, queryset):
        count = queryset.exclude(status=Registration.Status.ATTENDED).update(status=Registration.Status.CANCELLED)
        self.message_user(request, f"{count} registrations cancelled.")

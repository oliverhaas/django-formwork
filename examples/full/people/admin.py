from django.db.models import Count
from django.utils import timezone

from django_formwork import admin

from .models import Department, Employee, Equipment, TimeOff


class EmployeeInline(admin.TabularInline):
    model = Employee
    fk_name = "department"
    fields = ["member", "job_title", "employment_type", "start_date"]
    extra = 0
    show_change_link = True


class TimeOffInline(admin.TabularInline):
    model = TimeOff
    fields = ["kind", "starts_on", "ends_on", "status"]
    extra = 0


class EquipmentInline(admin.TabularInline):
    model = Equipment
    fields = ["asset_tag", "kind", "model_name", "warranty_until"]
    extra = 0
    show_change_link = True


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    icon = "network"
    list_display = ["name", "code", "head", "headcount", "standup_time", "budget"]
    search_fields = ["name", "code"]
    inlines = [EmployeeInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(num_employees=Count("employees"))

    @admin.display(description="Headcount", ordering="num_employees")
    def headcount(self, obj):
        return obj.num_employees


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    icon = "id-card"
    list_display = ["member", "job_title", "department", "manager", "employment_type", "start_date", "remote"]
    list_select_related = ["member", "department", "manager__member"]
    list_filter = ["department", "employment_type", "remote", ("end_date", admin.EmptyFieldListFilter), "start_date"]
    list_badges = {"employment_type": Employee.TYPE_COLORS}
    search_fields = ["member__name", "member__email", "job_title"]
    autocomplete_fields = ["member", "manager"]
    fieldsets = [
        (None, {"fields": ["member", ("department", "job_title"), "manager"]}),
        ("Contract", {"fields": [("employment_type", "weekly_hours"), ("start_date", "end_date"), "remote"]}),
    ]
    inlines = [TimeOffInline, EquipmentInline]


@admin.register(TimeOff)
class TimeOffAdmin(admin.ModelAdmin):
    icon = "tree-palm"
    list_display = ["employee", "kind", "starts_on", "ends_on", "days", "status"]
    list_select_related = ["employee__member"]
    list_filter = ["status", "kind", "employee__department", "starts_on"]
    list_badges = {"status": TimeOff.STATUS_COLORS}
    search_fields = ["employee__member__name", "note"]
    date_hierarchy = "starts_on"
    autocomplete_fields = ["employee"]
    radio_fields = {"kind": admin.HORIZONTAL}
    readonly_fields = ["requested_at", "decided_by"]
    actions = ["approve", "decline"]

    @admin.display(description="Days")
    def days(self, obj):
        return obj.days

    def _decide(self, request, queryset, status):
        count = queryset.filter(status=TimeOff.Status.PENDING).update(status=status)
        self.message_user(request, f"{count} requests {TimeOff.Status(status).label.lower()}.")

    @admin.action(description="Approve selected requests", icon="check")
    def approve(self, request, queryset):
        self._decide(request, queryset, TimeOff.Status.APPROVED)

    @admin.action(description="Decline selected requests", icon="x", danger=True)
    def decline(self, request, queryset):
        self._decide(request, queryset, TimeOff.Status.DECLINED)


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    icon = "laptop"
    list_display = ["asset_tag", "kind", "model_name", "assigned_to", "purchased_on", "in_warranty", "retired"]
    list_select_related = ["assigned_to__member"]
    list_filter = ["kind", "retired", ("assigned_to", admin.EmptyFieldListFilter), "warranty_until"]
    search_fields = ["asset_tag", "serial_number", "model_name", "assigned_to__member__name"]
    autocomplete_fields = ["assigned_to"]
    actions = ["retire"]

    @admin.display(description="Warranty", boolean=True, ordering="warranty_until")
    def in_warranty(self, obj):
        return obj.warranty_until is not None and obj.warranty_until >= timezone.localdate()

    @admin.action(description="Retire selected equipment", icon="archive")
    def retire(self, request, queryset):
        count = queryset.update(retired=True, assigned_to=None)
        self.message_user(request, f"{count} items retired.")

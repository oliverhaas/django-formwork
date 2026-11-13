from django.utils import timezone

from django_formwork import admin

from .models import Invoice, InvoiceLine, Payment


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    fields = ["description", "quantity", "unit_price", "tax_rate"]
    extra = 0
    min_num = 1


class PaymentInline(admin.TabularInline):
    model = Payment
    fields = ["amount", "received_on", "method", "reference"]
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    icon = "receipt"
    list_display = ["number", "company", "status", "issued_on", "due_on", "is_overdue", "total", "currency"]
    list_select_related = ["company"]
    list_filter = ["status", "currency", ("company", admin.RelatedOnlyFieldListFilter), "issued_on", "due_on"]
    list_badges = {"status": Invoice.STATUS_COLORS}
    search_fields = ["=number", "company__name"]
    date_hierarchy = "issued_on"
    autocomplete_fields = ["company"]
    readonly_fields = ["total"]
    fieldsets = [
        (
            None,
            {"fields": [("number", "status"), "company", ("issued_on", "due_on", "paid_on"), ("currency", "total")]},
        ),
        ("Attachments", {"fields": ["pdf", "notes"], "classes": ["collapse"]}),
    ]
    inlines = [InvoiceLineInline, PaymentInline]
    actions = ["mark_sent", "mark_paid", "void"]

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status == Invoice.Status.PAID:
            return ["number", "company", "currency", "issued_on", "due_on", "total"]
        return super().get_readonly_fields(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status == Invoice.Status.PAID:
            return False
        return super().has_delete_permission(request, obj)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.recalculate()

    @admin.display(description="Overdue", boolean=True)
    def is_overdue(self, obj):
        return obj.is_overdue

    @admin.action(description="Mark selected invoices as sent", icon="send")
    def mark_sent(self, request, queryset):
        count = queryset.filter(status=Invoice.Status.DRAFT).update(
            status=Invoice.Status.SENT, issued_on=timezone.localdate()
        )
        self.message_user(request, f"{count} draft invoices marked as sent.")

    @admin.action(description="Mark selected invoices as paid", icon="circle-check")
    def mark_paid(self, request, queryset):
        open_statuses = [Invoice.Status.SENT, Invoice.Status.OVERDUE]
        count = queryset.filter(status__in=open_statuses).update(
            status=Invoice.Status.PAID, paid_on=timezone.localdate()
        )
        self.message_user(request, f"{count} invoices marked as paid.")

    @admin.action(description="Void selected invoices", icon="circle-x", danger=True)
    def void(self, request, queryset):
        count = queryset.exclude(status=Invoice.Status.PAID).update(status=Invoice.Status.VOID)
        self.message_user(request, f"{count} invoices voided. Paid invoices stay as they are.")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    icon = "banknote"
    list_display = ["invoice", "invoice__company", "amount", "method", "received_on", "reference"]
    list_select_related = ["invoice__company"]
    list_filter = ["method", "received_on"]
    search_fields = ["reference", "invoice__number", "invoice__company__name"]
    date_hierarchy = "received_on"
    raw_id_fields = ["invoice"]

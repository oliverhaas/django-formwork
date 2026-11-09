from django.db.models import Count

from django_formwork import admin

from .models import Category, Item, Part, Review, Tag


class PartInline(admin.TabularInline):
    model = Part
    extra = 1


class ReviewInline(admin.StackedInline):
    model = Review
    extra = 0


class LowStockFilter(admin.SimpleListFilter):
    title = "stock"
    parameter_name = "stock"

    def lookups(self, request, model_admin):
        return [("low", "Low"), ("out", "Out of stock")]

    def queryset(self, request, queryset):
        if self.value() == "low":
            return queryset.filter(quantity__lt=10, quantity__gt=0)
        if self.value() == "out":
            return queryset.filter(quantity=0)
        return queryset


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    icon = "folder"
    list_display = ["name", "slug", "item_count"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(num_items=Count("items"))

    @admin.display(description="Items", ordering="num_items")
    def item_count(self, obj):
        return obj.num_items


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    icon = "tag"
    search_fields = ["name"]


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    icon = "package"
    list_display = ["name", "category", "status", "price", "quantity", "is_featured", "released"]
    list_filter = ["status", "category", "is_featured", "released", LowStockFilter, "tags"]
    list_editable = ["quantity"]
    import_formats = ("csv", "xlsx", "json")
    list_badges = {"status": {"draft": "neutral", "active": "success", "archived": "warning"}}
    search_fields = ["name", "category__name"]
    prepopulated_fields = {"slug": ["name"]}
    readonly_fields = ["created"]
    fieldsets = [
        (None, {"fields": ["name", "slug", ("category", "status"), "tags"]}),
        ("Stock", {"fields": [("price", "quantity"), ("is_featured", "released")]}),
        ("Details", {"fields": ["website", "notes", "data", "created"], "classes": ["collapse"]}),
    ]
    inlines = [PartInline, ReviewInline]
    actions = ["mark_active"]
    save_on_top = False

    @admin.action(description="Mark selected items as active", icon="circle-check")
    def mark_active(self, request, queryset):
        count = queryset.update(status=Item.Status.ACTIVE)
        self.message_user(request, f"{count} items marked as active.")

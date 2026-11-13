from django_formwork import admin

from .models import Draft, Plain


@admin.register(Draft)
class DraftAdmin(admin.ModelAdmin):
    fields = ["title", "status", "owner"]


@admin.register(Plain)
class PlainAdmin(admin.ModelAdmin):
    pass

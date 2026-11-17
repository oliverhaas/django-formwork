"""FilterSet for the board: django-filter drives the queryset, formwork renders it."""

from __future__ import annotations

import django_filters as filters
from django.db.models import Q

from django_formwork.widgets import SearchInput, Select

from .models import Tag, Task


class TaskFilter(filters.FilterSet):
    q = filters.CharFilter(
        method="search",
        label="Search",
        widget=SearchInput(attrs={"placeholder": "Search tasks"}),
    )
    priority = filters.ChoiceFilter(
        choices=Task.Priority.choices,
        label="Priority",
        widget=Select(attrs={"placeholder": "Any priority"}),
    )
    tag = filters.ModelChoiceFilter(
        field_name="tags",
        queryset=Tag.objects.all(),
        label="Tag",
        widget=Select(attrs={"placeholder": "Any tag"}),
    )

    class Meta:
        model = Task
        fields = ["q", "priority", "tag"]

    def search(self, queryset, _name, value):
        return queryset.filter(Q(title__icontains=value) | Q(description__icontains=value)).distinct()

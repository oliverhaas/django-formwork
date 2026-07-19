"""FilterSet for the task list: django-filter drives the queryset, formwork renders it."""

from __future__ import annotations

import django_filters as filters
from django.db.models import Q

from django_formwork.widgets import SearchInput, Select

from .models import Task


class TaskFilter(filters.FilterSet):
    q = filters.CharFilter(
        method="search",
        label="",
        widget=SearchInput(attrs={"placeholder": "Search…"}),
    )
    status = filters.ChoiceFilter(
        choices=Task.Status.choices,
        empty_label="All",
        label="",
        widget=Select(floating_label=True, attrs={"class": "select w-full", "placeholder": "Status"}),
    )
    priority = filters.ChoiceFilter(
        choices=Task.Priority.choices,
        empty_label="All",
        label="",
        widget=Select(floating_label=True, attrs={"class": "select w-full", "placeholder": "Priority"}),
    )

    class Meta:
        model = Task
        fields = ["q", "status", "priority"]

    def search(self, queryset, _name, value):
        return queryset.filter(Q(title__icontains=value) | Q(tags__name__icontains=value)).distinct()

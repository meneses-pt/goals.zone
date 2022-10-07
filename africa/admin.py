from django import forms
from django.contrib import admin

from .models import AfricaMatchesFilter


class AfricaMatchesFilterAdminForm(forms.ModelForm):
    class Meta:
        model = AfricaMatchesFilter
        fields = [
            "include_tournaments",
            "include_categories",
            "exclude_tournaments",
            "exclude_categories",
        ]


class AfricaMatchesFilterAdmin(admin.ModelAdmin):
    filter_horizontal = [
        "include_tournaments",
        "include_categories",
        "exclude_tournaments",
        "exclude_categories",
    ]
    form = AfricaMatchesFilterAdminForm


admin.site.register(AfricaMatchesFilter, AfricaMatchesFilterAdmin)

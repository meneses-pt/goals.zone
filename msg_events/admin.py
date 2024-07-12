from django import forms
from django.contrib import admin

from .models import CustomMessage, Tweet, Webhook


class WebhookAdminForm(forms.ModelForm):
    class Meta:
        model = Webhook
        fields = [
            "title",
            "destination",
            "event_type",
            "source",
            "webhook_url",
            "message",
            "link_regex",
            "author_filter",
            "include_tournaments",
            "include_categories",
            "include_teams",
            "exclude_tournaments",
            "exclude_categories",
            "exclude_teams",
            "active",
        ]
        widgets = {
            "message": forms.Textarea(attrs={"cols": 80, "rows": 3}),
        }


class WebhookAdmin(admin.ModelAdmin):
    search_fields = ["title"]

    autocomplete_fields = [
        "include_tournaments",
        "include_categories",
        "include_teams",
        "exclude_tournaments",
        "exclude_categories",
        "exclude_teams",
    ]
    form = WebhookAdminForm


class CustomMessageAdminForm(forms.ModelForm):
    class Meta:
        model = CustomMessage
        fields = ["message", "webhooks", "tweets", "result"]
        widgets = {
            "message": forms.Textarea(attrs={"cols": 80, "rows": 3}),
            "result": forms.Textarea(attrs={"cols": 80, "rows": 3}),
        }


class CustomMessageAdmin(admin.ModelAdmin):
    autocomplete_fields = ["webhooks", "tweets"]
    form = CustomMessageAdminForm


class TweetAdminForm(forms.ModelForm):
    class Meta:
        model = Tweet
        fields = [
            "title",
            "event_type",
            "source",
            "consumer_key",
            "consumer_secret",
            "access_token_key",
            "access_token_secret",
            "message",
            "link_regex",
            "author_filter",
            "include_tournaments",
            "include_categories",
            "include_teams",
            "exclude_tournaments",
            "exclude_categories",
            "exclude_teams",
            "active",
        ]
        widgets = {
            "message": forms.Textarea(attrs={"cols": 80, "rows": 3}),
        }


class TweetAdmin(admin.ModelAdmin):
    search_fields = ["title"]

    autocomplete_fields = [
        "include_tournaments",
        "include_categories",
        "include_teams",
        "exclude_tournaments",
        "exclude_categories",
        "exclude_teams",
    ]
    form = TweetAdminForm


admin.site.register(Webhook, WebhookAdmin)
admin.site.register(CustomMessage, CustomMessageAdmin)
admin.site.register(Tweet, TweetAdmin)

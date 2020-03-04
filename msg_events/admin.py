from django import forms
from django.contrib import admin

from .models import Webhook, Tweet


class WebhookAdminForm(forms.ModelForm):
    class Meta:
        model = Webhook
        fields = ['title', 'webhook_url', 'message', 'destination']
        widgets = {
            'message': forms.Textarea(attrs={'cols': 80, 'rows': 3}),
        }


class WebhookAdmin(admin.ModelAdmin):
    form = WebhookAdminForm


class TweetAdminForm(forms.ModelForm):
    class Meta:
        model = Tweet
        fields = ['title', 'consumer_key', 'consumer_secret', 'access_token_key', 'access_token_secret', 'message']
        widgets = {
            'message': forms.Textarea(attrs={'cols': 80, 'rows': 3}),
        }


class TweetAdmin(admin.ModelAdmin):
    form = TweetAdminForm


admin.site.register(Webhook, WebhookAdmin)
admin.site.register(Tweet, TweetAdmin)

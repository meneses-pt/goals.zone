# Generated by Django 3.0.3 on 2020-03-08 17:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("msg_events", "0010_auto_20200306_1507"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tweet",
            name="author_filter",
            field=models.CharField(blank=True, default=None, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name="tweet",
            name="link_regex",
            field=models.CharField(blank=True, default=None, max_length=2000, null=True),
        ),
        migrations.AlterField(
            model_name="webhook",
            name="author_filter",
            field=models.CharField(blank=True, default=None, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name="webhook",
            name="link_regex",
            field=models.CharField(blank=True, default=None, max_length=2000, null=True),
        ),
    ]

# Generated by Django 4.2.4 on 2023-08-12 09:44

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("matches", "0057_rename_last_sent_tweet_match_last_tweet_time_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="TweetSent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("text", models.CharField(max_length=1024)),
                ("sent_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]

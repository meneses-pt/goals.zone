# Generated by Django 4.1.2 on 2022-10-06 13:25

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("matches", "0051_match_matches_mat_first_v_9623a2_idx"),
    ]

    operations = [
        migrations.CreateModel(
            name="MatchTweet",
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
                ("id_str", models.CharField(max_length=25, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "match",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="matches.match"),
                ),
            ],
        ),
    ]

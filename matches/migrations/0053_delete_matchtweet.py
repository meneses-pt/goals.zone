# Generated by Django 4.1.2 on 2022-10-07 14:09

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("matches", "0052_matchtweet"),
    ]

    operations = [
        migrations.DeleteModel(
            name="MatchTweet",
        ),
    ]
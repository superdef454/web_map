# Generated by Django 5.0.4 on 2024-05-13 06:15

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('PetriNET', '0007_alter_route_interval_alter_tc_description'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='city',
            name='region',
        ),
    ]

# Generated by Django 5.2.4 on 2025-07-25 13:23

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mohi', '0002_alter_customuser_managers'),
    ]

    operations = [
        migrations.AlterField(
            model_name='loan',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='loans', to=settings.AUTH_USER_MODEL),
        ),
    ]

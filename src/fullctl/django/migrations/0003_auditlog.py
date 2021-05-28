# Generated by Django 2.2.20 on 2021-05-28 12:01

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
        ('django_fullctl', '0002_delete_apikey'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now=True)),
                ('user_key', models.CharField(blank=True, max_length=8, null=True)),
                ('org_key', models.CharField(blank=True, max_length=8, null=True)),
                ('action', models.CharField(max_length=32)),
                ('info', models.CharField(help_text='Any extra information for the log entry', max_length=255)),
                ('data', models.TextField(default='{}', help_text='Any extra data for the log entry')),
                ('object_id', models.PositiveIntegerField()),
                ('object_type', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='contenttypes.ContentType')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]

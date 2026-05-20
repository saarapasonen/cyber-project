from django.contrib import admin

from .models import Profile, TimeEntry


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'owner', 'project', 'hours', 'date')
    list_filter = ('owner',)
    search_fields = ('project', 'description')


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'pin')

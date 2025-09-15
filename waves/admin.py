from django.contrib import admin
from .models import Wave

@admin.register(Wave)
class WaveAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_locked')
    search_fields = ('name',)


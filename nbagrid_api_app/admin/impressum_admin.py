from django.contrib import admin

from nbagrid_api_app.models import ImpressumContent

@admin.register(ImpressumContent)
class ImpressumContentAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'order', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at')
    list_editable = ('is_active', 'order')
    search_fields = ('title', 'content')
    ordering = ('order', 'created_at')
    fields = ('title', 'content', 'is_active', 'order')
    
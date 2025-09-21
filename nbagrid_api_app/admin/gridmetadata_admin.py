from django.contrib import admin
from django import forms

from nbagrid_api_app.models import GridMetadata


class GridMetadataAdminForm(forms.ModelForm):
    """Custom form for GridMetadata with proper date widget"""
    
    class Meta:
        model = GridMetadata
        fields = '__all__'
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'format': 'YYYY-MM-DD'}),
        }


@admin.register(GridMetadata)
class GridMetadataAdmin(admin.ModelAdmin):
    form = GridMetadataAdminForm
    list_display = ("formatted_date", "game_title")
    search_fields = ("date", "game_title")
    ordering = ("-date",)  # Most recent dates first

    def formatted_date(self, obj):
        """Format date as YYYY-MM-DD for consistent display"""
        return obj.date.strftime('%Y-%m-%d')
    formatted_date.short_description = 'Date'
    formatted_date.admin_order_field = 'date'

    def has_add_permission(self, request):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return True

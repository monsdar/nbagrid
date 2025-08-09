from django.contrib import admin

from nbagrid_api_app.models import GameFilterDB

@admin.register(GameFilterDB)
class GameFilterDBAdmin(admin.ModelAdmin):
    list_display = ("date", "filter_type", "filter_class", "filter_index")
    list_filter = ("date", "filter_type", "filter_class")
    search_fields = ("date", "filter_class")
    date_hierarchy = "date"

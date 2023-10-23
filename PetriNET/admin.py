from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import City, BusStop, Route, TC


@admin.register(Route)
class ClassAdmin(admin.ModelAdmin):
    fields = ['city', 'name', 'tc', 'interval', 'amount']
    list_display = ('name', 'city', 'tc')
    list_filter = ('city',)
    search_fields = ('name',)


@admin.register(BusStop)
class ClassAdmin(admin.ModelAdmin):
    fields = ['city', 'name']
    list_filter = ('city',)
    search_fields = ('name',)
    list_display = ('name', 'city')


admin.site.register(City)
admin.site.register(TC)
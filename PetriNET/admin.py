from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import City, BusStop, Route, TC


@admin.register(Route)
class ClassAdmin(admin.ModelAdmin):
    fields = ['city', 'name', 'tc', 'interval', 'amount']


@admin.register(BusStop)
class ClassAdmin(admin.ModelAdmin):
    fields = ['city', 'name']


admin.site.register(City)
admin.site.register(TC)
from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import City, BusStop, Route, TC, EI


@admin.register(Route)
class ClassAdmin(admin.ModelAdmin):
    # Отключение возможность создания маршрутов без остановок из админ-панели
    def has_add_permission(self, request, obj=None):
        return False
    fields = ['city', 'name', 'tc', 'interval', 'amount']
    list_display = ('name', 'city', 'tc')
    list_filter = ('city',)
    search_fields = ('name',)


@admin.register(BusStop)
class ClassAdmin(admin.ModelAdmin):
    list_filter = ('city',)
    search_fields = ('name',)
    list_display = ('name', 'city')


@admin.register(TC)
class ClassTC(admin.ModelAdmin):
    list_display = ('name', 'capacity')
    search_fields = ('name',)


admin.site.register(City)
# admin.site.register(EI)
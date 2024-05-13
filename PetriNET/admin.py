from django.contrib import admin
from django.core.management import call_command
from .models import City, BusStop, Route, TC


@admin.register(Route)
class ClassRouteAdmin(admin.ModelAdmin):
    # Отключение возможность создания маршрутов без остановок из админ-панели
    def has_add_permission(self, request, obj=None):
        return False
    fields = ['city', 'name', 'tc', 'interval', 'amount']
    list_display = ('name', 'city', 'tc')
    list_filter = ('city',)
    search_fields = ('name',)


@admin.register(BusStop)
class ClassBusStopAdmin(admin.ModelAdmin):
    list_filter = ('city',)
    search_fields = ('name',)
    list_display = ('name', 'city')
    save_on_top = True


@admin.register(TC)
class ClassTCAdmin(admin.ModelAdmin):
    list_display = ('name', 'capacity')
    search_fields = ('name',)


@admin.register(City)
class ClassCityAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    actions = ['update_bus_stops']
    save_on_top = True

    def update_bus_stops(self, request, queryset):
        for city in queryset:
            call_command('load_stations', city_id=city.id)
        self.message_user(request, "Bus stops updated successfully.")
    update_bus_stops.short_description = "Добавление данных остановочных пунктов"

# admin.site.register(EI)

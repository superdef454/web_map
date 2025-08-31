from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from django.core.management import call_command
from .models import City, BusStop, Route, TC, District


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


@admin.register(District)
class DistrictAdmin(GISModelAdmin):
    """Админ-панель для районов с геополем"""
    list_display = ('name', 'city')
    list_filter = ('city',)
    search_fields = ('name', 'city__name')
    ordering = ('city__name', 'name')
    
    # Настройки для карты
    default_zoom = 12
    map_width = 800
    map_height = 600
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('city', 'name', 'description')
        }),
        ('Географические данные', {
            'fields': ('polygon',)
        }),
    )


class DistrictInline(admin.TabularInline):
    """Инлайн для отображения районов на странице города"""
    model = District
    extra = 0
    fields = ('name', 'description')
    readonly_fields = ()


@admin.register(City)
class ClassCityAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    list_display = ('name', 'districts_count')
    actions = ['update_bus_stops']
    ordering = ('name',)
    inlines = [DistrictInline]

    def districts_count(self, obj):
        """Подсчет количества районов в городе"""
        return obj.districts.count()
    districts_count.short_description = 'Количество районов'

    def update_bus_stops(self, request, queryset):
        for city in queryset:
            call_command('load_stations', city_id=city.id)
        self.message_user(request, "Остановочные пункты успешно добавлены.")
    update_bus_stops.short_description = "Добавление данных остановочных пунктов"

# admin.site.register(EI)

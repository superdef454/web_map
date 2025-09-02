import logging
import os

from django.contrib import admin, messages
from django.contrib.admin import StackedInline
from django.contrib.gis.admin import GISModelAdmin
from django.contrib.gis.db import models as gis_models
from django.contrib.gis.forms.widgets import OSMWidget
from django.core.management import call_command
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import path
from django.utils.html import format_html

from .models import TC, BusStop, City, District, Route, Simulation
from .petri_net_utils import CreateResponseFile


class GISStackedInline(StackedInline):
    """StackedInline с поддержкой геоданных"""
    formfield_overrides = {
        gis_models.PolygonField: {'widget': OSMWidget},
    }


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
    raw_id_fields = ('city',)
    
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


class DistrictInline(GISStackedInline):
    """Инлайн для отображения районов на странице города"""
    model = District
    extra = 0
    fields = ('name', 'description', 'polygon')
    readonly_fields = ()


@admin.register(City)
class ClassCityAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    list_display = ('name', 'districts_count')
    actions = ['update_bus_stops', 'update_routes']
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

    def update_routes(self, request, queryset):
        for city in queryset:
            call_command('get_city_routes', city_id=city.id)
        self.message_user(request, "Маршруты успешно обновлены.")
    update_routes.short_description = "Обновление данных маршрутов"


@admin.register(Simulation)
class SimulationAdmin(admin.ModelAdmin):
    """Админ-панель для симуляций с возможностью генерации и скачивания отчётов"""
    
    list_display = ('id', 'created_at', 'download_report_action')
    list_filter = ('created_at',)
    search_fields = ('description',)
    readonly_fields = ('id', 'created_at', 'download_report_action')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('id', 'created_at', 'description')
        }),
        ('Данные расчёта', {
            'fields': ('input_data', 'report_data'),
            'classes': ('collapse',)
        }),
        ('Действия', {
            'fields': ('download_report_action',),
        }),
    )
    
    def has_add_permission(self, request, obj=None):
        """Запрещаем ручное создание симуляций через админку"""
        return False
    
    def download_report_action(self, obj):
        """Кнопка для генерации и скачивания отчёта"""
        if obj.pk:
            return format_html(
                '<a href="/admin/PetriNET/simulation/{}/download-report/" '
                'class="button" target="_blank">Скачать отчёт</a>',
                obj.pk
            )
        return "Сохраните объект для генерации отчёта"
    download_report_action.short_description = 'Отчёт'
    
    def get_urls(self):
        """Добавляем кастомный URL для скачивания отчёта"""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:simulation_id>/download-report/',
                self.admin_site.admin_view(self.download_report_view),
                name='petri_simulation_download_report',
            ),
        ]
        return custom_urls + urls
    
    def download_report_view(self, request, simulation_id):
        """Представление для генерации и скачивания отчёта"""
        try:
            simulation = Simulation.objects.get(pk=simulation_id)
            
            # Генерируем отчёт
            logger = logging.getLogger('PetriNetAPI')
            logger.info(f"Генерация отчёта для симуляции {simulation_id}")
            
            file_path = CreateResponseFile(simulation.report_data)
            
            # Читаем файл и отдаём для скачивания
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    response = HttpResponse(
                        f.read(), 
                        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                    )
                    response['Content-Disposition'] = f'attachment; filename="simulation_report_{simulation_id}.docx"'
                    
                # Удаляем временный файл после отправки
                try:
                    os.remove(file_path)
                except OSError:
                    logger.warning(f"Не удалось удалить временный файл: {file_path}")
                    
                return response
            else:
                messages.error(request, "Ошибка: файл отчёта не был создан")
                
        except Simulation.DoesNotExist:
            messages.error(request, "Симуляция не найдена")
        except Exception as e:
            logger.exception(f"Ошибка при генерации отчёта для симуляции {simulation_id}")
            messages.error(request, f"Ошибка при генерации отчёта: {str(e)}")
        
        return redirect('admin:PetriNET_simulation_change', simulation_id)


# admin.site.register(EI)

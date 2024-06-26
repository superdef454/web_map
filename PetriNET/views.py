import json
import logging
from typing import Any
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

from PetriNET.petri_net_utils import CreateResponseFile, GetDataToCalculate, PetriNet
from PetriNET.utils import auth_required

from .models import City, BusStop, Route


logger = logging.getLogger('PetriNetAPI')


class MainMap(LoginRequiredMixin, TemplateView):
    template_name = "PetriNET/leaflet/index.html"

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['citys'] = list(City.objects.values('name', 'latitude', 'longitude', 'id').order_by('name'))
        return context


# Добавить миксин проверки логина

class CityView(View):
    """Класс работы с городами"""

    @method_decorator(auth_required())
    def get(self, request):
        """Получение данных города"""
        city_id = request.GET.get('city_id')
        if not city_id:
            return JsonResponse({
                'error': 1,
                'error_message': 'Ошибка заполнения данных'
            })
        response = {'error': 0}
        BSList = list(BusStop.objects.filter(city_id=city_id).values('name', 'latitude', 'longitude', 'id'))
        Routes = Route.objects.filter(city_id=city_id).prefetch_related('busstop')
        RouteList = []
        for route in Routes:
            if len(route.list_coord) != route.busstop.all().count():
                route.delete()
                continue
            RouteList.append(
                {
                    'name': route.name,
                    'list_coord': route.list_coord,
                    'id': route.id
                }
            )
        RouteList.sort(key=lambda route: len(route['list_coord']), reverse=True)
        response.update(
            {
                'BSList': BSList,
                'RouteList': RouteList
            }
        )
        return JsonResponse(response)


class BusStopView(View):
    """Класс работы с остановками"""

    @method_decorator(auth_required())
    def post(self, request):
        """Добавление остановки"""
        lat = request.POST.get('lat')
        lng = request.POST.get('lng')
        name = request.POST.get('name')
        city_id = request.POST.get('city_id')
        if not lat or not lng or not name or not city_id:
            return JsonResponse({
                'error': 1,
                'error_message': 'Ошибка заполнения данных'
            })
        add = BusStop.objects.create(
            city=City.objects.get(id=city_id),
            name=name,
            latitude=lat,
            longitude=lng
        )
        return JsonResponse({'error': 0, 'BusStop': {'id': add.id}})

    def get(self, request):
        """Добавление остановки"""
        id = request.GET.get('id')
        if not id:
            return JsonResponse({
                'error': 1,
                'error_message': 'Ошибка заполнения данных'
            })
        bus_stop = BusStop.objects.get(
            id=id,
        )
        return JsonResponse({'error': 0, 'BusStop': {
            'id': bus_stop.id,
            'lat': bus_stop.latitude,
            'lng': bus_stop.longitude,
            }})


class RouteView(View):
    """Класс работы с маршрутами"""

    @method_decorator(auth_required())
    def post(self, request):
        """Добавление маршрута"""
        list_coord = json.loads(request.POST.get('list_coord'))
        name = request.POST.get('name')
        city_id = request.POST.get('city_id')
        if not list_coord or not name or not city_id:
            return JsonResponse({
                'error': 1,
                'error_message': 'Ошибка заполнения данных'
            })
        try:
            list_bs = [BusStop.objects.get(latitude=bs[0], longitude=bs[1]) for bs in list_coord]
        except Exception:
            return JsonResponse({
                'error': 1,
                'error_message': 'Ошибка заполнения данных'
            })
        add = Route.objects.create(
            city=City.objects.get(id=city_id),
            name=name,
        )
        add.busstop.add(*list_bs)
        add.list_coord = list_coord
        add.save()
        return JsonResponse({'error': 0, 'Route': {
            'name': add.name,
            'list_coord': add.list_coord,
            'id': add.id
            }})


class Calculate(View):
    """Класс расчёта нагрузки"""

    @method_decorator(auth_required())
    def post(self, request):
        response = {'error': 0}
        try:
            request_data_to_calculate = json.loads(request.POST.get('DataToCalculate'))
            logger.info(f"Данные для разбора: {request_data_to_calculate}")
            DataToCalculate = GetDataToCalculate(request_data_to_calculate)
        except Exception:
            logger.exception("Ошибка получения данных для рассчёта")
            response.update(
                {
                    'error': 1,
                    'error_message': 'Ошибка заполнения данных'
                }
            )
            return JsonResponse(response)
        else:
            logger.info(f"Данные для расчёта: {DataToCalculate}")

        try:
            petri_net = PetriNet(DataToCalculate)
            calculate = petri_net.Calculation()
            data_to_report = petri_net.CreateDataToReport()
        except Exception:
            logger.exception("Ошибка расчёта нагрузки")
            response.update(
                {
                    'error': 2,
                    'error_message': 'Ошибка расчёта нагрузки'
                }
            )
            return JsonResponse(response)

        response.update({
            'calculate': calculate,
            'data_to_report': data_to_report,
        })

        return JsonResponse(response)


def download_report_file(request):
    data_to_report = json.loads(request.POST.get('data_to_report'))
    file_path = ""
    try:
        file_path = CreateResponseFile(data_to_report)
    except Exception:
        logger.exception('Ошибка формирования файла отчёта')
    # Возвращаем URL для скачивания файла
    file_path = file_path
    return JsonResponse({'file_path': file_path})

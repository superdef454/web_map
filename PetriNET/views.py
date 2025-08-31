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

from .models import City, TC, BusStop, Route, EI, District
from django.db.models import Count, Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from TransportMap.utils import (
    ValidatedDjangoFilterBackend,
    ValidatedSearchFilter,
    ValidatedOrderingFilter,
    ValidatedPageNumberPagination
)

from .serializers import (
    CitySerializer,
    TCSerializer, 
    BusStopSerializer,
    BusStopGeoSerializer,
    RouteSerializer,
    RouteDetailSerializer,
    RouteCreateUpdateSerializer,
    EISerializer,
    DistrictSerializer,
    DistrictGeoSerializer
)


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


@extend_schema_view(
    list=extend_schema(
        summary="Получить список городов",
        description="Возвращает список всех городов с возможностью фильтрации и поиска",
        tags=['Города']
    ),
    retrieve=extend_schema(
        summary="Получить информацию о городе",
        description="Возвращает детальную информацию о конкретном городе",
        tags=['Города']
    ),
    create=extend_schema(
        summary="Создать новый город",
        description="Создает новый город с указанными параметрами",
        tags=['Города']
    ),
    update=extend_schema(
        summary="Обновить информацию о городе",
        description="Полностью обновляет информацию о городе",
        tags=['Города']
    ),
    partial_update=extend_schema(
        summary="Частично обновить информацию о городе",
        description="Частично обновляет информацию о городе",
        tags=['Города']
    ),
    destroy=extend_schema(
        summary="Удалить город",
        description="Удаляет город из системы",
        tags=['Города']
    )
)
class CityViewSet(viewsets.ModelViewSet):
    """
    ViewSet для работы с городами.
    
    Предоставляет CRUD операции для модели City.
    Поддерживает фильтрацию по названию и координатам.
    """
    queryset = City.objects.all().order_by('name')
    serializer_class = CitySerializer
    permission_classes = [IsAuthenticated]
    
    filter_backends = [
        ValidatedDjangoFilterBackend,
        ValidatedSearchFilter,
        ValidatedOrderingFilter,
    ]
    
    filterset_fields = {
        'name': ['exact', 'icontains'],
        'latitude': ['exact', 'gte', 'lte'],
        'longitude': ['exact', 'gte', 'lte'],
    }
    
    search_fields = ['name']
    ordering_fields = ['name', 'latitude', 'longitude', 'id']
    ordering = ['name']
    
    pagination_class = ValidatedPageNumberPagination


@extend_schema_view(
    list=extend_schema(
        summary="Получить список типов транспорта",
        description="Возвращает список всех типов транспортных средств",
        tags=['Типы транспорта']
    ),
    retrieve=extend_schema(
        summary="Получить информацию о типе транспорта",
        description="Возвращает детальную информацию о конкретном типе транспорта",
        tags=['Типы транспорта']
    ),
    create=extend_schema(
        summary="Создать новый тип транспорта",
        description="Создает новый тип транспортного средства",
        tags=['Типы транспорта']
    ),
    update=extend_schema(
        summary="Обновить информацию о типе транспорта",
        description="Полностью обновляет информацию о типе транспорта",
        tags=['Типы транспорта']
    ),
    partial_update=extend_schema(
        summary="Частично обновить информацию о типе транспорта",
        description="Частично обновляет информацию о типе транспорта",
        tags=['Типы транспорта']
    ),
    destroy=extend_schema(
        summary="Удалить тип транспорта",
        description="Удаляет тип транспорта из системы",
        tags=['Типы транспорта']
    )
)
class TCViewSet(viewsets.ModelViewSet):
    """
    ViewSet для работы с типами транспортных средств.
    
    Предоставляет CRUD операции для модели TC.
    Поддерживает фильтрацию по названию и вместимости.
    """
    queryset = TC.objects.all().order_by('name')
    serializer_class = TCSerializer
    permission_classes = [IsAuthenticated]
    
    filter_backends = [
        ValidatedDjangoFilterBackend,
        ValidatedSearchFilter,
        ValidatedOrderingFilter,
    ]
    
    filterset_fields = {
        'name': ['exact', 'icontains'],
        'capacity': ['exact', 'gte', 'lte'],
    }
    
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'capacity', 'id']
    ordering = ['name']
    
    pagination_class = ValidatedPageNumberPagination


@extend_schema_view(
    list=extend_schema(
        summary="Получить список остановок",
        description="Возвращает список всех остановок с возможностью фильтрации",
        tags=['Остановки']
    ),
    retrieve=extend_schema(
        summary="Получить информацию об остановке",
        description="Возвращает детальную информацию о конкретной остановке",
        tags=['Остановки']
    ),
    create=extend_schema(
        summary="Создать новую остановку",
        description="Создает новую остановку с указанными координатами",
        tags=['Остановки']
    ),
    update=extend_schema(
        summary="Обновить информацию об остановке",
        description="Полностью обновляет информацию об остановке",
        tags=['Остановки']
    ),
    partial_update=extend_schema(
        summary="Частично обновить информацию об остановке",
        description="Частично обновляет информацию об остановке",
        tags=['Остановки']
    ),
    destroy=extend_schema(
        summary="Удалить остановку",
        description="Удаляет остановку из системы",
        tags=['Остановки']
    )
)
class BusStopViewSet(viewsets.ModelViewSet):
    """
    ViewSet для работы с остановками.
    
    Предоставляет CRUD операции для модели BusStop.
    Поддерживает фильтрацию по городу, названию и координатам.
    """
    queryset = BusStop.objects.select_related('city').prefetch_related('route_set').order_by('name')
    serializer_class = BusStopSerializer
    permission_classes = [IsAuthenticated]
    
    filter_backends = [
        ValidatedDjangoFilterBackend,
        ValidatedSearchFilter,
        ValidatedOrderingFilter,
    ]
    
    filterset_fields = {
        'city': ['exact'],
        'city__name': ['exact', 'icontains'],
        'name': ['exact', 'icontains'],
        'latitude': ['exact', 'gte', 'lte'],
        'longitude': ['exact', 'gte', 'lte'],
    }
    
    search_fields = ['name', 'city__name']
    ordering_fields = ['name', 'latitude', 'longitude', 'city__name', 'id']
    ordering = ['name']
    
    pagination_class = ValidatedPageNumberPagination

    @extend_schema(
        summary="Получить остановки в формате GeoJSON",
        description="Возвращает остановки в формате GeoJSON для отображения на карте",
        parameters=[
            OpenApiParameter(
                name='city',
                description='ID города для фильтрации',
                required=False,
                type=OpenApiTypes.INT
            ),
        ],
        tags=['Остановки']
    )
    @action(detail=False, methods=['get'])
    def geojson(self, request):
        """Получить остановки в формате GeoJSON"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = BusStopGeoSerializer(queryset, many=True)
        
        geojson_data = {
            'type': 'FeatureCollection',
            'features': serializer.data
        }
        
        return Response(geojson_data)

    @extend_schema(
        summary="Получить маршруты остановки",
        description="Возвращает список маршрутов, проходящих через данную остановку",
        tags=['Остановки']
    )
    @action(detail=True, methods=['get'])
    def routes(self, request, pk=None):
        """Получить маршруты, проходящие через остановку"""
        busstop = self.get_object()
        routes = busstop.route_set.all()
        serializer = RouteSerializer(routes, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="Получить список маршрутов",
        description="Возвращает список всех маршрутов с возможностью фильтрации",
        tags=['Маршруты']
    ),
    retrieve=extend_schema(
        summary="Получить информацию о маршруте",
        description="Возвращает детальную информацию о конкретном маршруте",
        tags=['Маршруты']
    ),
    create=extend_schema(
        summary="Создать новый маршрут",
        description="Создает новый маршрут с указанными остановками",
        tags=['Маршруты']
    ),
    update=extend_schema(
        summary="Обновить информацию о маршруте",
        description="Полностью обновляет информацию о маршруте",
        tags=['Маршруты']
    ),
    partial_update=extend_schema(
        summary="Частично обновить информацию о маршруте",
        description="Частично обновляет информацию о маршруте",
        tags=['Маршруты']
    ),
    destroy=extend_schema(
        summary="Удалить маршрут",
        description="Удаляет маршрут из системы",
        tags=['Маршруты']
    )
)
class RouteViewSet(viewsets.ModelViewSet):
    """
    ViewSet для работы с маршрутами.
    
    Предоставляет CRUD операции для модели Route.
    Поддерживает фильтрацию по городу, типу транспорта и другим параметрам.
    """
    queryset = Route.objects.select_related('city', 'tc').prefetch_related('busstop').order_by('name')
    permission_classes = [IsAuthenticated]
    
    filter_backends = [
        ValidatedDjangoFilterBackend,
        ValidatedSearchFilter,
        ValidatedOrderingFilter,
    ]
    
    filterset_fields = {
        'city': ['exact'],
        'city__name': ['exact', 'icontains'],
        'tc': ['exact'],
        'tc__name': ['exact', 'icontains'],
        'name': ['exact', 'icontains'],
        'interval': ['exact', 'gte', 'lte'],
        'amount': ['exact', 'gte', 'lte'],
    }
    
    search_fields = ['name', 'city__name', 'tc__name']
    ordering_fields = ['name', 'interval', 'amount', 'city__name', 'tc__name', 'id']
    ordering = ['name']
    
    pagination_class = ValidatedPageNumberPagination

    def get_serializer_class(self):
        """Возвращает соответствующий сериализатор в зависимости от действия"""
        if self.action == 'retrieve':
            return RouteDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return RouteCreateUpdateSerializer
        return RouteSerializer

    @extend_schema(
        summary="Получить остановки маршрута",
        description="Возвращает список остановок для данного маршрута в правильном порядке",
        tags=['Маршруты']
    )
    @action(detail=True, methods=['get'])
    def busstops(self, request, pk=None):
        """Получить остановки маршрута"""
        route = self.get_object()
        busstops = route.busstop.all()
        serializer = BusStopSerializer(busstops, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="Получить список единиц измерения",
        description="Возвращает список всех единиц измерения",
        tags=['Единицы измерения']
    ),
    retrieve=extend_schema(
        summary="Получить информацию о единице измерения",
        description="Возвращает детальную информацию о конкретной единице измерения",
        tags=['Единицы измерения']
    ),
    create=extend_schema(
        summary="Создать новую единицу измерения",
        description="Создает новую единицу измерения",
        tags=['Единицы измерения']
    ),
    update=extend_schema(
        summary="Обновить информацию о единице измерения",
        description="Полностью обновляет информацию о единице измерения",
        tags=['Единицы измерения']
    ),
    partial_update=extend_schema(
        summary="Частично обновить информацию о единице измерения",
        description="Частично обновляет информацию о единице измерения",
        tags=['Единицы измерения']
    ),
    destroy=extend_schema(
        summary="Удалить единицу измерения",
        description="Удаляет единицу измерения из системы",
        tags=['Единицы измерения']
    )
)
class EIViewSet(viewsets.ModelViewSet):
    """
    ViewSet для работы с единицами измерения.
    
    Предоставляет CRUD операции для модели EI.
    Поддерживает фильтрацию и поиск по названию.
    """
    queryset = EI.objects.all().order_by('name')
    serializer_class = EISerializer
    permission_classes = [IsAuthenticated]
    
    filter_backends = [
        ValidatedDjangoFilterBackend,
        ValidatedSearchFilter,
        ValidatedOrderingFilter,
    ]
    
    filterset_fields = {
        'name': ['exact', 'icontains'],
        'short_name': ['exact', 'icontains'],
    }
    
    search_fields = ['name', 'short_name']
    ordering_fields = ['name', 'short_name', 'id']
    ordering = ['name']
    
    pagination_class = ValidatedPageNumberPagination


@extend_schema_view(
    list=extend_schema(
        summary="Получить список районов",
        description="Возвращает список всех районов с возможностью фильтрации и поиска",
        tags=['Районы']
    ),
    retrieve=extend_schema(
        summary="Получить информацию о районе",
        description="Возвращает подробную информацию о конкретном районе",
        tags=['Районы']
    ),
    create=extend_schema(
        summary="Создать новый район",
        description="Создает новый район в системе",
        tags=['Районы']
    ),
    update=extend_schema(
        summary="Обновить информацию о районе",
        description="Полностью обновляет информацию о районе",
        tags=['Районы']
    ),
    partial_update=extend_schema(
        summary="Частично обновить информацию о районе",
        description="Частично обновляет информацию о районе",
        tags=['Районы']
    ),
    destroy=extend_schema(
        summary="Удалить район",
        description="Удаляет район из системы",
        tags=['Районы']
    )
)
class DistrictViewSet(viewsets.ModelViewSet):
    """
    ViewSet для работы с районами города.
    
    Предоставляет CRUD операции для модели District.
    Поддерживает фильтрацию по городу, поиск по названию и геопространственные запросы.
    """
    queryset = District.objects.select_related('city').order_by('city__name', 'name')
    serializer_class = DistrictSerializer
    permission_classes = [IsAuthenticated]
    
    filter_backends = [
        ValidatedDjangoFilterBackend,
        ValidatedSearchFilter,
        ValidatedOrderingFilter,
    ]
    
    filterset_fields = {
        'city': ['exact'],
        'city__name': ['exact', 'icontains'],
        'name': ['exact', 'icontains'],
    }
    
    search_fields = ['name', 'city__name', 'description']
    ordering_fields = ['name', 'city__name', 'id']
    ordering = ['city__name', 'name']
    
    pagination_class = ValidatedPageNumberPagination
    
    def get_serializer_class(self):
        """Выбор сериализатора в зависимости от действия"""
        if self.action == 'geo_list':
            return DistrictGeoSerializer
        return self.serializer_class
    
    @extend_schema(
        summary="Получить районы в формате GeoJSON",
        description="Возвращает районы в формате GeoJSON для отображения на карте",
        responses={200: DistrictGeoSerializer(many=True)},
        tags=['Районы']
    )
    @action(detail=False, methods=['get'], url_path='geo')
    def geo_list(self, request):
        """Возвращает районы в формате GeoJSON"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = DistrictGeoSerializer(queryset, many=True)
        return Response(serializer.data)

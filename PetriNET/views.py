import json
import logging
import os
from typing import Any
from urllib.parse import quote

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from PetriNET.petri_net_utils import CreateResponseFile, GetDataToCalculate, PetriNet
from PetriNET.utils import auth_required
from TransportMap.utils import (
    ValidatedDjangoFilterBackend,
    ValidatedOrderingFilter,
    ValidatedPageNumberPagination,
    ValidatedSearchFilter,
)

from .models import EI, TC, BusStop, City, District, Route, Simulation
from .serializers import (
    BusStopGeoSerializer,
    BusStopSerializer,
    CalculationRequestSerializer,
    CalculationResponseSerializer,
    CitySerializer,
    DistrictGeoSerializer,
    DistrictSerializer,
    EISerializer,
    RouteCreateUpdateSerializer,
    RouteDetailSerializer,
    RouteSerializer,
    SimulationSerializer,
    TCSerializer,
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
        
        # Получаем данные о районах
        Districts = District.objects.filter(city_id=city_id)
        DistrictList = []
        for district in Districts:
            # Преобразуем полигон в GeoJSON формат
            district_geojson = {
                'id': district.id,
                'name': district.name,
                'description': district.description,
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [[[coord[0], coord[1]] for coord in district.polygon.coords[0]]]
                }
            }
            DistrictList.append(district_geojson)
        
        Routes = Route.objects.filter(city_id=city_id).prefetch_related('busstop')
        RouteList = [
            {
                "name": route.name,
                "list_coord": route.list_coord,
                "list_coord_to_render": route.list_coord_to_render,
                "id": route.pk,
            }
            for route in Routes
        ]
        RouteList.sort(key=lambda route: len(route['list_coord']), reverse=True)
        response.update(
            {
                'BSList': BSList,
                'RouteList': RouteList,
                'DistrictList': DistrictList
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
        add.list_coord_to_render = list_coord
        add.save()
        return JsonResponse({'error': 0, 'Route': {
            'name': add.name,
            'list_coord': add.list_coord,
            'list_coord_to_render': add.list_coord_to_render,
            'id': add.id
            }})



def download_report_file(request):    
    data_to_report = json.loads(request.POST.get('data_to_report'))
    file_path = ""
    try:
        file_path = CreateResponseFile(data_to_report)
        
        # Проверяем существование файла
        if not os.path.exists(file_path):
            return JsonResponse({'error': 'Файл не найден'}, status=404)
        
        # Получаем имя файла из пути
        filename = os.path.basename(file_path)
        # Кодируем имя файла для корректной передачи кириллицы (RFC 5987)
        encoded_filename = quote(filename)
        
        # Читаем файл и отдаём через HttpResponse для полного контроля над заголовками
        from django.http import HttpResponse
        with open(file_path, 'rb') as f:
            response = HttpResponse(
                f.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        
        # ASCII fallback имя файла (без кириллицы)
        ascii_filename = f"report_{data_to_report.get('data', 'unknown')}.xlsx"
        
        # Устанавливаем заголовки напрямую через headers (Django 3.2+)
        response.headers['Content-Disposition'] = f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}"
        response.headers['Access-Control-Expose-Headers'] = 'Content-Disposition'
        
        return response
        
    except Exception:
        logger.exception('Ошибка формирования файла отчёта')
        return JsonResponse({'error': 'Ошибка при создании отчета'}, status=500)


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


@extend_schema_view(
    calculate=extend_schema(
        summary="Расчёт нагрузки транспортной сети",
        description="Выполняет расчёт нагрузки транспортной сети на основе переданных данных о маршрутах, "
                   "остановках и параметрах транспортных средств. Возвращает результаты расчёта и данные для отчёта.",
        request=CalculationRequestSerializer,
        responses={
            200: CalculationResponseSerializer,
            400: 'Ошибка в данных для расчёта',
            500: 'Ошибка при выполнении расчёта'
        },
        tags=['Расчёты']
    )
)
class CalculationViewSet(viewsets.GenericViewSet):
    """
    ViewSet для выполнения расчётов нагрузки транспортной сети.
    
    Предоставляет endpoint для расчёта нагрузки на основе данных о маршрутах,
    остановках и параметрах транспортных средств.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CalculationRequestSerializer
    
    @extend_schema(
        summary="Выполнить расчёт нагрузки",
        description="Принимает данные для расчёта нагрузки транспортной сети и возвращает результаты расчёта",
        request=CalculationRequestSerializer,
        responses={200: CalculationResponseSerializer}
    )
    @action(detail=False, methods=['post'])
    def calculate(self, request):
        """Выполнение расчёта нагрузки транспортной сети"""
        # Этап 1: Валидация входных данных
        logger.info("Начало расчёта нагрузки транспортной сети")
        logger.debug(f"Пользователь: {request.user.username}, IP: {request.META.get('REMOTE_ADDR')}")
        
        serializer = CalculationRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            logger.warning(
                f"Ошибка валидации входных данных: {serializer.errors}",
                extra={
                    'user': request.user.username,
                    'errors': serializer.errors
                }
            )
            return Response({
                'error': 1,
                'error_message': 'Ошибка валидации входных данных. Проверьте корректность отправленных данных.',
                'details': serializer.errors,
                'stage': 'validation'
            }, status=400)
        
        logger.info("Валидация входных данных успешно пройдена")
        
        # Этап 2: Получение и обработка данных из базы данных
        try:
            processed_data = serializer.validated_data['data_to_calculate']
            city_id = processed_data.get('city_id')
            routes_count = len(processed_data.get('routes', []))
            busstops_count = len(processed_data.get('busstops', {}))
            
            logger.info(
                f"Обработка данных: город ID={city_id}, маршрутов={routes_count}, остановок={busstops_count}"
            )
            
            data_to_calculate = GetDataToCalculate(processed_data)
            
            logger.info(
                f"Данные успешно получены из БД: "
                f"маршрутов={len(data_to_calculate.get('routes', []))}, "
                f"остановок={len(data_to_calculate.get('busstops', []))}, "
                f"направлений={len(data_to_calculate.get('busstops_directions', []))}"
            )
            
        except ValueError as e:
            logger.exception(
                "Ошибка в структуре данных при получении данных для расчёта",
                extra={'user': request.user.username, 'city_id': city_id}
            )
            return Response({
                'error': 1,
                'error_message': 'Ошибка в структуре данных для расчёта',
                'details': str(e),
                'stage': 'data_preparation',
                'hint': 'Проверьте корректность указанных ID маршрутов и остановок'
            }, status=400)
            
        except KeyError as e:
            logger.exception(
                "Отсутствует обязательное поле в данных",
                extra={'user': request.user.username}
            )
            return Response({
                'error': 1,
                'error_message': f'Отсутствует обязательное поле: {str(e)}',
                'details': f'Не найдено поле {str(e)} в данных для расчёта',
                'stage': 'data_preparation'
            }, status=400)
            
        except Exception as e:
            error_message = str(e)
            logger.exception(
                "Непредвиденная ошибка при подготовке данных для расчёта",
                extra={'user': request.user.username, 'city_id': city_id}
            )
            
            # Определяем специфичные ошибки для пользователя
            user_message = error_message
            hint = None
            
            if 'Отсутствуют маршруты' in error_message:
                hint = 'Убедитесь, что выбранные маршруты существуют в базе данных для указанного города'
            elif 'Отсутствуют остановки' in error_message:
                hint = 'Добавьте хотя бы одну остановку с пассажирами для начала расчёта'
            elif 'Отсутствуют пассажиры' in error_message:
                hint = 'Укажите направления движения и количество пассажиров на остановках'
                
            return Response({
                'error': 1,
                'error_message': f'Ошибка подготовки данных: {user_message}',
                'details': error_message,
                'stage': 'data_preparation',
                'hint': hint
            }, status=400)

        # Этап 3: Инициализация сети Петри и выполнение расчёта
        try:
            logger.info("Инициализация сети Петри")
            petri_net = PetriNet(data_to_calculate)
            
            logger.info("Запуск расчёта нагрузки")
            calculate_result = petri_net.Calculation()
            
            logger.info(
                f"Расчёт успешно завершён, временных точек: {len(calculate_result) if calculate_result else 0}"
            )
            
        except ValueError as e:
            logger.exception(
                "Ошибка валидации данных при инициализации сети Петри",
                extra={'user': request.user.username}
            )
            return Response({
                'error': 2,
                'error_message': 'Ошибка в данных маршрутов или остановок',
                'details': str(e),
                'stage': 'petri_net_initialization',
                'hint': 'Проверьте корректность координат остановок и структуры маршрутов'
            }, status=400)
            
        except AttributeError as e:
            logger.exception(
                "Ошибка доступа к атрибутам объектов при расчёте",
                extra={'user': request.user.username}
            )
            return Response({
                'error': 2,
                'error_message': 'Ошибка в структуре данных маршрутов',
                'details': str(e),
                'stage': 'calculation',
                'hint': 'Убедитесь, что для всех маршрутов указаны типы транспорта и количество автобусов'
            }, status=400)
            
        except ZeroDivisionError:
            logger.exception(
                "Ошибка деления на ноль при расчёте (вероятно, отсутствуют данные)",
                extra={'user': request.user.username}
            )
            return Response({
                'error': 2,
                'error_message': 'Недостаточно данных для расчёта',
                'details': 'Отсутствуют данные для вычисления средних показателей',
                'stage': 'calculation',
                'hint': 'Убедитесь, что на маршрутах есть автобусы и пассажиры'
            }, status=400)
            
        except Exception as e:
            error_message = str(e)
            logger.exception(
                f"Критическая ошибка при выполнении расчёта: {error_message}",
                extra={'user': request.user.username}
            )
            
            # Определяем специфичные ошибки
            user_message = error_message
            hint = None
            
            if 'Отсутствуют автобусы на маршрутах' in error_message:
                hint = 'Укажите количество автобусов и тип транспорта для каждого маршрута'
            elif 'Не удалось найти остановку для точки маршрута' in error_message:
                hint = 'Возможно, координаты остановок на маршруте не совпадают с координатами в базе данных'
            elif 'Неправильное получение длительности пути пассажира' in error_message:
                hint = 'Проверьте, что конечная остановка пассажира находится после начальной на маршруте'
                
            return Response({
                'error': 2,
                'error_message': f'Ошибка при выполнении расчёта: {user_message}',
                'details': error_message,
                'stage': 'calculation',
                'hint': hint
            }, status=500)
        
        # Этап 4: Формирование данных для отчёта
        try:
            logger.info("Формирование данных для отчёта")
            data_to_report = petri_net.CreateDataToReport()
            
            logger.info(
                f"Данные для отчёта сформированы: "
                f"остановок={len(data_to_report.get('bus_stops', []))}, "
                f"маршрутов={len(data_to_report.get('routes', []))}"
            )
            
        except Exception:
            logger.exception(
                "Ошибка при формировании данных для отчёта",
                extra={'user': request.user.username}
            )
            return Response({
                'error': 2,
                'error_message': 'Ошибка при формировании данных для отчёта',
                'stage': 'report_generation',
                'hint': 'Расчёт выполнен, но не удалось сформировать отчёт'
            }, status=500)
        
        # Формирование успешного ответа
        response = {'error': 0}
        
        if serializer.validated_data.get('get_timeline'):
            response['calculate'] = calculate_result
            logger.debug(f"Включены данные временной шкалы ({len(calculate_result)} точек)")

        response.update({
            'data_to_report': data_to_report,
        })

        # Этап 5: Сохранение симуляции в базу данных
        try:
            logger.info("Сохранение результатов симуляции в БД")
            
            simulation = Simulation.objects.create(
                input_data=serializer.validated_data,
                report_data=data_to_report
            )
            
            response['simulation_id'] = simulation.pk
            
            logger.info(f"Симуляция успешно сохранена с ID={simulation.pk}")
            
        except Exception:
            logger.exception(
                "Ошибка при сохранении симуляции в БД",
                extra={'user': request.user.username}
            )
            # Не прерываем выполнение, если не удалось сохранить симуляцию
            # Расчёт всё равно был успешным
            logger.warning("Продолжаем выполнение без сохранения симуляции")

        # Этап 6: Валидация и возврат ответа
        try:
            # Не выполняем строгую валидацию, т.к. calculate содержит кортежи
            # и data_to_report имеет динамическую структуру
            response_serializer = CalculationResponseSerializer(data=response)
            if response_serializer.is_valid():
                logger.info("Расчёт успешно завершён, данные отправлены клиенту")
                return Response(response_serializer.validated_data, status=200)
            else:
                # Логируем ошибки валидации, но все равно возвращаем результат
                logger.warning(
                    f"Ошибка валидации ответа (возвращаем данные как есть): {response_serializer.errors}"
                )
                logger.info("Расчёт успешно завершён, данные отправлены клиенту")
                return Response(response, status=200)
                
        except Exception:
            logger.exception(
                "Ошибка при финальной валидации ответа",
                extra={'user': request.user.username}
            )
            # Всё равно возвращаем результат, т.к. расчёт выполнен успешно
            logger.info("Расчёт успешно завершён, данные отправлены клиенту (без валидации)")
            return Response(response, status=200)


@extend_schema_view(
    list=extend_schema(
        summary="Получить список симуляций",
        description="Возвращает список всех сохранённых симуляций с краткой информацией",
        parameters=[
            OpenApiParameter(
                name='ordering',
                description='Поле для сортировки. Доступные поля: created_at, id',
                required=False,
                type=OpenApiTypes.STR,
                default='-created_at'
            ),
        ]
    ),
    retrieve=extend_schema(
        summary="Получить детальную информацию о симуляции",
        description="Возвращает полную информацию о симуляции, включая входные данные и результаты расчёта"
    )
)
class SimulationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для работы с симуляциями (только чтение).
    
    Предоставляет операции получения списка и детальной информации для сохранённых симуляций транспортной сети.
    Симуляции содержат входные данные расчёта и результаты обработки.
    Создание, изменение и удаление симуляций недоступно через API.
    """
    
    queryset = Simulation.objects.all()
    serializer_class = SimulationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [ValidatedDjangoFilterBackend, ValidatedSearchFilter, ValidatedOrderingFilter]
    pagination_class = ValidatedPageNumberPagination
    
    # Поля для фильтрации
    filterset_fields = {
        'created_at': ['exact', 'gte', 'lte', 'range'],
        'id': ['exact', 'in'],
    }
    
    # Поля для поиска
    search_fields = ['description']
    
    # Поля для сортировки
    ordering_fields = ['created_at', 'id']
    ordering = ['-created_at']  # Сортировка по умолчанию (новые сверху)

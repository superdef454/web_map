from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BusStopView,
    BusStopViewSet,
    CalculationViewSet,
    CityView,
    CityViewSet,
    DistrictViewSet,
    EIViewSet,
    MainMap,
    RouteView,
    RouteViewSet,
    SimulationViewSet,
    TCViewSet,
    download_report_file,
)

app_name = 'PetriNET'

# Создаем роутер для API
api_router = DefaultRouter()
api_router.register(r'cities', CityViewSet, basename='city')
api_router.register(r'transport-types', TCViewSet, basename='tc')
api_router.register(r'busstops', BusStopViewSet, basename='busstop')
api_router.register(r'routes', RouteViewSet, basename='route')
api_router.register(r'districts', DistrictViewSet, basename='district')
api_router.register(r'calculations', CalculationViewSet, basename='calculation')
api_router.register(r'simulations', SimulationViewSet, basename='simulation')
# api_router.register(r'measurement-units', EIViewSet, basename='ei')


urlpatterns = [
    path('', MainMap.as_view(), name='main_map'),
    path('api/', include(api_router.urls)),
    path('ajax/city/get', CityView.as_view(), name='get_city_data'),
    path('ajax/BS/add', BusStopView.as_view(), name='create_bs'),
    path('ajax/BS/get', BusStopView.as_view(), name='get_bs'),
    path('ajax/route/add', RouteView.as_view(), name='create_route'),
    path('ajax/download_report_file', download_report_file, name='download_report_file'),
]

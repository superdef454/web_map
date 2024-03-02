from django.urls import path
from .views import (
    BusStopView, Calculate, CityView, MainMap, RouteView
)


app_name = 'PetriNET'

urlpatterns = [
    path('', MainMap.as_view(), name='main_map'),
    path('ajax/city/get', CityView.as_view(), name='get_city_data'),
    path('ajax/BS/add', BusStopView.as_view(), name='create_bs'),
    path('ajax/route/add', RouteView.as_view(), name='create_route'),
    path('ajax/load_calculation', Calculate.as_view(), name='load_calculation'),
]
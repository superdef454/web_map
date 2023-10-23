from django.urls import path
from .views import (
    leaflet, ajax_bs_add, ajax_route_add, ajax_city_data_get, load_calculation
)


app_name = 'PetriNET'

urlpatterns = [
    path('', leaflet, name='main_map'),
    path('ajax/BS/add', ajax_bs_add, name='ajax_bs_add'),
    path('ajax/route/add', ajax_route_add, name='ajax_route_add'),
    path('ajax/city/get', ajax_city_data_get, name='ajax_city_data_get'),
    path('ajax/load_calculation', load_calculation, name='load_calculation'),
]
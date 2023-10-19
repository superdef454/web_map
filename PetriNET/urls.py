from django.urls import path
from .views import (
    main_index, leaflet, ajax_bs_add, ajax_route_add, ajax_city_data_get
)


app_name = 'PetriNET'

urlpatterns = [
    path('', main_index, name='main_index'),
    path('leaflet/', leaflet, name='leaflet'),
    path('ajax/BS/add', ajax_bs_add, name='ajax_bs_add'),
    path('ajax/route/add', ajax_route_add, name='ajax_route_add'),
    path('ajax/city/get', ajax_city_data_get, name='ajax_city_data_get'),
]
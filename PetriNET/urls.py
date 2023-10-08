from django.urls import path
from .views import (
    main_index, leaflet, ajax_bs_add, ajax_bs_get
)


app_name = 'PetriNET'

urlpatterns = [
    path('', main_index, name='main_index'),
    path('leaflet/', leaflet, name='leaflet'),
    path('ajax/BS/add', ajax_bs_add, name='ajax_bs_add'),
    path('ajax/BS/get', ajax_bs_get, name='ajax_bs_get'),
]
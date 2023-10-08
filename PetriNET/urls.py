from django.urls import path
from .views import (
    main_index, leaflet, ajax_bs_add
)


app_name = 'PetriNET'

urlpatterns = [
    path('', main_index, name='main_index'),
    path('leaflet/', leaflet, name='leaflet'),
    path('ajax/BS/add', ajax_bs_add, name='ajax_bs_add'),
]
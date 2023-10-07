from django.urls import path
from .views import (
    main_map
)


app_name = 'PetriNET'

urlpatterns = [
    path('', main_map, name='main_map'),
]
import csv
from django.conf import settings
from django.core.management.base import BaseCommand
from PetriNET.models import BusStop
# from OSMPythonTools.api import Api
# from OSMPythonTools.nominatim import Nominatim



class Command(BaseCommand):
    help = 'Парсинг данных остановок с апи OSM'

    def handle(self, *args, **kwargs):
        pass
        # https://wiki.openstreetmap.org/wiki/RU:API_v0.6
        # https://data.nextgis.com/ru/region/RU-ORE/base
        # https://stackoverflow.com/questions/15617077/overpass-api-get-all-public-transport-stops-with-a-certain-name?rq=4
        # https://stackoverflow.com/questions/26126272/getting-every-single-public-transport-stop-coordinates?rq=4
        # https://stackoverflow.com/questions/20322823/how-to-get-all-roads-around-a-given-location-in-openstreetmap?rq=3
        # https://stackoverflow.com/questions/7139118/list-of-bus-stops-from-google-maps?rq=3
from django.core.management.base import BaseCommand
import requests
from PetriNET.models import BusStop, City


class Command(BaseCommand):
    help = 'Парсинг данных остановок'

    def add_arguments(self, parser):
        parser.add_argument('--city_id', type=int, required=True)

    def handle(self, city_id, *args, **kwargs):
        self.get_bus_stops(city_id=city_id)

    def get_bus_stops(self, city_id: int) -> None:
        """
        Получение остановок города
        """
        city = City.objects.get(id=city_id)
        url = "https://overpass-api.de/api/interpreter"
        query = f"""
        [out:json];
        node(around:10000,{city.latitude},{city.longitude})["highway"="bus_stop"];
        out;
        """
        response = requests.get(url, params={'data': query})
        bus_stops_data = response.json()

        bus_stops = []
        for element in bus_stops_data['elements']:
            if 'tags' in element and 'name' in element['tags']:
                bus_stop_name = element['tags']['name']
                bus_stop_lat = element['lat']
                bus_stop_lon = element['lon']
                bus_stops.append(BusStop(
                    city=city,
                    name=bus_stop_name,
                    latitude=bus_stop_lat,
                    longitude=bus_stop_lon
                ))
        BusStop.objects.bulk_create(bus_stops)

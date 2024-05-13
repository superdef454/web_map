import logging
from django.core.management.base import BaseCommand
from PetriNET.models import City
import requests


logger = logging.getLogger('PetriNetManager')


class Command(BaseCommand):
    help = 'Парсинг данных городов с апи OSM'

    def handle(self, *args, **kwargs):
        self.get_city_data()

    def get_city_data(self):
        url = "https://overpass-api.de/api/interpreter"
        query = """
        [out:json];
        area["ISO3166-1"="RU"][admin_level=2];
        (node["place"="city"](area);
        way["place"="city"](area);
        rel["place"="city"](area);
        );
        out center;
        """
        response = requests.get(url, params={'data': query})
        data = response.json()

        for element in data['elements']:
            if 'tags' in element and 'name' in element['tags']:
                city_name = element['tags']['name']
                latitude = element.get('lat', element.get('center', {}).get('lat'))
                longitude = element.get('lon', element.get('center', {}).get('lon'))
                city, create = City.objects.get_or_create(name=city_name, defaults={
                    'latitude': latitude,
                    'longitude': longitude,
                    })
                if create:
                    logger.info(f"create city: {city.name}")

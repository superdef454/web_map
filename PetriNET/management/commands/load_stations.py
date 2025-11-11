import requests
from django.core.management.base import BaseCommand

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
        
        # Проверяем, есть ли уже остановки в этом городе
        existing_stops_count = BusStop.objects.filter(city=city).count()
        
        url = "https://overpass-api.de/api/interpreter"
        query = f"""
        [out:json];
        node(around:10000,{city.latitude},{city.longitude})["highway"="bus_stop"];
        out;
        """
        response = requests.get(url, params={'data': query})
        response.raise_for_status()
        bus_stops_data = response.json()

        bus_stops = []
        
        if existing_stops_count == 0:
            # Быстрое добавление - нет существующих остановок
            self.stdout.write(f"Быстрое добавление остановок для города {city.name} (остановок нет)")
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
            created_count = len(BusStop.objects.bulk_create(bus_stops))
            self.stdout.write(f"Создано {created_count} остановок")
        else:
            # Проверяем дубликаты - есть существующие остановки
            self.stdout.write(f"Проверка дубликатов для города {city.name} (найдено {existing_stops_count} остановок)")
            
            # Получаем существующие координаты остановок
            existing_coords = set(
                BusStop.objects.filter(city=city).values_list('latitude', 'longitude')
            )
            
            new_stops = []
            skipped_count = 0
            
            for element in bus_stops_data['elements']:
                if 'tags' in element and 'name' in element['tags']:
                    bus_stop_name = element['tags']['name']
                    bus_stop_lat = element['lat']
                    bus_stop_lon = element['lon']
                    
                    # Проверяем, нет ли уже остановки с такими координатами
                    coord_tuple = (bus_stop_lat, bus_stop_lon)
                    if coord_tuple not in existing_coords:
                        new_stops.append(BusStop(
                            city=city,
                            name=bus_stop_name,
                            latitude=bus_stop_lat,
                            longitude=bus_stop_lon
                        ))
                        # Добавляем в set, чтобы избежать дубликатов в текущей партии
                        existing_coords.add(coord_tuple)
                    else:
                        skipped_count += 1
            
            if new_stops:
                created_count = len(BusStop.objects.bulk_create(new_stops))
                self.stdout.write(f"Создано {created_count} новых остановок, пропущено {skipped_count} дубликатов")
            else:
                self.stdout.write(f"Новых остановок не найдено, пропущено {skipped_count} дубликатов")

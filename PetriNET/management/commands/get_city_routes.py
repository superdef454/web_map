import logging
import re
from decimal import Decimal
from typing import Any

import requests
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from shapely.geometry import LineString
from shapely.ops import linemerge, unary_union

from PetriNET.models import TC, BusStop, City, Route

logger = logging.getLogger('PetriNetManager')


class Command(BaseCommand):
    help = 'Парсинг данных маршрутов общественного транспорта для указанного города'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--city_id', type=int, required=True, help='ID города для получения маршрутов')
        parser.add_argument('--transport_type', type=str, default='all', 
                          choices=['bus', 'trolleybus', 'tram', 'all'],
                          help='Тип транспорта (bus, trolleybus, tram, all)')

    def handle(self, city_id: int, transport_type: str = 'bus', *args: Any, **kwargs: Any) -> None:
        try:
            self.get_city_routes(city_id=city_id, transport_type=transport_type)
            self.stdout.write(
                self.style.SUCCESS(f'Успешно получены маршруты для города ID: {city_id}')
            )
        except (ValueError, requests.RequestException) as e:
            logger.exception("Ошибка при получении маршрутов")
            self.stdout.write(
                self.style.ERROR(f'Ошибка при получении маршрутов: {str(e)}')
            )

    def get_city_routes(self, city_id: int, transport_type: str = 'bus') -> None:
        """
        Получение маршрутов общественного транспорта для города
        """
        try:
            city = City.objects.get(id=city_id)
        except City.DoesNotExist as exc:
            error_msg = f"Город с ID {city_id} не найден"
            raise ValueError(error_msg) from exc

        url = "https://overpass-api.de/api/interpreter"
        
        # Расширенный радиус поиска для крупных городов
        radius = 15000  # 15 км

        # Создаем запрос в зависимости от типа транспорта
        if transport_type == 'all':
            query = f"""
            [out:json];
            (
              relation["route"="bus"](around:{radius},{city.latitude},{city.longitude});
              relation["route"="trolleybus"](around:{radius},{city.latitude},{city.longitude});
              relation["route"="tram"](around:{radius},{city.latitude},{city.longitude});
            );
            out geom;
            """
        else:
            query = f"""
            [out:json];
            (
              relation["route"="{transport_type}"](around:{radius},{city.latitude},{city.longitude});
            );
            out geom;
            """

        self.stdout.write(f"Поиск маршрутов типа '{transport_type}' в радиусе {radius/1000} км от города {city.name}")
        
        try:
            response = requests.get(url, params={'data': query}, timeout=50000)
            response.raise_for_status()
            routes_data = response.json()
        except requests.RequestException as e:
            error_msg = f"Ошибка запроса к Overpass API: {str(e)}"
            raise ValueError(error_msg) from e

        if not routes_data.get('elements'):
            self.stdout.write(
                self.style.WARNING(f'Маршруты не найдены для города {city.name}')
            )
            return

        self.stdout.write(f"Найдено {len(routes_data['elements'])} маршрутов")
        
        # Получаем или создаем типы транспорта
        transport_types = self._get_or_create_transport_types()
        
        routes_created = 0
        routes_updated = 0

        with transaction.atomic():
            for element in routes_data['elements']:
                if element.get('type') != 'relation':
                    continue
                    
                tags = element.get('tags', {})
                route_type = tags.get('route', '').lower()
                
                # Извлекаем основную информацию о маршруте
                route_ref = tags.get('ref', tags.get('name', f'Неизвестный маршрут {element["id"]}'))
                route_name = tags.get('name', f'Маршрут {route_ref}')
                
                # Очищаем название от проблемных Unicode символов для логирования
                clean_route_name = self._clean_unicode_for_logging(route_name)
                
                # Определяем тип транспорта
                tc = transport_types.get(route_type)
                if not tc:
                    tc = transport_types.get('bus')  # По умолчанию автобус
                
                # Извлекаем геометрию маршрута
                coordinates = self._extract_route_coordinates(element)
                
                # Интервал движения (если указан)
                interval = self._parse_interval(tags.get('interval', ''))
                
                # Проверяем, существует ли уже такой маршрут
                route, created = Route.objects.get_or_create(
                    city=city,
                    name=route_name,
                    defaults={
                        'tc': tc,
                        'interval': interval,
                        'list_coord': coordinates,
                    }
                )
                
                if created:
                    routes_created += 1
                    logger.debug(f"Создан маршрут: {clean_route_name}")
                else:
                    # Обновляем существующий маршрут
                    route.tc = tc
                    route.interval = interval
                    route.list_coord = coordinates
                    route.save()
                    routes_updated += 1
                    logger.debug(f"Обновлен маршрут: {clean_route_name}")
                
                # Связываем остановки с маршрутом
                # self._link_bus_stops_to_route(route, element, city)

        self.stdout.write(
            self.style.SUCCESS(
                f'Обработка завершена. Создано: {routes_created}, обновлено: {routes_updated} маршрутов'
            )
        )

    def _get_or_create_transport_types(self) -> dict[str, TC]:
        """Получает или создает типы транспортных средств"""
        transport_types = {}
        
        # Автобус
        tc_bus, _ = TC.objects.get_or_create(
            name='Автобус',
            defaults={
                'capacity': 50,
                'description': 'Городской автобус'
            }
        )
        transport_types['bus'] = tc_bus
        
        # Троллейбус
        tc_trolley, _ = TC.objects.get_or_create(
            name='Троллейбус',
            defaults={
                'capacity': 45,
                'description': 'Городской троллейбус'
            }
        )
        transport_types['trolleybus'] = tc_trolley
        
        # Трамвай
        tc_tram, _ = TC.objects.get_or_create(
            name='Трамвай',
            defaults={
                'capacity': 60,
                'description': 'Городской трамвай'
            }
        )
        transport_types['tram'] = tc_tram
        
        return transport_types

    def _extract_route_coordinates(self, element: dict[str, Any]) -> list[list[float]]:
        """Извлекает координаты маршрута и корректно упорядочивает"""
        segments = []

        for member in element.get('members', []):
            if member.get('type') == 'way' and 'geometry' in member:
                coords = [(pt['lon'], pt['lat']) for pt in member['geometry']]
                if len(coords) >= 2:  # только линии
                    segments.append(LineString(coords))
            # elif member.get('type') == 'node':
            #     # одиночные точки пропускаем или сохраняем отдельно
            #     lon = member.get('lon')
            #     lat = member.get('lat')
            #     if lon is not None and lat is not None:
            #         # такие точки просто добавим потом в итоговый список
            #         segments.append(LineString([(lon, lat), (lon, lat)]))  # дублируем точку

        if not segments:
            return []

        try:
            merged = linemerge(unary_union(segments))

            if merged.geom_type == 'LineString':
                coords = list(merged.coords)
            elif merged.geom_type == 'MultiLineString':
                # Выбираем LineString с наибольшим количеством точек
                longest_line = max(merged.geoms, key=lambda line: len(line.coords))
                coords = list(longest_line.coords)
            else:
                coords = []

            return [[lat, lon] for lon, lat in coords]

        except Exception as e:
            self.style.WARNING(f"Ошибка при объединении сегментов маршрута {element.get('id')}: {e}")
            raw_coords = []
            for seg in segments:
                raw_coords.extend([[lat, lon] for lon, lat in seg.coords])
            return raw_coords

    def _parse_interval(self, interval_str: str) -> int:
        """Парсит интервал движения из строки"""
        if not interval_str:
            return 10  # По умолчанию 10 минут
            
        try:
            # Извлекаем числа из строки
            numbers = re.findall(r'\d+', interval_str)
            if numbers:
                return int(numbers[0])
        except (ValueError, IndexError):
            logger.warning(f"Не удалось распарсить интервал: {interval_str}")
            
        return 10  # По умолчанию

    def _link_bus_stops_to_route(self, route: Route, element: dict[str, Any], city: City) -> None:
        """Связывает остановки с маршрутом"""
        # Собираем ID остановок из членов отношения
        stop_ids = [
            member['ref'] for member in element.get('members', [])
            if member.get('role') in ['stop', 'platform'] and member.get('type') == 'node'
        ]
        
        if not stop_ids:
            return
            
        # Поиск остановок в базе данных по координатам
        # Сначала получаем координаты остановок через дополнительный запрос
        try:
            url = "https://overpass-api.de/api/interpreter"
            nodes_query = f"""
            [out:json];
            (
              node(id:{','.join(map(str, stop_ids))});
            );
            out;
            """
            
            response = requests.get(url, params={'data': nodes_query}, timeout=50000)
            response.raise_for_status()
            nodes_data = response.json()
            
            linked_stops = []
            for node in nodes_data.get('elements', []):
                if node.get('type') != 'node':
                    continue
                    
                lat = Decimal(str(node['lat']))
                lon = Decimal(str(node['lon']))
                
                # Ищем ближайшую остановку в базе данных
                # Допустимое отклонение в координатах (примерно 100 метров)
                tolerance = Decimal('0.001')
                
                nearby_stops = BusStop.objects.filter(
                    city=city,
                    latitude__range=(lat - tolerance, lat + tolerance),
                    longitude__range=(lon - tolerance, lon + tolerance)
                )
                
                if nearby_stops.exists():
                    linked_stops.extend(nearby_stops)
            
            # Связываем найденные остановки с маршрутом
            if linked_stops:
                route.busstop.set(linked_stops)
                clean_name = self._clean_unicode_for_logging(route.name)
                logger.info(f"Связано {len(linked_stops)} остановок с маршрутом {clean_name}")
                
        except (requests.RequestException, ValueError) as e:
            clean_name = self._clean_unicode_for_logging(route.name)
            logger.warning(f"Не удалось связать остановки с маршрутом {clean_name}: {str(e)}")

    def _clean_unicode_for_logging(self, text: str) -> str:
        """
        Очищает текст от символов Unicode, которые не поддерживаются в cp1251
        """
        if not text:
            return text
        
        # Заменяем проблемные Unicode символы на безопасные ASCII аналоги
        replacements = {
            '→': ' -> ',  # Стрелка вправо
            '←': ' <- ',  # Стрелка влево
            '↔': ' <-> ', # Стрелка в обе стороны
            '—': ' - ',   # Длинное тире
            '–': ' - ',   # Среднее тире
            '"': '"',     # Кавычка  
            '…': '...',   # Многоточие
        }
        
        cleaned_text = text
        for unicode_char, ascii_replacement in replacements.items():
            cleaned_text = cleaned_text.replace(unicode_char, ascii_replacement)
        
        # Удаляем все остальные символы, которые не входят в cp1251
        try:
            cleaned_text.encode('cp1251')
            return cleaned_text
        except UnicodeEncodeError:
            # Если все еще есть проблемы, кодируем с игнорированием ошибок
            return cleaned_text.encode('cp1251', errors='ignore').decode('cp1251')
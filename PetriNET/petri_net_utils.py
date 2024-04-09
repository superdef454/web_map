import datetime
import logging
import os
import random
from docx import Document
from docx.shared import Pt
from geopy import distance
from faker import Faker
from .models import BusStop, City, Route

logger = logging.getLogger('PetriNetManager')

fake = Faker("ru_RU")

MAX_PASSENGERS_COUNT_FOR_RESPONSE = 100


def GetDataToCalculate(request_data_to_calculate: dict) -> dict:
    city_id = int(request_data_to_calculate['city_id'])
    DataToCalculate = {
        'city_id': city_id
    }

    # Получения маршрутов из бд
    routes = []
    for request_route in request_data_to_calculate['routes']:
        route = Route.objects.filter(city_id=city_id,
                                     id=request_route['id']).prefetch_related('busstop').first()
        if not route:
            route = Route.objects.filter(city_id=city_id,
                                         name__icontains=request_route['name']).prefetch_related('busstop').first()
        if route:
            routes.append(route)
        else:
            logger.warn("Отсутствует маршрут", args={"id": request_route['id']})

    if not routes:
        raise Exception("Отсутствуют маршруты")
    DataToCalculate['routes'] = routes

    # Получение остановок и путей пассажиров
    busstops_directions = []
    busstops = BusStop.objects.filter(
        city_id=city_id,
        route__id__in=[route.id for route in routes]
    ).prefetch_related('route_set').distinct()

    for busstop in busstops:
        try:
            BSAddItem = {
                "busstop": busstop.id,
                "directions": {
                    # 3:5,  # 5 человек поедут на 3 ОП
                    # 4:3,  # 3 человека поедут на 4 ОП
                    # 7:2,  # 2 человека поедут на 7 ОП
                    # 0:12  # 12 человек поедут рандомно
                }
            }
            valid_bus_stops = BusStop.objects.filter(
                route__id__in=busstop.get_routes_ids()).values_list('id', flat=True).distinct()  # Пока делаем без пересадок
            busstop_from_request = request_data_to_calculate['busstops'].pop(str(busstop.id), None)
            if busstop_from_request:
                PassengersWithoutDirection = int(busstop_from_request.get('PWD', 0))
                if PassengersWithoutDirection:
                    BSAddItem['directions'].update({
                        0: PassengersWithoutDirection
                    })
                for key, value in busstop_from_request['Directions'].items():
                    BusStopID = int(value.get(f"BusStopID{key}", 0))
                    PassengersCount = int(value.get(f"PassengersCount{key}", 0))
                    if BusStopID and PassengersCount and busstops.filter(id=BusStopID).exists() and \
                       BusStopID != busstop.id and BusStopID in valid_bus_stops:
                        BSAddItem['directions'].update({
                            BusStopID: PassengersCount
                        })
                    else:
                        pass
            if BSAddItem['directions']:
                busstops_directions.append(BSAddItem)
        except Exception:
            logger.exception(f"Ошибка разбора данных остановки {busstop_from_request}")

    if not busstops_directions:
        raise Exception("Отсутствуют остановки")
    DataToCalculate['busstops'] = busstops
    DataToCalculate['busstops_directions'] = busstops_directions

    return DataToCalculate


def GetTravelTime(latitude_start: float, longitude_start: float,
                  latitude_end: float, longitude_end: float) -> int:
    # Написать функцию получения времени, за которое автобус проедет расстояние между остановками в секундах
    return 60 * 3


def GetTravelRange(latitude_start: float, longitude_start: float,
                   latitude_end: float, longitude_end: float) -> int:
    """Нахождение расстояния между координатами в км"""
    return distance.distance((latitude_start, longitude_start), (latitude_end, longitude_end)).km


class PetriNet():
    passenger_time = 4  # Время входа или выхода пассажира (секунд)

    class Bus():
        """Автобус"""
        def __init__(self, route: Route, bus_id) -> None:
            # К какому маршруту относится
            self.route = route
            self.bus_id = bus_id
            # Вместимость
            self.capacity = self.route.tc.capacity
            # Координаты пути
            self.route_list = [self.serialize_route_point(point) for point in self.route.list_coord.copy()]
            self.bus_stop_ids = [bs.id for bs in self.route.busstop.all()]
            # Индекс остановки из пути
            self.bus_stop_index_now = 0
            # Пассажиры внутри
            self.passengers = []
            # Наверное сюда можно статистику добавить

        @property
        def get_rest_route(self) -> list[int]:
            """Получение списка id оставшихся ОП до конечной"""
            if self.ending_station():
                route_list = self.route_list.copy()
                route_list.reverse()
                return [point['bus_stop_id'] for point in route_list[0:]]
            return [point['bus_stop_id'] for point in self.route_list[self.bus_stop_index_now:]]

        def serialize_route_point(self, point: list):
            # Удобное хранение данных маршрута
            bus_stop_id = 0
            for bs in self.route.busstop.all():
                if point[0] == bs.latitude and point[1] == bs.longitude:
                    bus_stop_id = bs.id
                    break
            return {
                "bus_stop_id": bus_stop_id,
                "latitude": point[0],
                "longitude": point[1],
                }

        def ending_station(self) -> bool:
            """Проверяет конечную станцию"""
            return True if self.bus_stop_index_now == len(self.route_list) - 1 else False

        def chech_of_travel_permit(self, busstops: 'PetriNet.BusStop', seconds_from_start: int) -> bool:
            """Проверяет что с текущей остановки достаточно давно выезжал автобус"""
            if self.route.id in busstops.routs_last_start_bus_time and \
                    (seconds_from_start - busstops.routs_last_start_bus_time[self.route.id]) < self.route.interval * 60:
                return False
            else:
                return True

        def get_travel_time(self) -> int:
            """Возвращает время, требуемое на дорогу до следующей остановки"""
            start_index = self.bus_stop_index_now
            end_index = start_index - 1 if self.ending_station() else start_index + 1
            return GetTravelTime(
                self.route_list[start_index]["latitude"],
                self.route_list[start_index]["longitude"],
                self.route_list[end_index]["latitude"],
                self.route_list[end_index]["longitude"],
                )

        def drive_to_next_bus_stop(self):
            """Передвигает автобус на следующиую остановку"""
            if self.ending_station():
                self.route_list.reverse()
                self.bus_stop_index_now = 1
            else:
                self.bus_stop_index_now += 1

        def get_action(self) -> dict:
            return {"Bus": [self]}

        def to_dict(self) -> dict:
            """Получение данных для отображения на сайте"""
            return {
                "bus_id": self.bus_id,
                "route_id": self.route.pk,
                "capacity": self.capacity,
                "bus_stop_id": self.route_list[self.bus_stop_index_now]["bus_stop_id"],
                "lat": self.route_list[self.bus_stop_index_now]["latitude"],
                "lng": self.route_list[self.bus_stop_index_now]["longitude"],
                "passengers": [pas.to_dict() for pas in self.passengers[0:MAX_PASSENGERS_COUNT_FOR_RESPONSE]],
                "passengers_count": len(self.passengers)
            }

    class BusStop():
        """Остановочный пункт"""
        def __init__(self, bus_stop: BusStop, passengers: list) -> None:
            self.bus_stop = bus_stop
            self.passengers = passengers
            # Время последнего отправления автобуса для каждого маршрута
            self.routs_last_start_bus_time = {}

        def set_last_start_bus_time(self, route_id: int, seconds_from_start: int):
            """Устанавливает остановке последнее время отправления для текущего маршрута"""
            self.routs_last_start_bus_time[route_id] = seconds_from_start

        def to_dict(self) -> dict:
            """Получение данных для отображения на сайте"""
            return {
                "id": self.bus_stop.pk,
                "lat": self.bus_stop.latitude,
                "lng": self.bus_stop.longitude,
                "passengers": [pas.to_dict() for pas in self.passengers[0:MAX_PASSENGERS_COUNT_FOR_RESPONSE]],
                "passengers_count": len(self.passengers)
            }

    class Passenger():
        """Пассажир"""
        def __init__(self, start_point: int, end_point: int) -> None:
            self.name = fake.first_name()
            self.start_bus_stop_id = start_point
            self.end_bus_stop_id = end_point

        def get_route_count(self, bus_stop_ids: list[int]) -> int:
            """Получение длительности пути пассажира (кол-ва остановок)"""
            start_index = bus_stop_ids.index(self.start_bus_stop_id)
            end_index = bus_stop_ids.index(self.end_bus_stop_id)
            if start_index >= end_index:
                raise Exception("Неправильное получение длительности пути пассажира")
            return end_index - start_index

        def to_dict(self) -> dict:
            """Получение данных для отображения на сайте"""
            return {
                "name": self.name,
                "start": self.start_bus_stop_id,
                "end": self.end_bus_stop_id
            }

    class TimeLine():
        """Порядок расчёта, класс работы с таймлайном"""
        def __init__(self, bus_stops_now: dict) -> None:
            self.timeline = {}
            # Указатель на автобусы из расчёта
            self.bus_stops_now = bus_stops_now
            # Данные для отправки на страницу расчёта
            self.data_to_response = []

        def add_timepoint(self, seconds_from_start: int, action: dict):
            """
            Функция добавление действиея в очередь

            seconds_from_start - Количество секунд со старта расчёта
            action - Данные в этот момент времени
            """
            if seconds_from_start in self.timeline:
                action_in_timeline = self.timeline[seconds_from_start]
                for key, value in action.items():
                    if key in action_in_timeline:
                        action_in_timeline[key].extend(value)
                    else:
                        action_in_timeline[key] = value
            else:
                self.timeline[seconds_from_start] = action

        def add_list_timepoints(self, list_timepoints: list) -> None:
            """
            Добавления списка действий в очередь
            """
            for action in list_timepoints:
                self.add_timepoint(seconds_from_start=action['seconds_from_start'],
                                   action=action['action'])

        def process_item_for_responce(self, item: dict) -> dict:
            item_for_responce = item.copy()
            for key, value in item.items():
                if isinstance(value, list):
                    item_for_responce[key] = [v.to_dict() for v in value]
                else:
                    item_for_responce[key] = value.to_dict()
            # Отправляем только остановки с пассажирами
            item_for_responce["BusStops"] = [bus_stop.to_dict() for bus_stop in self.bus_stops_now.values() if
                                             bus_stop.passengers]
            return item_for_responce

        def add_data_to_response(self, seconds_from_start: int, action: dict) -> None:
            """Добавляет действие для отрисовки"""
            self.data_to_response.append((seconds_from_start, self.process_item_for_responce(action)))

        def pop_first_timepoint(self) -> tuple[int, dict]:
            if not self.timeline:
                return None, None
            first_seconds_from_start, _ = self.get_first_timepoint()
            first_action = self.timeline.pop(first_seconds_from_start)
            self.data_to_response.append((first_seconds_from_start, self.process_item_for_responce(first_action)))
            return first_seconds_from_start, first_action

        def get_first_timepoint(self) -> tuple[int, dict]:
            list_actions = [key for key in self.timeline.keys()]
            list_actions.sort()
            first_key = list_actions[0]
            return first_key, self.timeline[first_key]

    def __init__(self, data_to_calculate: dict = {}) -> None:
        self.data_to_calculate = data_to_calculate
        self.routes = data_to_calculate['routes']
        self.data_to_report = {'routes': {route.id: {'route': route,
                                                     'average_passengers_stops_count': [0, 0],
                                                     'average_fullness': [0, 0],
                                                     } for route in self.routes}}
        # Список объектов остановок с пассажирами
        self.busstops = {}
        self.busstops_cached = {busstop.id: busstop for busstop in data_to_calculate['busstops']}
        self.timeline = self.TimeLine(self.busstops)
        self.init_action()
        # Наверное переделать Имитацию работы онлайн с 400мс. на относительную скорость движения между actions

    def init_action(self):
        """Создание объектов для расчёта (пассажиров и автобусов)"""
        add_timepoints = []

        for route in self.routes:
            time = 0
            if not route.amount or not route.tc:
                logger.warn(f"На маршруте {route.id} не указаны автобусы, маршрут не будет учитываться в расчёте")
            else:
                for bus_id in range(route.amount):
                    add_timepoints.append({
                        "seconds_from_start": time,
                        "action": {
                            "Bus": [
                                self.Bus(route, bus_id + 1),
                            ]
                        }
                    })
                    time += route.interval * 60

        if not add_timepoints:
            raise Exception("Отсутствуют автобусы на маршрутах")

        for busstops_direction in self.data_to_calculate['busstops_directions']:
            bus_stop = self.busstops_cached[busstops_direction['busstop']]
            valid_bus_stops = list(BusStop.objects.filter(
                route__id__in=bus_stop.get_routes_ids(),
                id__in=list(self.busstops_cached.keys())).values_list('id', flat=True).distinct())
            if busstops_direction['busstop'] in valid_bus_stops:
                valid_bus_stops.remove(busstops_direction['busstop'])
            passengers = []
            for direction, count in busstops_direction['directions'].items():
                if direction == 0:
                    passengers.extend(
                        self.Passenger(bus_stop.id,
                                       random.choice(valid_bus_stops)) for pas in range(count)
                                       )
                else:
                    passengers.extend(self.Passenger(bus_stop.id, direction) for pas in range(count))
            self.busstops.update({bus_stop.id: self.BusStop(bus_stop, passengers)})

        if not self.busstops:
            raise Exception("Отсутствуют пассажиры")

        for busstop in self.data_to_calculate['busstops']:
            if busstop.id not in self.busstops:
                self.busstops.update({busstop.id: self.BusStop(busstop, [])})

        self.timeline.add_list_timepoints(add_timepoints)

    def Calculation(self):
        """Модуль расчёта"""
        # Получаем первый таймпоинт
        this_seconds_from_start, this_action = self.timeline.pop_first_timepoint()
        # Проходим по всем таймпоинтам
        while this_seconds_from_start or this_action:
            # Проверяем все автобусы в таймпоинте
            for bus in this_action["Bus"].copy():
                # Сколько временя заняло действие
                time_delta = 0
                # id текущей остановки автобуса
                bus_stop_id_now = bus.route_list[bus.bus_stop_index_now]["bus_stop_id"]
                # Сначала высаживаются из автобуса
                for pas in bus.passengers.copy():
                    # Если конечная точка пассажира совпадает с текущей автобуса
                    if pas.end_bus_stop_id == bus_stop_id_now:
                        # Пассажир прибыл в место назначения
                        bus.passengers.remove(pas)
                        time_delta += self.passenger_time
                # Добавить таймпоинт после высадки людей
                if time_delta:
                    this_seconds_from_start += time_delta
                    time_delta = 0
                    self.timeline.add_data_to_response(this_seconds_from_start, bus.get_action())
                # Заходят пассажиры, которые могут доехать до своей остановки
                for pas in self.busstops[bus_stop_id_now].passengers.copy():
                    # Если конечная точка пассажира есть в оставшемся пути автобуса (до конечной),
                    # и места в автобусе ещё есть
                    if pas.end_bus_stop_id in bus.get_rest_route and len(bus.passengers) < bus.capacity:
                        # Пассажир уходит с остановки
                        self.busstops[bus_stop_id_now].passengers.remove(pas)
                        # Садится в автобус
                        bus.passengers.append(pas)
                        # Считается средняя длительность пути пассажиров
                        self.data_to_report['routes'][bus.route.id]['average_passengers_stops_count'][0] +=\
                            pas.get_route_count(bus.get_rest_route)
                        self.data_to_report['routes'][bus.route.id]['average_passengers_stops_count'][1] += 1
                        # Это занимает некоторое время
                        time_delta += self.passenger_time
                # Добавить таймпоинт после посадки людей
                if time_delta:
                    this_seconds_from_start += time_delta
                    time_delta = 0
                    self.timeline.add_data_to_response(this_seconds_from_start, bus.get_action())

                def exists_pass_in_bus_path(bus_stop_ids: list) -> bool:
                    """Проверяем есть ли пассажиры на пути автобуса"""
                    stop_intersections = set(bus_stop_ids) & \
                        set([busstop.bus_stop.id for busstop in self.busstops.values() if busstop.passengers])
                    return True if stop_intersections else False
                # Автобус отправляется на следующую остановку,
                # если она конечная: если есть пассажиры на его пути или в нём едем дальше, иначе останавливаемся
                if bus.ending_station() and not (bus.passengers or
                                                 exists_pass_in_bus_path(bus.bus_stop_ids)):
                    # В этот момент можно у маркера отключить анимацию
                    pass
                else:
                    # При достижении начальной остановки, если за последние route.interval минут выезжал автобус
                    if bus.ending_station() and not bus.chech_of_travel_permit(self.busstops[bus_stop_id_now],
                                                                               this_seconds_from_start):
                        # Этот автобус ждёт route.interval минут
                        time_delta += bus.route.interval * 60
                    else:
                        # Устанавливаем остановке последнее время отправления для текущего маршрута
                        self.busstops[bus_stop_id_now].set_last_start_bus_time(bus.route.id, this_seconds_from_start)
                        # Добавляем время пути до следующей остановки
                        time_delta += bus.get_travel_time()
                        # Считаем среднюю наполненность
                        self.data_to_report['routes'][bus.route.id]['average_fullness'][0] += len(bus.passengers)
                        self.data_to_report['routes'][bus.route.id]['average_fullness'][1] += 1
                        # Передвигаем автобус
                        bus.drive_to_next_bus_stop()
                    this_action["Bus"].remove(bus)
                    # Добавляем следующий таймпоинт в таймлайн
                    self.timeline.add_timepoint(this_seconds_from_start + time_delta, bus.get_action())
            this_seconds_from_start, this_action = self.timeline.pop_first_timepoint()
        self.timeline.data_to_response.sort(key=lambda i: i[0])
        return self.timeline.data_to_response

    def CreateDataToReport(self) -> dict:
        """Собирает данные для отчёта"""
        data_to_report = {}
        data_to_report['city_name'] = City.objects.get(id=self.data_to_calculate['city_id']).name
        data_to_report['data'] = str(datetime.datetime.now().isoformat(sep='_', timespec='seconds'))
        data_to_report['bus_stops'] = []
        for bus_stop in self.data_to_calculate['busstops']:
            bus_add = {}
            for bus_in_calculate in self.timeline.data_to_response[0][1]['BusStops']:
                if bus_in_calculate['id'] == bus_stop.id:
                    bus_add['bus_name'] = bus_stop.name
                    bus_add['passengers_count'] = bus_in_calculate['passengers_count']
                    break
            if bus_add:
                for timepoint in self.timeline.data_to_response:
                    for bus_in_calculate in timepoint[1]['BusStops']:
                        if bus_in_calculate['id'] == bus_stop.id:
                            bus_add['max_waiting_time'] = timepoint[0]
                            break
                    else:
                        break
                bus_add['max_waiting_time'] = int(bus_add['max_waiting_time'] / 60)
                bus_add['routes_count'] = len(bus_stop.route_set.all())
                data_to_report['bus_stops'].append(bus_add)
        results_add = {
            'bus_name': 'Итоги',
            'passengers_count': 0,
            'max_waiting_time': [],
            'routes_count': ''
        }
        for bus_stop in data_to_report['bus_stops']:
            results_add['passengers_count'] += bus_stop['passengers_count']
            results_add['max_waiting_time'].append(bus_stop['max_waiting_time'])
        # Среднее время ожидания
        results_add['max_waiting_time'] = int(sum(results_add['max_waiting_time']) /
                                              len(results_add['max_waiting_time']))
        data_to_report['bus_stops'].append(results_add)
        # Формировать цвет время ожидания автобуса относительно среднего
        # bus_add['color'] = 'white'
        data_to_report['routes'] = []
        for route in self.data_to_report['routes'].values():
            add_route = route.copy()
            add_route.pop('route')
            add_route['name'] = route['route'].name
            TC = route['route'].tc
            add_route['TC'] = f'{TC.name}, {TC.capacity}' if TC else ''
            add_route['interval'] = route['route'].interval
            add_route['average_passengers_stops_count'] = round(route['average_passengers_stops_count'][0] /
                                                                (route['average_passengers_stops_count'][1] or 1), 2)
            add_route['average_fullness'] = str(round((route['average_fullness'][0] /
                                                       (route['average_fullness'][1] or 1) /
                                                       (TC.capacity or 1)) * 100, 2)) + '%'
            add_route['bus_stop_count'] = len(route['route'].busstop.all())
            add_route['route_length'] = 0
            last_bus_stop = None
            for now_bus_stop in route['route'].busstop.all():
                if not last_bus_stop:
                    last_bus_stop = now_bus_stop
                    continue
                add_route['route_length'] += GetTravelRange(
                    last_bus_stop.latitude,
                    last_bus_stop.longitude,
                    now_bus_stop.latitude,
                    now_bus_stop.longitude,
                    )
            add_route['route_length'] = round(add_route['route_length'], 2)
            add_route['TC_count'] = route['route'].amount
            data_to_report['routes'].append(add_route)
        return data_to_report


def CreateResponseFile(data_to_report: dict) -> str:
    city_name = data_to_report.get('city_name', '')
    date = data_to_report.get('data', '')

    path = 'media/reports/'
    file_name = f'report_{city_name}_{date}.docx'
    file_path = path + file_name
    if os.path.isfile(file_path):
        return file_path

    # Создаем новый документ Word
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(14)

    bus_stops = data_to_report.get('bus_stops', [])
    routes = data_to_report.get('routes', [])

    # Добавляем заголовок
    doc.add_paragraph(f'Результат расчёта нагрузки на транспортную сеть с использованием маршрутов: {", ".join([route["name"] for route in routes])} \n')

    doc.add_paragraph(f"Населённый пункт: {city_name}")
    doc.add_paragraph(f"Дата: {date}\n")

    # Добавляем таблицу автобусных остановок
    if bus_stops:
        doc.add_paragraph('Автобусные остановки:')
        table = doc.add_table(rows=1, cols=4)
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Остановка'
        hdr_cells[1].text = 'Количество пассажиров'
        hdr_cells[2].text = 'Максимальное время ожидания автобуса, мин.'
        hdr_cells[3].text = 'Количество маршрутов, шт.'

        for stop in bus_stops:
            row_cells = table.add_row().cells
            row_cells[0].text = stop.get('bus_name', '')
            row_cells[1].text = str(stop.get('passengers_count', ''))
            row_cells[2].text = str(stop.get('max_waiting_time', ''))
            row_cells[3].text = str(stop.get('routes_count', ''))

    # Добавляем таблицу маршрутов
    if routes:
        doc.add_paragraph('\nМаршруты:')
        table = doc.add_table(rows=1, cols=8)
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Маршрут'
        hdr_cells[1].text = 'Тип транспортного средства, Название, вместимость'
        hdr_cells[2].text = 'Интервал движения автобусов, мин.'
        hdr_cells[3].text = 'Средняя длительность пути пассажиров, кол-во ОП'
        hdr_cells[4].text = 'Средняя наполненность автобусов, %'
        hdr_cells[5].text = 'Количество остановок'
        hdr_cells[6].text = 'Протяжённость'
        hdr_cells[7].text = 'Кол-во автобусов на маршруте'

        for route in routes:
            row_cells = table.add_row().cells
            row_cells[0].text = route.get('name', '')
            row_cells[1].text = route.get('TC', '')
            row_cells[2].text = str(route.get('interval', ''))
            row_cells[3].text = str(route.get('average_passengers_stops_count', ''))
            row_cells[4].text = route.get('average_fullness', '')
            row_cells[5].text = str(route.get('bus_stop_count', ''))
            row_cells[6].text = str(route.get('route_length', ''))
            row_cells[7].text = str(route.get('TC_count', ''))

    if not os.path.exists(path):
        os.makedirs(path)
    # Сохраняем файл локально на сервере
    doc.save(file_path)

    return file_path

# Проверка что на маршруте 2 и более остановок

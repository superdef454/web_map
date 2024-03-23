from datetime import datetime
import logging
import random
from .models import BusStop, Route

logger = logging.getLogger('PetriNetManager')


def GetDataToCalculate(request_data_to_calculate: dict) -> dict:
    city_id = int(request_data_to_calculate['city_id'])
    DataToCalculate = {
        'city_id': city_id
    }

    # Получения маршрутов из бд
    routes = []
    for request_route in request_data_to_calculate['routes']:
        route = Route.objects.filter(city_id=city_id,
                                     id=request_route['id']).first()
        if not route:
            route = Route.objects.filter(city_id=city_id,
                                         name__icontains=request_route['name']).first()
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
    )

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
                route__id__in=busstop.get_routes_ids()).values_list('id', flat=True)  # Пока делаем без пересадок
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


def GetTravelTime(latitude: float, longitude: float) -> datetime:
    # Написать функцию получения времени, за которое автобус проедет расстояние между остановками

    # Можно найти растояние между двумя остановками с помощью geopy.distance
    pass


class PetriNet():
    passenger_time = 4  # Время входа или выхода пассажира (секунд)

    class Bus():
        """Автобус"""
        def __init__(self, route: Route) -> None:
            # К какому маршруту относится
            self.route = route
            # Вместимость
            self.capacity = self.route.tc.capacity
            # Текущие координаты
            self.latitude = self.route.list_coord[0][0]
            self.longitude = self.route.list_coord[0][1]
            # Пассажиры внутри
            self.passengers = []
            # Наверное сюда можно статистику добавить

        def __str__(self) -> str:
            pass

        def __dict__(self) -> dict:
            pass

    class BusStop():
        """Остановочный пункт"""
        def __init__(self, bus_stop: BusStop, passengers: list) -> None:
            self.bus_stop = bus_stop
            self.passengers = passengers
        #     self.create_passengers(directions)

        # def create_passengers(self, directions: dict):
        #     for passenger in directions:
        #         Passenger
        #     pass

    class Passenger():
        """Пассажир"""
        def __init__(self, start_point: int, end_point: int) -> None:
            self.start_bus_stop_id = start_point
            self.end_bus_stop_id = end_point

    class TimeLine():
        """Порядок расчёта, класс работы с таймлайном"""
        def __init__(self) -> None:
            self.timeline = {}

        def add_action(self, seconds_from_start: int, action: dict):
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

        def add_list_actions(self, list_actions: list) -> None:
            """
            Добавления списка действий в очередь
            """
            for action in list_actions:
                self.add_action(seconds_from_start=action['seconds_from_start'],
                                action=action['action'])

        def process_item_for_responce(self, item: dict) -> dict:
            # TODO Преобразовать item в подходящий для разбора контент
            return str(item)

        def get_actions_from_timeline(self) -> list[int, dict]:
            list_actions = [(key, self.process_item_for_responce(item)) for key, item in self.timeline.items()]
            list_actions.sort(key=lambda item: item[0])
            return list_actions

    def __init__(self, data_to_calculate: dict = {
        'city_id': 3,
        'routes': ['<Route: Единственный маршрут Актобе>'],
        'busstops': '<QuerySet [<BusStop: ЖД Вокзал>, <BusStop: Акация>, <BusStop: Красснощекова>]>',
        'busstops_directions': [{'busstop': '<BusStop: ЖД Вокзал>', 'directions': {...}},
                                {'busstop': '<BusStop: Акация>', 'directions': {...}},
                                {'busstop': '<BusStop: Красснощекова>', 'directions': {...}}],
    }) -> None:  # TODO Убрать пример данных
        self.data_to_calculate = data_to_calculate
        self.routes = data_to_calculate['routes']
        self.busstops = data_to_calculate['busstops']
        self.busstops_cached = {busstop.id: busstop for busstop in self.busstops}
        self.timeline = self.TimeLine()
        self.init_action()
        # Начальное положение без автобусов (Список остановок с каждым человеком на ней (его id, начальное и конечное положение для отображения людей на остановках и в автобусе))
        # На карте остановки с пассажирами (в инокне остановки должно быть число пассажиров на ней а при popup показываться список пассажиров (брать динамически от текущего actions))
        # Идентичное поведение остановкам для автобусов
        # Наверное переделать Имитацию работы онлайн с 400мс. на относительную скорость движения между actions
        # Чтобы при достижении начальной остановки, если за последние route.interval минут выезжал автобус, то этот ждал

    def init_action(self):
        """Создание объектов для расчёта (пассажиров и автобусов)"""
        add_actions = []
        # {
        #     "Bus": [],
        #     "BusStop": []
        # }

        # Создание объектов автобусов
        for route in self.routes:
            time = 0
            if not route.amount or not route.tc:
                logger.warn(f"На маршруте {route.id} не указаны автобусы, маршрут не будет учитываться в расчёте")
            else:
                for bus in range(route.amount):
                    add_actions.append({
                        "seconds_from_start": time,
                        "action": {
                            "Bus": [
                                self.Bus(route),
                            ]
                        }
                    })
                    time += route.interval * 60

        if not add_actions:
            raise Exception("Отсутствуют автобусы на маршрутах")

        add_action = {
            "seconds_from_start": 0,
            "action": {
                "BusStops": []
            }
        }
        for busstops_direction in self.data_to_calculate['busstops_directions']:
            bus_stop = self.busstops_cached[busstops_direction['busstop']]
            valid_bus_stops = BusStop.objects.filter(
                route__id__in=bus_stop.get_routes_ids(),
                id__in=list(self.busstops_cached.keys())).values_list('id', flat=True)
            passengers = []
            for direction, count in busstops_direction['directions'].items():
                if direction == 0:
                    passengers.extend(self.Passenger(bus_stop.id, random.choice(valid_bus_stops)) for pas in range(count))
                else:
                    passengers.extend(self.Passenger(bus_stop.id, direction) for pas in range(count))
            add_action['action']['BusStops'].append(self.BusStop(bus_stop, passengers))

        if add_action['action']['BusStops']:
            add_actions.append(add_action)
        else:
            raise Exception("Отсутствуют пассажиры")

        self.timeline.add_list_actions(add_actions)

    def Calculation(self):
        return self.timeline.get_actions_from_timeline()

# Не число шагов, а время

# Проверка что на маршруте 2 и более остановок

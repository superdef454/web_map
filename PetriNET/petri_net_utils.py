from datetime import datetime
import logging
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
                "busstop": busstop,
                "directions": {
                    # 3:5,  # 5 человек поедут на 3 ОП
                    # 4:3,  # 3 человека поедут на 4 ОП
                    # 7:2,  # 2 человека поедут на 7 ОП
                    # 0:12  # 12 человек поедут рандомно
                }
            }
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
                       BusStopID != busstop.id:
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
    pass


class PetriNet():
    passenger_time = 4  # Время входа или выхода пассажира (секунд)

    class Bus():
        pass

    class BusStop():
        pass

    class Passenger():
        pass

    class TimeLine():
        def __init__(self) -> None:
            self.timeline = []

        def add_data(self, seconds_from_start: int, action: dict):
            """
            Функция работы с таймлайном

            seconds_from_start - Количество секунд со старта расчёта
            action - Данные в этот момент времени
            """
            pass

    def __init__(self, DataToCalculate: dict = {
        'city_id': 3,
        'routes': ['<Route: Единственный маршрут Актобе>'],
        'busstops': '<QuerySet [<BusStop: ЖД Вокзал>, <BusStop: Акация>, <BusStop: Красснощекова>]>',
        'busstops_directions': [{'busstop': '<BusStop: ЖД Вокзал>', 'directions': {...}},
                                {'busstop': '<BusStop: Акация>', 'directions': {...}},
                                {'busstop': '<BusStop: Красснощекова>', 'directions': {...}}],
    }) -> None:
        self.DataToCalculate = DataToCalculate
        self.timeline = self.TimeLine()
        self.init_action()
        print(self.passenger_time)
        # Начальное положение без автобусов (Список остановок с каждым человеком на ней (его id, начальное и конечное положение для отображения людей на остановках и в автобусе))
        # На карте остановки с пассажирами (в инокне остановки должно быть число пассажиров на ней а при popup показываться список пассажиров (брать динамически от текущего actions))
        # Идентичное поведение остановкам для автобусов
        # Если пассажир вышел на остановку с пересадкой отрисовать остановку
        # Наверное переделать Имитацию работы онлайн с 400мс. на относительную скорость движения между actions

    def init_action(self):
        action = {
            "Bus": [],
            "BusStop": []
        }

        # for

        self.timeline.add_data(0, action)

    def Calculation(self):
        return {"actions": []}

# Не число шагов, а время

# Написать функцию получения времени, за которое автобус проедет расстояние между остановками
    
# Можно найти растояние между двумя остановками с помощью geopy.distance

# Пример выходных данных (будет пересмотрен)

# actions = [
#     [
#         {
#             "route_id":3,
#             "latlng":[1.1234,2.3213],
#             "capacity":130,
#             "passengers":65,
#         },
#         {
#             "route_id":2,
#             "latlng":[1.1334,2.3313],
#             "capacity":70,
#             "passengers":43,
#         }
#     ],
#         [
#         {
#             "route_id":3,
#             "latlng":[1.2234,2.4213],
#             "capacity":130,
#             "passengers":57,
#         },
#         {
#             "route_id":2,
#             "latlng":[1.2334,2.4313],
#             "capacity":70,
#             "passengers":40,
#         }
#     ]
# ]

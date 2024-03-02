import logging
from .models import City, BusStop, Route

logger = logging.getLogger('PetriNetManager')


def GetDataToCalculate(request_data_to_calculate: dict) -> dict:
    city_id = request_data_to_calculate['city_id']

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
            logger.warn("Отсутствует маршрут", args={"id":request_route['id']})
    
    if not routes:
        raise Exception("Отсутствуют маршруты")

    busstops = BusStop.objects.filter(
        city_id=city_id,
        route_set_id__in=[route.id for route in routes]
    )

    if not busstops:
        raise Exception("Отсутствуют остановки")

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

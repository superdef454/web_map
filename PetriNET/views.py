import json
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

from .models import City, BusStop, Route


@login_required
def ajax_bs_add(request):
    if request.method == "POST":
        if request.user.is_superuser:
            lat = request.POST.get('lat')
            lng = request.POST.get('lng')
            name = request.POST.get('name')
            city_id = request.POST.get('city_id')
            if not lat or not lng or not name or not city_id:
                return JsonResponse({
                    'error': 1,
                    'error_messgae': 'Ошибка заполнения данных'
                })
            add = BusStop.objects.create(
                city=City.objects.get(id=city_id),
                name=name,
                latitude=lat,
                longitude=lng
            )
            return JsonResponse({'error': 0, 'BusStop': {'id': add.id}})
        else:
            return JsonResponse({'error': 2, 'error_message': 'Ошибка прав доступа'})
    return JsonResponse({'error': 1})

# {
#     "routs":[1,2,3],
#     "busstops":[
#         {
#             "busstop_id":1,  # С 1 ОП
#             "passengers":{
#                 3:5,  # 5 человек поедут на 3 ОП
#                 4:3,  # 3 человека поедут на 4 ОП
#                 7:2,  # 2 человека поедут на 7 ОП
#                 0:12  # 12 человек поедут рандомно
#             }
#         }
#     ]
# }

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

@login_required
def ajax_route_add(request):
    if request.method == "POST":
        if request.user.is_superuser:
            list_coord = json.loads(request.POST.get('list_coord'))
            name = request.POST.get('name')
            city_id = request.POST.get('city_id')
            if not list_coord or not name or not city_id:
                return JsonResponse({
                    'error': 1,
                    'error_messgae': 'Ошибка заполнения данных'
                })
            try:
                list_bs = [BusStop.objects.get(latitude = bs[0], longitude = bs[1]) for bs in list_coord]
            except:
                return JsonResponse({
                    'error': 1,
                    'error_messgae': 'Ошибка заполнения данных'
                })
            add = Route.objects.create(
                city=City.objects.get(id=city_id),
                name=name,
            )
            add.busstop.add(*list_bs)
            add.list_coord = list_coord
            add.save()
            return JsonResponse({'error': 0, 'Route': {
                'name': add.name,
                'list_coord': add.list_coord,
                'id': add.id
                }})
        else:
            return JsonResponse({'error': 2, 'error_message': 'Ошибка прав доступа'})
    return JsonResponse({'error': 1})

@login_required
def ajax_city_data_get(request):
    if request.method == "POST":
        if request.user.is_authenticated:
            city_id = request.POST.get('city_id')
            if not city_id:
                return JsonResponse({
                    'error': 1,
                    'error_messgae': 'Ошибка заполнения данных'
                })
            city = City.objects.get(id=city_id)
            response = {'error': 0}
            BSList = list(BusStop.objects.filter(city=city).values('name', 'latitude', 'longitude', 'id'))
            RouteList = [{
                'name': route.name,
                'list_coord': route.list_coord,
                'id': route.id
                } for route in Route.objects.filter(city=city)] # Если len(route.list_coord) < route.busstop.all().count() удалить маршрут и вызвать ошибку
            RouteList.sort(key=lambda route: len(route['list_coord']), reverse=True)
            response.update(
                {
                    'BSList': BSList,
                    'RouteList': RouteList
                }
            )
            return JsonResponse(response)
    return JsonResponse({})

# Можно найти растояние между двумя остановками с помощью geopy.distance

# Функция проверки заполненной сети
@login_required
def load_calculation(request):
    if request.method == "POST":
        if request.user.is_authenticated:
            try:
                DataToCalculate = json.loads(request.POST.get('DataToCalculate'))
            except Exception:
                return JsonResponse({
                    'error': 1,
                    'error_messgae': 'Ошибка заполнения данных'
                })                
            if not DataToCalculate:
                return JsonResponse({
                    'error': 1,
                    'error_messgae': 'Ошибка заполнения данных'
                })
            print(DataToCalculate)
            # city = City.objects.get(id=city_id)
            response = {'error': 0}
            # BSList = list(BusStop.objects.filter(city=city).values('name', 'latitude', 'longitude', 'id'))
            # RouteList = [{
            #     'name': route.name,
            #     'list_coord': route.list_coord,
            #     'id': route.id
            #     } for route in Route.objects.filter(city=city)] # Если len(route.list_coord) < route.busstop.all().count() удалить маршрут и вызвать ошибку
            # RouteList.sort(key=lambda route: len(route['list_coord']), reverse=True)
            # response.update(
            #     {
            #         'BSList': BSList,
            #         'RouteList': RouteList
            #     }
            # )
            return JsonResponse(response)
    return JsonResponse({})

@login_required
def leaflet(request):
    responce = {}
    responce['citys'] = list(City.objects.values('name', 'latitude', 'longitude', 'id'))
    return render(
        request,
        'PetriNET/leaflet/index.html',
        responce
    )
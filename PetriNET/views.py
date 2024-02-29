import json
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

from PetriNET.petri_net_utils import GetDataToCalculate

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
            response = {'error': 0}
            BSList = list(BusStop.objects.filter(city_id=city_id).values('name', 'latitude', 'longitude', 'id'))
            Routes = Route.objects.filter(city_id=city_id)
            RouteList = []
            for route in Routes:
                if len(route.list_coord) < route.busstop.all().count():
                    route.delete()
                    continue
                RouteList.append(
                    {
                        'name': route.name,
                        'list_coord': route.list_coord,
                        'id': route.id
                    }
                )
            RouteList.sort(key=lambda route: len(route['list_coord']), reverse=True)
            response.update(
                {
                    'BSList': BSList,
                    'RouteList': RouteList
                }
            )
            return JsonResponse(response)
    return JsonResponse({'error': 1})

# Можно найти растояние между двумя остановками с помощью geopy.distance

# Функция проверки заполненной сети
@login_required
def load_calculation(request):
    if request.method == "POST":
        if request.user.is_authenticated:
            try:
                request_data_to_calculate = json.loads(request.POST.get('DataToCalculate'))
                DataToCalculate = GetDataToCalculate()
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
            response = {'error': 0}
            return JsonResponse(response)
    return JsonResponse({'error': 404})

@login_required
def leaflet(request):
    responce = {}
    responce['citys'] = list(City.objects.values('name', 'latitude', 'longitude', 'id'))
    return render(
        request,
        'PetriNET/leaflet/index.html',
        responce
    )
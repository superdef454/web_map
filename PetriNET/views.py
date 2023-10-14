from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

from .models import City, BusStop

def main_index(request):
    responce = {}
    return render(
        request,
        'PetriNET/index.html',
        responce
    )

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
            BusStop.objects.create(
                city=City.objects.get(id=city_id),
                name=name,
                latitude=lat,
                longitude=lng
            )
            return JsonResponse({'error': 0})
        else:
            return JsonResponse({'error': 2, 'error_message': 'Ошибка прав доступа'})
    return JsonResponse({'error': 1})

@login_required
def ajax_bs_get(request):
    if request.method == "POST":
        if request.user.is_authenticated:
            city_id = request.POST.get('city_id')
            if not city_id:
                return JsonResponse({
                    'error': 1,
                    'error_messgae': 'Ошибка заполнения данных'
                })
            response = {
                'error': 0,
            }
            response.update(
                {'BSList': list(BusStop.objects.filter(city=City.objects.get(id=city_id)).values('name', 'latitude', 'longitude', 'id'))}
            )
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
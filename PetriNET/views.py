from django.shortcuts import render

def main_map(request):
    responce = {}
    return render(
        request,
        'PetriNET/index.html',
        responce
    )
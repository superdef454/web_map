from django.http import JsonResponse
from django.contrib.auth.decorators import login_required


def auth_required(permissions=[]):
    def real_decorator(func):
        def wrapper(request, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({'error': 403, 'error_message': 'Ошибка авторизации'})
            # if request.user.user_permissions ... permissions
            #    return JsonResponse({'error': 402, 'error_message': 'Ошибка прав доступа'})
            return func(request, **kwargs)

        return wrapper
    
    return real_decorator
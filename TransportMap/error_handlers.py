"""
Кастомные обработчики исключений для Django REST Framework.
Обеспечивают единообразный формат ответов для ошибок и детальные сообщения.
"""
import logging
import sys
import traceback
from typing import Any, Optional

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.csrf import requires_csrf_token
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Optional[Response]:
    """
    Кастомный обработчик исключений для DRF.
    
    Обрабатывает исключения permission denied и добавляет детальные сообщения.
    """
    # Если это Django ValidationError — преобразуем в DRF ValidationError (400)
    if isinstance(exc, DjangoValidationError):
        data = {}
        
        if hasattr(exc, 'error_dict') and exc.error_dict:
            # Если это ValidationError с полями (из Model.clean() или формы)
            for field, errors in exc.error_dict.items():
                if isinstance(errors, list):
                    data[field] = [str(error.message) if hasattr(error, 'message') else str(error) for error in errors]
                else:
                    data[field] = [str(errors)]
        elif hasattr(exc, 'error_list') and exc.error_list:
            # Если это ValidationError со списком ошибок (обычно для __all__)
            data['__all__'] = [str(error.message) if hasattr(error, 'message') else str(error) for error in exc.error_list]
        else:
            # Если это просто ValidationError с сообщением
            data['__all__'] = [str(exc)]

        return Response({'errors': data, 'timestamp': timezone.now().isoformat()}, status=400)

    # Вызываем стандартный обработчик исключений DRF
    response = exception_handler(exc, context)
    
    # Получаем view и request из контекста
    view = context.get('view')
    request = context.get('request')
    
    if response is None:
        from rest_framework import status
        from rest_framework.response import Response as DRFResponse
        
        custom_response_data = {
            'error': 'Internal Server Error',
            'status_code': 500,
            'timestamp': timezone.now().isoformat()
        }
        
        # Проверяем, нужно ли показывать детали ошибки
        if request:
            show_details = _should_show_error_details(request)
            
            if show_details:
                # Получаем информацию об ошибке
                exc_type, exc_value, exc_traceback = sys.exc_info()
                if exc_type:
                    custom_response_data.update({
                        'error_type': exc_type.__name__,
                        'error_message': str(exc_value) if exc_value else 'No details available',
                        'traceback': (''.join(traceback.format_tb(exc_traceback)) 
                                    if exc_traceback else 'No traceback available')
                    })
                    
                    # Логируем детальную ошибку
                    logger.error(
                        "Unhandled exception for user %s on %s %s: %s\n%s",
                        getattr(request.user, 'username', 'Anonymous'),
                        request.method,
                        request.path,
                        str(exc),
                        ''.join(traceback.format_tb(exc_traceback)) if exc_traceback else ''
                    )
            else:
                # Логируем ошибку без деталей для обычных пользователей
                logger.error(
                    "Unhandled exception for user %s on %s %s: %s",
                    getattr(request.user, 'username', 'Anonymous'),
                    request.method,
                    request.path,
                    str(exc)
                )
        else:
            # Если нет request, просто логируем исключение
            logger.error("Unhandled exception: %s", str(exc))
        
        # Создаем DRF Response для необработанного исключения
        return DRFResponse(custom_response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Если response есть, обрабатываем известные статус коды
    if response is not None:
        # Обрабатываем исключения PermissionDenied (403)
        if response.status_code == 403:
            custom_response_data = {
                'error': 'permission_denied',
                'detail': 'У вас нет разрешения на выполнение этого действия.',
                'status_code': response.status_code,
            }
            
            # Логируем информацию о запрете доступа
            if request:
                logger.warning(
                    "Permission denied for user %s on %s %s: %s",
                    getattr(request.user, 'username', 'Anonymous'),
                    request.method,
                    request.path,
                    str(exc)
                )
            
            # Получаем детальные сообщения от permission классов (рекурсивно из объектов AND/OR/NOT)
            if view and hasattr(view, 'get_permissions'):
                try:
                    permissions = view.get_permissions()

                    def _collect_permission_messages(perms) -> list[str]:
                        """
                        Оценивает объекты разрешений с учётом логики короткого замыкания
                        (AND/OR/NOT) и возвращает сообщения только от тех leaf-permission,
                        которые реально вернули False в ходе этой оценки.
                        """
                        messages: list[str] = []

                        def _evaluate(p) -> tuple[bool, list[str]]:
                            """Возвращает (passed, messages_from_failed_leaves).

                            Правила:
                            - Для OR: если левая ветвь прошла, правая не оценивается; если обе
                              не прошли — возвращаем сообщения обеих.
                            - Для AND: если левая ветвь не прошла, правая не оценивается; если
                              обе прошли — возвращаем True.
                            - Для NOT: успех, если внутренняя ветвь не прошла.
                            - Для листа (BasePermission) — вызываем has_permission и в случае
                              False возвращаем его сообщение (если есть).
                            """

                            # Определение имени класса оператора (AND/OR/NOT или другие)
                            cls_name = p.__class__.__name__

                            # Бинарные операторы (AND/OR)
                            if hasattr(p, 'op1') and hasattr(p, 'op2'):
                                # OR: короткое замыкание при True
                                if cls_name == 'OR':
                                    left_passed, left_msgs = _evaluate(p.op1)
                                    if left_passed:
                                        return True, []
                                    right_passed, right_msgs = _evaluate(p.op2)
                                    if right_passed:
                                        return True, []
                                    return False, left_msgs + right_msgs

                                # AND: короткое замыкание при False
                                if cls_name == 'AND':
                                    left_passed, left_msgs = _evaluate(p.op1)
                                    if not left_passed:
                                        return False, left_msgs
                                    right_passed, right_msgs = _evaluate(p.op2)
                                    if not right_passed:
                                        return False, right_msgs
                                    return True, []

                                # Неизвестный бинарный оператор — fallback: оценим по has_permission,
                                # если False — рекурсивно соберём сообщения из детей.
                                try:
                                    passed = bool(p.has_permission(request, view))
                                except Exception:
                                    passed = False
                                if passed:
                                    return True, []
                                # Собираем из детей
                                left_passed, left_msgs = _evaluate(p.op1)
                                right_passed, right_msgs = _evaluate(p.op2)
                                return False, left_msgs + right_msgs

                            # Унарный оператор (NOT / SingleOperand)
                            if hasattr(p, 'op1'):
                                if cls_name == 'NOT':
                                    child_passed, child_msgs = _evaluate(p.op1)
                                    # NOT возвращает True, если внутренняя ветвь вернула False
                                    if child_passed:
                                        return False, []
                                    return True, []

                                # Fallback для неизвестного унарного оператора
                                try:
                                    passed = bool(p.has_permission(request, view))
                                except Exception:
                                    passed = False
                                if passed:
                                    return True, []
                                child_passed, child_msgs = _evaluate(p.op1)
                                return False, child_msgs

                            # Leaf permission: обычный BasePermission
                            try:
                                passed = bool(p.has_permission(request, view))
                            except Exception:
                                passed = False
                            if passed:
                                return True, []
                            msg = getattr(p, 'message', None)
                            return False, [msg] if msg else []

                        for perm in perms:
                            try:
                                passed, msgs = _evaluate(perm)
                                # Сообщения возвращаем только для той top-level permission,
                                # которая первой вернула False (как делает DRF — первое
                                # отрицательное разрешение вызывает PermissionDenied).
                                if not passed:
                                    # Убираем дубликаты, сохраняя порядок
                                    return list(dict.fromkeys(msgs))
                                # Иначе продолжаем проверять следующую permission
                            except Exception:
                                logger.debug('Error evaluating permission object', exc_info=True)

                        return []

                    permission_messages = _collect_permission_messages(permissions)

                    if permission_messages:
                        # Используем последнее сообщение как основное (наиболее специфичное)
                        custom_response_data['detail'] = permission_messages[-1]
                        # Если сообщений несколько, добавляем их все для отладки
                        if len(permission_messages) > 1:
                            custom_response_data['permission_messages'] = permission_messages

                except Exception:
                    logger.exception("Error getting permission messages")
            
            # Если в исходном исключении есть детали, используем их
            if hasattr(exc, 'detail'):
                detail = exc.detail
                if isinstance(detail, str):
                    custom_response_data['detail'] = detail
                elif isinstance(detail, dict) and 'detail' in detail:
                    custom_response_data['detail'] = detail['detail']
            
            response.data = custom_response_data
        
        # Обрабатываем исключения аутентификации (401)
        elif response.status_code == 401:
            custom_response_data = {
                'error': 'authentication_required',
                'detail': 'Необходима аутентификация для доступа к этому ресурсу.',
                'status_code': response.status_code,
            }
            
            # Если в исходном исключении есть детали, используем их
            if hasattr(exc, 'detail'):
                detail = exc.detail
                if isinstance(detail, str):
                    custom_response_data['detail'] = detail
                elif isinstance(detail, dict) and 'detail' in detail:
                    custom_response_data['detail'] = detail['detail']
            
            response.data = custom_response_data
        
        # Обрабатываем внутренние ошибки сервера (500) когда response уже создан
        elif response.status_code == 500:
            custom_response_data = {
                'error': 'Internal Server Error',
                'status_code': 500,
            }
            
            # Проверяем, нужно ли показывать детали ошибки
            if request:
                show_details = _should_show_error_details(request)
                
                if show_details:
                    # Получаем информацию об ошибке
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    if exc_type:
                        custom_response_data.update({
                            'error_type': exc_type.__name__,
                            'error_message': str(exc_value) if exc_value else 'No details available',
                            'traceback': (''.join(traceback.format_tb(exc_traceback)) 
                                        if exc_traceback else 'No traceback available')
                        })
                        
                        # Логируем детальную ошибку
                        logger.error(
                            "Internal server error for user %s on %s %s: %s\n%s",
                            getattr(request.user, 'username', 'Anonymous'),
                            request.method,
                            request.path,
                            str(exc),
                            ''.join(traceback.format_tb(exc_traceback)) if exc_traceback else ''
                        )
                else:
                    # Логируем ошибку без деталей для обычных пользователей
                    logger.error(
                        "Internal server error for user %s on %s %s: %s",
                        getattr(request.user, 'username', 'Anonymous'),
                        request.method,
                        request.path,
                        str(exc)
                    )
            
            response.data = custom_response_data
        
        # Добавляем timestamp для всех ошибок
        if response.data and isinstance(response.data, dict) and 'timestamp' not in response.data:
            response.data['timestamp'] = timezone.now().isoformat()
    
    return response


def _should_show_error_details(request: HttpRequest) -> bool:
    """
    Определяет, следует ли показывать детали ошибки пользователю.
    
    Детали показываются если:
    1. Пользователь является администратором или суперпользователем
    2. Пользователь имеет специальные debug права
    3. Включен DEBUG режим
    """
    # В DEBUG режиме показываем детали всем
    if getattr(settings, 'DEBUG', False):
        return True
    
    # Проверяем, является ли пользователь администратором
    if request and hasattr(request, 'user') and request.user and request.user.is_authenticated:
        if hasattr(request.user, 'is_staff') and hasattr(request.user, 'is_superuser'):
            if request.user.is_staff or request.user.is_superuser:
                return True
        
        # Проверяем наличие debug permissions у пользователя
        if hasattr(request.user, 'has_perm'):
            if (request.user.has_perm('admin.debug') or 
                request.user.has_perm('authorization.admin_access')):
                return True
    
    # return False
    return True


def _is_api_request(request: HttpRequest) -> bool:
    """
    Проверяет, является ли запрос API-запросом, основываясь на заголовках и пути.
    
    Запрос считается API-запросом, если:
    1. Заголовок Accept содержит 'application/json'
    2. Заголовок Content-Type содержит 'application/json'
    3. Есть заголовок HTTP_X_REQUESTED_WITH со значением 'XMLHttpRequest' (AJAX)
    """
    accept_header = request.META.get('HTTP_ACCEPT', '')
    content_type = request.META.get('CONTENT_TYPE', '')
    requested_with = request.META.get('HTTP_X_REQUESTED_WITH', '')

    return (
        "application/json" in accept_header
        or "*/*" in accept_header
        or "application/json" in content_type
        or requested_with == "XMLHttpRequest"
    ) and "text/html" not in accept_header


@requires_csrf_token
def server_error(request: HttpRequest, exception: Exception = None):
    """
    Кастомный обработчик ошибок 500 для Django (не DRF).
    Отображает трейсбек ошибки в случае, если запрос идет от администратора
    или от авторизованного API-клиента с нужными правами.
    
    Для API-запросов возвращает JSON, для обычных запросов - HTML.
    """
    # Получаем информацию об ошибке из sys.exc_info()
    exc_type, exc_value, exc_traceback = sys.exc_info()
    error_info = None
    
    # Проверяем доступ к подробной информации об ошибке
    show_details = _should_show_error_details(request)
    
    # Формируем трейсбек для авторизованных пользователей с нужными правами
    if show_details and exc_traceback:
        error_info = {
            'type': exc_type.__name__ if exc_type else 'Unknown Error',
            'value': str(exc_value) if exc_value else 'No details available',
            'traceback': (''.join(traceback.format_tb(exc_traceback)) 
                         if exc_traceback else 'No traceback available')
        }
    
    # Определяем, является ли запрос API-запросом
    is_api_request = _is_api_request(request)
    
    if is_api_request:
        # Для API-запросов возвращаем JSON в том же формате, что и DRF
        error_response = {
            'error': 'Internal Server Error',
            'status_code': 500,
            'timestamp': timezone.now().isoformat()
        }
        
        # Добавляем детали ошибки, если доступны
        if error_info:
            error_response.update({
                'error_type': error_info['type'],
                'error_message': error_info['value'],
                'traceback': error_info['traceback']
            })
        
        return JsonResponse(error_response, status=500)
    
    # Для обычных запросов возвращаем HTML
    context = {
        'error_info': error_info,
        'debug': settings.DEBUG,
    }
    
    html = render_to_string('500.html', context, request)
    return HttpResponse(html, status=500)
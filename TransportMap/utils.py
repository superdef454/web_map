from django.contrib.gis.gdal import GDALException
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.geos.error import GEOSException
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework_gis.fields import GeometryField


class GeometryValidationError(Exception):
    """Кастомное исключение для ошибок валидации геометрии с детальными сообщениями."""


class ValidatedGeometryField(GeometryField):
    """
    Универсальное геометрическое поле с валидацией и понятными сообщениями об ошибках.
    
    Проверяет корректность геометрических данных и возвращает информативные
    сообщения об ошибках вместо технических деталей GEOS.
    """
    
    default_error_messages = {
        'invalid_geometry': 'Поле "{field_name}" указано неверно. '
                           'Ожидался корректный геометрический объект в формате WKT, EWKT, GeoJSON или HEXEWKB.',
        'invalid_wkt': 'Поле "{field_name}" содержит некорректный WKT. '
                      'Пример корректного формата: "POINT(30 10)" или "POLYGON((30 10, 40 40, 20 40, 10 20, 30 10))"',
        'invalid_geojson': 'Поле "{field_name}" содержит некорректный GeoJSON. '
                          'Пример: {{"type": "Point", "coordinates": [30, 10]}}',
        'empty_geometry': 'Поле "{field_name}" не может быть пустым.',
        'unsupported_type': 'Поле "{field_name}" содержит неподдерживаемый тип геометрии: {geom_type}. '
                           'Поддерживаемые типы: Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon',
    }
    
    def __init__(self, **kwargs):
        # Получаем имя поля для использования в сообщениях об ошибках
        self.field_name = kwargs.pop('field_name', None)
        super().__init__(**kwargs)
    
    def bind(self, field_name, parent):
        """Автоматически получаем имя поля при привязке к сериализатору."""
        super().bind(field_name, parent)
        if not self.field_name:
            self.field_name = field_name
    
    def to_internal_value(self, value):
        """
        Преобразует входное значение в геометрический объект с валидацией.
        """
        if value is None or value == '':
            if self.required:
                self.fail('empty_geometry', field_name=self.field_name or 'geometry')
            return None
        
        try:
            # Пытаемся создать геометрический объект
            if isinstance(value, dict):
                # Обрабатываем GeoJSON
                geometry = self._parse_geojson(value)
            elif isinstance(value, str):
                # Обрабатываем WKT/EWKT/HEXEWKB
                geometry = self._parse_string_geometry(value)
            else:
                # Пытаемся использовать стандартную обработку
                geometry = super().to_internal_value(value)
            
            # Дополнительная валидация геометрии
            self._validate_geometry(geometry)
            
            return geometry
            
        except ValidationError:
            # Повторно поднимаем ValidationError без изменений
            raise
        except (GEOSException, GDALException, ValueError, TypeError) as e:
            # Обрабатываем ошибки GEOS, GDAL и другие
            self._handle_geometry_error(value, e)
    
    def _parse_geojson(self, value):
        """Парсит GeoJSON с детальными сообщениями об ошибках."""
        try:
            # Дополнительная валидация GeoJSON структуры
            if isinstance(value, dict):
                self._validate_geojson_structure(value)
            
            return GEOSGeometry(str(value))
        except GeometryValidationError as e:
            # Наше кастомное исключение с детальным сообщением
            raise ValidationError(
                f'Поле "{self.field_name or "geometry"}": {str(e)}'
            )
        except ValueError as e:
            # ValueError из _validate_geojson_structure или других проверок
            raise ValidationError(
                f'Поле "{self.field_name or "geometry"}" содержит некорректный GeoJSON. {str(e)}'
            )
        except (GEOSException, GDALException, TypeError) as e:
            # Остальные ошибки GEOS/GDAL - используем стандартное сообщение
            self.fail('invalid_geojson', field_name=self.field_name or 'geometry')
    
    def _validate_geojson_structure(self, geojson_dict):
        """Валидация структуры GeoJSON перед обработкой GEOS."""
        if not isinstance(geojson_dict, dict):
            raise GeometryValidationError("GeoJSON должен быть объектом")
        
        geom_type = geojson_dict.get('type')
        coordinates = geojson_dict.get('coordinates')
        
        if not geom_type:
            raise GeometryValidationError("Отсутствует обязательное поле 'type' в GeoJSON")
        
        if coordinates is None:
            raise GeometryValidationError("Отсутствует обязательное поле 'coordinates' в GeoJSON")
        
        # Специальная проверка для Point
        if geom_type == 'Point':
            if not isinstance(coordinates, list) or len(coordinates) < 2:
                raise GeometryValidationError("Координаты точки должны содержать минимум 2 элемента [longitude, latitude]")
            
            # Проверяем, что все координаты - числа
            for i, coord in enumerate(coordinates[:2]):  # Проверяем только первые 2 координаты
                if not isinstance(coord, (int, float)):
                    coord_name = "долготы" if i == 0 else "широты"
                    raise GeometryValidationError(f"Некорректное значение {coord_name}: '{coord}'. Ожидается число с точкой как десятичным разделителем, например: 48.5178")
            
            # Предупреждение о 3D координатах, если их больше 2
            if len(coordinates) > 2:
                raise GeometryValidationError("База данных не поддерживает 3D координаты. Используйте только [longitude, latitude] и точку как десятичный разделитель.")
            
            # Проверяем разумные диапазоны координат
            longitude, latitude = coordinates[0], coordinates[1]
            if not (-180 <= longitude <= 180):
                raise GeometryValidationError(f"Долгота должна быть в диапазоне [-180, 180], получено: {longitude}")
            if not (-90 <= latitude <= 90):
                raise GeometryValidationError(f"Широта должна быть в диапазоне [-90, 90], получено: {latitude}")
    
    def _parse_string_geometry(self, value):
        """Парсит строковое представление геометрии."""
        try:
            return GEOSGeometry(value)
        except (GEOSException, GDALException, ValueError, TypeError) as e:
            # Проверяем, похоже ли на WKT
            if any(geom_type in value.upper() for geom_type in 
                   ['POINT', 'LINESTRING', 'POLYGON', 'MULTIPOINT', 'MULTILINESTRING', 'MULTIPOLYGON']):
                self.fail('invalid_wkt', field_name=self.field_name or 'geometry')
            else:
                self.fail('invalid_geometry', field_name=self.field_name or 'geometry')
    
    def _validate_geometry(self, geometry):
        """Дополнительная валидация геометрического объекта."""
        if geometry is None:
            return
        
        # Проверяем, что геометрия валидна
        if not geometry.valid:
            raise ValidationError(
                f'Поле "{self.field_name or "geometry"}" содержит невалидную геометрию. '
                f'Причина: {geometry.valid_reason if hasattr(geometry, "valid_reason") else "неизвестная ошибка"}'
            )
        
        # Проверяем поддерживаемые типы геометрии (опционально)
        supported_types = getattr(self, 'supported_geom_types', None)
        if supported_types and geometry.geom_type not in supported_types:
            self.fail('unsupported_type', 
                     field_name=self.field_name or 'geometry',
                     geom_type=geometry.geom_type)
    
    def _handle_geometry_error(self, value, original_error):
        """Обрабатывает ошибки геометрии и возвращает понятные сообщения."""
        error_str = str(original_error).lower()
        
        # Специальные проверки для частых ошибок
        if 'z dimension' in error_str and 'column does not' in error_str:
            raise ValidationError(
                f'Поле "{self.field_name or "geometry"}" содержит 3D координаты, но база данных поддерживает только 2D. '
                f'Убедитесь, что координаты содержат только [longitude, latitude] и используют точку как десятичный разделитель.'
            )
        
        # Анализируем тип ошибки для более точного сообщения
        if 'wkt' in error_str or 'well-known text' in error_str:
            self.fail('invalid_wkt', field_name=self.field_name or 'geometry')
        elif 'geojson' in error_str or 'json' in error_str or 'ogr_g_creategeometryfromjson' in error_str:
            self.fail('invalid_geojson', field_name=self.field_name or 'geometry')
        elif 'hexewkb' in error_str or 'hex' in error_str:
            raise ValidationError(
                f'Поле "{self.field_name or "geometry"}" содержит некорректный HEXEWKB формат.'
            )
        else:
            self.fail('invalid_geometry', field_name=self.field_name or 'geometry')


# Специализированные поля для конкретных типов геометрии
class ValidatedPointField(ValidatedGeometryField):
    """Поле для точек с валидацией."""
    
    def __init__(self, **kwargs):
        kwargs.setdefault('field_name', 'coordinates')
        super().__init__(**kwargs)
        self.supported_geom_types = ['Point']
    
    default_error_messages = {
        **ValidatedGeometryField.default_error_messages,
        'invalid_wkt': 'Поле "{field_name}" содержит некорректные координаты точки. '
                      'Пример корректного формата: "POINT(30 10)" или "POINT(долгота широта)"',
        'invalid_geometry': 'Поле "{field_name}" содержит некорректные координаты точки. '
                      'Пример корректного формата: "POINT(30 10)" или "POINT(долгота широта)"',
        'invalid_geojson': 'Поле "{field_name}" содержит некорректный GeoJSON для точки. '
                          'Пример: {{"type": "Point", "coordinates": [30.311, 10.133]}}. '
                          'Убедитесь, что координаты содержат только [longitude, latitude] и используют точку как десятичный разделитель.',
    }


class ValidatedPolygonField(ValidatedGeometryField):
    """Поле для полигонов с валидацией."""
    
    def __init__(self, **kwargs):
        kwargs.setdefault('field_name', 'polygon')
        super().__init__(**kwargs)
        self.supported_geom_types = ['Polygon', 'MultiPolygon']
    
    default_error_messages = {
        **ValidatedGeometryField.default_error_messages,
        'invalid_wkt': 'Поле "{field_name}" содержит некорректный полигон. '
                      'Пример: "POLYGON((30 10, 40 40, 20 40, 10 20, 30 10))" - '
                      'первая и последняя точки должны совпадать',
        'invalid_geojson': 'Поле "{field_name}" содержит некорректный GeoJSON для полигона. '
                          'Пример: {{"type": "Polygon", "coordinates": [[[30,10],[40,40],[20,40],[10,20],[30,10]]]}}',
    }


class ValidatedDjangoFilterBackend(DjangoFilterBackend):
    """
    Универсальный класс для валидации параметров фильтрации.
    
    Проверяет, что переданные параметры фильтрации входят в список разрешенных полей,
    и возвращает ошибку 400 с описанием доступных полей при использовании неподдерживаемых параметров.
    Также включает валидацию булевых значений.
    """
    
    VALID_BOOLEAN_VALUES = {
        'true': True, 'false': False,
        '1': True, '0': False,
        'yes': True, 'no': False,
        'on': True, 'off': False,
    }
    
    # Кеш для булевых полей моделей - избегаем повторного анализа
    _boolean_fields_cache = {}
    
    def filter_queryset(self, request, queryset, view):
        """
        Фильтрует queryset с валидацией параметров фильтрации, включая булевые поля.
        """
        # Сначала проверяем параметры фильтрации
        self.validate_filter_params(request, view)
        
        # Затем проверяем булевые значения
        self.validate_boolean_params(request, view)
        
        # Если все параметры валидны, выполняем стандартную фильтрацию
        return super().filter_queryset(request, queryset, view)
    
    def validate_filter_params(self, request, view):
        """
        Проверяет, что все параметры фильтрации поддерживаются.
        """
        filterset_fields = getattr(view, 'filterset_fields', {})
        if not filterset_fields:
            return
        
        # Получаем все поддерживаемые параметры фильтрации
        supported_params = set()
        
        if isinstance(filterset_fields, dict):
            for field, lookups in filterset_fields.items():
                supported_params.add(field)
                if isinstance(lookups, list):
                    for lookup in lookups:
                        supported_params.add(f"{field}__{lookup}")
        elif isinstance(filterset_fields, list):
            supported_params.update(filterset_fields)
        
        # Добавляем стандартные параметры, которые не относятся к фильтрации
        standard_params = {
            'page', 'page_size', 'search', 'ordering',
            'limit', 'offset', 'format'
        }
        supported_params.update(standard_params)
        
        # Получаем поля поиска если они есть
        search_fields = getattr(view, 'search_fields', [])
        if search_fields:
            supported_params.add('search')
        
        # Получаем поля сортировки если они есть
        ordering_fields = getattr(view, 'ordering_fields', [])
        if ordering_fields:
            supported_params.add('ordering')
        
        # Проверяем неподдерживаемые параметры
        unsupported_params = []
        
        # Получаем query parameters - поддерживаем и Django request, и DRF request
        query_params = getattr(request, 'query_params', None) or getattr(request, 'GET', {})
        
        for param in query_params:
            if param not in supported_params:
                unsupported_params.append(param)
        
        if unsupported_params:
            # Формируем список доступных параметров фильтрации (исключаем стандартные)
            filter_params = supported_params - standard_params
            available_filters = ', '.join(sorted(filter_params)) if filter_params else 'нет доступных фильтров'
            
            raise ValidationError({
                'filter_params': [
                    f"Неподдерживаемые параметры: {', '.join(unsupported_params)}. "
                    f"Доступные параметры фильтрации: {available_filters}"
                ]
            })
    
    def validate_boolean_params(self, request, view):
        """
        Проверяет корректность булевых значений в параметрах запроса.
        """
        filterset_fields = getattr(view, 'filterset_fields', {})
        if not filterset_fields:
            return
        
        # Получаем модель для определения типов полей
        model = self._get_model_from_view(view)
        if not model:
            return
        
        # Собираем информацию о булевых полях с кешированием
        boolean_fields = self._get_boolean_fields_cached(model, filterset_fields)
        
        # Если нет булевых полей, пропускаем валидацию
        if not boolean_fields:
            return
        
        # Проверяем значения булевых полей в параметрах запроса
        errors = {}
        
        # Получаем query parameters - поддерживаем и Django request, и DRF request
        query_params = getattr(request, 'query_params', None) or getattr(request, 'GET', {})
        
        for param_name, value in query_params.items():
            if param_name in boolean_fields and not self._is_valid_boolean_value(value):
                field_name = boolean_fields[param_name]
                errors[param_name] = [
                    f"Некорректное значение для булевого поля '{field_name}': '{value}'. "
                    f"Допустимые значения: true, false, 1, 0, yes, no, on, off (регистр не важен)."
                ]
        
        if errors:
            raise ValidationError(errors)
    
    def _get_model_from_view(self, view):
        """Получает модель из view."""
        if hasattr(view, 'queryset') and view.queryset is not None:
            return view.queryset.model
        if hasattr(view, 'model'):
            return view.model
        return None
    
    def _get_boolean_fields_cached(self, model, filterset_fields):
        """
        Возвращает словарь с булевыми полями с кешированием для улучшения производительности.
        """
        # Создаем ключ для кеша на основе модели и filterset_fields
        cache_key = (
            model.__name__,
            str(sorted(filterset_fields.items()) if isinstance(filterset_fields, dict) else sorted(filterset_fields))
        )
        
        # Проверяем кеш
        if cache_key in self._boolean_fields_cache:
            return self._boolean_fields_cache[cache_key]
        
        # Если нет в кеше, вычисляем и кешируем
        boolean_fields = self._get_boolean_fields(model, filterset_fields)
        self._boolean_fields_cache[cache_key] = boolean_fields
        
        # Ограничиваем размер кеша (избегаем утечек памяти)
        if len(self._boolean_fields_cache) > 200:
            # Удаляем половину записей (простая стратегия)
            keys_to_remove = list(self._boolean_fields_cache.keys())[:100]
            for key in keys_to_remove:
                del self._boolean_fields_cache[key]
        
        return boolean_fields
    
    def _get_boolean_fields(self, model, filterset_fields):
        """
        Возвращает словарь с булевыми полями и их параметрами фильтрации.
        """
        boolean_fields = {}
        
        # Получаем все булевые поля модели
        model_boolean_fields = {}
        for field in model._meta.get_fields():
            if hasattr(field, 'get_internal_type') and field.get_internal_type() == 'BooleanField':
                model_boolean_fields[field.name] = field.name
        
        # Обрабатываем filterset_fields в зависимости от типа
        if isinstance(filterset_fields, dict):
            for field_name, lookups in filterset_fields.items():
                base_field_name = field_name.split('__')[0]
                final_field_name = field_name.split('__')[-1]
                
                # Если это булевое поле с exact lookup или без указания lookups
                if (base_field_name in model_boolean_fields or final_field_name in model_boolean_fields) and \
                   ((isinstance(lookups, list) and 'exact' in lookups) or not isinstance(lookups, list)):
                    boolean_fields[field_name] = field_name
                
                # Проверяем связанные модели
                if '__' in field_name:
                    self._check_related_boolean_fields(model, field_name, boolean_fields)
        
        elif isinstance(filterset_fields, list):
            for field_name in filterset_fields:
                if field_name in model_boolean_fields:
                    boolean_fields[field_name] = field_name
                elif '__' in field_name:
                    self._check_related_boolean_fields(model, field_name, boolean_fields)
        
        return boolean_fields
    
    def _check_related_boolean_fields(self, model, field_name, boolean_fields):
        """Проверяет булевые поля в связанных моделях."""
        try:
            field_parts = field_name.split('__')
            current_model = model
            
            # Проходим по всем частям пути к полю
            for part in field_parts[:-1]:
                field = current_model._meta.get_field(part)
                if hasattr(field, 'related_model'):
                    current_model = field.related_model
                else:
                    return
            
            # Проверяем последнее поле
            final_field_name = field_parts[-1]
            try:
                final_field = current_model._meta.get_field(final_field_name)
                if hasattr(final_field, 'get_internal_type') and final_field.get_internal_type() == 'BooleanField':
                    boolean_fields[field_name] = field_name
            except Exception:
                pass
        except Exception:
            pass
    
    def _is_valid_boolean_value(self, value):
        """Проверяет, является ли значение валидным булевым значением."""
        if isinstance(value, bool):
            return True
        
        if isinstance(value, str):
            return value.lower() in self.VALID_BOOLEAN_VALUES
        
        return False


class ValidatedOrderingFilter(filters.OrderingFilter):
    """
    Универсальный класс для валидации полей сортировки.
    
    Проверяет, что переданные поля для сортировки входят в список разрешенных полей,
    и возвращает ошибку 400 с описанием доступных полей при использовании недопустимого поля.
    """
    
    def get_ordering(self, request, queryset, view):
        """
        Переопределяем get_ordering для валидации полей до их обработки.
        """
        # Получаем ordering параметр из запроса
        # Поддерживаем и Django request, и DRF request
        query_params = getattr(request, 'query_params', None) or getattr(request, 'GET', {})
        ordering_param = query_params.get(self.ordering_param)
        if not ordering_param:
            return self.get_default_ordering(view)
        
        # Разбираем ordering параметр на отдельные поля
        fields = [param.strip() for param in ordering_param.split(',')]
        
        # Получаем список разрешенных полей для сортировки из view
        ordering_fields = getattr(view, 'ordering_fields', [])
        
        if ordering_fields == '__all__':
            # Если разрешены все поля, получаем их из модели
            if hasattr(view, 'queryset') and view.queryset is not None:
                model = view.queryset.model
                ordering_fields = [field.name for field in model._meta.fields]
            else:
                ordering_fields = []
        
        # Проверяем каждое поле
        for field_name in fields:
            if not field_name:  # Пропускаем пустые поля
                continue
                
            # Убираем префикс '-' для проверки
            clean_field_name = field_name.removeprefix('-')
            
            if clean_field_name not in ordering_fields:
                available_fields = ', '.join(sorted(ordering_fields))
                raise ValidationError({
                    'ordering': [
                        f"Недопустимое поле для сортировки: '{clean_field_name}'. "
                        f"Доступные поля: {available_fields}"
                    ]
                })
        
        # Если все поля валидны, возвращаем их для дальнейшей обработки
        return fields
    
    def filter_queryset(self, request, queryset, view):
        """
        Фильтрует queryset с уже проверенными полями сортировки.
        """
        ordering = self.get_ordering(request, queryset, view)
        
        if ordering:
            return queryset.order_by(*ordering)
        
        return queryset


class ValidatedPageNumberPagination(PageNumberPagination):
    """
    Универсальный класс для валидации параметров пагинации.
    
    Проверяет корректность параметров page и page_size,
    и возвращает ошибку 400 с подробным описанием при некорректных значениях.
    """
    
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 500
    
    def get_page_number(self, request, paginator):
        """
        Переопределяем получение номера страницы с валидацией.
        """
        # Поддерживаем и Django request, и DRF request
        query_params = getattr(request, 'query_params', None) or getattr(request, 'GET', {})
        page_number = query_params.get(self.page_query_param, 1)
        
        # Валидация параметра page
        if page_number != 1:  # Если не дефолтное значение
            try:
                page_number = int(page_number)
            except (TypeError, ValueError):
                page_param_value = query_params.get(self.page_query_param)
                raise ValidationError({
                    'page': [
                        f"Неверный формат номера страницы: '{page_param_value}'. "
                        f"Ожидается положительное целое число."
                    ]
                })
            
            if page_number < 1:
                raise ValidationError({
                    'page': [
                        f"Номер страницы должен быть больше 0, получено: {page_number}"
                    ]
                })
        
        return page_number
    
    def get_page_size(self, request):
        """
        Переопределяем получение размера страницы с валидацией.
        """
        if self.page_size_query_param:
            # Поддерживаем и Django request, и DRF request
            query_params = getattr(request, 'query_params', None) or getattr(request, 'GET', {})
            page_size_param = query_params.get(self.page_size_query_param)
            
            if page_size_param is not None:
                try:
                    page_size = int(page_size_param)
                except (TypeError, ValueError):
                    raise ValidationError({
                        'page_size': [
                            f"Неверный формат размера страницы: '{page_size_param}'. "
                            f"Ожидается положительное целое число."
                        ]
                    })
                
                if page_size < 1:
                    raise ValidationError({
                        'page_size': [
                            f"Размер страницы должен быть больше 0, получено: {page_size}"
                        ]
                    })
                
                if self.max_page_size and page_size > self.max_page_size:
                    raise ValidationError({
                        'page_size': [
                            f"Размер страницы превышает максимально допустимый. "
                            f"Максимум: {self.max_page_size}, получено: {page_size}"
                        ]
                    })
                
                return page_size
        
        return self.page_size
    
    def paginate_queryset(self, queryset, request, view=None):
        """
        Переопределяем основной метод пагинации с нашей валидацией.
        """
        # Сначала валидируем параметры
        page_size = self.get_page_size(request)
        if not page_size:
            return None
        
        paginator = self.django_paginator_class(queryset, page_size)
        page_number = self.get_page_number(request, paginator)
        
        # Проверяем, что номер страницы не превышает общее количество страниц
        if page_number > paginator.num_pages and paginator.num_pages > 0:
            raise ValidationError({
                'page': [
                    f"Номер страницы {page_number} превышает общее количество страниц ({paginator.num_pages}). "
                    f"Доступные страницы: 1-{paginator.num_pages}"
                ]
            })
        
        try:
            self.page = paginator.page(page_number)
        except Exception as exc:
            # Перехватываем любые другие ошибки пагинации и превращаем в ValidationError
            raise ValidationError({
                'page': [
                    f"Ошибка получения страницы {page_number}: {str(exc)}"
                ]
            })
        
        if paginator.num_pages > 1 and self.template is not None:
            # The browsable API should display pagination controls.
            self.display_page_controls = True
        
        self.request = request
        return list(self.page)


class ValidatedSearchFilter(filters.SearchFilter):
    """
    Переопределяем фильтр поиска с требуемой логикой.
    """
    search_description = _("Фильтр поиска по полям (Частичное вхождение).")
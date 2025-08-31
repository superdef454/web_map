from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from drf_spectacular.utils import extend_schema_field
from .models import City, TC, BusStop, Route, EI, District


class CitySerializer(serializers.ModelSerializer):
    """Сериализатор для модели City"""
    
    class Meta:
        model = City
        fields = ['id', 'name', 'latitude', 'longitude']
        
    def validate_latitude(self, value):
        if not (-90 <= value <= 90):
            raise serializers.ValidationError('Широта должна быть в пределах от -90 до 90.')
        return value
        
    def validate_longitude(self, value):
        if not (-180 <= value <= 180):
            raise serializers.ValidationError('Долгота должна быть в пределах от -180 до 180.')
        return value


class TCSerializer(serializers.ModelSerializer):
    """Сериализатор для модели TC (Тип транспортного средства)"""
    
    class Meta:
        model = TC
        fields = ['id', 'name', 'capacity', 'description']
        
    def validate_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError('Вместимость должна быть больше нуля.')
        return value


class BusStopSerializer(serializers.ModelSerializer):
    """Сериализатор для модели BusStop"""
    city_name = serializers.CharField(source='city.name', read_only=True)
    routes_count = serializers.SerializerMethodField()
    
    class Meta:
        model = BusStop
        fields = [
            'id', 'name', 'latitude', 'longitude', 
            'city', 'city_name', 'routes_count'
        ]
    
    def get_routes_count(self, obj) -> int:
        """Возвращает количество маршрутов, проходящих через остановку"""
        return obj.route_set.count()
        
    def validate_latitude(self, value):
        if not (-90 <= float(value) <= 90):
            raise serializers.ValidationError('Широта должна быть в пределах от -90 до 90.')
        return value
        
    def validate_longitude(self, value):
        if not (-180 <= float(value) <= 180):
            raise serializers.ValidationError('Долгота должна быть в пределах от -180 до 180.')
        return value


class BusStopGeoSerializer(GeoFeatureModelSerializer):
    """GeoJSON сериализатор для остановок с географическими данными"""
    city_name = serializers.CharField(source='city.name', read_only=True)
    
    class Meta:
        model = BusStop
        geo_field = 'coordinates'
        fields = ['id', 'name', 'city', 'city_name']
        
    def to_representation(self, instance):
        """Преобразует координаты в формат GeoJSON Point"""
        ret = super().to_representation(instance)
        # Создаем Point из latitude и longitude
        ret['geometry'] = {
            'type': 'Point',
            'coordinates': [float(instance.longitude), float(instance.latitude)]
        }
        return ret


class RouteDetailSerializer(serializers.ModelSerializer):
    """Детальный сериализатор для маршрута с остановками"""
    city_name = serializers.CharField(source='city.name', read_only=True)
    tc_name = serializers.CharField(source='tc.name', read_only=True)
    busstops = serializers.SerializerMethodField()
    busstops_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Route
        fields = [
            'id', 'name', 'city', 'city_name', 'tc', 'tc_name',
            'interval', 'amount', 'list_coord', 
            'busstops', 'busstops_count'
        ]
    
    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_busstops(self, obj):
        """Возвращает список остановок на маршруте"""
        busstops = obj.busstop.all()
        return [
            {
                'id': bs.id,
                'name': bs.name,
                'latitude': bs.latitude,
                'longitude': bs.longitude,
                'city': bs.city.id,
                'city_name': bs.city.name,
            }
            for bs in busstops
        ]
        
    def get_busstops_count(self, obj) -> int:
        """Возвращает количество остановок на маршруте"""
        return obj.busstop.count()


class RouteSerializer(serializers.ModelSerializer):
    """Базовый сериализатор для маршрута"""
    city_name = serializers.CharField(source='city.name', read_only=True)
    tc_name = serializers.CharField(source='tc.name', read_only=True)
    busstops_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Route
        fields = [
            'id', 'name', 'city', 'city_name', 'tc', 'tc_name',
            'interval', 'amount', 'list_coord', 'busstops_count'
        ]
    
    def get_busstops_count(self, obj) -> int:
        """Возвращает количество остановок на маршруте"""
        return obj.busstop.count()
        
    def validate_interval(self, value):
        if value <= 0:
            raise serializers.ValidationError('Интервал движения должен быть больше нуля.')
        return value
        
    def validate_amount(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError('Количество транспорта должно быть больше нуля.')
        return value


class RouteCreateUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления маршрута"""
    busstop_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="Список ID остановок для маршрута"
    )
    
    class Meta:
        model = Route
        fields = [
            'id', 'name', 'city', 'tc', 'interval', 
            'amount', 'list_coord', 'busstop_ids'
        ]
        
    def create(self, validated_data):
        busstop_ids = validated_data.pop('busstop_ids', [])
        route = Route.objects.create(**validated_data)
        
        if busstop_ids:
            busstops = BusStop.objects.filter(id__in=busstop_ids)
            route.busstop.set(busstops)
            
        return route
        
    def update(self, instance, validated_data):
        busstop_ids = validated_data.pop('busstop_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if busstop_ids is not None:
            busstops = BusStop.objects.filter(id__in=busstop_ids)
            instance.busstop.set(busstops)
            
        return instance


class EISerializer(serializers.ModelSerializer):
    """Сериализатор для модели EI (Единица измерения)"""
    
    class Meta:
        model = EI
        fields = ['id', 'name', 'short_name']


class DistrictSerializer(serializers.ModelSerializer):
    """Сериализатор для модели District"""
    city_name = serializers.CharField(source='city.name', read_only=True)
    
    class Meta:
        model = District
        fields = [
            'id', 'name', 'city', 'city_name', 
            'polygon', 'description'
        ]


class DistrictGeoSerializer(GeoFeatureModelSerializer):
    """Геосериализатор для модели District для работы с картами"""
    city_name = serializers.CharField(source='city.name', read_only=True)
    
    class Meta:
        model = District
        geo_field = 'polygon'
        fields = [
            'id', 'name', 'city', 'city_name', 'description'
        ]


class CalculationRequestSerializer(serializers.Serializer):
    """Сериализатор для запроса расчета нагрузки транспортной сети"""
    
    DataToCalculate = serializers.JSONField(
        help_text="Данные для расчета нагрузки в формате JSON. "
                  "Должны содержать информацию о маршрутах, остановках, "
                  "параметрах транспортных средств и временных интервалах."
    )
    
    def validate_data_to_calculate(self, value):
        """Валидация данных для расчета"""
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "DataToCalculate должно быть JSON-объектом"
            )
        
        # Проверяем наличие обязательных полей
        required_fields = ['routes', 'transport_params']
        for field in required_fields:
            if field not in value:
                error_msg = f"Отсутствует обязательное поле: {field}"
                raise serializers.ValidationError(error_msg)
        
        return value


class CalculationResultDataSerializer(serializers.Serializer):
    """Сериализатор для данных результата расчета"""
    
    route_id = serializers.IntegerField(help_text="ID маршрута")
    route_name = serializers.CharField(help_text="Название маршрута")
    load_factor = serializers.FloatField(help_text="Коэффициент загрузки")
    passenger_flow = serializers.IntegerField(help_text="Пассажиропоток")
    vehicle_count = serializers.IntegerField(help_text="Количество транспортных средств")
    interval = serializers.FloatField(help_text="Интервал движения в минутах")


class ReportDataSerializer(serializers.Serializer):
    """Сериализатор для данных отчета"""
    
    calculation_date = serializers.DateTimeField(help_text="Дата и время расчета")
    total_routes = serializers.IntegerField(help_text="Общее количество маршрутов")
    avg_load_factor = serializers.FloatField(help_text="Средний коэффициент загрузки")
    total_passenger_flow = serializers.IntegerField(help_text="Общий пассажиропоток")
    routes_data = CalculationResultDataSerializer(
        many=True, 
        help_text="Детальные данные по каждому маршруту"
    )


class CalculationResponseSerializer(serializers.Serializer):
    """Сериализатор для ответа на запрос расчета нагрузки"""
    
    error = serializers.IntegerField(
        help_text="Код ошибки (0 - успех, 1 - ошибка данных, 2 - ошибка расчета)"
    )
    error_message = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Сообщение об ошибке (если error != 0)"
    )
    calculate = CalculationResultDataSerializer(
        many=True,
        required=False,
        help_text="Результаты расчета по маршрутам"
    )
    data_to_report = ReportDataSerializer(
        required=False,
        help_text="Данные для формирования отчета"
    )
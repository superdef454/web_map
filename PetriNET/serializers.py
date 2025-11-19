from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .models import EI, TC, BusStop, City, District, Route, Simulation


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
            'interval', 'amount', 'list_coord', 'list_coord_to_render',
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
            'interval', 'amount', 'list_coord', 'list_coord_to_render', 'busstops_count'
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
            'amount', 'list_coord', 'list_coord_to_render', 'busstop_ids'
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


class RouteCalculationDataSerializer(serializers.Serializer):
    """Сериализатор для данных маршрута в расчете"""
    id = serializers.IntegerField(help_text="ID маршрута")
    name = serializers.CharField(max_length=255, help_text="Название маршрута")


class BusStopDirectionSerializer(serializers.Serializer):
    """Сериализатор для направления пассажиров с остановки"""
    busstop_id = serializers.IntegerField(help_text="ID остановки назначения")
    passengers_count = serializers.IntegerField(
        min_value=0, 
        help_text="Количество пассажиров, направляющихся к данной остановке"
    )


class BusStopCalculationDataSerializer(serializers.Serializer):
    """Сериализатор для данных остановки в расчете"""
    busstop_id = serializers.IntegerField(help_text="ID остановки")
    passengers_without_direction = serializers.IntegerField(
        default=0,
        min_value=0,
        help_text="Количество пассажиров без определенного направления"
    )
    directions = BusStopDirectionSerializer(
        many=True,
        required=False,
        help_text="Направления пассажиров с данной остановки"
    )


class CalculationDataSerializer(serializers.Serializer):
    """Сериализатор для основных данных расчета"""
    city_id = serializers.IntegerField(help_text="ID города")
    routes = RouteCalculationDataSerializer(
        many=True,
        help_text="Список маршрутов для расчета"
    )
    busstops = serializers.DictField(
        child=BusStopCalculationDataSerializer(),
        help_text="Данные остановок, где ключ - ID остановки"
    )
    
    def validate_routes(self, value):
        """Валидация маршрутов"""
        if not value:
            error_msg = "Список маршрутов не может быть пустым"
            raise serializers.ValidationError(error_msg)
        return value
    
    def validate_city_id(self, value):
        """Валидация ID города"""
        if not City.objects.filter(id=value).exists():
            error_msg = f"Город с ID {value} не найден"
            raise serializers.ValidationError(error_msg)
        return value


class CalculationRequestSerializer(serializers.Serializer):
    """Сериализатор для запроса расчета нагрузки транспортной сети"""
    
    data_to_calculate = CalculationDataSerializer(
        help_text="Данные для расчета нагрузки"
    )
    get_timeline = serializers.BooleanField(
        default=True,
        help_text="Флаг для возвращения временной шкалы с имитацией работы транспортной сети"
    )


class BusStopReportSerializer(serializers.Serializer):
    """Сериализатор для данных остановки в отчете"""
    bus_name = serializers.CharField(help_text="Название остановки")
    passengers_count = serializers.IntegerField(help_text="Количество пассажиров")
    max_waiting_time = serializers.IntegerField(
        required=False,
        help_text="Максимальное время ожидания в минутах"
    )
    routes_count = serializers.CharField(
        required=False,
        help_text="Количество маршрутов"
    )


class RouteReportSerializer(serializers.Serializer):
    """Сериализатор для данных маршрута в отчете"""
    name = serializers.CharField(help_text="Название маршрута")
    TC = serializers.CharField(required=False, help_text="Тип транспортного средства")
    interval = serializers.FloatField(help_text="Интервал движения в минутах")
    average_passengers_stops_count = serializers.FloatField(
        help_text="Средняя длительность пути пассажиров (кол-во ОП)"
    )
    average_fullness = serializers.CharField(help_text="Средняя наполненность автобусов")
    bus_stop_count = serializers.IntegerField(help_text="Количество остановок")
    route_length = serializers.FloatField(help_text="Протяжённость маршрута в км")
    TC_count = serializers.IntegerField(
        required=False,
        help_text="Количество автобусов на маршруте"
    )


class ReportDataSerializer(serializers.Serializer):
    """Сериализатор для данных отчета"""
    city_name = serializers.CharField(help_text="Название города")
    data = serializers.CharField(help_text="Дата и время расчета")
    bus_stops = BusStopReportSerializer(
        many=True,
        required=False,
        help_text="Данные по остановкам"
    )
    routes = RouteReportSerializer(
        many=True,
        required=False,
        help_text="Данные по маршрутам"
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
    calculate = serializers.ListField(
        required=False,
        help_text="Временная шкала расчета (список кортежей: время, данные)"
    )
    data_to_report = ReportDataSerializer(
        required=False,
        help_text="Данные для формирования отчета"
    )
    simulation_id = serializers.IntegerField(
        required=False,
        help_text="ID симуляции в базе (если есть)"
    )


class SimulationSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Simulation"""
    
    class Meta:
        model = Simulation
        fields = [
            'id', 
            'created_at', 
            'input_data', 
            'report_data', 
            'description',
        ]
        read_only_fields = ['id', 'created_at']
from decimal import Decimal

from django.contrib.gis.db import models as gis_models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.forms import ValidationError


def validate_latitude(value):
    if not (-90 <= value <= 90):
        raise ValidationError('Широта должна быть в пределах от -90 до 90.')


def validate_longitude(value):
    if not (-180 <= value <= 180):
        raise ValidationError('Долгота должна быть в пределах от -180 до 180.')


class City(models.Model):
    # region = models.SmallIntegerField(verbose_name="Регион", validators=[MaxValueValidator(1000)])
    name = models.CharField(verbose_name="Название города", max_length=250)
    latitude = models.FloatField(verbose_name="Широта", validators=[validate_latitude])
    longitude = models.FloatField(verbose_name="Долгота", validators=[validate_longitude])

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Город'
        verbose_name_plural = 'Города'


class District(gis_models.Model):
    """Модель для хранения районов города с полигонами"""
    city = models.ForeignKey(
        City, 
        verbose_name="Город", 
        on_delete=models.CASCADE, 
        related_name='districts'
    )
    name = models.CharField(verbose_name="Название района", max_length=250)
    polygon = gis_models.PolygonField(verbose_name="Полигон района", srid=4326)
    description = models.TextField(verbose_name="Описание", null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.city.name})"

    class Meta:
        verbose_name = 'Район'
        verbose_name_plural = 'Районы'
        unique_together = ('city', 'name')


class TC(models.Model):
    name = models.CharField(verbose_name="Название типа транспортного средства", max_length=250, unique=True)
    # TODO Добавить поле изображения для визализации что это за транспорт
    capacity = models.SmallIntegerField(verbose_name="Вместимость")
    description = models.TextField(verbose_name="Описание", null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Тип транспортного средства'
        verbose_name_plural = 'Типы транспортных средств'


class BusStop(models.Model):
    # TODO one-to-one field к остановке напротив, также добавить в расчёт чтобы пассажир доезжал только до остановки напротив если она ближе
    city = models.ForeignKey(City, verbose_name="Город", on_delete=models.CASCADE, db_index=True)
    name = models.CharField(verbose_name="Название остановки", max_length=250)
    latitude = models.DecimalField(
        verbose_name="Широта",
        max_digits=9,  # Максимальное количество цифр всего (включая знаки после запятой)
        decimal_places=5,  # Количество знаков после запятой
        validators=[
            MinValueValidator(Decimal('-90.0')),
            MaxValueValidator(Decimal('90.0'))
        ]
    )
    longitude = models.DecimalField(
        verbose_name="Долгота",
        max_digits=10,  # Учитывая, что долгота может быть от -180 до 180
        decimal_places=5,
        validators=[
            MinValueValidator(Decimal('-180.0')),
            MaxValueValidator(Decimal('180.0'))
        ]
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Остановка'
        verbose_name_plural = 'Остановки'
        unique_together = ('latitude', 'longitude')

        indexes = [
            models.Index(fields=['latitude', 'longitude'])
        ]

    def get_routes_ids(self):
        routes_ids = self.route_set.all().values_list('id', flat=True)
        return routes_ids


class Route(models.Model):
    city = models.ForeignKey(City, verbose_name="Город", on_delete=models.CASCADE)
    name = models.CharField(verbose_name="Название маршрута", max_length=250)
    tc = models.ForeignKey(TC, verbose_name="Тип транспортного средства", on_delete=models.SET_NULL, null=True)
    interval = models.SmallIntegerField(verbose_name="Интервал движения в минутах", default=5)
    amount = models.SmallIntegerField(verbose_name="Количество транспорта на маршруте", null=True)
    list_coord = models.JSONField('Список координат, по которым проходит маршрут', null=True)
    list_coord_to_render = models.JSONField('Список координат для рендеринга', null=True)
    busstop = models.ManyToManyField(BusStop, verbose_name='Остановки')

    def __str__(self):
        return f"{self.city.name}: {self.name}"

    class Meta:
        verbose_name = 'Маршрут'
        verbose_name_plural = 'Маршруты'


class EI(models.Model):
    name = models.CharField(verbose_name="Название единицы измерения", max_length=250)
    short_name = models.CharField(verbose_name="Краткое название", max_length=15)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Единица измерения'
        verbose_name_plural = 'Единицы измерения'


class PassengerFlow(models.Model):
    """Модель сценария пассажиропотока"""
    city = models.ForeignKey(
        City,
        verbose_name="Город",
        on_delete=models.CASCADE,
        related_name='passenger_flows'
    )
    routes = models.ManyToManyField(
        Route,
        verbose_name="Маршруты",
        blank=True,
        related_name='passenger_flows',
        help_text="Маршруты, участвующие в сценарии"
    )
    name = models.CharField(
        verbose_name="Название сценария",
        max_length=250
    )
    description = models.TextField(
        verbose_name="Описание сценария",
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(
        verbose_name="Дата создания",
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        verbose_name="Дата обновления",
        auto_now=True
    )

    def __str__(self):
        return f"{self.name} ({self.city.name})"

    class Meta:
        verbose_name = 'Сценарий пассажиропотока'
        verbose_name_plural = 'Сценарии пассажиропотока'
        ordering = ['-created_at']


class PassengerFlowEntry(models.Model):
    """Модель для описания записи пассажиропотока (откуда-куда и сколько)"""
    passenger_flow = models.ForeignKey(
        PassengerFlow,
        verbose_name="Сценарий пассажиропотока",
        on_delete=models.CASCADE,
        related_name='entries'
    )
    from_stop = models.ForeignKey(
        BusStop,
        verbose_name="Остановка отправления",
        on_delete=models.CASCADE,
        related_name='passenger_flow_from'
    )
    to_stop = models.ForeignKey(
        BusStop,
        verbose_name="Остановка назначения",
        on_delete=models.CASCADE,
        related_name='passenger_flow_to',
        blank=True,
        null=True,
        help_text="Если не указано, пассажиры распределяются по маршруту"
    )
    passengers_count = models.PositiveIntegerField(
        verbose_name="Количество пассажиров",
        validators=[MinValueValidator(1)],
        help_text="Количество людей, следующих по данному направлению"
    )

    def __str__(self):
        to_stop_name = self.to_stop.name if self.to_stop else "любую остановку"
        return f"{self.from_stop.name} → {to_stop_name}: {self.passengers_count} чел."

    class Meta:
        verbose_name = 'Запись пассажиропотока'
        verbose_name_plural = 'Записи пассажиропотока'
        ordering = ['from_stop__name']


class Simulation(models.Model):
    """Модель для сохранения результатов расчётов нагрузки транспортной сети"""
    created_at = models.DateTimeField(
        verbose_name="Дата создания",
        auto_now_add=True
    )
    
    # Входные данные для расчёта
    input_data = models.JSONField(
        verbose_name="Входные данные для расчёта",
        help_text="Данные маршрутов, остановок и параметров, переданные для расчёта"
    )

    # Данные для отчёта
    report_data = models.JSONField(
        verbose_name="Данные для отчёта",
        help_text="Обработанные данные для генерации отчёта"
    )
    
    description = models.TextField(
        verbose_name="Описание",
        blank=True,
        null=True,
        help_text="Дополнительное описание симуляции"
    )
    
    def __str__(self):
        return f"<Симуляция {self.pk} {self.created_at.strftime('%d.%m.%Y %H:%M')}>"

    class Meta:
        verbose_name = 'Симуляция'
        verbose_name_plural = 'Симуляции'
        ordering = ['-created_at']

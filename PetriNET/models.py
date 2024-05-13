from django.db import models
from django.forms import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator


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


class TC(models.Model):
    name = models.CharField(verbose_name="Название типа транспортного средства", max_length=250)
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
            MinValueValidator(-90.0),
            MaxValueValidator(90.0)
        ]
    )
    longitude = models.DecimalField(
        verbose_name="Долгота",
        max_digits=10,  # Учитывая, что долгота может быть от -180 до 180
        decimal_places=5,
        validators=[
            MinValueValidator(-180.0),
            MaxValueValidator(180.0)
        ]
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Остановка'
        verbose_name_plural = 'Остановки'

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
    busstop = models.ManyToManyField(BusStop, verbose_name='Остановки')

    def __str__(self):
        return self.name

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

# Simulation
# Таблица сохранения результатов расчёта (без визуализации онлайн, только данные для ворд файла (или сам ворд файл))

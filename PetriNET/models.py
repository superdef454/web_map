from django.db import models

class City(models.Model):
    region = models.SmallIntegerField(verbose_name="Регион")
    name = models.CharField(verbose_name="Название города", max_length=250)
    latitude = models.FloatField(verbose_name="Широта")
    longitude = models.FloatField(verbose_name="Долгота")

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Город'
        verbose_name_plural = 'Города'


class TC(models.Model):
    name = models.CharField(verbose_name="Название типа транспортного средства", max_length=250)
    # TODO Добавить поле изображения для визализации что это за транспорт
    capacity = models.SmallIntegerField(verbose_name="Вместимость")
    description = models.TextField(verbose_name="Описание")
    
    class Meta:
        verbose_name = 'Тип транспортного средства'
        verbose_name_plural = 'Типы транспортных средств'


class BusStop(models.Model):
    # Быть может one-to-one field к остановке напротив
    city = models.ForeignKey(City, verbose_name="Город", on_delete=models.CASCADE)
    name = models.CharField(verbose_name="Название остановки", max_length=250)
    latitude = models.FloatField(verbose_name="Широта")
    longitude = models.FloatField(verbose_name="Долгота")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Остановка'
        verbose_name_plural = 'Остановки'


class Route(models.Model):
    city = models.ForeignKey(City, verbose_name="Город", on_delete=models.CASCADE)
    name = models.CharField(verbose_name="Название маршрута", max_length=250)
    tc = models.ForeignKey(TC, verbose_name="Тип транспортного средства", on_delete=models.SET_NULL, null=True)
    interval = models.SmallIntegerField(verbose_name="Интервал движения")
    amount = models.SmallIntegerField(verbose_name="Количество транспорта на маршруте")

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Маршрут'
        verbose_name_plural = 'Маршруты'
    
# Simulation
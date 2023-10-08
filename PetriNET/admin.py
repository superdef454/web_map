from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import City, BusStop, Route, TC


# class ClassInline(admin.StackedInline):
#     model = Class
#     extra = 0


# @admin.register(Shcool)
# class ShcoolAdmin(admin.ModelAdmin):
#     readonly_fields = ["preview"]
#     inlines = [
#         ClassInline
#     ]

#     def preview(self, obj):
#         return mark_safe(f'<img src="{obj.image.url}" style="max-height: 400px;">')


# @admin.register(Class)
# class ClassAdmin(admin.ModelAdmin):
#     search_fields = ['class_name', 'students__surname', 'students__name']
#     list_filter = ('year', 'school')


# class AchievementsInline(admin.StackedInline):
#     model = Achievements
#     extra = 0


# @admin.register(Student)
# class StudentAdmin(admin.ModelAdmin):
#     inlines = [
#         AchievementsInline
#     ]
#     list_filter = ('school', 'gender')
#     search_fields = ['surname', 'name', 'middle_name']


admin.site.register(City)
admin.site.register(BusStop)
admin.site.register(Route)
admin.site.register(TC)
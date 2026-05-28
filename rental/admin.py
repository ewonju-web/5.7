from django.contrib import admin

from .models import RentalCompany, RentalPost


@admin.register(RentalCompany)
class RentalCompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'region', 'contact', 'is_active', 'lat', 'lng')
    list_filter = ('is_active', 'region')
    search_fields = ('name', 'region', 'contact', 'address')


@admin.register(RentalPost)
class RentalPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'equipment_type', 'region', 'rental_price', 'is_available', 'lat', 'lng', 'created_at')
    list_filter = ('is_available', 'equipment_type', 'region')
    search_fields = ('title', 'contact', 'address')
    raw_id_fields = ('author',)

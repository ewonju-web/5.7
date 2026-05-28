from django.urls import path

from . import views

urlpatterns = [
    path('<int:pk>/', views.rental_detail, name='rental_detail'),
]

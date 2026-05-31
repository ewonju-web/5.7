from django.urls import path

from . import views

app_name = 'trust'

urlpatterns = [
    path('reviews/create/', views.review_create, name='review_create'),
    path('reports/create/', views.report_create, name='report_create'),
    path('seller/<int:user_id>/profile/', views.seller_profile, name='seller_profile'),
    path('seller/<int:user_id>/reviews/', views.seller_reviews, name='seller_reviews'),
]

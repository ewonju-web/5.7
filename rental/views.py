from django.shortcuts import get_object_or_404, render

from .models import RentalPost


def rental_detail(request, pk):
    post = get_object_or_404(RentalPost, pk=pk, is_available=True)
    return render(request, 'rental/rental_detail.html', {'post': post})

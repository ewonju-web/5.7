from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import SellerReport, SellerReview
from .services import recalculate_manner_score


@receiver(post_save, sender=SellerReview)
def on_review_saved(sender, instance, **kwargs):
    recalculate_manner_score(instance.seller)


@receiver(post_delete, sender=SellerReview)
def on_review_deleted(sender, instance, **kwargs):
    recalculate_manner_score(instance.seller)


@receiver(post_save, sender=SellerReport)
def on_report_saved(sender, instance, **kwargs):
    recalculate_manner_score(instance.seller)

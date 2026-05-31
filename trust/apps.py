from django.apps import AppConfig


class TrustConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'trust'
    verbose_name = '판매자 신뢰도'

    def ready(self):
        import trust.signals  # noqa: F401

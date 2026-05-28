from django.conf import settings
from django.db import models


class RentalCompany(models.Model):
    """장비 임대 업체 (부품 A/S 지도에 표시)."""

    EQUIPMENT_TYPE_KEYS = (
        'excavator', 'forklift', 'dump', 'loader', 'crane', 'attachment', 'other',
    )

    name = models.CharField(max_length=100, verbose_name='업체명')
    equipment_types = models.JSONField(default=list, blank=True, verbose_name='취급 장비')
    region = models.CharField(max_length=50, verbose_name='지역')
    contact = models.CharField(max_length=50, verbose_name='연락처')
    address = models.CharField(max_length=200, blank=True, default='', verbose_name='주소')
    lat = models.FloatField(null=True, blank=True, verbose_name='위도')
    lng = models.FloatField(null=True, blank=True, verbose_name='경도')
    note = models.CharField(max_length=200, blank=True, default='', verbose_name='비고')
    is_active = models.BooleanField(default=True, verbose_name='활성')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '임대 업체'
        verbose_name_plural = '임대 업체'
        ordering = ['region', 'name']

    def __str__(self):
        return f'{self.name} ({self.region})'


class RentalPost(models.Model):
    """개인 장비 임대 매물."""

    EQUIPMENT_TYPE_CHOICES = [
        ('excavator', '굴삭기'),
        ('forklift', '지게차'),
        ('dump', '덤프트럭'),
        ('loader', '스키로더·로더'),
        ('crane', '크레인'),
        ('attachment', '어태치먼트'),
        ('other', '기타'),
    ]

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='rental_posts',
        verbose_name='작성자',
    )
    title = models.CharField(max_length=120, verbose_name='제목')
    equipment_type = models.CharField(
        max_length=20,
        choices=EQUIPMENT_TYPE_CHOICES,
        default='excavator',
        verbose_name='기종',
    )
    region = models.CharField(max_length=50, verbose_name='지역')
    rental_price = models.CharField(max_length=80, blank=True, default='', verbose_name='임대료')
    rental_period = models.CharField(max_length=80, blank=True, default='', verbose_name='임대 기간')
    contact = models.CharField(max_length=50, verbose_name='연락처')
    address = models.CharField(max_length=200, blank=True, default='', verbose_name='주소')
    lat = models.FloatField(null=True, blank=True, verbose_name='위도')
    lng = models.FloatField(null=True, blank=True, verbose_name='경도')
    description = models.TextField(blank=True, default='', verbose_name='상세 설명')
    is_available = models.BooleanField(default=True, verbose_name='임대 가능')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '개인 임대'
        verbose_name_plural = '개인 임대'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def display_name(self):
        name = (getattr(self.author, 'first_name', None) or '').strip()
        return name or self.author.username

from django.conf import settings
from django.db import models


class SellerReview(models.Model):
    REVIEW_TYPE = [
        ('good', '좋았어요'),
        ('bad', '아쉬웠어요'),
    ]

    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='given_reviews',
        verbose_name='평가자',
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_reviews',
        verbose_name='판매자',
    )
    equipment = models.ForeignKey(
        'equipment.Equipment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='매물',
    )
    review_type = models.CharField(max_length=10, choices=REVIEW_TYPE, verbose_name='평가 유형')
    comment = models.TextField(blank=True, default='', verbose_name='코멘트')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='작성일')

    score_accuracy = models.PositiveSmallIntegerField(default=0, verbose_name='사진/설명 정확도')
    score_response = models.PositiveSmallIntegerField(default=0, verbose_name='응답 속도')
    score_promise = models.PositiveSmallIntegerField(default=0, verbose_name='약속 이행')
    score_price = models.PositiveSmallIntegerField(default=0, verbose_name='가격 정직성')
    score_disclosure = models.PositiveSmallIntegerField(default=0, verbose_name='하자 고지 성실도')

    class Meta:
        verbose_name = '판매자 거래 평가'
        verbose_name_plural = '판매자 거래 평가'
        constraints = [
            models.UniqueConstraint(
                fields=['reviewer', 'equipment'],
                name='trust_unique_reviewer_equipment',
                condition=models.Q(reviewer__isnull=False, equipment__isnull=False),
            ),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.seller_id} ← {self.review_type} ({self.reviewer_id})'


class ReviewBadTag(models.Model):
    TAG_CHOICES = [
        ('fake_photo', '허위 사진'),
        ('desc_exaggerate', '설명 과장'),
        ('broken_promise', '약속 불이행'),
        ('slow_response', '응답 느림'),
        ('overpriced', '가격 바가지'),
        ('rude', '비매너/불친절'),
        ('hidden_defect', '결함 은폐'),
    ]

    review = models.ForeignKey(
        SellerReview,
        on_delete=models.CASCADE,
        related_name='bad_tags',
        verbose_name='평가',
    )
    tag = models.CharField(max_length=30, choices=TAG_CHOICES, verbose_name='태그')

    class Meta:
        verbose_name = '불합리 태그'
        verbose_name_plural = '불합리 태그'
        unique_together = [('review', 'tag')]

    def __str__(self):
        return self.get_tag_display()


class SellerReport(models.Model):
    REPORT_CHOICES = [
        ('fake_photo', '사진과 실물 다름'),
        ('hidden_defect', '설명과 실제 상태 다름'),
        ('price_change', '가격 흥정 후 일방적 취소/변경'),
        ('broken_promise', '약속된 날짜/장소 불이행'),
        ('rude', '비매너/욕설/협박'),
        ('duplicate', '중복 등록/허위 매물'),
        ('other', '기타'),
    ]

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='seller_reports_filed',
        verbose_name='신고자',
    )
    reporter_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='신고 IP')
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports',
        verbose_name='판매자',
    )
    equipment = models.ForeignKey(
        'equipment.Equipment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='매물',
    )
    reason = models.CharField(max_length=30, choices=REPORT_CHOICES, verbose_name='사유')
    detail = models.TextField(blank=True, default='', verbose_name='상세')
    is_handled = models.BooleanField(default=False, verbose_name='처리 완료')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='신고일')

    class Meta:
        verbose_name = '판매자 신고'
        verbose_name_plural = '판매자 신고'
        ordering = ['-created_at']

    def __str__(self):
        return f'신고 #{self.pk} → {self.seller_id}'


class MannerScore(models.Model):
    TIER_CHOICES = [
        ('best', '우수 판매자'),
        ('verified', '일반 인증'),
        ('caution', '주의 판매자'),
        ('blocked', '이용 제한'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='manner_score',
        verbose_name='회원',
    )
    score = models.FloatField(default=70.0, verbose_name='매너점수')
    tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        default='verified',
        verbose_name='등급',
    )
    total_reviews = models.PositiveIntegerField(default=0, verbose_name='총 평가 수')
    good_count = models.PositiveIntegerField(default=0, verbose_name='좋았어요')
    bad_count = models.PositiveIntegerField(default=0, verbose_name='아쉬웠어요')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='갱신일')

    class Meta:
        verbose_name = '매너점수'
        verbose_name_plural = '매너점수'

    def __str__(self):
        return f'{self.user_id}: {self.score} ({self.tier})'

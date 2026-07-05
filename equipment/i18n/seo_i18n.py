# SEO default meta (title, description, OG/Twitter) per language for base.html.
# TODO: native speaker review pending for all non-Korean entries.

from equipment.templatetags.i18n_extras import LANGUAGE_ORDER, SUPPORTED_LANGS

_KO_DESCRIPTION = (
    "굴삭기나라에서 중고 굴삭기 매매와 직거래를 쉽고 빠르게 이용하세요. "
    "굴삭기 판매·구매는 물론 지게차, 덤프트럭 거래, 구인구직, 정비 유튜브, 부품 A/S까지 "
    "건설장비에 필요한 정보를 한곳에서 안전하게 제공합니다."
)
_KO_TITLE = "굴삭기나라 | 중고 굴삭기 매매·판매·구매·직거래 플랫폼"

# TODO: native speaker review pending
SEO_DEFAULTS = {
    "ko": {
        "title": _KO_TITLE,
        "description": _KO_DESCRIPTION,
        "og_title": _KO_TITLE,
        "og_description": _KO_DESCRIPTION,
    },
    "en": {
        "title": "Gulsakginara | Used Excavator Buy, Sell & Direct Trade",
        "description": (
            "Buy and sell used excavators with fast direct deals on Gulsakginara. "
            "Listings for excavators, forklifts, and dump trucks, plus jobs, repair YouTube, "
            "and parts A/S — all the heavy equipment information you need in one safe place."
        ),
        "og_title": "Gulsakginara | Used Excavator Buy, Sell & Direct Trade",
        "og_description": (
            "Buy and sell used excavators with fast direct deals on Gulsakginara. "
            "Listings for excavators, forklifts, and dump trucks, plus jobs, repair YouTube, "
            "and parts A/S — all the heavy equipment information you need in one safe place."
        ),
    },
    "ru": {
        "title": "Gulsakginara | Покупка и продажа б/у экскаваторов, прямые сделки",
        "description": (
            "Покупайте и продавайте б/у экскаваторы с быстрыми прямыми сделками на Gulsakginara. "
            "Объявления по экскаваторам, погрузчикам и самосвалам, а также вакансии, YouTube по ремонту "
            "и запчасти A/S — вся информация о спецтехнике в одном безопасном месте."
        ),
        "og_title": "Gulsakginara | Покупка и продажа б/у экскаваторов, прямые сделки",
        "og_description": (
            "Покупайте и продавайте б/у экскаваторы с быстрыми прямыми сделками на Gulsakginara. "
            "Объявления по экскаваторам, погрузчикам и самосвалам, а также вакансии, YouTube по ремонту "
            "и запчасти A/S — вся информация о спецтехнике в одном безопасном месте."
        ),
    },
    "vi": {
        "title": "Gulsakginara | Mua bán máy xúc cũ & giao dịch trực tiếp",
        "description": (
            "Mua bán máy xúc cũ và giao dịch trực tiếp nhanh chóng trên Gulsakginara. "
            "Tin đăng máy xúc, xe nâng, xe ben, việc làm, YouTube sửa chữa và phụ tùng A/S — "
            "mọi thông tin thiết bị hạng nặng bạn cần ở một nơi an toàn."
        ),
        "og_title": "Gulsakginara | Mua bán máy xúc cũ & giao dịch trực tiếp",
        "og_description": (
            "Mua bán máy xúc cũ và giao dịch trực tiếp nhanh chóng trên Gulsakginara. "
            "Tin đăng máy xúc, xe nâng, xe ben, việc làm, YouTube sửa chữa và phụ tùng A/S — "
            "mọi thông tin thiết bị hạng nặng bạn cần ở một nơi an toàn."
        ),
    },
    "mn": {
        "title": "Gulsakginara | Хэрэглэсэн экскаватор худалдаа & шууд арилжаа",
        "description": (
            "Gulsakginara дээр хэрэглэсэн экскаваторыг хурдан шууд арилжаагаар худалдаж авна уу. "
            "Экскаватор, ачаа өргөгч, самосвалын зар, ажлын байр, засварын YouTube, сэлбэг A/S — "
            "хүнд техникийн мэдээллийг нэг аюулгүй газарт."
        ),
        "og_title": "Gulsakginara | Хэрэглэсэн экскаватор худалдаа & шууд арилжаа",
        "og_description": (
            "Gulsakginara дээр хэрэглэсэн экскаваторыг хурдан шууд арилжаагаар худалдаж авна уу. "
            "Экскаватор, ачаа өргөгч, самосвалын зар, ажлын байр, засварын YouTube, сэлбэг A/S — "
            "хүнд техникийн мэдээллийг нэг аюулгүй газарт."
        ),
    },
    "ky": {
        "title": "Gulsakginara | Колдонулган экскаватор сатуу-сатып алуу жана түз арилжа",
        "description": (
            "Gulsakginaraда колдонулган экскаваторду тез түз арилжа менен сатып алыңыз же сатыңыз. "
            "Экскаватор, жүк көтөргүч, самосвал жарыялары, жумуш, оңдоо YouTube, сапчасть A/S — "
            "оор техника боюнча бардык маалымат бир коопсуз жерде."
        ),
        "og_title": "Gulsakginara | Колдонулган экскаватор сатуу-сатып алуу жана түз арилжа",
        "og_description": (
            "Gulsakginaraда колдонулган экскаваторду тез түз арилжа менен сатып алыңыз же сатыңыз. "
            "Экскаватор, жүк көтөргүч, самосвал жарыялары, жумуш, оңдоо YouTube, сапчасть A/S — "
            "оор техника боюнча бардык маалымат бир коопсуз жерде."
        ),
    },
    "uz": {
        "title": "Gulsakginara | Ishlatilgan ekskavator savdosi va to'g'ridan-to'g'ri bitimlar",
        "description": (
            "Gulsakginarada ishlatilgan ekskavatorlarni tez va to'g'ridan-to'g'ri bitimlar bilan sotib oling yoki soting. "
            "Ekskavator, yuk ko'targich, samosval e'lonlari, ishlar, ta'mirlash YouTube va ehtiyot qismlar A/S — "
            "og'ir texnika haqidagi barcha ma'lumotlar bir xavfsiz joyda."
        ),
        "og_title": "Gulsakginara | Ishlatilgan ekskavator savdosi va to'g'ridan-to'g'ri bitimlar",
        "og_description": (
            "Gulsakginarada ishlatilgan ekskavatorlarni tez va to'g'ridan-to'g'ri bitimlar bilan sotib oling yoki soting. "
            "Ekskavator, yuk ko'targich, samosval e'lonlari, ishlar, ta'mirlash YouTube va ehtiyot qismlar A/S — "
            "og'ir texnika haqidagi barcha ma'lumotlar bir xavfsiz joyda."
        ),
    },
    "kk": {
        "title": "Gulsakginara | Қолданылған экскаватор сату-сатып алу және тікелей мәміле",
        "description": (
            "Gulsakginaraда қолданылған экскаваторларды жылдам тікелей мәміле арқылы сатып алыңыз немесе сатыңыз. "
            "Экскаватор, автопогрузчик, самосвал хабарландырулары, жұмыс, жөндеу YouTube, бөлшектер A/S — "
            "ауыр техника туралы барлық ақпарат бір қауіпсіз орында."
        ),
        "og_title": "Gulsakginara | Қолданылған экскаватор сату-сатып алу және тікелей мәміле",
        "og_description": (
            "Gulsakginaraда қолданылған экскаваторларды жылдам тікелей мәміле арқылы сатып алыңыз немесе сатыңыз. "
            "Экскаватор, автопогрузчик, самосвал хабарландырулары, жұмыс, жөндеу YouTube, бөлшектер A/S — "
            "ауыр техника туралы барлық ақпарат бір қауіпсіз орында."
        ),
    },
    "ur": {
        "title": "Gulsakginara | استعمال شدہ excavator خرید و فروخت اور براہِ راست تجارت",
        "description": (
            "Gulsakginara پر استعمال شدہ ایکسکیویٹرز تیز براہِ راست سودوں کے ساتھ خریدیں اور بیچیں۔ "
            "ایکسکیویٹر، فورک لفٹ، ڈمپ ٹرک کی فہرستیں، ملازمتیں، مرمت YouTube اور پرزے A/S — "
            "بھاری مشینری کی تمام معلومات ایک محفوظ جگہ پر۔"
        ),
        "og_title": "Gulsakginara | استعمال شدہ excavator خرید و فروخت اور براہِ راست تجارت",
        "og_description": (
            "Gulsakginara پر استعمال شدہ ایکسکیویٹرز تیز براہِ راست سودوں کے ساتھ خریدیں اور بیچیں۔ "
            "ایکسکیویٹر، فورک لفٹ، ڈمپ ٹرک کی فہرستیں، ملازمتیں، مرمت YouTube اور پرزے A/S — "
            "بھاری مشینری کی تمام معلومات ایک محفوظ جگہ پر۔"
        ),
    },
    "es": {
        "title": "Gulsakginara | Compra, venta y comercio directo de excavadoras usadas",
        "description": (
            "Compre y venda excavadoras usadas con tratos directos rápidos en Gulsakginara. "
            "Anuncios de excavadoras, montacargas y camiones volquete, empleo, YouTube de reparación "
            "y repuestos A/S — toda la información de maquinaria pesada en un solo lugar seguro."
        ),
        "og_title": "Gulsakginara | Compra, venta y comercio directo de excavadoras usadas",
        "og_description": (
            "Compre y venda excavadoras usadas con tratos directos rápidos en Gulsakginara. "
            "Anuncios de excavadoras, montacargas y camiones volquete, empleo, YouTube de reparación "
            "y repuestos A/S — toda la información de maquinaria pesada en un solo lugar seguro."
        ),
    },
}

OG_LOCALE_MAP = {
    "ko": "ko_KR",
    "en": "en_US",
    "ru": "ru_RU",
    "vi": "vi_VN",
    "mn": "mn_MN",
    "ky": "ky_KG",
    "uz": "uz_UZ",
    "kk": "kk_KZ",
    "ur": "ur_PK",
    "es": "es_ES",
}

SEO_HREFLANG_CODES = tuple(LANGUAGE_ORDER)


def get_seo_meta(lang_code: str) -> dict:
    """Return SEO default strings for lang; fallback to Korean."""
    code = (lang_code or "ko").strip().lower()
    if code not in SUPPORTED_LANGS:
        code = "ko"
    return dict(SEO_DEFAULTS.get(code, SEO_DEFAULTS["ko"]))


def get_og_locale(lang_code: str) -> str:
    code = (lang_code or "ko").strip().lower()
    if code not in SUPPORTED_LANGS:
        code = "ko"
    return OG_LOCALE_MAP.get(code, "ko_KR")

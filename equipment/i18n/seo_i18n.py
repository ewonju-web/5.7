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

# Category listing page SEO (?category=xx). Keys match Equipment.equipment_type codes.
# Equipment display names align with i18n_extras cat_* where available; attachment added here.
# TODO: native speaker review pending for all non-Korean entries.
CATEGORY_DISPLAY_NAMES = {
    "excavator": {
        "ko": '굴삭기',
        "en": 'Excavator',
        "ru": 'Экскаватор',
        "vi": 'Máy xúc',
        "mn": 'Экскаватор',
        "ky": 'Экскаватор',
        "uz": 'Ekskavator',
        "kk": 'Экскаватор',
        "ur": 'ایکسکیویٹر',
        "es": 'Excavadora',
    },
    "forklift": {
        "ko": '지게차',
        "en": 'Forklift',
        "ru": 'Погрузчик',
        "vi": 'Xe nâng',
        "mn": 'Ачаа өргөгч',
        "ky": 'Жүк көтөргүч',
        "uz": "Yuk ko'targich",
        "kk": 'Автопогрузчик',
        "ur": 'فورک لفٹ',
        "es": 'Montacargas',
    },
    "dump": {
        "ko": '덤프트럭',
        "en": 'Dump truck',
        "ru": 'Самосвал',
        "vi": 'Xe ben',
        "mn": 'Самосвал',
        "ky": 'Самосвал',
        "uz": 'Samosval',
        "kk": 'Самосвал',
        "ur": 'ڈمپ ٹرک',
        "es": 'Camión volquete',
    },
    "loader": {
        "ko": '스키로더·로더',
        "en": 'Skid steer/Loader',
        "ru": 'Мини-погрузчик/Погрузчик',
        "vi": 'Xe xúc lật',
        "mn": 'Скийн өргөгч/Погрузчик',
        "ky": 'Скийд-стир/Погрузчик',
        "uz": 'Skid-steer/Pogruzchik',
        "kk": 'Скийд-стир/Погрузчик',
        "ur": 'Skid steer/Loader',
        "es": 'Minicargadora/Cargadora',
    },
    "crane": {
        "ko": '크레인',
        "en": 'Crane',
        "ru": 'Кран',
        "vi": 'Cần cẩu',
        "mn": 'Кран',
        "ky": 'Кран',
        "uz": 'Kran',
        "kk": 'Кран',
        "ur": 'کرین',
        "es": 'Grúa',
    },
    "attachment": {
        "ko": '어태치먼트',
        "en": 'Attachment',
        "ru": 'Навесное оборудование',
        "vi": 'Phụ kiện gắn máy',
        "mn": 'Хавсралт',
        "ky": 'Тиркеме',
        "uz": 'Biriktirma',
        "kk": 'Тіркеме',
        "ur": 'Attachment',
        "es": 'Accesorio',
    },
    "other": {
        "ko": '건설기계·중장비',
        "en": 'Other heavy equipment',
        "ru": 'Другая спецтехника',
        "vi": 'Thiết bị khác',
        "mn": 'Бусад хүнд техник',
        "ky": 'Башка оор техника',
        "uz": "Boshqa og'ir texnika",
        "kk": 'Басқа ауыр техника',
        "ur": 'دیگر بھاری مشینری',
        "es": 'Otra maquinaria pesada',
    },
}

CATEGORY_SEO_I18N = {
    "excavator": {
        "ko": {"title": '중고 굴삭기 매물·실시간 시세 | 굴삭기나라', "description": '전국 중고 굴삭기 매물을 실시간 등록 시세와 함께 직거래로 확인하세요. 미니·중형·대형 굴삭기를 연식·가동시간·지역별로 비교할 수 있습니다 — 굴삭기나라.'},
        "en": {"title": 'Used Excavator Listings & Live Prices | Gulsakginara', "description": 'Browse used excavators nationwide with live listing prices and direct trade on Gulsakginara. Compare mini, mid-size, and large excavators by year, operating hours, and region.'},
        "ru": {"title": 'Б/у экскаваторы — объявления и актуальные цены | Gulsakginara', "description": 'Смотрите объявления о б/у экскаваторах по всей стране с актуальными ценами и прямыми сделками на Gulsakginara. Сравнивайте мини-, средние и крупные экскаваторы по году, наработке и региону.'},
        "vi": {"title": 'Máy xúc cũ — tin đăng & giá thị trường | Gulsakginara', "description": 'Xem tin máy xúc cũ toàn quốc với giá đăng thời gian thực và giao dịch trực tiếp trên Gulsakginara. So sánh máy mini, trung và lớn theo năm, giờ vận hành và khu vực.'},
        "mn": {"title": 'Хэрэглэсэн экскаваторын зар & бодит үнэ | Gulsakginara', "description": 'Gulsakginara дээр бүх улсын хэрэглэсэн экскаваторын зарыг бодит үнэтэй, шууд арилжаагаар үзнэ үү. Жижиг, дунд, том экскаваторыг он, ажлын цаг, бүс нутагаар харьцуулна.'},
        "ky": {"title": 'Колдонулган экскаватор жарыялары жана актуалдуу баалар | Gulsakginara', "description": 'Gulsakginaraда өлкө боюнча колдонулган экскаватор жарыяларын жандуу баалар жана түз арилжа менен көрүңүз. Мини, орто жана чоң экскаваторду жылы, иш сааты жана аймак боюнча салыштырыңыз.'},
        "uz": {"title": "Ishlatilgan ekskavator e'lonlari va jonli narxlar | Gulsakginara", "description": "Gulsakginarada butun mamlakat bo'ylab ishlatilgan ekskavator e'lonlarini jonli narxlar va to'g'ridan-to'g'ri bitimlar bilan ko'ring. Mini, o'rta va katta ekskavatorlarni yil, ish soati va hudud bo'yicha solishtiring."},
        "kk": {"title": 'Қолданылған экскаватор хабарландырулары мен нақты бағалар | Gulsakginara', "description": 'Gulsakginaraда ел бойынша қолданылған экскаватор хабарландыруларын нақты бағалармен және тікелей мәміле арқылы қараңыз. Шағын, орта және ірі экскаваторларды жылы, жұмыс уақыты мен аймақ бойынша салыстырыңыз.'},
        "ur": {"title": 'استعمال شدہ excavator لسٹنگز اور براہِ راست قیمتیں | Gulsakginara', "description": 'Gulsakginara پر ملک بھر کے استعمال شدہ excavator اشتہارات براہِ راست تجارت اور تازہ قیمتوں کے ساتھ دیکھیں۔ mini، درمیانے اور بڑے excavator کو سال، گھنٹوں اور علاقے کے لحاظ سے موازنہ کریں۔'},
        "es": {"title": 'Excavadoras usadas — anuncios y precios en vivo | Gulsakginara', "description": 'Consulte excavadoras usadas en todo el país con precios en vivo y comercio directo en Gulsakginara. Compare mini, medianas y grandes por año, horas de uso y región.'},
    },
    "forklift": {
        "ko": {"title": '중고 지게차 매물·실시간 시세 | 굴삭기나라', "description": '전국 중고 지게차 매물을 실시간 등록 시세와 함께 직거래로 확인하세요. 디젤·전동 지게차를 톤수·연식·지역별로 비교할 수 있습니다 — 굴삭기나라.'},
        "en": {"title": 'Used Forklift Listings & Live Prices | Gulsakginara', "description": 'Browse used forklifts nationwide with live listing prices and direct trade on Gulsakginara. Compare diesel and electric forklifts by capacity, year, and region.'},
        "ru": {"title": 'Б/у погрузчики — объявления и актуальные цены | Gulsakginara', "description": 'Смотрите объявления о б/у погрузчиках по всей стране с актуальными ценами и прямыми сделками на Gulsakginara. Сравнивайте дизельные и электрические погрузчики по грузоподъёмности, году и региону.'},
        "vi": {"title": 'Xe nâng cũ — tin đăng & giá thị trường | Gulsakginara', "description": 'Xem tin xe nâng cũ toàn quốc với giá đăng thời gian thực và giao dịch trực tiếp trên Gulsakginara. So sánh xe dầu và điện theo tải trọng, năm và khu vực.'},
        "mn": {"title": 'Хэрэглэсэн ачаа өргөгчийн зар & бодит үнэ | Gulsakginara', "description": 'Gulsakginara дээр бүх улсын хэрэглэсэн ачаа өргөгчийн зарыг бодит үнэтэй, шууд арилжаагаар үзнэ үү. Дизель, цахилгаан өргөгчийг даац, он, бүс нутагаар харьцуулна.'},
        "ky": {"title": 'Колдонулган жүк көтөргүч жарыялары жана актуалдуу баалар | Gulsakginara', "description": 'Gulsakginaraда өлкө боюнча колдонулган жүк көтөргүч жарыяларын жандуу баалар жана түз арилжа менен көрүңүз. Дизель жана электр көтөргүчтөрдү жүктөмдүүлүк, жылы жана аймак боюнча салыштырыңыз.'},
        "uz": {"title": "Ishlatilgan yuk ko'targich e'lonlari va jonli narxlar | Gulsakginara", "description": "Gulsakginarada butun mamlakat bo'ylab ishlatilgan yuk ko'targich e'lonlarini jonli narxlar va to'g'ridan-to'g'ri bitimlar bilan ko'ring. Dizel va elektr ko'targichlarni yuk ko'tarish, yil va hudud bo'yicha solishtiring."},
        "kk": {"title": 'Қолданылған автопогрузчик хабарландырулары мен нақты бағалар | Gulsakginara', "description": 'Gulsakginaraда ел бойынша қолданылған автопогрузчик хабарландыруларын нақты бағалармен және тікелей мәміле арқылы қараңыз. Дизель және электр погрузчиктерді жүк көтеру, жылы мен аймақ бойынша салыстырыңыз.'},
        "ur": {"title": 'استعمال شدہ فورک لفٹ لسٹنگز اور براہِ راست قیمتیں | Gulsakginara', "description": 'Gulsakginara پر ملک بھر کے استعمال شدہ فورک لفٹ اشتہارات براہِ راست تجارت اور تازہ قیمتوں کے ساتھ دیکھیں۔ ڈیزل اور الیکٹرک فورک لفٹ کو capacity، سال اور علاقے کے لحاظ سے موازنہ کریں۔'},
        "es": {"title": 'Montacargas usados — anuncios y precios en vivo | Gulsakginara', "description": 'Consulte montacargas usados en todo el país con precios en vivo y comercio directo en Gulsakginara. Compare diésel y eléctricos por capacidad, año y región.'},
    },
    "dump": {
        "ko": {"title": '중고 덤프트럭 매물·실시간 시세 | 굴삭기나라', "description": '전국 중고 덤프트럭 매물을 실시간 등록 시세와 함께 직거래로 확인하세요. 축수·연식·지역별로 매물을 비교할 수 있습니다 — 굴삭기나라.'},
        "en": {"title": 'Used Dump Truck Listings & Live Prices | Gulsakginara', "description": 'Browse used dump trucks nationwide with live listing prices and direct trade on Gulsakginara. Compare listings by axle configuration, year, and region.'},
        "ru": {"title": 'Б/у самосвалы — объявления и актуальные цены | Gulsakginara', "description": 'Смотрите объявления о б/у самосвалах по всей стране с актуальными ценами и прямыми сделками на Gulsakginara. Сравнивайте по колёсной формуле, году выпуска и региону.'},
        "vi": {"title": 'Xe ben cũ — tin đăng & giá thị trường | Gulsakginara', "description": 'Xem tin xe ben cũ toàn quốc với giá đăng thời gian thực và giao dịch trực tiếp trên Gulsakginara. So sánh theo cấu hình trục, năm và khu vực.'},
        "mn": {"title": 'Хэрэглэсэн самосвалын зар & бодит үнэ | Gulsakginara', "description": 'Gulsakginara дээр бүх улсын хэрэглэсэн самосвалын зарыг бодит үнэтэй, шууд арилжаагаар үзнэ үү. Тэнхлэгийн тохиргоо, он, бүс нутагаар харьцуулна.'},
        "ky": {"title": 'Колдонулган самосвал жарыялары жана актуалдуу баалар | Gulsakginara', "description": 'Gulsakginaraда өлкө боюнча колдонулган самосвал жарыяларын жандуу баалар жана түз арилжа менен көрүңүз. Ось конфигурациясы, жылы жана аймак боюнча салыштырыңыз.'},
        "uz": {"title": "Ishlatilgan samosval e'lonlari va jonli narxlar | Gulsakginara", "description": "Gulsakginarada butun mamlakat bo'ylab ishlatilgan samosval e'lonlarini jonli narxlar va to'g'ridan-to'g'ri bitimlar bilan ko'ring. O'q konfiguratsiyasi, yil va hudud bo'yicha solishtiring."},
        "kk": {"title": 'Қолданылған самосвал хабарландырулары мен нақты бағалар | Gulsakginara', "description": 'Gulsakginaraда ел бойынша қолданылған самосвал хабарландыруларын нақты бағалармен және тікелей мәміле арқылы қараңыз. Ось конфигурациясы, жылы мен аймақ бойынша салыстырыңыз.'},
        "ur": {"title": 'استعمال شدہ ڈمپ ٹرک لسٹنگز اور براہِ راست قیمتیں | Gulsakginara', "description": 'Gulsakginara پر ملک بھر کے استعمال شدہ ڈمپ ٹرک اشتہارات براہِ راست تجارت اور تازہ قیمتوں کے ساتھ دیکھیں۔ محور کی ترتیب، سال اور علاقے کے لحاظ سے موازنہ کریں۔'},
        "es": {"title": 'Camiones volquete usados — anuncios y precios en vivo | Gulsakginara', "description": 'Consulte camiones volquete usados en todo el país con precios en vivo y comercio directo en Gulsakginara. Compare por configuración de ejes, año y región.'},
    },
    "loader": {
        "ko": {"title": '중고 스키로더·로더 매물·실시간 시세 | 굴삭기나라', "description": '전국 중고 스키로더·로더 매물을 실시간 등록 시세와 함께 직거래로 확인하세요. 연식·가동시간·지역별로 비교할 수 있습니다 — 굴삭기나라.'},
        "en": {"title": 'Used Skid Steer & Loader Listings & Live Prices | Gulsakginara', "description": 'Browse used skid steers and loaders nationwide with live listing prices and direct trade on Gulsakginara. Compare by year, operating hours, and region.'},
        "ru": {"title": 'Б/у мини-погрузчики и погрузчики — объявления и цены | Gulsakginara', "description": 'Смотрите объявления о б/у мини-погрузчиках и погрузчиках по всей стране с актуальными ценами и прямыми сделками на Gulsakginara. Сравнивайте по году, наработке и региону.'},
        "vi": {"title": 'Xe xúc lật & máy xúc cũ — tin đăng & giá thị trường | Gulsakginara', "description": 'Xem tin xe xúc lật và máy xúc cũ toàn quốc với giá đăng thời gian thực và giao dịch trực tiếp trên Gulsakginara. So sánh theo năm, giờ vận hành và khu vực.'},
        "mn": {"title": 'Хэрэглэсэн скийн өргөгч, погрузчикийн зар & бодит үнэ | Gulsakginara', "description": 'Gulsakginara дээр бүх улсын хэрэглэсэн скийн өргөгч, погрузчикийн зарыг бодит үнэтэй, шууд арилжаагаар үзнэ үү. Он, ажлын цаг, бүс нутагаар харьцуулна.'},
        "ky": {"title": 'Колдонулган скийд-стир жана погрузчик жарыялары | Gulsakginara', "description": 'Gulsakginaraда өлкө боюнча колдонулган скийд-стир жана погрузчик жарыяларын жандуу баалар жана түз арилжа менен көрүңүз. Жылы, иш сааты жана аймак боюнча салыштырыңыз.'},
        "uz": {"title": "Ishlatilgan skid-steer va pogruzchik e'lonlari | Gulsakginara", "description": "Gulsakginarada butun mamlakat bo'ylab ishlatilgan skid-steer va pogruzchik e'lonlarini jonli narxlar va to'g'ridan-to'g'ri bitimlar bilan ko'ring. Yil, ish soati va hudud bo'yicha solishtiring."},
        "kk": {"title": 'Қолданылған скийд-стир және погрузчик хабарландырулары | Gulsakginara', "description": 'Gulsakginaraда ел бойынша қолданылған скийд-стир және погрузчик хабарландыруларын нақты бағалармен және тікелей мәміле арқылы қараңыз. Жылы, жұмыс уақыты мен аймақ бойынша салыстырыңыз.'},
        "ur": {"title": 'استعمال شدہ skid steer اور loader لسٹنگز | Gulsakginara', "description": 'Gulsakginara پر ملک بھر کے استعمال شدہ skid steer اور loader اشتہارات براہِ راست تجارت اور تازہ قیمتوں کے ساتھ دیکھیں۔ سال، گھنٹوں اور علاقے کے لحاظ سے موازنہ کریں۔'},
        "es": {"title": 'Minicargadoras y cargadoras usadas — anuncios y precios | Gulsakginara', "description": 'Consulte minicargadoras y cargadoras usadas en todo el país con precios en vivo y comercio directo en Gulsakginara. Compare por año, horas de uso y región.'},
    },
    "crane": {
        "ko": {"title": '중고 크레인 매물·실시간 시세 | 굴삭기나라', "description": '전국 중고 크레인 매물을 실시간 등록 시세와 함께 직거래로 확인하세요. 톤수·연식·지역별로 매물을 비교할 수 있습니다 — 굴삭기나라.'},
        "en": {"title": 'Used Crane Listings & Live Prices | Gulsakginara', "description": 'Browse used cranes nationwide with live listing prices and direct trade on Gulsakginara. Compare by tonnage, year, and region.'},
        "ru": {"title": 'Б/у краны — объявления и актуальные цены | Gulsakginara', "description": 'Смотрите объявления о б/у кранах по всей стране с актуальными ценами и прямыми сделками на Gulsakginara. Сравнивайте по грузоподъёмности, году и региону.'},
        "vi": {"title": 'Cần cẩu cũ — tin đăng & giá thị trường | Gulsakginara', "description": 'Xem tin cần cẩu cũ toàn quốc với giá đăng thời gian thực và giao dịch trực tiếp trên Gulsakginara. So sánh theo tải trọng, năm và khu vực.'},
        "mn": {"title": 'Хэрэглэсэн краны зар & бодит үнэ | Gulsakginara', "description": 'Gulsakginara дээр бүх улсын хэрэглэсэн краны зарыг бодит үнэтэй, шууд арилжаагаар үзнэ үү. Ачааны хүч, он, бүс нутагаар харьцуулна.'},
        "ky": {"title": 'Колдонулган кран жарыялары жана актуалдуу баалар | Gulsakginara', "description": 'Gulsakginaraда өлкө боюнча колдонулган кран жарыяларын жандуу баалар жана түз арилжа менен көрүңүз. Жүктөмдүүлүк, жылы жана аймак боюнча салыштырыңыз.'},
        "uz": {"title": "Ishlatilgan kran e'lonlari va jonli narxlar | Gulsakginara", "description": "Gulsakginarada butun mamlakat bo'ylab ishlatilgan kran e'lonlarini jonli narxlar va to'g'ridan-to'g'ri bitimlar bilan ko'ring. Yuk ko'tarish, yil va hudud bo'yicha solishtiring."},
        "kk": {"title": 'Қолданылған кран хабарландырулары мен нақты бағалар | Gulsakginara', "description": 'Gulsakginaraда ел бойынша қолданылған кран хабарландыруларын нақты бағалармен және тікелей мәміле арқылы қараңыз. Жүк көтеру, жылы мен аймақ бойынша салыстырыңыз.'},
        "ur": {"title": 'استعمال شدہ کرین لسٹنگز اور براہِ راست قیمتیں | Gulsakginara', "description": 'Gulsakginara پر ملک بھر کے استعمال شدہ کرین اشتہارات براہِ راست تجارت اور تازہ قیمتوں کے ساتھ دیکھیں۔ ٹننیج، سال اور علاقے کے لحاظ سے موازنہ کریں۔'},
        "es": {"title": 'Grúas usadas — anuncios y precios en vivo | Gulsakginara', "description": 'Consulte grúas usadas en todo el país con precios en vivo y comercio directo en Gulsakginara. Compare por tonelaje, año y región.'},
    },
    "attachment": {
        "ko": {"title": '중고 어태치먼트 매물·실시간 시세 | 굴삭기나라', "description": '브레이커·집게·버킷 등 중고 어태치먼트 매물을 실시간 등록 시세와 함께 직거래로 확인하세요 — 굴삭기나라.'},
        "en": {"title": 'Used Attachment Listings & Live Prices | Gulsakginara', "description": 'Browse used attachments — breakers, grapples, buckets — with live listing prices and direct trade on Gulsakginara.'},
        "ru": {"title": 'Б/у навесное оборудование — объявления и цены | Gulsakginara', "description": 'Смотрите объявления о б/у навесном оборудовании — гидромолоты, грейферы, ковши — с актуальными ценами и прямыми сделками на Gulsakginara.'},
        "vi": {"title": 'Phụ kiện gắn máy cũ — tin đăng & giá thị trường | Gulsakginara', "description": 'Xem tin phụ kiện gắn máy cũ — búa phá, gầu, v.v. — với giá đăng thời gian thực và giao dịch trực tiếp trên Gulsakginara.'},
        "mn": {"title": 'Хэрэглэсэн хавсралтын зар & бодит үнэ | Gulsakginara', "description": 'Gulsakginara дээр хэрэглэсэн хавсралтын зарыг — эвдэгч, бариул, авс — бодит үнэтэй, шууд арилжаагаар үзнэ үү.'},
        "ky": {"title": 'Колдонулган тиркеме жарыялары жана актуалдуу баалар | Gulsakginara', "description": 'Gulsakginaraда колдонулган тиркеме жарыяларын — молот, кармагыч, ковш — жандуу баалар жана түз арилжа менен көрүңүз.'},
        "uz": {"title": "Ishlatilgan uskuna biriktirmalari e'lonlari | Gulsakginara", "description": "Gulsakginarada ishlatilgan biriktirmalar — mолот, tutqich, kovsh — e'lonlarini jonli narxlar va to'g'ridan-to'g'ri bitimlar bilan ko'ring."},
        "kk": {"title": 'Қолданылған тіркеме хабарландырулары мен нақты бағалар | Gulsakginara', "description": 'Gulsakginaraда қолданылған тіркемелер — молот, тістеуіш, ковш — хабарландыруларын нақты бағалармен және тікелей мәміле арқылы қараңыз.'},
        "ur": {"title": 'استعمال شدہ attachment لسٹنگز اور براہِ راست قیمتیں | Gulsakginara', "description": 'Gulsakginara پر استعمال شدہ attachments — breakers، grapples، buckets — براہِ راست تجارت اور تازہ قیمتوں کے ساتھ دیکھیں۔'},
        "es": {"title": 'Accesorios usados — anuncios y precios en vivo | Gulsakginara', "description": 'Consulte accesorios usados — martillos, cucharones, pinzas — con precios en vivo y comercio directo en Gulsakginara.'},
    },
    "other": {
        "ko": {"title": '중고 건설기계·중장비 매물·실시간 시세 | 굴삭기나라', "description": '그 밖의 중고 건설기계·중장비 매물을 실시간 등록 시세와 함께 직거래로 확인하세요. 종류·연식·지역별로 비교할 수 있습니다 — 굴삭기나라.'},
        "en": {"title": 'Used Construction Equipment Listings & Live Prices | Gulsakginara', "description": 'Browse other used construction and heavy equipment with live listing prices and direct trade on Gulsakginara. Compare by type, year, and region.'},
        "ru": {"title": 'Б/у строительная и спецтехника — объявления и цены | Gulsakginara', "description": 'Смотрите прочие объявления о б/у строительной и спецтехнике с актуальными ценами и прямыми сделками на Gulsakginara. Сравнивайте по типу, году и региону.'},
        "vi": {"title": 'Thiết bị xây dựng cũ khác — tin đăng & giá thị trường | Gulsakginara', "description": 'Xem các loại thiết bị xây dựng và hạng nặng cũ khác với giá đăng thời gian thực và giao dịch trực tiếp trên Gulsakginara. So sánh theo loại, năm và khu vực.'},
        "mn": {"title": 'Бусад хэрэглэсэн барилгын техникийн зар & бодит үнэ | Gulsakginara', "description": 'Gulsakginara дээр бусад хэрэглэсэн барилга, хүнд техникийн зарыг бодит үнэтэй, шууд арилжаагаар үзнэ үү. Төрөл, он, бүс нутагаар харьцуулна.'},
        "ky": {"title": 'Башка колдонулган курулуш техникасы жарыялары | Gulsakginara', "description": 'Gulsakginaraда башка колдонулган курулуш жана оор техника жарыяларын жандуу баалар жана түз арилжа менен көрүңүз. Түрү, жылы жана аймак боюнча салыштырыңыз.'},
        "uz": {"title": "Boshqa ishlatilgan qurilish texnikasi e'lonlari | Gulsakginara", "description": "Gulsakginarada boshqa ishlatilgan qurilish va og'ir texnika e'lonlarini jonli narxlar va to'g'ridan-to'g'ri bitimlar bilan ko'ring. Turi, yil va hudud bo'yicha solishtiring."},
        "kk": {"title": 'Басқа қолданылған құрылыс техникасы хабарландырулары | Gulsakginara', "description": 'Gulsakginaraда басқа қолданылған құрылыс және ауыр техника хабарландыруларын нақты бағалармен және тікелей мәміле арқылы қараңыз. Түрі, жылы мен аймақ бойынша салыстырыңыз.'},
        "ur": {"title": 'دیگر استعمال شدہ construction equipment لسٹنگز | Gulsakginara', "description": 'Gulsakginara پر دیگر استعمال شدہ construction اور بھاری مشینری براہِ راست تجارت اور تازہ قیمتوں کے ساتھ دیکھیں۔ قسم، سال اور علاقے کے لحاظ سے موازنہ کریں۔'},
        "es": {"title": 'Otra maquinaria de construcción usada — anuncios y precios | Gulsakginara', "description": 'Consulte otra maquinaria de construcción y pesada usada con precios en vivo y comercio directo en Gulsakginara. Compare por tipo, año y región.'},
    },
}


# Equipment detail page SEO: manufacturer romanization + phrase templates.
# TODO: native speaker review pending for all non-Korean entries.

MANUFACTURER_ROMANIZATION = {
    "두산": "Doosan",
    "볼보": "Volvo",
    "얀마": "Yanmar",
    "HD 현대": "HD Hyundai",
    "현대": "Hyundai",
    "SK": "Kobelco",
    "구보다": "Kubota",
    "구보": "Kubota",
    "히타치": "Hitachi",
    "코벨코": "Kobelco",
    "솔라": "Doosan Solar",
    "캐타필라": "Caterpillar",
    "케터피라": "Caterpillar",
    "밥캣": "Bobcat",
    "밥켓": "Bobcat",
    "바브캣": "Bobcat",
    "바브켓": "Bobcat",
    ",바브캣": "Bobcat",
    "코맥스": "Komax",
    "기타": "Other",
    "두산정품": "Doosan",
    "갤": "Gehl",
    "GEHL": "GEHL",
}

EQUIPMENT_SEO_PHRASES = {
    "ko": {
        "used": "중고",
        "sale": "매매",
        "listing": "매물입니다.",
        "year_suffix": "년식",
        "hours_label": "가동시간",
        "hours_unit": "시간",
        "sold_notice": "현재 판매가 완료된 매물입니다.",
        "cta": "판매가격과 상세사진을 확인하고 판매자에게 직접 문의하세요.",
        "tail_template": "굴삭기나라에서 다양한 {used} {type} 매물을 만나보세요.",
        "brand_suffix": "굴삭기나라",
        "spec_bridge": "{specs} 매물로, ",
        "type_fallback": "중장비",
    },
    "en": {
        "used": "Used",
        "sale": "for Sale",
        "listing": "for sale.",
        "year_suffix": "",
        "hours_label": "Operating hours",
        "hours_unit": " hrs",
        "sold_notice": "This listing has been sold.",
        "cta": "View price and photos, then contact the seller directly.",
        "tail_template": "Find more used {type} listings on Gulsakginara.",
        "brand_suffix": "Gulsakginara",
        "spec_bridge": "{specs}. ",
        "type_fallback": "heavy equipment",
    },
    "ru": {
        "used": "Б/у",
        "sale": "продажа",
        "listing": "в продаже.",
        "year_suffix": " г.",
        "hours_label": "Наработка",
        "hours_unit": " ч",
        "sold_notice": "Этот объект уже продан.",
        "cta": "Смотрите цену и фото и свяжитесь с продавцом напрямую.",
        "tail_template": "Больше объявлений о б/у {type} на Gulsakginara.",
        "brand_suffix": "Gulsakginara",
        "spec_bridge": "{specs}. ",
        "type_fallback": "спецтехника",
    },
    "vi": {
        "used": "Máy cũ",
        "sale": "bán",
        "listing": "đang rao bán.",
        "year_suffix": "",
        "hours_label": "Giờ vận hành",
        "hours_unit": " giờ",
        "sold_notice": "Tin đăng này đã bán xong.",
        "cta": "Xem giá và ảnh chi tiết, liên hệ trực tiếp người bán.",
        "tail_template": "Xem thêm tin {used} {type} trên Gulsakginara.",
        "brand_suffix": "Gulsakginara",
        "spec_bridge": "{specs}. ",
        "type_fallback": "thiết bị hạng nặng",
    },
    "mn": {
        "used": "Хэрэглэсэн",
        "sale": "худалдаа",
        "listing": "зар мэдээлэл.",
        "year_suffix": " он",
        "hours_label": "Ажлын цаг",
        "hours_unit": " цаг",
        "sold_notice": "Энэ зар одоогоор зарагдсан.",
        "cta": "Үнэ, зургийг үзээд борлуулагчтай шууд холбогдоно уу.",
        "tail_template": "Gulsakginara дээр илүү олон {used} {type} зар үзнэ үү.",
        "brand_suffix": "Gulsakginara",
        "spec_bridge": "{specs}. ",
        "type_fallback": "хүнд техник",
    },
    "ky": {
        "used": "Колдонулган",
        "sale": "сатуу",
        "listing": "жарыя.",
        "year_suffix": " жыл",
        "hours_label": "Иш сааты",
        "hours_unit": " саат",
        "sold_notice": "Бул жарыя сатылып бүткөн.",
        "cta": "Баасын жана сүрөттөрдү көрүп, сатуучуга түз кайрылыңыз.",
        "tail_template": "Gulsakginaraда көбүрөөк {used} {type} жарыяларын көрүңүз.",
        "brand_suffix": "Gulsakginara",
        "spec_bridge": "{specs}. ",
        "type_fallback": "оор техника",
    },
    "uz": {
        "used": "Ishlatilgan",
        "sale": "sotuv",
        "listing": "e'lon.",
        "year_suffix": " yil",
        "hours_label": "Ish soati",
        "hours_unit": " soat",
        "sold_notice": "Bu e'lon sotilgan.",
        "cta": "Narx va rasmlarni ko'rib, sotuvchi bilan to'g'ridan-to'g'ri bog'laning.",
        "tail_template": "Gulsakginarada ko'proq {used} {type} e'lonlarini ko'ring.",
        "brand_suffix": "Gulsakginara",
        "spec_bridge": "{specs}. ",
        "type_fallback": "og'ir texnika",
    },
    "kk": {
        "used": "Қолданылған",
        "sale": "сату",
        "listing": "хабарландыру.",
        "year_suffix": " ж.",
        "hours_label": "Жұмыс уақыты",
        "hours_unit": " сағ",
        "sold_notice": "Бұл хабарландыру сатылған.",
        "cta": "Баға мен фотосуреттерді қарап, сатушыға тікелей хабарласыңыз.",
        "tail_template": "Gulsakginaraда көбірек {used} {type} хабарландыруларын қараңыз.",
        "brand_suffix": "Gulsakginara",
        "spec_bridge": "{specs}. ",
        "type_fallback": "ауыр техника",
    },
    "ur": {
        "used": "استعمال شدہ",
        "sale": "فروخت",
        "listing": "لسٹنگ ہے۔",
        "year_suffix": " ماڈل",
        "hours_label": "چلنے کے گھنٹے",
        "hours_unit": "",
        "sold_notice": "یہ لسٹنگ فروخت ہو چکی ہے۔",
        "cta": "قیمت اور تفصیلی تصاویر دیکھیں اور فروخت کنندہ سے براہِ راست رابطہ کریں۔",
        "tail_template": "Gulsakginara پر مزید {used} {type} لسٹنگز دیکھیں۔",
        "brand_suffix": "Gulsakginara",
        "spec_bridge": "{specs}۔ ",
        "type_fallback": "بھاری مشینری",
    },
    "es": {
        "used": "Usado",
        "sale": "en venta",
        "listing": "en venta.",
        "year_suffix": "",
        "hours_label": "Horas de uso",
        "hours_unit": " h",
        "sold_notice": "Este anuncio ya se vendió.",
        "cta": "Consulte el precio y las fotos y contacte al vendedor directamente.",
        "tail_template": "Encuentre más anuncios de {type} usados en Gulsakginara.",
        "brand_suffix": "Gulsakginara",
        "spec_bridge": "{specs}. ",
        "type_fallback": "maquinaria pesada",
    },
}


def normalize_seo_lang(lang_code: str) -> str:
    code = (lang_code or "ko").strip().lower()
    if code not in SUPPORTED_LANGS:
        return "ko"
    return code


def get_equipment_seo_phrases(lang_code: str) -> dict:
    code = normalize_seo_lang(lang_code)
    return dict(EQUIPMENT_SEO_PHRASES.get(code, EQUIPMENT_SEO_PHRASES["ko"]))


def get_manufacturer_label(manufacturer: str, lang_code: str) -> str:
    raw = (manufacturer or "").strip()
    if not raw:
        return ""
    if normalize_seo_lang(lang_code) == "ko":
        return raw
    return MANUFACTURER_ROMANIZATION.get(raw, raw)


def get_category_type_label(equipment_type_code: str, lang_code: str, fallback_display: str = "") -> str:
    code = normalize_seo_lang(lang_code)
    cat = (equipment_type_code or "").strip()
    if cat in CATEGORY_DISPLAY_NAMES:
        label = CATEGORY_DISPLAY_NAMES[cat].get(code) or CATEGORY_DISPLAY_NAMES[cat].get("ko")
        if label:
            return label
    if fallback_display:
        return fallback_display
    return get_equipment_seo_phrases(code).get("type_fallback", "중장비")


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

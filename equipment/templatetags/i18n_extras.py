from django import template
import re

register = template.Library()


I18N = {
    "ko": {
        "lang_label": "한국어",
        "nav_market": "중고매물",
        "nav_market_view": "매물보기",
        "nav_jobs": "구인구직",
        "nav_attachment": "할부/금융",
        "nav_youtube": "정비유튜브",
        "nav_parts_as": "부품 A/S",
        "nav_soil": "현장 자재 나눔",
        "nav_chat": "채팅",
        "nav_mypage": "마이페이지",
        "nav_login": "로그인",
        "nav_logout": "로그아웃",
        "nav_signup": "회원가입",
        "nav_register": "매물등록",
        "mobile_home": "홈",
        "mobile_listings": "매물",
        "mobile_jobs": "구인구직",
        "mobile_my": "마이",
        "service_all": "전체 서비스",
        "service_trade": "장비 거래",
        "service_menu": "서비스",
        "service_market_home": "중고매물 홈",
        "service_attachment_sub": "어태치먼트",
        "service_parts_as_shop": "부품 A/S",
        "service_social_connect": "소셜 계정 연결",
        "mypage_title": "마이페이지",
        "mypage_favorites": "찜한 매물",
        "mypage_my_listings": "내가 올린 매물",
        "account_delete": "회원 탈퇴",
        "account_delete_cancel": "취소",
        "account_delete_confirm": "정말 탈퇴하시겠습니까?",
        "account_delete_submit": "정말 탈퇴합니다",
    },
    "en": {
        "lang_label": "English",
        "nav_market": "Listings",
        "nav_market_view": "Listings",
        "nav_jobs": "Jobs",
        "nav_attachment": "Finance",
        "nav_youtube": "Repair YouTube",
        "nav_parts_as": "Parts/AS",
        "nav_soil": "Site Material Share",
        "nav_chat": "Chats",
        "nav_mypage": "My Page",
        "nav_login": "Login",
        "nav_logout": "Logout",
        "nav_signup": "Sign Up",
        "nav_register": "Post Listing",
        "mobile_home": "Home",
        "mobile_listings": "Listings",
        "mobile_jobs": "Jobs",
        "mobile_my": "My",
        "service_all": "All Services",
        "service_trade": "Equipment Trade",
        "service_menu": "Services",
        "service_market_home": "Listings Home",
        "service_attachment_sub": "Attachment",
        "service_parts_as_shop": "Parts A/S Shop",
        "service_social_connect": "Connect Social Account",
        "mypage_title": "My Page",
        "mypage_favorites": "Favorites",
        "mypage_my_listings": "My Listings",
        "account_delete": "Delete Account",
        "account_delete_cancel": "Cancel",
        "account_delete_confirm": "Are you sure you want to delete your account?",
        "account_delete_submit": "Yes, delete my account",
    },
    "ru": {
        "lang_label": "Русский",
        "nav_market": "Объявления",
        "nav_market_view": "Объявления",
        "nav_jobs": "Работа",
        "nav_attachment": "Финансы",
        "nav_youtube": "YouTube по ремонту",
        "nav_parts_as": "Запчасти/Сервис",
        "nav_soil": "Раздача стройматериалов",
        "nav_chat": "Чаты",
        "nav_mypage": "Моя страница",
        "nav_login": "Войти",
        "nav_logout": "Выйти",
        "nav_signup": "Регистрация",
        "nav_register": "Добавить объявление",
        "mobile_home": "Главная",
        "mobile_listings": "Объявления",
        "mobile_jobs": "Работа",
        "mobile_my": "Мой",
        "service_all": "Все сервисы",
        "service_trade": "Техника",
        "service_menu": "Сервисы",
        "service_market_home": "Главная объявлений",
        "service_attachment_sub": "Навесное",
        "service_parts_as_shop": "Запчасти A/S",
        "service_social_connect": "Подключить соцаккаунт",
        "mypage_title": "Моя страница",
        "mypage_favorites": "Избранные объявления",
        "mypage_my_listings": "Мои объявления",
        "account_delete": "Удалить аккаунт",
        "account_delete_cancel": "Отмена",
        "account_delete_confirm": "Вы уверены, что хотите удалить аккаунт?",
        "account_delete_submit": "Да, удалить аккаунт",
    },
    "vi": {
        "lang_label": "Tiếng Việt",
        "nav_market": "Tin đăng",
        "nav_market_view": "Xem tin",
        "nav_jobs": "Việc làm",
        "nav_attachment": "Tài chính",
        "nav_youtube": "YouTube sửa chữa",
        "nav_parts_as": "Phụ tùng/AS",
        "nav_soil": "Chia sẻ vật liệu công trường",
        "nav_chat": "Chat",
        "nav_mypage": "Trang của tôi",
        "nav_login": "Đăng nhập",
        "nav_logout": "Đăng xuất",
        "nav_signup": "Đăng ký",
        "nav_register": "Đăng bán",
        "mobile_home": "Trang chủ",
        "mobile_listings": "Tin đăng",
        "mobile_jobs": "Việc làm",
        "mobile_my": "Của tôi",
        "service_all": "Tất cả dịch vụ",
        "service_trade": "Giao dịch thiết bị",
        "service_menu": "Dịch vụ",
        "service_market_home": "Trang tin đăng",
        "service_attachment_sub": "Phụ kiện",
        "service_parts_as_shop": "Phụ tùng A/S",
        "service_social_connect": "Kết nối tài khoản mạng xã hội",
        "mypage_title": "Trang của tôi",
        "mypage_favorites": "Tin đã lưu",
        "mypage_my_listings": "Tin tôi đã đăng",
        "account_delete": "Xóa tài khoản",
        "account_delete_cancel": "Hủy",
        "account_delete_confirm": "Bạn có chắc muốn xóa tài khoản?",
        "account_delete_submit": "Tôi đồng ý xóa tài khoản",
    },
    "mn": {
        "lang_label": "Монгол",
        "lang_short": "MN",
        "nav_market": "Зар",
        "nav_market_view": "Зар үзэх",
        "nav_jobs": "Ажлын байр",
        "nav_attachment": "Санхүүжилт",
        "nav_youtube": "Засвар YouTube",
        "nav_parts_as": "Сэлбэг/AS",
        "nav_soil": "Барилгын материал",
        "nav_chat": "Чат",
        "nav_mypage": "Миний хуудас",
        "nav_login": "Нэвтрэх",
        "nav_logout": "Гарах",
        "nav_signup": "Бүртгүүлэх",
        "nav_register": "Зар бүртгэх",
        "mobile_home": "Нүүр",
        "mobile_listings": "Зар",
        "mobile_jobs": "Ажил",
        "mobile_my": "Миний",
        "service_all": "Бүх үйлчилгээ",
        "service_trade": "Техникийн худалдаа",
        "service_menu": "Үйлчилгээ",
        "service_market_home": "Зарын нүүр",
        "service_attachment_sub": "Хавсралт",
        "service_parts_as_shop": "Сэлбэг A/S",
        "service_social_connect": "Сошиал холбох",
        "mypage_title": "Миний хуудас",
        "mypage_favorites": "Хадгалсан зар",
        "mypage_my_listings": "Миний зар",
        "account_delete": "Бүртгэл устгах",
        "account_delete_cancel": "Цуцлах",
        "account_delete_confirm": "Бүртгэлээ устгах уу?",
        "account_delete_submit": "Тийм, устгана",
    },
    "ky": {
        "lang_label": "Кыргызча",
        "lang_short": "KY",
        "nav_market": "Жарыялар",
        "nav_market_view": "Жарыяларды көрүү",
        "nav_jobs": "Жумуш",
        "nav_attachment": "Финансы",
        "nav_youtube": "Оңдоо YouTube",
        "nav_parts_as": "Запчасттар/AS",
        "nav_soil": "Курулуш материалдары",
        "nav_chat": "Чат",
        "nav_mypage": "Менин баракчам",
        "nav_login": "Кирүү",
        "nav_logout": "Чыгуу",
        "nav_signup": "Катталуу",
        "nav_register": "Жарыя кошуу",
        "mobile_home": "Башкы",
        "mobile_listings": "Жарыя",
        "mobile_jobs": "Жумуш",
        "mobile_my": "Менин",
        "service_all": "Бардык кызматтар",
        "service_trade": "Техника соодасы",
        "service_menu": "Кызматтар",
        "service_market_home": "Жарыялар башкысы",
        "service_attachment_sub": "Тиркеме",
        "service_parts_as_shop": "Запчасттар A/S",
        "service_social_connect": "Социалдык аккаунт",
        "mypage_title": "Менин баракчам",
        "mypage_favorites": "Сакталгандар",
        "mypage_my_listings": "Менин жарыяларым",
        "account_delete": "Аккаунтту өчүрүү",
        "account_delete_cancel": "Жокко чыгаруу",
        "account_delete_confirm": "Аккаунтту өчүрөсүзбү?",
        "account_delete_submit": "Ооба, өчүрөм",
    },
    "uz": {
        "lang_label": "Oʻzbekcha",
        "lang_short": "UZ",
        "nav_market": "E'lonlar",
        "nav_market_view": "E'lonlarni ko'rish",
        "nav_jobs": "Ishlar",
        "nav_attachment": "Moliya",
        "nav_youtube": "Ta'mirlash YouTube",
        "nav_parts_as": "Ehtiyot qismlar/AS",
        "nav_soil": "Qurilish materiallari",
        "nav_chat": "Chat",
        "nav_mypage": "Mening sahifam",
        "nav_login": "Kirish",
        "nav_logout": "Chiqish",
        "nav_signup": "Ro'yxatdan o'tish",
        "nav_register": "E'lon qo'shish",
        "mobile_home": "Bosh",
        "mobile_listings": "E'lon",
        "mobile_jobs": "Ish",
        "mobile_my": "Mening",
        "service_all": "Barcha xizmatlar",
        "service_trade": "Texnika savdosi",
        "service_menu": "Xizmatlar",
        "service_market_home": "E'lonlar bosh sahifa",
        "service_attachment_sub": "Nasadka",
        "service_parts_as_shop": "Ehtiyot qismlar A/S",
        "service_social_connect": "Ijtimoiy tarmoq ulanishi",
        "mypage_title": "Mening sahifam",
        "mypage_favorites": "Saqlanganlar",
        "mypage_my_listings": "Mening e'lonlarim",
        "account_delete": "Hisobni o'chirish",
        "account_delete_cancel": "Bekor qilish",
        "account_delete_confirm": "Hisobni o'chirmoqchimisiz?",
        "account_delete_submit": "Ha, o'chiraman",
    },
    "kk": {
        "lang_label": "Қазақша",
        "lang_short": "KK",
        "nav_market": "Хабарландырулар",
        "nav_market_view": "Хабарландыруларды көру",
        "nav_jobs": "Жұмыс",
        "nav_attachment": "Қаржы",
        "nav_youtube": "Жөндеу YouTube",
        "nav_parts_as": "Бөлшектер/AS",
        "nav_soil": "Құрылыс материалдары",
        "nav_chat": "Чат",
        "nav_mypage": "Менің бетім",
        "nav_login": "Кіру",
        "nav_logout": "Шығу",
        "nav_signup": "Тіркелу",
        "nav_register": "Хабарландыру қосу",
        "mobile_home": "Басты",
        "mobile_listings": "Хабарландыру",
        "mobile_jobs": "Жұмыс",
        "mobile_my": "Менің",
        "service_all": "Барлық қызметтер",
        "service_trade": "Техника саудасы",
        "service_menu": "Қызметтер",
        "service_market_home": "Хабарландырулар басты",
        "service_attachment_sub": "Тіркеме",
        "service_parts_as_shop": "Бөлшектер A/S",
        "service_social_connect": "Әлеуметтік аккаунт",
        "mypage_title": "Менің бетім",
        "mypage_favorites": "Сақталғандар",
        "mypage_my_listings": "Менің хабарландыруларым",
        "account_delete": "Аккаунтты жою",
        "account_delete_cancel": "Болдырмау",
        "account_delete_confirm": "Аккаунтты жойғыңыз келе ме?",
        "account_delete_submit": "Иә, жоямын",
    },
    "ur": {
        "lang_label": "پښتو / اردو",
        "lang_short": "UR",
        "nav_market": "اشتہارات",
        "nav_market_view": "اشتہارات دیکھیں",
        "nav_jobs": "ملازمتیں",
        "nav_attachment": "فنانس / قسط",
        "nav_youtube": "مرمت YouTube",
        "nav_parts_as": "پارٹس / سروس",
        "nav_soil": "سائٹ مواد بانٹنا",
        "nav_chat": "چیٹ",
        "nav_mypage": "میرا صفحہ",
        "nav_login": "لاگ ان",
        "nav_logout": "لاگ آؤٹ",
        "nav_signup": "سائن اپ",
        "nav_register": "اشتہار شامل کریں",
        "mobile_home": "ہوم",
        "mobile_listings": "اشتہارات",
        "mobile_jobs": "ملازمت",
        "mobile_my": "میرا",
        "service_all": "تمام سروسز",
        "service_trade": "آلات کی تجارت",
        "service_menu": "سروسز",
        "service_market_home": "اشتہارات ہوم",
        "service_attachment_sub": "اٹیچمنٹ",
        "service_parts_as_shop": "پارٹس A/S",
        "service_social_connect": "سوشل اکاؤنٹ منسلک",
        "mypage_title": "میرا صفحہ",
        "mypage_favorites": "پسندیدہ",
        "mypage_my_listings": "میری اشتہارات",
        "account_delete": "اکاؤنٹ حذف",
        "account_delete_cancel": "منسوخ",
        "account_delete_confirm": "کیا آپ واقعی اکاؤنٹ حذف کرنا چاہتے ہیں؟",
        "account_delete_submit": "ہاں، حذف کریں",
    },
    "es": {
        "lang_label": "Español",
        "lang_short": "ES",
        "nav_market": "Anuncios",
        "nav_market_view": "Ver anuncios",
        "nav_jobs": "Empleo",
        "nav_attachment": "Financiación",
        "nav_youtube": "YouTube reparación",
        "nav_parts_as": "Repuestos/AS",
        "nav_soil": "Compartir materiales",
        "nav_chat": "Chat",
        "nav_mypage": "Mi página",
        "nav_login": "Iniciar sesión",
        "nav_logout": "Cerrar sesión",
        "nav_signup": "Registrarse",
        "nav_register": "Publicar anuncio",
        "mobile_home": "Inicio",
        "mobile_listings": "Anuncios",
        "mobile_jobs": "Empleo",
        "mobile_my": "Mi cuenta",
        "service_all": "Todos los servicios",
        "service_trade": "Comercio de equipos",
        "service_menu": "Servicios",
        "service_market_home": "Inicio anuncios",
        "service_attachment_sub": "Accesorio",
        "service_parts_as_shop": "Repuestos A/S",
        "service_social_connect": "Conectar cuenta social",
        "mypage_title": "Mi página",
        "mypage_favorites": "Favoritos",
        "mypage_my_listings": "Mis anuncios",
        "account_delete": "Eliminar cuenta",
        "account_delete_cancel": "Cancelar",
        "account_delete_confirm": "¿Seguro que desea eliminar su cuenta?",
        "account_delete_submit": "Sí, eliminar cuenta",
    },
}

LANGUAGE_ORDER = ("ko", "en", "ru", "vi", "mn", "ky", "uz", "kk", "ur", "es")
SUPPORTED_LANGS = frozenset(I18N.keys())

# 기존 언어에 모바일 약어 추가
for _code, _short in (("ko", "KO"), ("en", "EN"), ("ru", "RU"), ("vi", "VI")):
    I18N[_code].setdefault("lang_short", _short)

# 채팅·흙나눔·공통 UI (템플릿 |tr 용)
_UI_EXTRA = {
    "ko": {
        "chat_title": "내 채팅", "chat_me": "나", "chat_seller": "판매자", "chat_buyer": "구매자",
        "chat_start": "대화를 시작해보세요", "chat_empty": "아직 채팅이 없습니다. 매물 상세에서 '채팅으로 문의하기'를 눌러 시작하세요.",
        "chat_send_ph": "메시지를 입력하세요", "chat_send": "전송", "chat_send_hint": "메시지를 입력해 보세요.",
        "soil_write": "글쓰기", "soil_empty": "등록된 글이 없습니다.", "soil_delete_confirm": "이 글을 삭제할까요?",
        "btn_edit": "수정", "btn_delete": "삭제", "btn_cancel": "취소", "username_suffix": "님",
        "cat_excavator": "굴삭기", "cat_forklift": "지게차", "cat_dump": "덤프트럭",
        "cat_loader": "스키로더/로더", "cat_crane": "크레인", "cat_other": "기타 중장비",
    },
    "en": {
        "chat_title": "My Chats", "chat_me": "Me", "chat_seller": "Seller", "chat_buyer": "Buyer",
        "chat_start": "Start the conversation", "chat_empty": "No chats yet. Start from a listing with Chat with seller.",
        "chat_send_ph": "Type a message...", "chat_send": "Send", "chat_send_hint": "Send a message.",
        "soil_write": "Post", "soil_empty": "No posts yet.", "soil_delete_confirm": "Delete this post?",
        "btn_edit": "Edit", "btn_delete": "Delete", "btn_cancel": "Cancel", "username_suffix": "",
        "cat_excavator": "Excavator", "cat_forklift": "Forklift", "cat_dump": "Dump truck",
        "cat_loader": "Skid steer/Loader", "cat_crane": "Crane", "cat_other": "Other heavy equipment",
    },
    "ru": {
        "chat_title": "Мои чаты", "chat_me": "Я", "chat_seller": "Продавец", "chat_buyer": "Покупатель",
        "chat_start": "Начните диалог", "chat_empty": "Чатов пока нет. Начните с объявления — «Написать продавцу».",
        "chat_send_ph": "Введите сообщение...", "chat_send": "Отправить", "chat_send_hint": "Введите сообщение.",
        "soil_write": "Опубликовать", "soil_empty": "Записей пока нет.", "soil_delete_confirm": "Удалить эту запись?",
        "btn_edit": "Изменить", "btn_delete": "Удалить", "btn_cancel": "Отмена", "username_suffix": "",
        "cat_excavator": "Экскаватор", "cat_forklift": "Погрузчик", "cat_dump": "Самосвал",
        "cat_loader": "Погрузчик", "cat_crane": "Кран", "cat_other": "Другая техника",
    },
    "vi": {
        "chat_title": "Chat của tôi", "chat_me": "Tôi", "chat_seller": "Người bán", "chat_buyer": "Người mua",
        "chat_start": "Bắt đầu trò chuyện", "chat_empty": "Chưa có chat. Bắt đầu từ trang chi tiết tin đăng.",
        "chat_send_ph": "Nhập tin nhắn...", "chat_send": "Gửi", "chat_send_hint": "Gửi tin nhắn.",
        "soil_write": "Đăng bài", "soil_empty": "Chưa có bài viết.", "soil_delete_confirm": "Xóa bài này?",
        "btn_edit": "Sửa", "btn_delete": "Xóa", "btn_cancel": "Hủy", "username_suffix": "",
        "cat_excavator": "Máy xúc", "cat_forklift": "Xe nâng", "cat_dump": "Xe ben",
        "cat_loader": "Xe xúc", "cat_crane": "Cần cẩu", "cat_other": "Thiết bị khác",
    },
    "mn": {
        "chat_title": "Миний чат", "chat_me": "Би", "chat_seller": "Зарагч", "chat_buyer": "Худалдан авагч",
        "chat_start": "Яриа эхлүүлээрэй", "chat_empty": "Чат байхгүй. Зарын дэлгэрэнгээс чат эхлүүлнэ үү.",
        "chat_send_ph": "Зурвас бичнэ үү...", "chat_send": "Илгээх", "chat_send_hint": "Зурвас илгээнэ үү.",
        "soil_write": "Бичих", "soil_empty": "Бичлэг байхгүй.", "soil_delete_confirm": "Энэ бичлэгийг устгах уу?",
        "btn_edit": "Засах", "btn_delete": "Устгах", "btn_cancel": "Цуцлах", "username_suffix": "",
        "cat_excavator": "Экскаватор", "cat_forklift": "Автопогрузчик", "cat_dump": "Самосвал",
        "cat_loader": "Погрузчик", "cat_crane": "Кран", "cat_other": "Бусу тяжелая техника",
    },
    "ky": {
        "chat_title": "Менин чаттар", "chat_me": "Мен", "chat_seller": "Сатуучу", "chat_buyer": "Сатып алуучу",
        "chat_start": "Сүйлөшүүнү баштаңыз", "chat_empty": "Азырынча чат жок. Жарыядан баштаңыз.",
        "chat_send_ph": "Билдирүү жазыңыз...", "chat_send": "Жөнөтүү", "chat_send_hint": "Билдирүү жөнөтүңүз.",
        "soil_write": "Жазуу", "soil_empty": "Жазуу жок.", "soil_delete_confirm": "Бул жазууну өчүрөсүзбү?",
        "btn_edit": "Оңдоо", "btn_delete": "Өчүрүү", "btn_cancel": "Жокко чыгаруу", "username_suffix": "",
        "cat_excavator": "Ekskavator", "cat_forklift": "Yuk ko'targich", "cat_dump": "Samosval",
        "cat_loader": "Pogruzchik", "cat_crane": "Kran", "cat_other": "Boshqa og'ir texnika",
    },
    "uz": {
        "chat_title": "Chatlarim", "chat_me": "Men", "chat_seller": "Sotuvchi", "chat_buyer": "Xaridor",
        "chat_start": "Suhbatni boshlang", "chat_empty": "Hali chat yo'q. E'londan boshlang.",
        "chat_send_ph": "Xabar yozing...", "chat_send": "Yuborish", "chat_send_hint": "Xabar yuboring.",
        "soil_write": "Yozish", "soil_empty": "Yozuvlar yo'q.", "soil_delete_confirm": "Bu yozuv o'chirilsinmi?",
        "btn_edit": "Tahrirlash", "btn_delete": "O'chirish", "btn_cancel": "Bekor qilish", "username_suffix": "",
        "cat_excavator": "Ekskavator", "cat_forklift": "Yuk ko'targich", "cat_dump": "Samosval",
        "cat_loader": "Pogruzchik", "cat_crane": "Kran", "cat_other": "Basqa agyr tekhnika",
    },
    "kk": {
        "chat_title": "Чаттарым", "chat_me": "Мен", "chat_seller": "Сатушы", "chat_buyer": "Сатып алушы",
        "chat_start": "Әңгімені бастаңыз", "chat_empty": "Чат жоқ. Хабарландырудан бастаңыз.",
        "chat_send_ph": "Хабарлама жазыңыз...", "chat_send": "Жіберу", "chat_send_hint": "Хабарлама жіберіңіз.",
        "soil_write": "Жазу", "soil_empty": "Жазба жоқ.", "soil_delete_confirm": "Бұл жазба жойылсын ба?",
        "btn_edit": "Өңдеу", "btn_delete": "Жою", "btn_cancel": "Болдырмау", "username_suffix": "",
        "cat_excavator": "Экскаватор", "cat_forklift": "Автопогрузчик", "cat_dump": "Самосвал",
        "cat_loader": "Погрузчик", "cat_crane": "Кран", "cat_other": "Басқа ауыр техника",
    },
    "ur": {
        "chat_title": "میری چیٹس", "chat_me": "میں", "chat_seller": "فروخت کنندہ", "chat_buyer": "خریدار",
        "chat_start": "بات چیت شروع کریں", "chat_empty": "ابھی چیٹ نہیں۔ اشتہار سے شروع کریں۔",
        "chat_send_ph": "پیغام لکھیں...", "chat_send": "بھیجیں", "chat_send_hint": "پیغام بھیجیں۔",
        "soil_write": "پوسٹ", "soil_empty": "کوئی پوسٹ نہیں۔", "soil_delete_confirm": "یہ پوسٹ حذف کریں؟",
        "btn_edit": "ترمیم", "btn_delete": "حذف", "btn_cancel": "منسوخ", "username_suffix": "",
        "cat_excavator": "ایکسکیویٹر", "cat_forklift": "فورک لفٹ", "cat_dump": "ڈمپ ٹرک",
        "cat_loader": "لوڈر", "cat_crane": "کرین", "cat_other": "دیگر بھاری مشینری",
    },
    "es": {
        "chat_title": "Mis chats", "chat_me": "Yo", "chat_seller": "Vendedor", "chat_buyer": "Comprador",
        "chat_start": "Inicie la conversación", "chat_empty": "Sin chats aún. Empiece desde un anuncio.",
        "chat_send_ph": "Escriba un mensaje...", "chat_send": "Enviar", "chat_send_hint": "Envíe un mensaje.",
        "soil_write": "Publicar", "soil_empty": "No hay publicaciones.", "soil_delete_confirm": "¿Eliminar esta publicación?",
        "btn_edit": "Editar", "btn_delete": "Eliminar", "btn_cancel": "Cancelar", "username_suffix": "",
        "cat_excavator": "Excavadora", "cat_forklift": "Montacargas", "cat_dump": "Camión volquete",
        "cat_loader": "Cargadora", "cat_crane": "Grúa", "cat_other": "Otra maquinaria pesada",
    },
}
for _code in LANGUAGE_ORDER:
    I18N[_code].update(_UI_EXTRA.get(_code, _UI_EXTRA["en"]))

# 장비 상세·우측 레일·부품A/S 카드 (|tr 용)
_EQ_DETAIL_I18N = {
    "ko": {
        "eq_detail_title_description": "상세 설명",
        "eq_detail_description_empty": "내용이 없습니다.",
        "eq_detail_title_photos": "사진 보기",
        "eq_detail_title_similar_stats": "비슷한 기종·년식 시세",
        "eq_detail_similar_none": "같은 제조사·비슷한 년식의 다른 매물이 없어 시세를 산출할 수 없습니다.",
        "eq_detail_title_similar_list": "비슷한 매물 보기",
        "eq_detail_back_to_list": "목록으로",
        "eq_detail_right_title_attachment_ad": "어태치먼트·타이어 광고",
        "eq_detail_register_guide": "등록안내",
        "eq_detail_ad_empty": "유료 광고가 등록되면 이곳에 표시됩니다.",
        "eq_detail_attachment_site_link": "업체 사이트 연결",
        "eq_detail_attachment_intro": "공식 업체 명함",
        "eq_detail_inquiry_title": "문의하기",
        "eq_detail_no_contact": "연락처 없음",
        "eq_detail_chat_inquiry": "카톡·채팅 문의",
        "eq_detail_my_listing": "내 매물",
        "eq_detail_favorite_add": "찜하기",
        "eq_detail_favorite_remove": "찜 해제",
        "eq_detail_link_copy": "링크 복사",
        "eq_detail_link_copied": "✓ 링크 복사 완료",
        "parts_as_card_title": "전국 부품점 A/S센터",
        "parts_as_view_all": "전체보기",
        "parts_as_filter_all": "전체",
        "parts_as_filter_as": "AS센터",
        "parts_as_filter_parts": "부품점",
        "parts_as_filter_rental": "지역중기",
        "parts_as_map_aria": "전국 부품점 A/S 지도",
        "parts_as_map_fallback": "전국 부품 A/S 지도 보기",
    },
    "en": {
        "eq_detail_title_description": "Description",
        "eq_detail_description_empty": "No description provided.",
        "eq_detail_title_photos": "Photos",
        "eq_detail_title_similar_stats": "Similar Model/Year Pricing",
        "eq_detail_similar_none": "No comparable listings were found for this maker and similar year range.",
        "eq_detail_title_similar_list": "View Similar Listings",
        "eq_detail_back_to_list": "Back to List",
        "eq_detail_right_title_attachment_ad": "Attachment/Tire Ads",
        "eq_detail_register_guide": "Guide",
        "eq_detail_ad_empty": "Paid ads will appear here once registered.",
        "eq_detail_attachment_site_link": "Open company site",
        "eq_detail_attachment_intro": "Official company card",
        "eq_detail_inquiry_title": "Contact",
        "eq_detail_no_contact": "No contact",
        "eq_detail_chat_inquiry": "Kakao/Chat Inquiry",
        "eq_detail_my_listing": "My Listing",
        "eq_detail_favorite_add": "Add Favorite",
        "eq_detail_favorite_remove": "Remove Favorite",
        "eq_detail_link_copy": "Copy Link",
        "eq_detail_link_copied": "✓ Link copied",
        "parts_as_card_title": "Nationwide Parts A/S Centers",
        "parts_as_view_all": "View All",
        "parts_as_filter_all": "All",
        "parts_as_filter_as": "A/S",
        "parts_as_filter_parts": "Parts",
        "parts_as_filter_rental": "Regional Heavy",
        "parts_as_map_aria": "Nationwide parts A/S map",
        "parts_as_map_fallback": "Open Parts A/S map",
    },
}
for _code in LANGUAGE_ORDER:
    I18N[_code].update(_EQ_DETAIL_I18N.get(_code, _EQ_DETAIL_I18N["en"]))

# 판매자 매너점수·신고 (|tr 용)
_TRUST_I18N = {
    "ko": {
        "trust_seller_reliability": "판매자 신뢰도",
        "trust_manner_score": "매너점수",
        "trust_review_good": "좋았어요",
        "trust_review_bad": "아쉬웠어요",
        "trust_item_accuracy": "사진·설명 정확도",
        "trust_item_response": "응답 속도",
        "trust_item_promise": "약속 이행",
        "trust_item_price": "가격 정직성",
        "trust_item_disclosure": "하자 고지",
        "trust_btn_review": "거래 평가하기",
        "trust_btn_report": "신고하기",
        "trust_review_done": "이 매물에 평가를 남기셨습니다.",
        "trust_tab_all": "전체",
        "trust_tab_good": "좋았어요",
        "trust_tab_bad": "아쉬웠어요",
        "trust_reviews_loading": "후기 불러오는 중…",
        "trust_reviews_empty": "아직 후기가 없습니다.",
        "trust_reviews_more": "더 보기",
        "trust_modal_review_title": "거래 후 평가",
        "trust_review_type": "평가 선택",
        "trust_review_good_label": "좋았어요",
        "trust_review_bad_label": "아쉬웠어요",
        "trust_bad_tags": "불합리 태그 (선택)",
        "trust_review_comment_ph": "간단한 코멘트 (선택)",
        "trust_btn_submit_review": "평가 등록",
        "trust_modal_report_title": "판매자 신고",
        "trust_report_reason": "신고 사유",
        "trust_report_detail_ph": "상세 내용 (선택)",
        "trust_btn_submit_report": "신고 접수",
        "trust_bad_fake_photo": "허위 사진",
        "trust_bad_desc_exaggerate": "설명 과장",
        "trust_bad_broken_promise": "약속 불이행",
        "trust_bad_slow_response": "응답 느림",
        "trust_bad_overpriced": "가격 바가지",
        "trust_bad_rude": "비매너/불친절",
        "trust_bad_hidden_defect": "결함 은폐",
        "trust_report_fake_photo": "사진과 실물 다름",
        "trust_report_hidden_defect": "설명과 실제 상태 다름",
        "trust_report_price_change": "가격 흥정 후 일방적 취소/변경",
        "trust_report_broken_promise": "약속된 날짜/장소 불이행",
        "trust_report_rude": "비매너/욕설/협박",
        "trust_report_duplicate": "중복 등록/허위 매물",
        "trust_report_other": "기타",
        "trust_tier_best": "우수 판매자",
        "trust_tier_verified": "일반 인증",
        "trust_tier_caution": "주의 판매자",
        "trust_tier_blocked": "이용 제한",
    },
    "en": {
        "trust_seller_reliability": "Seller reliability",
        "trust_manner_score": "Manner score",
        "trust_review_good": "Positive",
        "trust_review_bad": "Negative",
        "trust_item_accuracy": "Photo/description accuracy",
        "trust_item_response": "Response speed",
        "trust_item_promise": "Keeps promises",
        "trust_item_price": "Fair pricing",
        "trust_item_disclosure": "Defect disclosure",
        "trust_btn_review": "Leave review",
        "trust_btn_report": "Report seller",
        "trust_review_done": "You already reviewed this listing.",
        "trust_tab_all": "All",
        "trust_tab_good": "Positive",
        "trust_tab_bad": "Negative",
        "trust_reviews_loading": "Loading reviews…",
        "trust_reviews_empty": "No reviews yet.",
        "trust_reviews_more": "Load more",
        "trust_modal_review_title": "Transaction review",
        "trust_review_type": "Rating",
        "trust_review_good_label": "Good",
        "trust_review_bad_label": "Poor",
        "trust_bad_tags": "Issues (optional)",
        "trust_review_comment_ph": "Short comment (optional)",
        "trust_btn_submit_review": "Submit review",
        "trust_modal_report_title": "Report seller",
        "trust_report_reason": "Reason",
        "trust_report_detail_ph": "Details (optional)",
        "trust_btn_submit_report": "Submit report",
        "trust_bad_fake_photo": "Fake photos",
        "trust_bad_desc_exaggerate": "Exaggerated description",
        "trust_bad_broken_promise": "Broken promise",
        "trust_bad_slow_response": "Slow response",
        "trust_bad_overpriced": "Overpriced",
        "trust_bad_rude": "Rude behavior",
        "trust_bad_hidden_defect": "Hidden defects",
        "trust_report_fake_photo": "Photos differ from item",
        "trust_report_hidden_defect": "Description differs from condition",
        "trust_report_price_change": "Price changed after negotiation",
        "trust_report_broken_promise": "Missed appointment",
        "trust_report_rude": "Abuse or threats",
        "trust_report_duplicate": "Duplicate/fake listing",
        "trust_report_other": "Other",
        "trust_tier_best": "Top seller",
        "trust_tier_verified": "Verified",
        "trust_tier_caution": "Caution",
        "trust_tier_blocked": "Restricted",
    },
}
for _code in LANGUAGE_ORDER:
    I18N[_code].update(_TRUST_I18N.get(_code, _TRUST_I18N["en"]))


@register.simple_tag
def language_menu():
    """(코드, 표시이름) 목록 — 언어 선택 메뉴용."""
    return [(code, I18N[code]["lang_label"]) for code in LANGUAGE_ORDER if code in I18N]


@register.filter(name="tr")
def translate(lang_code, key):
    lang = (lang_code or "ko").strip().lower()
    if lang not in I18N:
        lang = "ko"
    return I18N.get(lang, I18N["ko"]).get(key, I18N["ko"].get(key, key))


@register.filter
def format_phone(value: str) -> str:
    """
    휴대폰 번호를 010-0000-0000 형식으로 변환.
    - 숫자만 남기고, 10~11자리만 처리
    - 그 외 길이는 원본 그대로 반환
    """
    if not value:
        return ""
    raw = str(value)
    digits = re.sub(r"[^0-9]", "", raw)

    # 값 안에 전화번호가 2개 이상(개행/공백 포함) 섞여 들어오는 경우가 있어,
    # 숫자 길이가 10/11이 아니더라도 "첫 번째 정상 전화번호"만 뽑아 포맷합니다.
    m010 = re.search(r"(010\d{8})", digits)
    if m010:
        d = m010.group(1)
        return f"{d[0:3]}-{d[3:7]}-{d[7:11]}"

    m10 = re.search(r"(\d{10})", digits)
    if m10:
        d = m10.group(1)
        return f"{d[0:3]}-{d[3:6]}-{d[6:10]}"

    # 기존 동작(입력 자체가 이미 포맷된 케이스)에 최대한 호환
    if len(digits) == 11 and digits.startswith("010"):
        return f"{digits[0:3]}-{digits[3:7]}-{digits[7:11]}"
    if len(digits) == 10:
        return f"{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"

    return raw


@register.filter
def mask_phone(value: str) -> str:
    """비회원용 연락처 표시 (예: 010-****-1234)."""
    if not value:
        return ""
    digits = re.sub(r"[^0-9]", "", str(value))
    m010 = re.search(r"(010\d{8})", digits)
    if m010:
        d = m010.group(1)
        return f"{d[0:3]}-****-{d[7:11]}"
    m10 = re.search(r"(\d{10,11})", digits)
    if m10:
        d = m10.group(1)
        if len(d) >= 11:
            return f"{d[0:3]}-****-{d[-4:]}"
        return f"{d[0:3]}-****-{d[-4:]}"
    return "***-****-****"


@register.filter
def user_phone(user) -> str:
    """
    User에서 Profile.phone을 안전하게 꺼냄.
    OneToOne Profile이 없는 계정도 예외 없이 빈 문자열 반환.
    """
    if not user:
        return ""
    try:
        profile = getattr(user, "profile", None)
        if not profile:
            return ""
        return (getattr(profile, "phone", None) or "").strip()
    except Exception:
        return ""


@register.filter
def equipment_row_contact(equipment):
    """
    목록(더보기 표) 등록인/연락처 표시.
    작성자 Profile.phone → 없으면 equipment_detail과 동일한 sibling(동일 모델·가격·위치·등록일) fallback.
    """
    if not equipment:
        return "-"
    from equipment.models import Equipment

    if equipment.author_id:
        try:
            profile = getattr(equipment.author, "profile", None)
            if profile:
                ph = (getattr(profile, "phone", None) or "").strip()
                if ph and any(ch.isdigit() for ch in ph):
                    return format_phone(ph)
        except Exception:
            pass
        un = (getattr(equipment.author, "username", None) or "").strip()
        return un if un else "-"

    sibling_qs = (
        Equipment.objects.visible()
        .select_related("author__profile")
        .exclude(pk=equipment.pk)
        .exclude(author__isnull=True)
        .filter(
            model_name=equipment.model_name,
            listing_price=equipment.listing_price,
            current_location=equipment.current_location,
            created_at__date=equipment.created_at.date(),
        )
        .order_by("-created_at")
    )
    for sibling in sibling_qs[:10]:
        sp = getattr(getattr(sibling, "author", None), "profile", None)
        sibling_phone = getattr(sp, "phone", None) if sp else None
        if not sibling_phone:
            continue
        ph = str(sibling_phone).strip()
        if ph and not any(ch.isdigit() for ch in ph):
            continue
        return format_phone(ph)
    return "-"


@register.filter
def hide_code_text(value):
    """
    의미 없는 코드형 텍스트(예: 0101, 02-02, 01/02)는 화면에서 숨김.
    숫자/공백/-,/ 만으로 이루어진 경우 빈 문자열을 반환한다.
    """
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if re.fullmatch(r"[0-9\-\s/]+", text):
        return ""
    return text


from django import forms
from django.contrib.auth.forms import PasswordResetForm, _unicode_ci_compare
from .models import Equipment, Profile, Part

class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = [
            "equipment_type",
            "model_name",
            "manufacturer",
            "sub_type",
            "weight_class",
            "mast_type",
            "year_manufactured",
            "month_manufactured",
            "operating_hours",
            "listing_price",
            "region_sido",
            "region_sigungu",
            "vehicle_number",
            "description",
        ]
        widgets = {
            "equipment_type": forms.Select(attrs={"class": "form-select"}),
            "model_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "예) HX360"}),
            "manufacturer": forms.TextInput(attrs={"class": "form-control", "placeholder": "예) 현대"}),
            "sub_type": forms.HiddenInput(),
            "weight_class": forms.HiddenInput(),
            "mast_type": forms.HiddenInput(),
            "year_manufactured": forms.NumberInput(attrs={"class": "form-control", "min": 1980, "max": 2100, "placeholder": "예) 2000 (모르면 비워도 됨)"}),
            "month_manufactured": forms.TextInput(attrs={
                "class": "form-control",
                "inputmode": "numeric",
                "pattern": "[0-9]*",
                "maxlength": "2",
                "placeholder": "1~12",
                "autocomplete": "off",
                "onfocus": "if(!this.dataset.firstClearDone){this.value='';this.dataset.firstClearDone='1';}"
            }),
            "operating_hours": forms.TextInput(attrs={
                "class": "form-control",
                "inputmode": "numeric",
                "pattern": "[0-9]*",
                "maxlength": "8",
                "placeholder": "가동시간",
                "autocomplete": "off",
                "onfocus": "if(!this.dataset.firstClearDone){this.value='';this.dataset.firstClearDone='1';}"
            }),
            "listing_price": forms.NumberInput(attrs={"class": "form-control", "min": 0, "placeholder": "예) 3500 (만원)"}),
            "region_sido": forms.HiddenInput(),
            "region_sigungu": forms.HiddenInput(),
            "vehicle_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "예) 12가3456 (모르면 비워도 됨)"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3, "maxlength": 50, "placeholder": "최대 50자 (선택)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not getattr(self.instance, "pk", None) and not self.is_bound:
            self.initial.setdefault("month_manufactured", "")
            self.initial.setdefault("operating_hours", "")
        self.fields["model_name"].required = False
        self.fields["manufacturer"].required = False
        self.fields["year_manufactured"].required = False
        self.fields["month_manufactured"].required = False
        self.fields["operating_hours"].required = False
        self.fields["vehicle_number"].required = False
        self.fields["description"].required = False
        # 필수: 기종, 가격 (기종은 빈 선택지 추가 → 미선택 시 서버 검증)
        self.fields["equipment_type"].required = True
        self.fields["equipment_type"].choices = [("", "---------")] + list(self.fields["equipment_type"].choices)
        self.fields["listing_price"].required = True

        # equipment_type: instance → initial → POST 순
        eq_type = None
        if self.instance and getattr(self.instance, "pk", None) and hasattr(self.instance, "equipment_type"):
            eq_type = self.instance.equipment_type
        if eq_type is None and self.initial:
            eq_type = self.initial.get("equipment_type")
        if eq_type is None and self.data:
            eq_type = self.data.get("equipment_type")
        # 덤프/로더/크레인/어태치먼트/기타: 제조사·모델명·톤수·년월·지역·가격 동일하게 등록 가능. 세부종류/마스트/가동시간만 숨김. 톤수는 템플릿 simple-type-fields에서 별도 입력란으로 노출.
        if eq_type == "attachment":
            self.fields["sub_type"].initial = "EXC_ATTACHMENT"
            self.fields["sub_type"].widget = forms.HiddenInput()
            self.fields["sub_type"].required = False
            for name in ("mast_type", "operating_hours"):
                self.fields[name].widget = forms.HiddenInput()
                self.fields[name].required = False
            self.fields["weight_class"].required = False
        elif eq_type in ("crane", "loader", "dump", "other"):
            for name in ("sub_type", "mast_type", "operating_hours"):
                self.fields[name].widget = forms.HiddenInput()
                self.fields[name].required = False
            self.fields["weight_class"].required = False

    def clean_year_manufactured(self):
        val = self.cleaned_data.get("year_manufactured")
        if val is None or val == "":
            return None
        if not isinstance(val, int):
            try:
                val = int(val)
            except (TypeError, ValueError):
                return None
        if 1980 <= val <= 2100:
            return val
        return None

    def clean_month_manufactured(self):
        val = self.cleaned_data.get("month_manufactured")
        if val is None or val == "":
            return None
        if not isinstance(val, int):
            try:
                val = int(val)
            except (TypeError, ValueError):
                return None
        if 1 <= val <= 12:
            return val
        return 1

    def clean_vehicle_number(self):
        data = (self.cleaned_data.get("vehicle_number") or "").strip()
        return data[:30] if data else ""

    def clean_operating_hours(self):
        val = self.cleaned_data.get("operating_hours")
        if val is None or val == "":
            return 0
        if not isinstance(val, int):
            try:
                val = int(str(val).strip())
            except (TypeError, ValueError):
                return 0
        return max(0, val)

    def clean_description(self):
        data = (self.cleaned_data.get("description") or "").strip()
        if len(data) > 50:
            raise forms.ValidationError("상세 설명은 최대 50자까지 입력 가능합니다.")
        return data[:50]

    def clean(self):
        cleaned = super().clean()
        eq_type = (cleaned.get("equipment_type") or "").strip()
        if eq_type == "attachment":
            cleaned["sub_type"] = "EXC_ATTACHMENT"
        return cleaned


class EquipmentEditForm(forms.ModelForm):
    """작성자(로그인 유저)만 수정 가능 → 비밀번호 필드 없음"""
    class Meta(EquipmentForm.Meta):
        fields = EquipmentForm.Meta.fields


class PartForm(forms.ModelForm):
    class Meta:
        model = Part
        fields = ["category", "title", "price", "compatibility", "description"]
        widgets = {
            "category": forms.RadioSelect,
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "상품명을 입력해 주세요"}),
            "price": forms.TextInput(attrs={"class": "form-control", "placeholder": "예) 1000"}),
            "compatibility": forms.TextInput(attrs={"class": "form-control", "placeholder": "예) 06급 호환"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 5, "placeholder": "상세 설명을 입력해 주세요"}),
        }

        labels = {
            "category": "카테고리",
            "title": "상품명",
            "price": "가격(만원)",
            "compatibility": "호환기종",
            "description": "설명",
        }

# === 회원가입: 중복확인, 비밀번호 재입력, 휴대폰 (추가) ===
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Profile


class TermsAgreementFieldsMixin:
    """회원가입 약관 동의 (필수 2 + 선택 1)."""

    agree_terms = forms.BooleanField(
        label="이용약관 동의",
        required=True,
        error_messages={"required": "이용약관에 동의해 주세요."},
    )
    agree_privacy = forms.BooleanField(
        label="개인정보처리방침 동의",
        required=True,
        error_messages={"required": "개인정보처리방침에 동의해 주세요."},
    )
    agree_marketing = forms.BooleanField(
        label="마케팅 수신 동의",
        required=False,
    )

    def _apply_marketing_consent(self, profile):
        if self.cleaned_data.get("agree_marketing"):
            profile.marketing_consent = True
            profile.marketing_consent_at = timezone.now()
        else:
            profile.marketing_consent = False
            profile.marketing_consent_at = None


class UserSignupForm(TermsAgreementFieldsMixin, forms.ModelForm):
    """회원가입 폼 - 이름, 아이디, 이메일, 비밀번호 재입력, 휴대폰"""
    name = forms.CharField(label="이름", max_length=50, required=True, widget=forms.TextInput(attrs={"placeholder": "이름"}))
    username = forms.CharField(label="아이디", max_length=150, widget=forms.TextInput(attrs={"placeholder": "아이디 입력"}))
    email = forms.EmailField(label="이메일", required=True, widget=forms.EmailInput(attrs={"placeholder": "이메일"}))
    password1 = forms.CharField(label="비밀번호", widget=forms.PasswordInput(attrs={"placeholder": "비밀번호"}))
    password2 = forms.CharField(label="비밀번호 재입력", widget=forms.PasswordInput(attrs={"placeholder": "비밀번호 재입력"}))
    phone = forms.CharField(label="휴대폰번호", max_length=20, widget=forms.TextInput(attrs={"placeholder": "010-0000-0000"}))

    class Meta:
        model = User
        fields = ("username", "email")

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise forms.ValidationError("이름을 입력하세요.")
        return name

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if not username:
            raise forms.ValidationError("아이디를 입력하세요.")
        from equipment.bot_blocklist import is_blocked_bot_username

        if is_blocked_bot_username(username):
            raise forms.ValidationError("사용할 수 없는 아이디입니다.")
        existing = User.objects.filter(username=username).first()
        if existing and existing.is_active:
            raise forms.ValidationError("이미 사용 중인 아이디입니다.")
        self._reusable_user = existing
        return username

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        from equipment.bot_blocklist import is_blocked_bot_phone

        if phone and is_blocked_bot_phone(phone):
            raise forms.ValidationError("사용할 수 없는 휴대폰 번호입니다.")
        return phone

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("비밀번호가 일치하지 않습니다.")
        return p2

    def validate_unique(self):
        """
        비활성(탈퇴) 계정 username 재사용 시 ModelForm의 기본 unique 검증 우회.
        """
        if getattr(self, "_reusable_user", None) is None:
            return super().validate_unique()
        exclude = self._get_validation_exclusions()
        exclude.add("username")
        try:
            self.instance.validate_unique(exclude=exclude)
        except ValidationError as e:
            self._update_errors(e)

    def save(self, commit=True):
        reusable_user = getattr(self, "_reusable_user", None)
        if reusable_user is not None and not reusable_user.is_active:
            user = reusable_user
            user.first_name = self.cleaned_data.get("name", "").strip()
            user.email = self.cleaned_data.get("email", "").strip()
            user.is_active = True
            user.set_password(self.cleaned_data["password1"])
            if commit:
                user.save(update_fields=["first_name", "email", "is_active", "password"])
                profile, _ = Profile.objects.get_or_create(user=user)
                profile.phone = self.cleaned_data.get("phone", "") or ""
                profile.withdrawn_at = None
                profile.listing_purge_at = None
                self._apply_marketing_consent(profile)
                profile.save(update_fields=["phone", "withdrawn_at", "listing_purge_at", "marketing_consent", "marketing_consent_at"])
            return user

        user = super().save(commit=False)
        user.first_name = self.cleaned_data.get("name", "").strip()
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.phone = self.cleaned_data.get("phone", "") or ""
            self._apply_marketing_consent(profile)
            profile.save(update_fields=["phone", "marketing_consent", "marketing_consent_at"])
        return user


class MigratedPasswordResetForm(PasswordResetForm):
    """비밀번호 미설정(이관) 회원도 재설정 메일을 받을 수 있게 한다."""

    def get_users(self, email):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        email_field_name = User.get_email_field_name()
        active_users = User._default_manager.filter(
            **{
                f'{email_field_name}__iexact': email,
                'is_active': True,
            }
        )
        return (
            u for u in active_users
            if _unicode_ci_compare(email, getattr(u, email_field_name))
        )

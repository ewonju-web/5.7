from django import forms
from django.core.exceptions import ValidationError
from .models import SoilPost
from .antispam import validate_soil_post_content


class SoilPostForm(forms.ModelForm):
    # 봇이 채우는 숨김 필드(사람은 보이지 않음)
    company_url = forms.CharField(
        required=False,
        label='',
        widget=forms.TextInput(attrs={
            'class': 'gn-hp-field',
            'tabindex': '-1',
            'autocomplete': 'off',
            'aria-hidden': 'true',
        }),
    )

    class Meta:
        model = SoilPost
        fields = ('post_type', 'material_type', 'title', 'quantity', 'location', 'contact', 'note', 'description', 'image')
        widgets = {
            'post_type': forms.Select(attrs={'class': 'form-select'}),
            'material_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 성토용 흙 나눔합니다'}),
            'quantity': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 약 5톤, 트럭 2대 분량'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 경기 남양주'}),
            'contact': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 010-1234-5678'}),
            'note': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 평일 오전 상차 가능'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': '상세내용을 입력해 주세요.'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean_company_url(self):
        if (self.cleaned_data.get('company_url') or '').strip():
            raise ValidationError('등록할 수 없습니다.')
        return ''

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        try:
            validate_soil_post_content(
                cleaned.get('title'),
                cleaned.get('location'),
                cleaned.get('contact', ''),
                cleaned.get('description', ''),
                cleaned.get('quantity', ''),
                cleaned.get('note', ''),
            )
        except ValidationError as e:
            raise ValidationError(e.messages[0] if e.messages else str(e))
        return cleaned

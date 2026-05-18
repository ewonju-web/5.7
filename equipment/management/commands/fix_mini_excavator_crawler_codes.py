# -*- coding: utf-8 -*-
"""
미니·소형 굴삭기 모델명 기준으로 sub_type / weight_class 를 크롤러 3.5톤 미만 코드로 일괄 보정.

대상: equipment_type=excavator 이고 모델명이 아래를 포함(또는 단어 경계/정규식)하는 매물
  VIO10, VIO17, VIO20, VIO25, VIO35, SK30, SK35, SK17,
  U10, U17, U20, U20s, U25, U30, U35 (단어 경계; U20 뒤 선택적 s),
  신차급VIO, 신차급17
  DX17, DX25, DX35(뒤 선택 알파벳: DX35Z 등), ZX17, ZX35(뒤 선택 알파벳: ZX35U 등)
  SK17, SK20, E20~E50 (밥캣, 단어 경계)
  U008, U006 등 U00x, U175·U175S 등 U100~U199
  특U- 뒤 숫자 (예: 특U-17, 특U-20)

보정값: sub_type=EXC_CRAWLER, weight_class=EXC_CR_LE_3_5

사용법:
  python manage.py fix_mini_excavator_crawler_codes              # 건수·샘플만 (변경 없음)
  python manage.py fix_mini_excavator_crawler_codes --apply      # YES 입력 후 UPDATE
  python manage.py fix_mini_excavator_crawler_codes --apply --no-input  # 확인 없이 UPDATE
"""
import re

from django.core.management.base import BaseCommand

from equipment.models import Equipment

# ASCII 토큰은 소문자 비교, 한글 토큰은 lower() 후 비교
_SUBSTR_ASCII = ("vio10", "vio17", "vio20", "vio25", "vio35", "sk30", "sk35")
_SUBSTR_KO = ("신차급vio", "신차급17")

# U100 등 오매칭 방지. U20s(밥캣 계열 표기)는 20 뒤 선택적 s.
_U_MODEL_RE = re.compile(
    r"(?<![A-Za-z0-9])U(10|17|20s?|25|30|35)(?![A-Za-z0-9])",
    re.IGNORECASE,
)

# 두산 DX / 히타치 ZX / 코벨코 SK — DX35·ZX35 는 뒤에 알파벳 0~1개(Z, U 등)
_MINI_CODE_RES = (
    re.compile(r"(?<![A-Za-z0-9])DX17(?![A-Za-z0-9])", re.I),
    re.compile(r"(?<![A-Za-z0-9])DX25(?![A-Za-z0-9])", re.I),
    re.compile(r"(?<![A-Za-z0-9])DX35[A-Za-z]?(?![A-Za-z0-9])", re.I),
    re.compile(r"(?<![A-Za-z0-9])ZX17(?![A-Za-z0-9])", re.I),
    re.compile(r"(?<![A-Za-z0-9])ZX35[A-Za-z]?(?![A-Za-z0-9])", re.I),
    re.compile(r"(?<![A-Za-z0-9])SK17(?![A-Za-z0-9])", re.I),
    re.compile(r"(?<![A-Za-z0-9])SK20(?![A-Za-z0-9])", re.I),
    re.compile(r"(?<![A-Za-z0-9])E(20|25|35|50)(?![A-Za-z0-9])", re.I),
)
# U008, U006 … (U 뒤 0 한 개 이상 + 숫자 1~2자리, 단어 경계)
_U00X_RE = re.compile(r"(?<![A-Za-z0-9])U0+[0-9]{1,2}(?![A-Za-z0-9])", re.I)
# U175, U175S … U100~U199 (U17 단독은 _U_MODEL_RE 에서 처리)
_U1XX_RE = re.compile(r"(?<![A-Za-z0-9])U1[0-9]{2}[A-Za-z]?(?![A-Za-z0-9])", re.I)
# 특U-17, 특U-20 등
_TUK_U_RE = re.compile(r"특U\s*-\s*\d{1,4}(?![0-9])")

_TARGET_SUB = "EXC_CRAWLER"
_TARGET_WEIGHT = "EXC_CR_LE_3_5"


def model_name_matches(model_name: str) -> bool:
    if not (model_name or "").strip():
        return False
    lower = model_name.lower()
    for tok in _SUBSTR_ASCII:
        if tok in lower:
            return True
    for tok in _SUBSTR_KO:
        if tok in lower:
            return True
    if _U_MODEL_RE.search(model_name):
        return True
    for rx in _MINI_CODE_RES:
        if rx.search(model_name):
            return True
    if _U00X_RE.search(model_name):
        return True
    if _U1XX_RE.search(model_name):
        return True
    if _TUK_U_RE.search(model_name):
        return True
    return False


class Command(BaseCommand):
    help = "미니/소형 모델명 매칭 굴삭기의 sub_type·weight_class 를 크롤러 EXC_CR_LE_3_5 로 보정"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="실제 UPDATE 수행 (없으면 대상 건수·샘플만 출력)",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="--apply 시 YES 확인 생략 (자동화·CI용)",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        no_input = options["no_input"]

        self.stdout.write(self.style.NOTICE("=== 미니 굴삭기 sub_type/weight_class 보정 ==="))
        self.stdout.write(f"보정값: sub_type={_TARGET_SUB}, weight_class={_TARGET_WEIGHT}")

        candidates = []
        for eq in Equipment.objects.filter(equipment_type="excavator").iterator(chunk_size=500):
            if not model_name_matches(eq.model_name or ""):
                continue
            candidates.append(eq)

        total = len(candidates)
        need_update = [
            eq
            for eq in candidates
            if (eq.sub_type or "") != _TARGET_SUB or (eq.weight_class or "") != _TARGET_WEIGHT
        ]
        already_ok = total - len(need_update)

        self.stdout.write(self.style.WARNING(f"\n[1] 모델명 조건 충족(굴삭기): {total}건"))
        self.stdout.write(f"    이미 목표값과 동일: {already_ok}건")
        self.stdout.write(f"    UPDATE 필요: {len(need_update)}건")

        sample_n = min(25, len(need_update))
        if sample_n:
            self.stdout.write(self.style.NOTICE(f"\n[2] UPDATE 대상 샘플 (최대 {sample_n}건, id / model_name / sub_type / weight_class):"))
            for eq in need_update[:sample_n]:
                self.stdout.write(
                    f"    id={eq.pk}\t{(eq.model_name or '')[:40]!r}\t"
                    f"sub_type={eq.sub_type!r}\tweight_class={eq.weight_class!r}"
                )
            if len(need_update) > sample_n:
                self.stdout.write(f"    ... 외 {len(need_update) - sample_n}건")

        if not apply_changes:
            self.stdout.write(
                self.style.SUCCESS("\n드라이런 종료. 변경 없음. 적용하려면: python manage.py fix_mini_excavator_crawler_codes --apply")
            )
            return

        if not no_input:
            self.stdout.write(self.style.WARNING(f"\n정말 {len(need_update)}건을 UPDATE 하시겠습니까? (YES 입력):"))
            if input().strip() != "YES":
                self.stdout.write(self.style.ERROR("중단되었습니다."))
                return

        if not need_update:
            self.stdout.write(self.style.SUCCESS("\n변경할 행이 없습니다."))
            return

        pks = [eq.pk for eq in need_update]
        updated = Equipment.objects.filter(pk__in=pks).update(
            sub_type=_TARGET_SUB,
            weight_class=_TARGET_WEIGHT,
        )
        self.stdout.write(self.style.SUCCESS(f"\n[3] UPDATE 완료: {updated}건 (sub_type, weight_class)"))
        self.stdout.write(f"    대상 pk 개수: {len(pks)} (DB 반영 행 수와 동일해야 정상)")

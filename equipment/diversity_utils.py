"""매물 목록 다양성 보정 (판매자 독점 완화)."""
from __future__ import annotations

from collections import OrderedDict, deque


def diversify_by_author(equipment_list, max_per_author: int = 2):
    """
    같은 판매자(author_id)의 매물이 리스트 앞쪽에 몰리지 않도록
    라운드로빈 방식으로 재배치한다.

    author_id가 None인 매물(미연결)은 각각 독립적인 그룹으로 취급한다.
    원래 순서(정렬 우선순위)는 그룹 내에서 유지한다.

    max_per_author: API 호환·안전장치용 파라미터.
    라운드로빈은 라운드당 판매자 1건만 뽑으므로 자연 분산되며,
    다른 판매자 잔여가 없을 때만 동일 판매자가 연속된다.
    """
    del max_per_author  # 라운드로빈(1건/라운드)이 기본; 시그니처만 유지
    items = list(equipment_list)
    if len(items) <= 1:
        return items

    groups: OrderedDict = OrderedDict()
    for idx, eq in enumerate(items):
        author_id = getattr(eq, "author_id", None)
        if author_id is None:
            key = ("__unclaimed__", idx)
        else:
            key = author_id
        if key not in groups:
            groups[key] = deque()
        groups[key].append(eq)

    result = []
    active_keys = list(groups.keys())
    while active_keys:
        next_keys = []
        for key in active_keys:
            queue = groups[key]
            if queue:
                result.append(queue.popleft())
            if queue:
                next_keys.append(key)
        active_keys = next_keys

    return result

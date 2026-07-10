"""다양성 보정 단위 테스트 (DB 불필요)."""
import unittest
from types import SimpleNamespace

from equipment.diversity_utils import diversify_by_author


def _eq(pk, author_id):
    return SimpleNamespace(pk=pk, author_id=author_id)


class DiversifyByAuthorTests(unittest.TestCase):
    def test_round_robin_prevents_author_monopoly_at_front(self):
        # A×5, B×1, C×1 — 앞쪽이 A만 몰리지 않고 A,B,C,A… 라운드로빈
        items = [
            _eq(1, "A"),
            _eq(2, "A"),
            _eq(3, "A"),
            _eq(4, "A"),
            _eq(5, "A"),
            _eq(6, "B"),
            _eq(7, "C"),
        ]
        result = diversify_by_author(items)
        authors = [x.author_id for x in result]
        self.assertEqual(authors, ["A", "B", "C", "A", "A", "A", "A"])
        self.assertNotEqual(authors[:3], ["A", "A", "A"])
        # 그룹 내 원래 순서 유지
        a_pks = [x.pk for x in result if x.author_id == "A"]
        self.assertEqual(a_pks, [1, 2, 3, 4, 5])

    def test_unclaimed_none_authors_are_independent(self):
        items = [
            _eq(1, None),
            _eq(2, None),
            _eq(3, "A"),
        ]
        result = diversify_by_author(items)
        self.assertEqual([x.pk for x in result], [1, 2, 3])

    def test_empty_and_single(self):
        self.assertEqual(diversify_by_author([]), [])
        one = [_eq(1, "A")]
        self.assertEqual(diversify_by_author(one), one)


if __name__ == "__main__":
    unittest.main()

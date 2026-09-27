"""验证共治领域模块守住契约不变量。"""
import unittest
from datetime import date, timedelta

from governance import (AllocationRule, BaselineStandard, EnforcementBoard,
                        LicenseOffice, Product, ResourcePool, SchoolProfile,
                        StandardRegistry, Store, TraceBook, Watchdog)

TODAY = date(2026, 9, 27)


def make_registry():
    registry = StandardRegistry()
    registry.publish_baseline(BaselineStandard(
        "B1", {"中心温度C": 70}, frozenset({"罂粟壳"}), ("品牌标识", "生产日期")))
    return registry


def make_office():
    office = LicenseOffice()
    office.register_store(Store("S1", "张家合作社", "东村老街1号"))
    office.register_store(Store("S2", "李家作坊", "西村桥头3号"))
    for store_id in ("S1", "S2"):
        office.apply(store_id, "张派", ["烧饼"], ["小王"], ["县粮油站"])
        office.complete_training(store_id, "小王")
        office.grant(store_id, TODAY + timedelta(days=180))
    return office


class StandardTest(unittest.TestCase):
    def test_profile_cannot_weaken_baseline(self):
        registry = make_registry()
        with self.assertRaises(ValueError):
            registry.register_profile(SchoolProfile(
                "张派", "1.0", "B1", {"中心温度C": 60}, ("面粉",), ("和面",),
                "酥脆", TODAY))
        with self.assertRaises(ValueError):
            registry.register_profile(SchoolProfile(
                "张派", "1.0", "B1", {"中心温度C": 70}, ("面粉", "罂粟壳"),
                ("和面",), "酥脆", TODAY))

    def test_transition_period_keeps_old_version_alive(self):
        registry = make_registry()
        registry.register_profile(SchoolProfile(
            "张派", "1.0", "B1", {"中心温度C": 70}, ("面粉",), ("和面",),
            "酥脆", date(2026, 1, 1)))
        registry.register_profile(SchoolProfile(
            "张派", "2.0", "B1", {"中心温度C": 75}, ("面粉", "芝麻"), ("和面", "醒发"),
            "酥脆带香", date(2026, 9, 1), transition_days=30))
        self.assertEqual(registry.acceptable_versions("张派", date(2026, 9, 15)),
                         ("2.0", "1.0"))
        self.assertEqual(registry.acceptable_versions("张派", date(2026, 10, 15)),
                         ("2.0",))


class LicenseTest(unittest.TestCase):
    def test_grant_requires_full_training(self):
        office = LicenseOffice()
        office.register_store(Store("S1", "张家合作社", "东村老街1号"))
        office.apply("S1", "张派", ["烧饼"], ["小王", "小李"], ["县粮油站"])
        office.complete_training("S1", "小王")
        with self.assertRaises(ValueError):
            office.grant("S1", TODAY)
        office.complete_training("S1", "小李")
        self.assertEqual(office.grant("S1", TODAY).state, "已授权")

    def test_authorization_bounded_by_term(self):
        office = make_office()
        self.assertTrue(office.is_authorized("S1", TODAY))
        self.assertFalse(office.is_authorized("S1", TODAY + timedelta(days=181)))
        self.assertIn("S1", office.expired(TODAY + timedelta(days=181)))


class EnforcementTest(unittest.TestCase):
    def test_failure_scoped_to_store_and_batch(self):
        office = make_office()
        board = EnforcementBoard(office)
        board.record("抽检", "S1", False, batch_id="B-01", detail="温度不达标", on=TODAY)
        self.assertEqual(office.license("S1").state, "整改中")
        self.assertEqual(office.license("S2").state, "已授权")  # 不连坐
        self.assertTrue(board.is_recalled("B-01"))
        self.assertFalse(board.is_recalled("B-02"))
        board.close_rectification("S1", True)
        self.assertEqual(office.license("S1").state, "已授权")


class DetectionTest(unittest.TestCase):
    def test_impostor_relocation_and_expiry(self):
        office = make_office()
        watchdog = Watchdog(office)
        self.assertTrue(watchdog.check_claim("SX", "陌生人", TODAY))  # 冒名
        self.assertTrue(watchdog.check_claim("S1", "冒名公司", TODAY))  # 主体不符
        self.assertFalse(watchdog.check_claim("S1", "张家合作社", TODAY))
        self.assertEqual(watchdog.relocated({"S1": "外省开发区9号", "S2": "西村桥头3号"}),
                         ["S1"])
        self.assertEqual(watchdog.expired(TODAY + timedelta(days=181)), ["S1", "S2"])


class ResourceTest(unittest.TestCase):
    def test_public_rules_and_no_double_dipping(self):
        office = make_office()
        pool = ResourcePool(office)
        pool.declare(AllocationRule("扶持资金", "2026", quota=1, amount=5000))
        grant = pool.apply("张家合作社", "扶持资金", "2026")
        self.assertEqual(grant.amount, 5000)
        with self.assertRaises(ValueError):  # 重复申报
            pool.apply("张家合作社", "扶持资金", "2026")
        with self.assertRaises(ValueError):  # 名额已满
            pool.apply("李家作坊", "扶持资金", "2026")
        with self.assertRaises(ValueError):  # 无授权主体无资格
            pool.apply("外来公司", "培训名额", "2026")


class TraceabilityTest(unittest.TestCase):
    def setUp(self):
        self.registry = make_registry()
        self.registry.register_profile(SchoolProfile(
            "张派", "1.0", "B1", {"中心温度C": 70}, ("面粉",), ("和面", "贴炉"),
            "酥脆", date(2026, 1, 1)))
        self.office = make_office()
        self.board = EnforcementBoard(self.office)
        self.book = TraceBook(self.office, self.registry, self.board)

    def product(self, **kw):
        data = dict(product_id="P1", store_id="S1", category="烧饼",
                    school="张派", school_version="1.0",
                    ingredients=(("面粉", "县粮油站", "B-01"),), made_on=TODAY)
        data.update(kw)
        return Product(**data)

    def test_register_checks_license_source_and_batch(self):
        self.book.register(self.product())
        with self.assertRaises(ValueError):  # 超获准品类
            self.book.register(self.product(product_id="P2", category="羊汤"))
        with self.assertRaises(ValueError):  # 来路不明的供应来源
            self.book.register(self.product(
                product_id="P3", ingredients=(("面粉", "陌生商贩", "B-09"),)))
        self.board.record("抽检", "S2", False, batch_id="B-02", on=TODAY)
        with self.assertRaises(ValueError):  # 已召回批次
            self.book.register(self.product(
                product_id="P4", ingredients=(("面粉", "县粮油站", "B-02"),)))

    def test_views_split_operator_from_public(self):
        self.board.record("抽检", "S1", True, on=TODAY)
        self.book.register(self.product())
        full = self.book.operator_trace("P1")
        self.assertEqual(full["流派版本"], "1.0")
        self.assertEqual(full["食材来源"][0]["供应商"], "县粮油站")
        self.assertTrue(full["最近检查"])
        public = self.book.public_summary("P1")
        self.assertTrue(public["授权有效"])
        self.assertNotIn("供应商", str(public))  # 不披露商业信息
        self.assertNotIn("工序", str(public))


if __name__ == "__main__":
    unittest.main()

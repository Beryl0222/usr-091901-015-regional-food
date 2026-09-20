"""共治后端领域规则测试。"""
import unittest
from datetime import date

from brandgov import (
    STATUS_AUTHORIZED,
    STATUS_RECTIFYING,
    STATUS_SUSPENDED,
    BrandRegistry,
    DomainError,
    IngredientLot,
    Requirement,
    StaffMember,
    SupplySource,
)

BASELINE_REQS = {
    "冷链温度": Requirement.at_most(4),
    "每日留样次数": Requirement.at_least(2),
    "明码标识": Requirement.required(),
}

SCHOOL_OVERLAY = {
    "冷链温度": Requirement.at_most(2),        # 比底线更严
    "每日留样次数": Requirement.at_least(3),
    "明码标识": Requirement.required(),
    "豆瓣酱发酵天数": Requirement.at_least(180),  # 流派自己的风味要求
}


def make_registry():
    reg = BrandRegistry()
    reg.standards.publish_baseline("BL1", BASELINE_REQS,
                                   date(2026, 1, 1), date(2026, 1, 1))
    reg.standards.publish_school_standard("老城派", "v1", "BL1", SCHOOL_OVERLAY,
                                          date(2026, 1, 1))
    return reg


def make_store(reg, name="张记锅贴", entity="91320100MA1AAAAA1A",
               address="老街1号", categories=("牛肉锅贴",),
               submitted_on=date(2026, 3, 1)):
    app = reg.licensing.apply(
        name, entity, address, list(categories), "老城派", "v1",
        [StaffMember("张三", "主理人"), StaffMember("李四", "帮厨")],
        [SupplySource("SUP1", "本地黄牛合作社", "牛肉", "本县"),
         SupplySource("SUP2", "山泉豆制品坊", "豆腐", "邻县")],
        submitted_on)
    reg.licensing.start_training(app.application_id)
    reg.licensing.complete_training(app.application_id, "张三", date(2026, 3, 10))
    reg.licensing.complete_training(app.application_id, "李四", date(2026, 3, 10))
    return reg.licensing.authorize(app.application_id,
                                   date(2026, 3, 15), date(2027, 3, 14))


class StandardsTest(unittest.TestCase):
    def test_overlay_cannot_relax_baseline(self):
        reg = BrandRegistry()
        reg.standards.publish_baseline("BL1", BASELINE_REQS,
                                       date(2026, 1, 1), date(2026, 1, 1))
        lax = dict(SCHOOL_OVERLAY, 冷链温度=Requirement.at_most(10))
        with self.assertRaises(DomainError):
            reg.standards.publish_school_standard("新城派", "v1", "BL1", lax,
                                                  date(2026, 1, 1))
        missing = {k: v for k, v in SCHOOL_OVERLAY.items() if k != "明码标识"}
        with self.assertRaises(DomainError):
            reg.standards.publish_school_standard("新城派", "v1", "BL1", missing,
                                                  date(2026, 1, 1))

    def test_stricter_overlay_and_local_flavor_allowed(self):
        reg = make_registry()
        std = reg.standards.school_standard("老城派", "v1")
        self.assertIn("豆瓣酱发酵天数", std.requirements)

    def test_revision_transition_window(self):
        reg = make_registry()
        reg.standards.publish_baseline(
            "BL2", dict(BASELINE_REQS, 每日留样次数=Requirement.at_least(3)),
            date(2026, 5, 1), date(2026, 6, 1),
            transition_until=date(2026, 8, 31))
        self.assertEqual(reg.standards.current_baseline(date(2026, 7, 1)).version, "BL2")
        self.assertTrue(reg.standards.baseline_acceptable("BL1", date(2026, 8, 31)))
        self.assertFalse(reg.standards.baseline_acceptable("BL1", date(2026, 9, 1)))

    def test_application_respects_transition(self):
        reg = make_registry()
        reg.standards.publish_baseline("BL2", BASELINE_REQS,
                                       date(2026, 5, 1), date(2026, 6, 1),
                                       transition_until=date(2026, 8, 31))
        # 过渡期内仍可依据旧底线对应的流派规范申请
        app = reg.licensing.apply(
            "过渡店", "91320100MA1BBBBB2B", "新街2号", ["豆腐圆"], "老城派", "v1",
            [StaffMember("王五", "主理人")],
            [SupplySource("SUP2", "山泉豆制品坊", "豆腐", "邻县")],
            date(2026, 7, 1))
        self.assertEqual(app.status, "申请加入")
        # 过渡期结束后必须改用现行版本
        with self.assertRaises(DomainError):
            reg.licensing.apply(
                "迟到店", "91320100MA1CCCCC3C", "新街3号", ["豆腐圆"], "老城派", "v1",
                [StaffMember("赵六", "主理人")],
                [SupplySource("SUP2", "山泉豆制品坊", "豆腐", "邻县")],
                date(2026, 9, 20))


class LicensingTest(unittest.TestCase):
    def setUp(self):
        self.reg = make_registry()

    def test_authorize_requires_all_staff_trained(self):
        app = self.reg.licensing.apply(
            "张记锅贴", "91320100MA1AAAAA1A", "老街1号", ["牛肉锅贴"],
            "老城派", "v1",
            [StaffMember("张三", "主理人"), StaffMember("李四", "帮厨")],
            [SupplySource("SUP1", "本地黄牛合作社", "牛肉", "本县")],
            date(2026, 3, 1))
        self.reg.licensing.start_training(app.application_id)
        self.reg.licensing.complete_training(app.application_id, "张三",
                                             date(2026, 3, 10))
        with self.assertRaises(DomainError):
            self.reg.licensing.authorize(app.application_id,
                                         date(2026, 3, 15), date(2027, 3, 14))

    def test_license_binds_entity_category_term(self):
        lic = make_store(self.reg)
        self.assertEqual(lic.entity_code, "91320100MA1AAAAA1A")
        self.assertEqual(lic.categories, ("牛肉锅贴",))
        self.assertEqual(lic.valid_to, date(2027, 3, 14))
        self.assertEqual(lic.supplier_ids, ("SUP1", "SUP2"))

    def test_uncertified_supplier_rejected(self):
        with self.assertRaises(DomainError):
            self.reg.licensing.apply(
                "黑店", "91320100MA1DDDDD4D", "暗巷4号", ["牛肉锅贴"],
                "老城派", "v1", [StaffMember("钱七", "主理人")],
                [SupplySource("SUP9", "来路不明批发商", "牛肉", "外地",
                              certified=False)],
                date(2026, 3, 1))

    def test_watchdog_detects_expiry_relocation_impostor(self):
        lic = make_store(self.reg)
        watchdog = self.reg.watchdog
        # 授权到期
        expired = watchdog.expired_licenses(date(2027, 3, 15))
        self.assertEqual([x.license_id for x in expired], [lic.license_id])
        self.assertEqual(watchdog.expired_licenses(date(2027, 3, 14)), [])
        # 异地迁店
        alert = watchdog.report_address(lic.license_id, "开发区99号",
                                        date(2026, 6, 1))
        self.assertEqual(alert["registered_address"], "老街1号")
        self.assertIsNone(watchdog.report_address(lic.license_id, "老街1号",
                                                  date(2026, 6, 1)))
        # 冒名核验
        self.assertEqual(watchdog.verify_claim("李鬼锅贴", "X", "Y",
                                               date(2026, 6, 1))["verdict"], "冒名")
        self.assertEqual(watchdog.verify_claim("张记锅贴", "假主体", "老街1号",
                                               date(2026, 6, 1))["verdict"], "冒名")
        self.assertEqual(watchdog.verify_claim("张记锅贴", lic.entity_code,
                                               "开发区99号",
                                               date(2026, 6, 1))["verdict"], "异地迁店")
        ok = watchdog.verify_claim("张记锅贴", lic.entity_code, "老街1号",
                                   date(2026, 6, 1))
        self.assertEqual(ok["verdict"], "有效")
        self.assertEqual(watchdog.verify_claim("张记锅贴", lic.entity_code,
                                               "老街1号",
                                               date(2027, 4, 1))["verdict"], "授权到期")


class EnforcementTest(unittest.TestCase):
    def setUp(self):
        self.reg = make_registry()
        self.lic_a = make_store(self.reg)
        self.lic_b = make_store(self.reg, name="李记汤包",
                                entity="91320100MA1EEEEE5E", address="老街2号",
                                categories=("蟹黄汤包",))

    def test_failed_inspection_scoped_to_single_store_and_batch(self):
        _, order = self.reg.enforcement.record_inspection(
            self.lic_a.license_id, date(2026, 6, 1), "不合格",
            findings=("冷链温度超标",), batch_nos=("B20260601",), inspector="检查员甲")
        self.assertEqual(self.reg.licensing.get_license(self.lic_a.license_id).status,
                         STATUS_RECTIFYING)
        # 不连坐：另一家门店不受影响
        self.assertEqual(self.reg.licensing.get_license(self.lic_b.license_id).status,
                         STATUS_AUTHORIZED)
        self.assertEqual(self.reg.enforcement.batch_status("B20260601"), "停售")
        self.assertEqual(self.reg.enforcement.batch_status("B20260602"), "正常")
        self.assertEqual(order.license_id, self.lic_a.license_id)
        # 整改验收后恢复
        self.reg.enforcement.complete_rectification(order.order_id, date(2026, 6, 20))
        self.assertEqual(self.reg.licensing.get_license(self.lic_a.license_id).status,
                         STATUS_AUTHORIZED)
        self.assertEqual(self.reg.enforcement.batch_status("B20260601"), "正常")

    def test_severe_complaint_suspends_only_target(self):
        _, order = self.reg.enforcement.record_complaint(
            self.lic_a.license_id, "B20260701", "吃出异物", date(2026, 7, 2),
            severe=True)
        self.assertEqual(self.reg.licensing.get_license(self.lic_a.license_id).status,
                         STATUS_SUSPENDED)
        self.assertEqual(self.reg.licensing.get_license(self.lic_b.license_id).status,
                         STATUS_AUTHORIZED)
        self.assertEqual(order.batch_nos, ("B20260701",))


class ResourceTest(unittest.TestCase):
    def setUp(self):
        self.reg = make_registry()
        self.lic = make_store(self.reg)
        self.reg.resources.create_program(
            "P2026", "扶持资金", "开店设备补贴",
            "已授权且无未结整改的主体可申报，每主体限 1 次",
            total_quota=2, per_entity_cap=1,
            open_from=date(2026, 4, 1), open_until=date(2026, 12, 31))

    def test_duplicate_application_rejected(self):
        self.reg.resources.apply("P2026", self.lic.entity_code, date(2026, 5, 1))
        with self.assertRaises(DomainError):
            self.reg.resources.apply("P2026", self.lic.entity_code, date(2026, 5, 2))

    def test_entity_in_rectification_not_eligible(self):
        self.reg.enforcement.record_inspection(
            self.lic.license_id, date(2026, 5, 1), "不合格")
        with self.assertRaises(DomainError):
            self.reg.resources.apply("P2026", self.lic.entity_code, date(2026, 5, 2))

    def test_quota_enforced(self):
        other = make_store(self.reg, name="李记汤包",
                           entity="91320100MA1EEEEE5E", address="老街2号",
                           categories=("蟹黄汤包",))
        third = make_store(self.reg, name="王记烧饼",
                           entity="91320100MA1FFFFF6F", address="老街3号",
                           categories=("烧饼",))
        self.reg.resources.apply("P2026", self.lic.entity_code, date(2026, 5, 1))
        self.reg.resources.apply("P2026", other.entity_code, date(2026, 5, 1))
        with self.assertRaises(DomainError):
            self.reg.resources.apply("P2026", third.entity_code, date(2026, 5, 1))


class TraceabilityTest(unittest.TestCase):
    def setUp(self):
        self.reg = make_registry()
        self.lic = make_store(self.reg)
        self.ingredients = [
            IngredientLot("牛肉", "SUP1", "本县"),
            IngredientLot("豆腐", "SUP2", "邻县"),
            IngredientLot("香葱", "SUP9", "本县", key=False),
        ]

    def register(self, batch_no="B20260601", **kw):
        args = dict(product_name="牛肉锅贴", category="牛肉锅贴",
                    license_id=self.lic.license_id, ingredients=self.ingredients,
                    produced_on=date(2026, 6, 1))
        args.update(kw)
        return self.reg.trace.register_batch(batch_no, **args)

    def test_register_guards_bindings(self):
        with self.assertRaises(DomainError):  # 品类超授权
            self.register(category="蟹黄汤包")
        with self.assertRaises(DomainError):  # 关键食材来路不明
            self.register(ingredients=[IngredientLot("牛肉", "SUPX", "外地")])
        with self.assertRaises(DomainError):  # 生产日期超期限
            self.register(produced_on=date(2027, 4, 1))
        self.assertEqual(self.register().batch_no, "B20260601")

    def test_operator_trace_and_public_summary(self):
        self.register()
        self.reg.enforcement.record_inspection(
            self.lic.license_id, date(2026, 6, 2), "合格", inspector="检查员甲")
        view = self.reg.trace.trace("B20260601")
        self.assertEqual(view["流派规范版本"], "v1")
        self.assertEqual(view["经营主体"], "91320100MA1AAAAA1A")
        self.assertEqual(view["关键食材"][0]["供应商"], "本地黄牛合作社")
        self.assertEqual(len(view["检查记录"]), 1)
        summary = self.reg.trace.public_summary("B20260601")
        self.assertEqual(summary["检查状态"], "合格在营")
        self.assertEqual(summary["关键食材产地"], ["本县", "邻县"])
        # 不披露供应商身份与工艺配方
        self.assertNotIn("供应商", str(summary))
        self.assertNotIn("发酵", str(summary))

    def test_public_summary_reflects_rectification(self):
        self.register()
        self.reg.enforcement.record_inspection(
            self.lic.license_id, date(2026, 6, 2), "不合格",
            findings=("留样不足",), batch_nos=("B20260601",))
        self.assertEqual(self.reg.trace.public_summary("B20260601")["检查状态"],
                         "停售整改")


if __name__ == "__main__":
    unittest.main()

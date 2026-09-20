"""门店授权与日常巡查识别。"""
from __future__ import annotations

import itertools

from .models import (
    STATUS_APPLYING,
    STATUS_AUTHORIZED,
    STATUS_EXITED,
    STATUS_RECTIFYING,
    STATUS_SUSPENDED,
    STATUS_TRAINING,
    DomainError,
    License,
    StoreApplication,
)
from .standards import StandardsService


class LicenseService:
    """受理申请、记录培训并签发限定主体、品类和期限的授权。"""

    def __init__(self, standards: StandardsService):
        self._standards = standards
        self._applications: dict[str, StoreApplication] = {}
        self._licenses: dict[str, License] = {}
        self._seq = itertools.count(1)

    def apply(self, store_name, entity_code, address, categories, school,
              school_standard_version, staff, suppliers, submitted_on):
        school_std = self._standards.school_standard(school, school_standard_version)
        if school_std is None:
            raise DomainError(f"流派规范 {school}@{school_standard_version} 不存在")
        if not self._standards.baseline_acceptable(school_std.baseline_version, submitted_on):
            raise DomainError("所依据的基础规范版本已过过渡期，请改用现行版本")
        if not categories:
            raise DomainError("申请品类不能为空")
        if not staff:
            raise DomainError("至少绑定一名培训人员")
        if any(not s.certified for s in suppliers):
            raise DomainError("供应来源必须全部经过认证，杜绝来路不明的食材")
        app_id = f"AP{next(self._seq):04d}"
        app = StoreApplication(
            app_id, store_name, entity_code, address, list(categories),
            school, school_standard_version, list(staff), list(suppliers), submitted_on,
        )
        self._applications[app_id] = app
        return app

    def application(self, app_id):
        try:
            return self._applications[app_id]
        except KeyError:
            raise DomainError(f"申请 {app_id} 不存在") from None

    def start_training(self, app_id):
        app = self.application(app_id)
        if app.status != STATUS_APPLYING:
            raise DomainError("只有申请加入状态可以进入培训")
        app.status = STATUS_TRAINING
        return app

    def complete_training(self, app_id, staff_name, on):
        app = self.application(app_id)
        if app.status != STATUS_TRAINING:
            raise DomainError("门店尚未进入培训")
        for member in app.staff:
            if member.name == staff_name:
                member.trained = True
                member.trained_on = on
                return member
        raise DomainError(f"人员 {staff_name} 不在申请绑定名单中")

    def authorize(self, app_id, valid_from, valid_to):
        """签发授权：全体绑定人员完成培训后方可生效。"""
        app = self.application(app_id)
        if app.status != STATUS_TRAINING:
            raise DomainError("门店须先完成培训流程")
        untrained = [m.name for m in app.staff if not m.trained]
        if untrained:
            raise DomainError(f"以下人员尚未完成培训：{'、'.join(untrained)}")
        if valid_to <= valid_from:
            raise DomainError("授权期限无效")
        license_id = f"LC{next(self._seq):04d}"
        lic = License(
            license_id, app.application_id, app.store_name, app.entity_code,
            app.address, tuple(app.categories), app.school,
            app.school_standard_version,
            tuple(s.supplier_id for s in app.suppliers),
            tuple(m.name for m in app.staff),
            valid_from, valid_to,
        )
        self._licenses[license_id] = lic
        app.status = STATUS_AUTHORIZED
        return lic

    def get_license(self, license_id):
        try:
            return self._licenses[license_id]
        except KeyError:
            raise DomainError(f"授权 {license_id} 不存在") from None

    def licenses(self):
        return list(self._licenses.values())

    def set_status(self, license_id, status):
        lic = self.get_license(license_id)
        lic.status = status
        return lic

    def exit(self, license_id):
        return self.set_status(license_id, STATUS_EXITED)


class Watchdog:
    """识别冒名店铺、异地迁店与授权到期。"""

    def __init__(self, licensing: LicenseService):
        self._licensing = licensing
        self._relocations: list[dict] = []

    def expired_licenses(self, today):
        """已过期但仍处于经营状态的授权。"""
        return [
            lic for lic in self._licensing.licenses()
            if lic.status in (STATUS_AUTHORIZED, STATUS_RECTIFYING)
            and lic.valid_to < today
        ]

    def report_address(self, license_id, observed_address, observed_on):
        """巡查上报实际经营地址，与授权地址不符即记录迁店线索。"""
        lic = self._licensing.get_license(license_id)
        if lic.address == observed_address:
            return None
        alert = {
            "license_id": lic.license_id,
            "store_name": lic.store_name,
            "registered_address": lic.address,
            "observed_address": observed_address,
            "observed_on": observed_on,
        }
        self._relocations.append(alert)
        return alert

    def relocation_alerts(self):
        return list(self._relocations)

    def verify_claim(self, store_name, entity_code, address, today):
        """核验一家自称使用品牌的店铺，返回可公开的结论。"""
        matches = [lic for lic in self._licensing.licenses()
                   if lic.store_name == store_name]
        if not matches:
            return {"verdict": "冒名", "reason": "品牌名录中不存在该门店"}
        lic = matches[-1]
        if lic.entity_code != entity_code:
            return {"verdict": "冒名", "reason": "经营主体与授权记录不符"}
        if lic.address != address:
            return {"verdict": "异地迁店", "reason": "实际经营地址与授权地址不符"}
        if lic.status == STATUS_EXITED or lic.valid_to < today:
            return {"verdict": "授权到期", "reason": "品牌授权已失效"}
        if lic.status == STATUS_SUSPENDED:
            return {"verdict": "暂停授权", "reason": "该门店授权已被暂停"}
        return {"verdict": "有效", "license_id": lic.license_id,
                "valid_to": lic.valid_to}

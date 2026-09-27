"""门店授权：绑定实际经营主体、培训人员、供应来源与获准品类。

不变量：门店授权限定主体、品类和期限。
"""

from dataclasses import dataclass, field
from datetime import date

STATES = ("申请加入", "培训中", "已授权", "整改中", "暂停授权", "已退出")


@dataclass(frozen=True)
class Store:
    """门店档案，地址用于识别异地迁店。"""

    store_id: str
    entity: str    # 实际经营主体
    address: str


@dataclass
class License:
    """品牌使用授权，状态取自领域契约。"""

    store_id: str
    entity: str
    school: str
    categories: frozenset   # 获准品类
    staff_required: tuple   # 须完成培训的人员
    staff_trained: set
    suppliers: tuple        # 获准供应来源
    state: str = "申请加入"
    valid_until: date | None = None


class LicenseOffice:
    """受理申请、培训、授权与状态变更。"""

    def __init__(self):
        self._stores = {}
        self._licenses = {}

    def register_store(self, store):
        self._stores[store.store_id] = store
        return store

    def store(self, store_id):
        return self._stores[store_id]

    def license(self, store_id):
        try:
            return self._licenses[store_id]
        except KeyError:
            raise KeyError(f"门店{store_id}无品牌授权记录") from None

    def licenses(self):
        return list(self._licenses.values())

    def apply(self, store_id, school, categories, staff, suppliers):
        """提交使用申请，主体以门店档案为准，不得冒用。"""
        if store_id in self._licenses and self._licenses[store_id].state != "已退出":
            raise ValueError(f"门店{store_id}已有进行中的授权")
        store = self.store(store_id)
        lic = License(
            store_id=store_id, entity=store.entity, school=school,
            categories=frozenset(categories), staff_required=tuple(staff),
            staff_trained=set(), suppliers=tuple(suppliers),
            state="培训中" if staff else "申请加入",
        )
        self._licenses[store_id] = lic
        return lic

    def complete_training(self, store_id, person):
        lic = self.license(store_id)
        if lic.state not in ("申请加入", "培训中"):
            raise ValueError(f"状态{lic.state}不可登记培训")
        if person not in lic.staff_required:
            raise ValueError(f"{person}不在门店{store_id}的培训名单")
        lic.staff_trained.add(person)
        lic.state = "培训中"
        return lic

    def grant(self, store_id, valid_until):
        """授予授权：全员完成培训方可生效，期限必填。"""
        lic = self.license(store_id)
        if lic.state not in ("申请加入", "培训中"):
            raise ValueError(f"状态{lic.state}不可授权")
        missing = [p for p in lic.staff_required if p not in lic.staff_trained]
        if missing:
            raise ValueError(f"人员{','.join(missing)}尚未完成培训")
        lic.state = "已授权"
        lic.valid_until = valid_until
        return lic

    def start_rectification(self, store_id):
        lic = self.license(store_id)
        if lic.state != "已授权":
            raise ValueError(f"状态{lic.state}不可转入整改")
        lic.state = "整改中"
        return lic

    def finish_rectification(self, store_id, passed):
        lic = self.license(store_id)
        if lic.state != "整改中":
            raise ValueError(f"状态{lic.state}不在整改中")
        lic.state = "已授权" if passed else "暂停授权"
        return lic

    def suspend(self, store_id):
        lic = self.license(store_id)
        if lic.state != "已授权":
            raise ValueError(f"状态{lic.state}不可暂停")
        lic.state = "暂停授权"
        return lic

    def exit(self, store_id):
        lic = self.license(store_id)
        lic.state = "已退出"
        return lic

    def is_authorized(self, store_id, on):
        """当日是否可有效使用品牌：状态在位且未过授权期限。"""
        try:
            lic = self._licenses[store_id]
        except KeyError:
            return False
        return lic.state == "已授权" and lic.valid_until is not None and on <= lic.valid_until

    def expired(self, on):
        """状态仍为已授权但期限已过的门店。"""
        return [lic.store_id for lic in self._licenses.values()
                if lic.state == "已授权" and lic.valid_until is not None and lic.valid_until < on]

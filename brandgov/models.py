"""共治后端共享的数据模型与业务词汇。

模型围绕领域契约的不可破坏原则设计：
- 底线不被放宽：Requirement 可在严格性上比较；
- 授权限定主体、品类和期限：License 绑定四要素与供应来源；
- 问题不连坐：RectificationOrder 只指向证据所及的门店与批次。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# 门店授权生命周期，与 domain_contract.json 的 states 保持一致
STATUS_APPLYING = "申请加入"
STATUS_TRAINING = "培训中"
STATUS_AUTHORIZED = "已授权"
STATUS_RECTIFYING = "整改中"
STATUS_SUSPENDED = "暂停授权"
STATUS_EXITED = "已退出"
STORE_STATES = (
    STATUS_APPLYING,
    STATUS_TRAINING,
    STATUS_AUTHORIZED,
    STATUS_RECTIFYING,
    STATUS_SUSPENDED,
    STATUS_EXITED,
)

# 规范要求的比较方式
REQ_MAX = "max"    # 数值上限，越低越严格，如冷链温度
REQ_MIN = "min"    # 数值下限，越高越严格，如每日留样次数
REQ_FLAG = "flag"  # 必须具备的制度，如明码标识


class DomainError(Exception):
    """业务规则被拒绝时抛出，消息面向操作者。"""


@dataclass(frozen=True)
class Requirement:
    """一条可在严格性上比较的规范要求。"""

    kind: str
    value: float | None = None

    @staticmethod
    def at_most(value: float) -> "Requirement":
        return Requirement(REQ_MAX, float(value))

    @staticmethod
    def at_least(value: float) -> "Requirement":
        return Requirement(REQ_MIN, float(value))

    @staticmethod
    def required() -> "Requirement":
        return Requirement(REQ_FLAG, None)

    def satisfied_by(self, other: "Requirement | None") -> bool:
        """判断 other 是否至少与本要求同样严格。"""
        if other is None or other.kind != self.kind:
            return False
        if self.kind == REQ_FLAG:
            return True
        if self.value is None or other.value is None:
            return False
        if self.kind == REQ_MAX:
            return other.value <= self.value
        return other.value >= self.value


@dataclass
class BaselineStandard:
    """协会发布的基础食品安全与标识规范版本。"""

    version: str
    requirements: dict[str, Requirement]
    issued_on: date
    effective_from: date
    transition_until: date | None = None  # 作为旧版本仍可使用的最后日期


@dataclass
class SchoolStandard:
    """流派在底线之上维护的原料、工序与风味规范版本。"""

    school: str
    version: str
    baseline_version: str
    requirements: dict[str, Requirement]
    effective_from: date


@dataclass
class StaffMember:
    """申请绑定的培训人员。"""

    name: str
    role: str
    trained: bool = False
    trained_on: date | None = None


@dataclass
class SupplySource:
    """申请绑定的供应来源，须经过认证。"""

    supplier_id: str
    name: str
    ingredient: str
    origin: str
    certified: bool = True


@dataclass
class StoreApplication:
    """品牌使用申请：绑定主体、人员、供应来源与申请品类。"""

    application_id: str
    store_name: str
    entity_code: str  # 实际经营主体（统一社会信用代码）
    address: str
    categories: list[str]
    school: str
    school_standard_version: str
    staff: list[StaffMember]
    suppliers: list[SupplySource]
    submitted_on: date
    status: str = STATUS_APPLYING


@dataclass
class License:
    """品牌授权：限定主体、品类和期限。"""

    license_id: str
    application_id: str
    store_name: str
    entity_code: str
    address: str
    categories: tuple[str, ...]
    school: str
    school_standard_version: str
    supplier_ids: tuple[str, ...]
    staff_names: tuple[str, ...]
    valid_from: date
    valid_to: date
    status: str = STATUS_AUTHORIZED


@dataclass
class Inspection:
    inspection_id: str
    license_id: str
    inspected_on: date
    result: str  # 合格 / 不合格
    findings: tuple[str, ...]
    batch_nos: tuple[str, ...]
    inspector: str


@dataclass
class Complaint:
    complaint_id: str
    license_id: str
    batch_no: str | None
    detail: str
    filed_on: date


@dataclass
class RectificationOrder:
    """整改单：只指向证据所及的门店与批次。"""

    order_id: str
    license_id: str
    batch_nos: tuple[str, ...]
    reason: str
    issued_on: date
    deadline: date
    source: str  # 抽检 / 投诉
    status: str = "待整改"
    closed_on: date | None = None


@dataclass
class ResourceProgram:
    """扶持资源项目，规则对外公开。"""

    program_id: str
    kind: str  # 扶持资金 / 培训名额 / 集采优惠
    title: str
    rule_text: str
    total_quota: int
    per_entity_cap: int
    open_from: date
    open_until: date


@dataclass
class ResourceGrant:
    grant_id: str
    program_id: str
    entity_code: str
    amount: int
    granted_on: date


@dataclass
class IngredientLot:
    """一批次商品用到的食材，关键食材必须来自绑定供应源。"""

    name: str
    supplier_id: str
    origin: str
    key: bool = True


@dataclass
class ProductBatch:
    """登记在案的品牌商品批次。"""

    batch_no: str
    product_name: str
    category: str
    license_id: str
    school: str
    school_standard_version: str
    ingredients: tuple[IngredientLot, ...]
    produced_on: date

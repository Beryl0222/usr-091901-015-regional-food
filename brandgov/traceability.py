"""品牌商品追溯：运营方全链路视图与公众摘要。"""
from __future__ import annotations

from .enforcement import EnforcementService
from .licensing import LicenseService
from .models import STATUS_AUTHORIZED, DomainError, ProductBatch

BRAND_NAME = "地域小吃公用品牌"


class TraceService:
    """从任一品牌商品查明流派版本、授权门店、关键食材来源与检查状态。"""

    def __init__(self, licensing: LicenseService, enforcement: EnforcementService):
        self._licensing = licensing
        self._enforcement = enforcement
        self._batches: dict[str, ProductBatch] = {}

    def register_batch(self, batch_no, product_name, category, license_id,
                       ingredients, produced_on):
        """登记品牌商品批次，绑定关系在登记时逐项核验。"""
        lic = self._licensing.get_license(license_id)
        if batch_no in self._batches:
            raise DomainError(f"批次 {batch_no} 已登记")
        if lic.status != STATUS_AUTHORIZED:
            raise DomainError("门店当前不在已授权状态，不得使用品牌生产")
        if category not in lic.categories:
            raise DomainError(f"品类 {category} 超出授权范围")
        if not (lic.valid_from <= produced_on <= lic.valid_to):
            raise DomainError("生产日期不在授权期限内")
        unknown = [lot.name for lot in ingredients
                   if lot.key and lot.supplier_id not in lic.supplier_ids]
        if unknown:
            raise DomainError(
                f"关键食材来源未在授权绑定范围内：{'、'.join(unknown)}")
        batch = ProductBatch(batch_no, product_name, category, license_id,
                             lic.school, lic.school_standard_version,
                             tuple(ingredients), produced_on)
        self._batches[batch_no] = batch
        return batch

    def batch(self, batch_no):
        try:
            return self._batches[batch_no]
        except KeyError:
            raise DomainError(f"批次 {batch_no} 不存在") from None

    def trace(self, batch_no):
        """运营方视图：完整的绑定关系与检查状态。"""
        batch = self.batch(batch_no)
        lic = self._licensing.get_license(batch.license_id)
        app = self._licensing.application(lic.application_id)
        supplier_names = {s.supplier_id: s.name for s in app.suppliers}
        return {
            "批次号": batch.batch_no,
            "产品": batch.product_name,
            "品类": batch.category,
            "生产日期": batch.produced_on,
            "门店": lic.store_name,
            "经营主体": lic.entity_code,
            "流派": batch.school,
            "流派规范版本": batch.school_standard_version,
            "关键食材": [
                {"名称": lot.name,
                 "供应商": supplier_names.get(lot.supplier_id, lot.supplier_id),
                 "产地": lot.origin}
                for lot in batch.ingredients if lot.key
            ],
            "门店状态": lic.status,
            "批次状态": self._enforcement.batch_status(batch.batch_no),
            "检查记录": self._enforcement.inspections_for(lic.license_id),
            "投诉记录": self._enforcement.complaints_for(lic.license_id),
            "未结整改": self._enforcement.open_orders(lic.license_id),
        }

    def public_summary(self, batch_no):
        """公众视图：可信，但不披露供应商身份与工艺配方。"""
        batch = self.batch(batch_no)
        lic = self._licensing.get_license(batch.license_id)
        if self._enforcement.batch_status(batch.batch_no) != "正常":
            status = "停售整改"
        elif self._enforcement.open_orders(lic.license_id):
            status = "整改中"
        elif lic.status != STATUS_AUTHORIZED:
            status = lic.status
        else:
            status = "合格在营"
        return {
            "品牌": BRAND_NAME,
            "产品": batch.product_name,
            "门店": lic.store_name,
            "流派": batch.school,
            "执行标准版本": batch.school_standard_version,
            "关键食材产地": list(dict.fromkeys(
                lot.origin for lot in batch.ingredients if lot.key)),
            "检查状态": status,
        }

"""抽检、投诉与整改：处置范围精确到门店与批次，不连坐。"""
from __future__ import annotations

import itertools
from datetime import timedelta

from .licensing import LicenseService
from .models import (
    STATUS_AUTHORIZED,
    STATUS_RECTIFYING,
    STATUS_SUSPENDED,
    Complaint,
    DomainError,
    Inspection,
    RectificationOrder,
)

RECTIFICATION_DAYS = 30


class EnforcementService:
    """记录抽检与投诉，整改处置只落在证据指向的门店与批次上。"""

    def __init__(self, licensing: LicenseService):
        self._licensing = licensing
        self._inspections: dict[str, Inspection] = {}
        self._complaints: dict[str, Complaint] = {}
        self._orders: dict[str, RectificationOrder] = {}
        self._batch_flags: dict[str, str] = {}  # batch_no -> 停售
        self._seq = itertools.count(1)

    def record_inspection(self, license_id, inspected_on, result, findings=(),
                          batch_nos=(), inspector="", severe=False):
        self._licensing.get_license(license_id)
        inspection_id = f"IN{next(self._seq):04d}"
        inspection = Inspection(inspection_id, license_id, inspected_on, result,
                                tuple(findings), tuple(batch_nos), inspector)
        self._inspections[inspection_id] = inspection
        order = None
        if result == "不合格":
            reason = "抽检不合格：" + ("；".join(findings) or "见检查记录")
            order = self._issue_order(license_id, tuple(batch_nos), reason,
                                      inspected_on, "抽检", severe)
        return inspection, order

    def record_complaint(self, license_id, batch_no, detail, filed_on, severe=False):
        self._licensing.get_license(license_id)
        complaint_id = f"CP{next(self._seq):04d}"
        complaint = Complaint(complaint_id, license_id, batch_no, detail, filed_on)
        self._complaints[complaint_id] = complaint
        batches = (batch_no,) if batch_no else ()
        order = self._issue_order(license_id, batches, f"顾客投诉：{detail}",
                                  filed_on, "投诉", severe)
        return complaint, order

    def _issue_order(self, license_id, batch_nos, reason, on, source, severe):
        order_id = f"RO{next(self._seq):04d}"
        order = RectificationOrder(order_id, license_id, tuple(batch_nos), reason,
                                   on, on + timedelta(days=RECTIFICATION_DAYS), source)
        self._orders[order_id] = order
        # 只处置证据指向的这一家门店，其余成员不受影响
        self._licensing.set_status(
            license_id, STATUS_SUSPENDED if severe else STATUS_RECTIFYING)
        for batch_no in batch_nos:
            self._batch_flags[batch_no] = "停售"
        return order

    def complete_rectification(self, order_id, on):
        """整改验收通过：恢复该门店授权，解除相关批次停售。"""
        order = self._orders.get(order_id)
        if order is None:
            raise DomainError(f"整改单 {order_id} 不存在")
        if order.status != "待整改":
            raise DomainError("整改单已关闭")
        order.status = "已整改"
        order.closed_on = on
        for batch_no in order.batch_nos:
            self._batch_flags.pop(batch_no, None)
        if not self.open_orders(order.license_id):
            self._licensing.set_status(order.license_id, STATUS_AUTHORIZED)
        return order

    def open_orders(self, license_id=None):
        return [o for o in self._orders.values()
                if o.status == "待整改"
                and (license_id is None or o.license_id == license_id)]

    def batch_status(self, batch_no):
        return self._batch_flags.get(batch_no, "正常")

    def inspections_for(self, license_id):
        return [i for i in self._inspections.values() if i.license_id == license_id]

    def complaints_for(self, license_id):
        return [c for c in self._complaints.values() if c.license_id == license_id]

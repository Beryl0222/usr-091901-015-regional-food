"""抽检、投诉与整改：只影响证据指向的门店或批次，不连坐其他成员。"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class EnforcementRecord:
    """一次抽检或投诉的处理记录，范围锁定到门店与批次。"""

    kind: str          # 抽检 / 投诉
    store_id: str
    batch_id: str | None
    passed: bool
    detail: str
    on: date


class EnforcementBoard:
    """记录执法事件并驱动涉事门店的整改流程。"""

    KINDS = ("抽检", "投诉")

    def __init__(self, office):
        self._office = office
        self._records = []
        self._recalled = set()  # 证据指向的问题批次

    def record(self, kind, store_id, passed, batch_id=None, detail="", on=None):
        """登记抽检或投诉；不通过时仅涉事门店转入整改、涉事批次召回。"""
        if kind not in self.KINDS:
            raise ValueError(f"未知执法类型:{kind}")
        lic = self._office.license(store_id)  # 无授权记录的门店直接报错
        rec = EnforcementRecord(kind, store_id, batch_id, bool(passed), detail,
                                on or date.today())
        self._records.append(rec)
        if not rec.passed:
            if rec.batch_id:
                self._recalled.add(rec.batch_id)
            if lic.state == "已授权":
                self._office.start_rectification(store_id)
        return rec

    def close_rectification(self, store_id, passed):
        """整改复核：通过恢复授权，不通过暂停授权。"""
        return self._office.finish_rectification(store_id, passed)

    def recalled_batches(self):
        return frozenset(self._recalled)

    def is_recalled(self, batch_id):
        return batch_id in self._recalled

    def history(self, store_id):
        """单店执法历史，供追溯视图引用。"""
        return [r for r in self._records if r.store_id == store_id]

    def last_result(self, store_id):
        records = self.history(store_id)
        return records[-1].passed if records else None

"""识别冒名店铺、异地迁店与授权到期。"""


class Watchdog:
    """基于授权台账的日常巡查。"""

    def __init__(self, office):
        self._office = office

    def expired(self, on):
        """授权到期但仍显示为已授权的门店。"""
        return self._office.expired(on)

    def check_claim(self, store_id, entity, on):
        """核对一处挂品牌经营的店铺，返回问题列表（空为可信）。"""
        problems = []
        try:
            lic = self._office.license(store_id)
        except KeyError:
            return [f"门店{store_id}无授权记录，疑似冒名"]
        if lic.entity != entity:
            problems.append(f"经营主体不符:登记为{lic.entity}")
        if lic.state in ("已退出", "暂停授权"):
            problems.append(f"授权状态为{lic.state}")
        elif lic.state != "已授权":
            problems.append(f"授权状态为{lic.state}，尚未有效")
        elif lic.valid_until is not None and lic.valid_until < on:
            problems.append(f"授权已于{lic.valid_until}到期")
        return problems

    def relocated(self, observed):
        """比对外卖平台或巡查采集的实际地址，找出异地迁店。

        observed: {store_id: 实际经营地址}
        """
        moved = []
        for store_id, address in observed.items():
            try:
                store = self._office.store(store_id)
            except KeyError:
                continue  # 无档案的由 check_claim 识别为冒名
            if store.address != address:
                moved.append(store_id)
        return moved

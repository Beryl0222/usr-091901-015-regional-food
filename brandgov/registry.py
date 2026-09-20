"""把各子服务装配成完整的共治后端。"""
from __future__ import annotations

from .enforcement import EnforcementService
from .licensing import LicenseService, Watchdog
from .models import STATUS_AUTHORIZED
from .resources import ResourceService
from .standards import StandardsService
from .traceability import TraceService


class BrandRegistry:
    """领域契约的运行时载体：规范、授权、执法、资源与追溯。"""

    def __init__(self):
        self.standards = StandardsService()
        self.licensing = LicenseService(self.standards)
        self.enforcement = EnforcementService(self.licensing)
        self.watchdog = Watchdog(self.licensing)
        self.resources = ResourceService(self._good_standing)
        self.trace = TraceService(self.licensing, self.enforcement)

    def _good_standing(self, entity_code):
        """公开规则引用的主体状态：已授权且无未结整改。"""
        licenses = [lic for lic in self.licensing.licenses()
                    if lic.entity_code == entity_code]
        if not licenses:
            return False
        latest = licenses[-1]
        if latest.status != STATUS_AUTHORIZED:
            return False
        return not self.enforcement.open_orders(latest.license_id)

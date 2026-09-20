"""协会基础规范与流派叠加规范的版本管理。"""
from __future__ import annotations

from .models import BaselineStandard, DomainError, Requirement, SchoolStandard


class StandardsService:
    """维护协会底线版本与流派版本，保证底线不被流派规则放宽。"""

    def __init__(self):
        self._baselines: dict[str, BaselineStandard] = {}
        self._order: list[str] = []  # 底线版本的发布顺序
        self._schools: dict[tuple[str, str], SchoolStandard] = {}

    def publish_baseline(self, version, requirements, issued_on, effective_from,
                         transition_until=None):
        """发布基础规范版本；transition_until 为上一版本设置的过渡截止日。"""
        if version in self._baselines:
            raise DomainError(f"基础规范版本 {version} 已存在")
        if not requirements:
            raise DomainError("基础规范不能为空")
        if self._order and transition_until is not None:
            previous = self._baselines[self._order[-1]]
            previous.transition_until = transition_until
        standard = BaselineStandard(version, dict(requirements), issued_on, effective_from)
        self._baselines[version] = standard
        self._order.append(version)
        return standard

    def baseline(self, version):
        return self._baselines.get(version)

    def current_baseline(self, on):
        """当日生效的底线版本。"""
        candidates = [v for v in self._order if self._baselines[v].effective_from <= on]
        if not candidates:
            raise DomainError("当日尚无生效的基础规范")
        return self._baselines[candidates[-1]]

    def baseline_acceptable(self, version, on) -> bool:
        """某底线版本当日是否仍可使用：现行版本，或仍在过渡期内。"""
        standard = self._baselines.get(version)
        if standard is None:
            return False
        if standard.version == self.current_baseline(on).version:
            return True
        return standard.transition_until is not None and on <= standard.transition_until

    def validate_overlay(self, baseline_version, overlay) -> list[str]:
        """检查流派叠加规范是否放宽了底线，返回问题列表。"""
        baseline = self._baselines.get(baseline_version)
        if baseline is None:
            return [f"基础规范版本 {baseline_version} 不存在"]
        problems = []
        for key, req in baseline.requirements.items():
            if not req.satisfied_by(overlay.get(key)):
                problems.append(f"流派规范放宽了底线要求：{key}")
        return problems

    def publish_school_standard(self, school, version, baseline_version,
                                requirements, effective_from):
        """流派在底线之上发布自己的原料、工序与风味规范。"""
        key = (school, version)
        if key in self._schools:
            raise DomainError(f"流派 {school} 的版本 {version} 已存在")
        problems = self.validate_overlay(baseline_version, requirements)
        if problems:
            raise DomainError("；".join(problems))
        standard = SchoolStandard(school, version, baseline_version,
                                  dict(requirements), effective_from)
        self._schools[key] = standard
        return standard

    def school_standard(self, school, version):
        return self._schools.get((school, version))

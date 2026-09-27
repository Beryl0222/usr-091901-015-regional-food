"""协会基础规范与流派标准的分层、版本与过渡期管理。

不变量：公共安全底线不得被流派规则放宽。
"""

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class BaselineStandard:
    """协会发布的基础食品安全与标识规范，任何流派不得放宽。"""

    version: str
    floors: dict          # 安全指标下限，如 {"中心温度C": 70}
    forbidden: frozenset  # 禁用原料或添加物
    labeling: tuple       # 必备标识项


@dataclass(frozen=True)
class SchoolProfile:
    """技艺流派在基础规范之上维护的原料、工序与风味差异。

    process 属商业配方细节，公众接口不得披露。
    """

    school: str
    version: str
    baseline_version: str
    floors: dict          # 流派自选指标，不得低于基础规范
    ingredients: tuple    # 原料清单，不得含禁用项
    process: tuple        # 工序要点
    flavor: str           # 风味描述
    effective_from: date
    transition_days: int = 0

    @property
    def transition_until(self):
        """过渡期截止日，此前旧版本仍可执行。"""
        return self.effective_from + timedelta(days=self.transition_days)


def check_profile(baseline, profile):
    """核对流派资料是否守住基础规范，返回违规原因列表（空为合规）。"""
    problems = []
    if profile.baseline_version != baseline.version:
        problems.append(f"流派未基于现行基础规范{baseline.version}")
    for key, floor in baseline.floors.items():
        value = profile.floors.get(key)
        if value is None or value < floor:
            problems.append(f"指标{key}低于基础下限{floor}")
    bad = sorted(baseline.forbidden.intersection(profile.ingredients))
    if bad:
        problems.append(f"含禁用原料:{','.join(bad)}")
    return problems


class StandardRegistry:
    """登记基础规范与各流派版本，处理修订过渡期。"""

    def __init__(self):
        self._baseline = None
        self._profiles = {}  # 流派名 -> [SchoolProfile]，按生效日期排序

    @property
    def baseline(self):
        return self._baseline

    def publish_baseline(self, baseline):
        self._baseline = baseline
        return baseline

    def register_profile(self, profile):
        """登记流派版本；触碰安全底线的版本直接拒绝。"""
        if self._baseline is None:
            raise ValueError("协会尚未发布基础规范")
        problems = check_profile(self._baseline, profile)
        if problems:
            raise ValueError(";".join(problems))
        versions = self._profiles.setdefault(profile.school, [])
        if any(p.version == profile.version for p in versions):
            raise ValueError(f"流派{profile.school}版本{profile.version}已存在")
        versions.append(profile)
        versions.sort(key=lambda p: p.effective_from)
        return profile

    def profile(self, school, version):
        for p in self._profiles.get(school, []):
            if p.version == version:
                return p
        raise KeyError(f"未登记的流派版本:{school}@{version}")

    def acceptable_versions(self, school, on):
        """当日可执行的流派版本：现行版，及仍处过渡期内的前一版。"""
        versions = [p for p in self._profiles.get(school, []) if p.effective_from <= on]
        if not versions:
            return ()
        accepted = [versions[-1].version]
        if len(versions) > 1 and on <= versions[-1].transition_until:
            accepted.append(versions[-2].version)
        return tuple(accepted)

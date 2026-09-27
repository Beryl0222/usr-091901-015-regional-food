"""扶持资金、培训名额与集采优惠：按公开规则分配，重复申报不得多占。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AllocationRule:
    """公开的分配规则，任何成员可查阅。"""

    program: str        # 扶持资金 / 培训名额 / 集采优惠
    period: str         # 分配周期，如 "2026"
    quota: int          # 本期名额
    amount: int = 0     # 单位额度（资金为元，名额与折扣可为 0）
    eligible_states: tuple = ("已授权",)


@dataclass(frozen=True)
class Grant:
    """一次资源分配结果。"""

    entity: str
    program: str
    period: str
    amount: int


class ResourcePool:
    """按规则受理申报；同一主体在同一周期同一项目只能获得一次。"""

    def __init__(self, office):
        self._office = office
        self._rules = {}
        self._grants = []

    def declare(self, rule):
        self._rules[(rule.program, rule.period)] = rule
        return rule

    def rules(self):
        """公开规则清单。"""
        return list(self._rules.values())

    def grants(self):
        """公开分配结果，接受成员监督。"""
        return list(self._grants)

    def apply(self, entity, program, period):
        rule = self._rules.get((program, period))
        if rule is None:
            raise ValueError(f"项目{program}周期{period}无公开规则")
        if any(g.entity == entity and g.program == program and g.period == period
               for g in self._grants):
            raise ValueError(f"主体{entity}在{period}已申报{program}，不得重复占用")
        eligible = any(
            lic.entity == entity and lic.state in rule.eligible_states
            for lic in self._office.licenses()
        )
        if not eligible:
            raise ValueError(f"主体{entity}不具备申报资格")
        used = sum(1 for g in self._grants
                   if g.program == program and g.period == period)
        if used >= rule.quota:
            raise ValueError(f"项目{program}周期{period}名额已满")
        grant = Grant(entity, program, period, rule.amount)
        self._grants.append(grant)
        return grant

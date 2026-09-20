"""扶持资源分配：公开规则、主体去重、总量与上限控制。"""
from __future__ import annotations

import itertools

from .models import DomainError, ResourceGrant, ResourceProgram


class ResourceService:
    """按公开规则分配扶持资金、培训名额与集采优惠。"""

    def __init__(self, good_standing):
        # good_standing(entity_code) -> bool，由注册中心按授权与整改状态判定
        self._good_standing = good_standing
        self._programs: dict[str, ResourceProgram] = {}
        self._grants: list[ResourceGrant] = []
        self._seq = itertools.count(1)

    def create_program(self, program_id, kind, title, rule_text, total_quota,
                       per_entity_cap, open_from, open_until):
        if program_id in self._programs:
            raise DomainError(f"项目 {program_id} 已存在")
        if total_quota < 1 or per_entity_cap < 1:
            raise DomainError("名额配置无效")
        if open_until < open_from:
            raise DomainError("申报期无效")
        program = ResourceProgram(program_id, kind, title, rule_text, total_quota,
                                  per_entity_cap, open_from, open_until)
        self._programs[program_id] = program
        return program

    def program(self, program_id):
        try:
            return self._programs[program_id]
        except KeyError:
            raise DomainError(f"项目 {program_id} 不存在") from None

    def apply(self, program_id, entity_code, on, amount=1):
        """申报资源：同一主体重复申报不得多占，总量先到先得。"""
        program = self.program(program_id)
        if not (program.open_from <= on <= program.open_until):
            raise DomainError("不在项目申报期内")
        if amount < 1:
            raise DomainError("申报数量无效")
        if not self._good_standing(entity_code):
            raise DomainError("主体当前状态不符合公开规则的申请条件")
        used_by_entity = sum(
            g.amount for g in self._grants
            if g.program_id == program_id and g.entity_code == entity_code)
        if used_by_entity + amount > program.per_entity_cap:
            raise DomainError("重复申报不得多占资源：已触及单主体上限")
        used_total = sum(g.amount for g in self._grants if g.program_id == program_id)
        if used_total + amount > program.total_quota:
            raise DomainError("项目资源已分配完毕")
        grant = ResourceGrant(f"GR{next(self._seq):04d}", program_id, entity_code,
                              amount, on)
        self._grants.append(grant)
        return grant

    def grants(self, program_id=None):
        return [g for g in self._grants
                if program_id is None or g.program_id == program_id]

    def remaining(self, program_id):
        program = self.program(program_id)
        used = sum(g.amount for g in self._grants if g.program_id == program_id)
        return program.total_quota - used

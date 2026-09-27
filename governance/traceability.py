"""品牌商品追溯：运营方全链路可查，公众只见可信且不泄密的摘要。"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Product:
    """一件挂牌出售的品牌商品。"""

    product_id: str
    store_id: str
    category: str
    school: str
    school_version: str
    ingredients: tuple  # (名称, 供应商, 批次号)
    made_on: date


class TraceBook:
    """登记品牌商品并提供分级追溯视图。"""

    def __init__(self, office, standards, board):
        self._office = office
        self._standards = standards
        self._board = board
        self._products = {}

    def register(self, product):
        """上架登记：授权、品类、流派版本、供应来源与批次状态逐项核对。"""
        lic = self._office.license(product.store_id)
        problems = []
        if not self._office.is_authorized(product.store_id, product.made_on):
            problems.append("门店当日无有效授权")
        if product.category not in lic.categories:
            problems.append(f"品类{product.category}未获授权")
        if product.school != lic.school:
            problems.append(f"门店授权流派为{lic.school}")
        elif product.school_version not in self._standards.acceptable_versions(
                product.school, product.made_on):
            problems.append(f"流派版本{product.school_version}当日不可执行")
        for name, supplier, batch_id in product.ingredients:
            if supplier not in lic.suppliers:
                problems.append(f"供应商{supplier}不在获准来源")
            if self._board.is_recalled(batch_id):
                problems.append(f"批次{batch_id}已被召回")
        if problems:
            raise ValueError(";".join(problems))
        self._products[product.product_id] = product
        return product

    def get(self, product_id):
        try:
            return self._products[product_id]
        except KeyError:
            raise KeyError(f"未登记的品牌商品:{product_id}") from None

    def operator_trace(self, product_id):
        """运营方视图：流派版本、授权门店、关键食材来源与检查状态。"""
        product = self.get(product_id)
        lic = self._office.license(product.store_id)
        return {
            "商品": product.product_id,
            "品类": product.category,
            "流派": product.school,
            "流派版本": product.school_version,
            "门店": product.store_id,
            "经营主体": lic.entity,
            "授权状态": lic.state,
            "授权截止": lic.valid_until.isoformat() if lic.valid_until else None,
            "食材来源": [
                {"名称": name, "供应商": supplier, "批次": batch_id,
                 "批次已召回": self._board.is_recalled(batch_id)}
                for name, supplier, batch_id in product.ingredients
            ],
            "最近检查": self._board.last_result(product.store_id),
            "执法记录数": len(self._board.history(product.store_id)),
        }

    def public_summary(self, product_id):
        """公众视图：可信但不披露工序配方与供应商明细。"""
        product = self.get(product_id)
        lic = self._office.license(product.store_id)
        profile = self._standards.profile(product.school, product.school_version)
        last = self._board.last_result(product.store_id)
        return {
            "品牌商品": product.product_id,
            "品类": product.category,
            "风味流派": product.school,
            "风味特点": profile.flavor,
            "授权有效": lic.state == "已授权",
            "最近检查合格": last,
            "食材来源可追溯": all(s in lic.suppliers
                                 for _, s, _ in product.ingredients),
        }

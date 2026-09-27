"""地域小吃品牌共治的服务入口：健康检查、领域契约与共治接口。"""

import argparse
import json
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from governance import (AllocationRule, BaselineStandard, EnforcementBoard,
                        LicenseOffice, Product, ResourcePool, SchoolProfile,
                        StandardRegistry, Store, TraceBook, Watchdog)

SERVICE_ID = "regional-food-brand"
SERVICE_NAME = "地域小吃品牌共治"
CONTRACT_PATH = Path(__file__).with_name("domain_contract.json")


def load_contract():
    """读取并校验项目领域契约。"""
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if contract.get("service_id") != SERVICE_ID:
        raise ValueError("领域契约与服务身份不一致")
    return contract


def health_payload():
    """返回服务运行状态。"""
    return {"status": "ok", "service": SERVICE_ID, "name": SERVICE_NAME}


def _date(text):
    return date.fromisoformat(text)


class Hub:
    """把各领域模块装配成可查询的共治台账。"""

    def __init__(self):
        self.standards = StandardRegistry()
        self.office = LicenseOffice()
        self.board = EnforcementBoard(self.office)
        self.watchdog = Watchdog(self.office)
        self.pool = ResourcePool(self.office)
        self.trace = TraceBook(self.office, self.standards, self.board)

    def post(self, path, data):
        """按路径分发写操作，返回可序列化的结果。"""
        routes = {
            "/api/stores": self._add_store,
            "/api/standards/baseline": self._publish_baseline,
            "/api/standards/profiles": self._register_profile,
            "/api/licenses/apply": self._apply_license,
            "/api/licenses/train": self._train,
            "/api/licenses/grant": self._grant,
            "/api/enforcement": self._enforce,
            "/api/resources/rules": self._declare_rule,
            "/api/resources/apply": self._apply_resource,
            "/api/products": self._register_product,
        }
        if path not in routes:
            raise KeyError(path)
        return routes[path](data)

    def get(self, path, query):
        """按路径分发读操作。"""
        if path.startswith("/api/trace/"):
            return self.trace.operator_trace(path.rsplit("/", 1)[1])
        if path.startswith("/api/public/"):
            return self.trace.public_summary(path.rsplit("/", 1)[1])
        if path == "/api/detection/expired":
            on = _date(query["on"][0]) if "on" in query else date.today()
            return {"到期门店": self.watchdog.expired(on)}
        if path == "/api/detection/claim":
            on = _date(query["on"][0]) if "on" in query else date.today()
            problems = self.watchdog.check_claim(
                query["store_id"][0], query["entity"][0], on)
            return {"可信": not problems, "问题": problems}
        if path == "/api/resources/rules":
            return {"规则": [r.__dict__ for r in self.pool.rules()],
                    "分配": [g.__dict__ for g in self.pool.grants()]}
        raise KeyError(path)

    def _add_store(self, d):
        store = self.office.register_store(Store(d["store_id"], d["entity"], d["address"]))
        return {"门店": store.store_id}

    def _publish_baseline(self, d):
        b = self.standards.publish_baseline(BaselineStandard(
            d["version"], d["floors"], frozenset(d["forbidden"]), tuple(d["labeling"])))
        return {"基础规范": b.version}

    def _register_profile(self, d):
        p = self.standards.register_profile(SchoolProfile(
            d["school"], d["version"], d["baseline_version"], d["floors"],
            tuple(d["ingredients"]), tuple(d["process"]), d["flavor"],
            _date(d["effective_from"]), d.get("transition_days", 0)))
        return {"流派版本": f"{p.school}@{p.version}"}

    def _apply_license(self, d):
        lic = self.office.apply(d["store_id"], d["school"], d["categories"],
                                d["staff"], d["suppliers"])
        return {"门店": lic.store_id, "状态": lic.state}

    def _train(self, d):
        lic = self.office.complete_training(d["store_id"], d["person"])
        return {"门店": lic.store_id, "状态": lic.state}

    def _grant(self, d):
        lic = self.office.grant(d["store_id"], _date(d["valid_until"]))
        return {"门店": lic.store_id, "状态": lic.state}

    def _enforce(self, d):
        rec = self.board.record(d["kind"], d["store_id"], d["passed"],
                                d.get("batch_id"), d.get("detail", ""),
                                _date(d["on"]) if "on" in d else None)
        lic = self.office.license(rec.store_id)
        return {"门店": rec.store_id, "状态": lic.state,
                "召回批次": sorted(self.board.recalled_batches())}

    def _declare_rule(self, d):
        rule = self.pool.declare(AllocationRule(
            d["program"], d["period"], d["quota"], d.get("amount", 0),
            tuple(d.get("eligible_states", ("已授权",)))))
        return {"规则": f"{rule.program}/{rule.period}"}

    def _apply_resource(self, d):
        grant = self.pool.apply(d["entity"], d["program"], d["period"])
        return {"主体": grant.entity, "项目": grant.program, "额度": grant.amount}

    def _register_product(self, d):
        p = self.trace.register(Product(
            d["product_id"], d["store_id"], d["category"], d["school"],
            d["school_version"], tuple(tuple(i) for i in d["ingredients"]),
            _date(d["made_on"])))
        return {"商品": p.product_id}


class Handler(BaseHTTPRequestHandler):
    """提供健康检查、领域契约与共治读写接口。"""

    hub = Hub()

    def do_GET(self):
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            return self._send_json(health_payload())
        if parsed.path == "/contract":
            return self._send_json(load_contract())
        try:
            return self._send_json(self.hub.get(parsed.path, parse_qs(parsed.query)))
        except KeyError:
            return self.send_error(404)
        except (ValueError, IndexError) as exc:
            return self._send_json({"错误": str(exc)}, status=400)

    def do_POST(self):
        from urllib.parse import urlparse
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            return self._send_json(self.hub.post(urlparse(self.path).path, data), status=201)
        except KeyError:
            return self.send_error(404)
        except (ValueError, json.JSONDecodeError) as exc:
            return self._send_json({"错误": str(exc)}, status=400)

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


def main():
    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        contract = load_contract()
        assert contract["states"] and contract["invariants"]
        Hub()  # 各领域模块可正常装配
        print("基础检查通过")
        return
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()

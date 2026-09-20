"""地域小吃品牌共治的服务入口：健康检查、领域契约与共治 API。"""

import argparse
import json
from dataclasses import asdict, is_dataclass
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from brandgov import (
    BrandRegistry,
    DomainError,
    IngredientLot,
    Requirement,
    StaffMember,
    SupplySource,
)

SERVICE_ID = "regional-food-brand"
SERVICE_NAME = "地域小吃品牌共治"
CONTRACT_PATH = Path(__file__).with_name("domain_contract.json")

REGISTRY = BrandRegistry()


def reset_state():
    """重置内存中的共治数据，供测试与演示使用。"""
    global REGISTRY
    REGISTRY = BrandRegistry()
    return REGISTRY


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
    if isinstance(text, date):
        return text
    return date.fromisoformat(text)


def _jsonable(value):
    if is_dataclass(value):
        return {k: _jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, date):
        return value.isoformat()
    return value


def _requirements(payload):
    return {key: Requirement(item["kind"], item.get("value"))
            for key, item in payload.items()}


# ---- 共治 API 动作 ----

def api_publish_baseline(body):
    return REGISTRY.standards.publish_baseline(
        body["version"], _requirements(body["requirements"]),
        _date(body["issued_on"]), _date(body["effective_from"]),
        _date(body["transition_until"]) if body.get("transition_until") else None)


def api_publish_school(body):
    return REGISTRY.standards.publish_school_standard(
        body["school"], body["version"], body["baseline_version"],
        _requirements(body["requirements"]), _date(body["effective_from"]))


def api_apply_store(body):
    staff = [StaffMember(s["name"], s.get("role", "")) for s in body["staff"]]
    suppliers = [SupplySource(s["supplier_id"], s["name"], s["ingredient"],
                              s["origin"], s.get("certified", True))
                 for s in body["suppliers"]]
    return REGISTRY.licensing.apply(
        body["store_name"], body["entity_code"], body["address"],
        body["categories"], body["school"], body["school_standard_version"],
        staff, suppliers, _date(body["submitted_on"]))


def api_record_inspection(body):
    inspection, order = REGISTRY.enforcement.record_inspection(
        body["license_id"], _date(body["inspected_on"]), body["result"],
        body.get("findings", ()), body.get("batch_nos", ()),
        body.get("inspector", ""), body.get("severe", False))
    return {"inspection": inspection, "rectification": order}


def api_record_complaint(body):
    complaint, order = REGISTRY.enforcement.record_complaint(
        body["license_id"], body.get("batch_no"), body["detail"],
        _date(body["filed_on"]), body.get("severe", False))
    return {"complaint": complaint, "rectification": order}


def api_create_program(body):
    return REGISTRY.resources.create_program(
        body["program_id"], body["kind"], body["title"], body["rule_text"],
        body["total_quota"], body["per_entity_cap"],
        _date(body["open_from"]), _date(body["open_until"]))


def api_register_batch(body):
    ingredients = [IngredientLot(i["name"], i["supplier_id"], i["origin"],
                                 i.get("key", True))
                   for i in body["ingredients"]]
    return REGISTRY.trace.register_batch(
        body["batch_no"], body["product_name"], body["category"],
        body["license_id"], ingredients, _date(body["produced_on"]))


POST_ROUTES = {
    "/api/standards/baseline": api_publish_baseline,
    "/api/standards/school": api_publish_school,
    "/api/stores/apply": api_apply_store,
    "/api/stores/training/start":
        lambda b: REGISTRY.licensing.start_training(b["application_id"]),
    "/api/stores/training/complete":
        lambda b: REGISTRY.licensing.complete_training(
            b["application_id"], b["staff_name"], _date(b["on"])),
    "/api/stores/authorize":
        lambda b: REGISTRY.licensing.authorize(
            b["application_id"], _date(b["valid_from"]), _date(b["valid_to"])),
    "/api/inspections": api_record_inspection,
    "/api/complaints": api_record_complaint,
    "/api/rectifications/complete":
        lambda b: REGISTRY.enforcement.complete_rectification(
            b["order_id"], _date(b["on"])),
    "/api/watchdog/verify":
        lambda b: REGISTRY.watchdog.verify_claim(
            b["store_name"], b["entity_code"], b["address"], _date(b["today"])),
    "/api/watchdog/report-address":
        lambda b: REGISTRY.watchdog.report_address(
            b["license_id"], b["observed_address"], _date(b["observed_on"]))
        or {"ok": True},
    "/api/resources/programs": api_create_program,
    "/api/resources/apply":
        lambda b: REGISTRY.resources.apply(
            b["program_id"], b["entity_code"], _date(b["on"]),
            b.get("amount", 1)),
    "/api/batches": api_register_batch,
}


class Handler(BaseHTTPRequestHandler):
    """提供健康检查、领域契约读取与共治业务接口。"""

    def do_GET(self):
        path = urlparse(self.path).path
        query = parse_qs(urlparse(self.path).query)
        try:
            if path == "/health":
                return self._send_json(health_payload())
            if path == "/contract":
                return self._send_json(load_contract())
            if path == "/api/licenses":
                return self._send_json(
                    [_jsonable(lic) for lic in REGISTRY.licensing.licenses()])
            if path == "/api/watchdog/expired":
                today = _date(query["today"][0])
                return self._send_json(
                    [_jsonable(lic)
                     for lic in REGISTRY.watchdog.expired_licenses(today)])
            if path == "/api/watchdog/relocations":
                return self._send_json(
                    _jsonable(REGISTRY.watchdog.relocation_alerts()))
            if path.startswith("/api/trace/"):
                batch_no = path.rsplit("/", 1)[1]
                return self._send_json(_jsonable(REGISTRY.trace.trace(batch_no)))
            if path.startswith("/api/public/"):
                batch_no = path.rsplit("/", 1)[1]
                return self._send_json(
                    _jsonable(REGISTRY.trace.public_summary(batch_no)))
            return self.send_error(404)
        except DomainError as exc:
            return self._send_json({"error": str(exc)}, status=400)
        except (KeyError, ValueError) as exc:
            return self._send_json({"error": f"请求参数无效: {exc}"}, status=400)

    def do_POST(self):
        path = urlparse(self.path).path
        action = POST_ROUTES.get(path)
        if action is None:
            return self.send_error(404)
        try:
            result = action(self._read_body())
            self._send_json(_jsonable(result) if result is not None else {"ok": True})
        except DomainError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except (KeyError, ValueError) as exc:
            self._send_json({"error": f"请求参数无效: {exc}"}, status=400)

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

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
        from brandgov import STORE_STATES
        contract = load_contract()
        assert contract["states"] and contract["invariants"]
        assert tuple(contract["states"]) == STORE_STATES, "契约状态与领域模型不一致"
        print("基础检查通过")
        return
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()

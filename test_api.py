"""共治 API 的端到端测试。"""
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import service
from service import Handler


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from http.server import ThreadingHTTPServer
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        service.reset_state()

    def post(self, path, payload):
        req = Request(self.base_url + path,
                      data=json.dumps(payload).encode("utf-8"),
                      headers={"Content-Type": "application/json"},
                      method="POST")
        with urlopen(req, timeout=2) as resp:
            self.assertEqual(resp.status, 200)
            return json.load(resp)

    def post_error(self, path, payload):
        req = Request(self.base_url + path,
                      data=json.dumps(payload).encode("utf-8"),
                      headers={"Content-Type": "application/json"},
                      method="POST")
        with self.assertRaises(HTTPError) as err:
            urlopen(req, timeout=2)
        self.assertEqual(err.exception.code, 400)
        err.exception.close()

    def get(self, path):
        with urlopen(self.base_url + path, timeout=2) as resp:
            self.assertEqual(resp.status, 200)
            return json.load(resp)

    def seed_store(self):
        self.post("/api/standards/baseline", {
            "version": "BL1",
            "requirements": {
                "冷链温度": {"kind": "max", "value": 4},
                "明码标识": {"kind": "flag"},
            },
            "issued_on": "2026-01-01", "effective_from": "2026-01-01"})
        self.post("/api/standards/school", {
            "school": "老城派", "version": "v1", "baseline_version": "BL1",
            "requirements": {
                "冷链温度": {"kind": "max", "value": 2},
                "明码标识": {"kind": "flag"},
                "豆瓣酱发酵天数": {"kind": "min", "value": 180},
            },
            "effective_from": "2026-01-01"})
        app = self.post("/api/stores/apply", {
            "store_name": "张记锅贴", "entity_code": "91320100MA1AAAAA1A",
            "address": "老街1号", "categories": ["牛肉锅贴"],
            "school": "老城派", "school_standard_version": "v1",
            "staff": [{"name": "张三", "role": "主理人"}],
            "suppliers": [{"supplier_id": "SUP1", "name": "本地黄牛合作社",
                           "ingredient": "牛肉", "origin": "本县"}],
            "submitted_on": "2026-03-01"})
        app_id = app["application_id"]
        self.post("/api/stores/training/start", {"application_id": app_id})
        self.post("/api/stores/training/complete",
                  {"application_id": app_id, "staff_name": "张三",
                   "on": "2026-03-10"})
        return self.post("/api/stores/authorize",
                         {"application_id": app_id,
                          "valid_from": "2026-03-15", "valid_to": "2027-03-14"})

    def test_full_governance_flow_over_http(self):
        lic = self.seed_store()
        self.assertEqual(lic["status"], "已授权")
        self.post("/api/batches", {
            "batch_no": "B20260601", "product_name": "牛肉锅贴",
            "category": "牛肉锅贴", "license_id": lic["license_id"],
            "ingredients": [{"name": "牛肉", "supplier_id": "SUP1",
                             "origin": "本县"}],
            "produced_on": "2026-06-01"})
        trace = self.get("/api/trace/B20260601")
        self.assertEqual(trace["流派规范版本"], "v1")
        self.assertEqual(trace["关键食材"][0]["供应商"], "本地黄牛合作社")
        summary = self.get("/api/public/B20260601")
        self.assertEqual(summary["检查状态"], "合格在营")
        self.assertNotIn("供应商", json.dumps(summary, ensure_ascii=False))
        # 抽检不合格 → 公众摘要反映整改，整改完成后恢复
        result = self.post("/api/inspections", {
            "license_id": lic["license_id"], "inspected_on": "2026-06-02",
            "result": "不合格", "findings": ["留样不足"],
            "batch_nos": ["B20260601"], "inspector": "检查员甲"})
        order_id = result["rectification"]["order_id"]
        self.assertEqual(self.get("/api/public/B20260601")["检查状态"], "停售整改")
        self.post("/api/rectifications/complete",
                  {"order_id": order_id, "on": "2026-06-20"})
        self.assertEqual(self.get("/api/public/B20260601")["检查状态"], "合格在营")

    def test_overlay_relaxing_baseline_rejected_over_http(self):
        self.post("/api/standards/baseline", {
            "version": "BL1",
            "requirements": {"冷链温度": {"kind": "max", "value": 4}},
            "issued_on": "2026-01-01", "effective_from": "2026-01-01"})
        self.post_error("/api/standards/school", {
            "school": "新城派", "version": "v1", "baseline_version": "BL1",
            "requirements": {"冷链温度": {"kind": "max", "value": 10}},
            "effective_from": "2026-01-01"})

    def test_watchdog_and_unknown_route(self):
        lic = self.seed_store()
        verdict = self.post("/api/watchdog/verify", {
            "store_name": "李鬼锅贴", "entity_code": "X", "address": "Y",
            "today": "2026-06-01"})
        self.assertEqual(verdict["verdict"], "冒名")
        self.post("/api/watchdog/report-address", {
            "license_id": lic["license_id"], "observed_address": "开发区99号",
            "observed_on": "2026-06-01"})
        alerts = self.get("/api/watchdog/relocations")
        self.assertEqual(alerts[0]["observed_address"], "开发区99号")
        with self.assertRaises(HTTPError) as err:
            urlopen(self.base_url + "/api/nope", timeout=2)
        self.assertEqual(err.exception.code, 404)
        err.exception.close()


if __name__ == "__main__":
    unittest.main()

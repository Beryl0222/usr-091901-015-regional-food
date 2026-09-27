"""验证共治 HTTP 接口的读写行为。"""
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from service import Handler, Hub


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from http.server import ThreadingHTTPServer
        Handler.hub = Hub()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def post(self, path, data):
        request = Request(f"{self.base_url}{path}", data=json.dumps(data).encode(),
                          headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=2) as response:
            self.assertEqual(response.status, 201)
            return json.load(response)

    def read_json(self, path):
        with urlopen(f"{self.base_url}{path}", timeout=2) as response:
            self.assertEqual(response.status, 200)
            return json.load(response)

    def test_full_governance_flow(self):
        self.post("/api/standards/baseline", {
            "version": "B1", "floors": {"中心温度C": 70},
            "forbidden": ["罂粟壳"], "labeling": ["品牌标识"]})
        self.post("/api/standards/profiles", {
            "school": "张派", "version": "1.0", "baseline_version": "B1",
            "floors": {"中心温度C": 70}, "ingredients": ["面粉"],
            "process": ["和面"], "flavor": "酥脆", "effective_from": "2026-01-01"})
        self.post("/api/stores", {
            "store_id": "S1", "entity": "张家合作社", "address": "东村老街1号"})
        self.post("/api/licenses/apply", {
            "store_id": "S1", "school": "张派", "categories": ["烧饼"],
            "staff": ["小王"], "suppliers": ["县粮油站"]})
        self.post("/api/licenses/train", {"store_id": "S1", "person": "小王"})
        result = self.post("/api/licenses/grant",
                           {"store_id": "S1", "valid_until": "2027-03-31"})
        self.assertEqual(result["状态"], "已授权")
        self.post("/api/products", {
            "product_id": "P1", "store_id": "S1", "category": "烧饼",
            "school": "张派", "school_version": "1.0",
            "ingredients": [["面粉", "县粮油站", "B-01"]], "made_on": "2026-09-27"})
        full = self.read_json("/api/trace/P1")
        self.assertEqual(full["经营主体"], "张家合作社")
        public = self.read_json("/api/public/P1")
        self.assertTrue(public["授权有效"])
        self.assertNotIn("县粮油站", json.dumps(public, ensure_ascii=False))
        claim = self.read_json("/api/detection/claim?" + urlencode(
            {"store_id": "S1", "entity": "张家合作社"}))
        self.assertTrue(claim["可信"])
        impostor = self.read_json("/api/detection/claim?" + urlencode(
            {"store_id": "SX", "entity": "陌生人"}))
        self.assertFalse(impostor["可信"])

    def test_enforcement_and_resources_over_http(self):
        self.post("/api/stores", {
            "store_id": "S2", "entity": "李家作坊", "address": "西村桥头3号"})
        self.post("/api/licenses/apply", {
            "store_id": "S2", "school": "张派", "categories": ["烧饼"],
            "staff": [], "suppliers": ["县粮油站"]})
        self.post("/api/licenses/grant",
                  {"store_id": "S2", "valid_until": "2027-03-31"})
        result = self.post("/api/enforcement", {
            "kind": "投诉", "store_id": "S2", "passed": False, "batch_id": "B-77"})
        self.assertEqual(result["状态"], "整改中")
        self.assertEqual(result["召回批次"], ["B-77"])
        self.post("/api/resources/rules", {
            "program": "集采优惠", "period": "2026", "quota": 5})
        with self.assertRaises(HTTPError) as error:  # 整改中不具备申报资格
            self.post("/api/resources/apply", {
                "entity": "李家作坊", "program": "集采优惠", "period": "2026"})
        self.assertEqual(error.exception.code, 400)
        error.exception.close()

    def test_unknown_routes_and_bad_input(self):
        with self.assertRaises(HTTPError) as error:
            self.read_json("/api/nope")
        self.assertEqual(error.exception.code, 404)
        error.exception.close()
        with self.assertRaises(HTTPError) as error:
            self.post("/api/standards/profiles", {
                "school": "李派", "version": "1.0", "baseline_version": "B1",
                "floors": {"中心温度C": 50}, "ingredients": ["面粉"],
                "process": [], "flavor": "", "effective_from": "2026-01-01"})
        self.assertEqual(error.exception.code, 400)  # 触碰安全底线被拒
        error.exception.close()


if __name__ == "__main__":
    unittest.main()

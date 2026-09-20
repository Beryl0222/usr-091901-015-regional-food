# 地域小吃品牌共治

协调公共安全规范、地方流派标准、门店授权和扶持资源。项目以领域契约约定参与者、状态和不可破坏的业务原则，各模块围绕同一语义协作。

## 领域模块（brandgov 包）

- `standards`：协会发布基础食品安全与标识规范（底线），各技艺流派在底线之上维护自己的原料、工序与风味差异；流派规范若放宽底线即被拒绝。标准修订设过渡期，过渡期内旧版本仍可使用。
- `licensing`：门店申请使用品牌时绑定实际经营主体、培训人员、供应来源和获准品类，经培训后签发限定主体、品类和期限的授权；巡查识别冒名店铺、异地迁店和授权到期。
- `enforcement`：抽检与顾客投诉生成整改单，只影响证据指向的门店与批次，不因一家问题连坐全部成员；整改验收后恢复。
- `resources`：扶持资金、培训名额和集采优惠依据公开规则分配，同一主体重复申报不得多占资源。
- `traceability`：运营方从任一品牌商品查明采用的流派版本、授权门店、关键食材来源和检查状态；公众只获得可信且不过度披露商业配方的摘要。

## 运行

- `python3 service.py --check`：核对服务配置与契约一致性。
- `python3 service.py --port 8000`：启动服务。
- `python3 -m unittest -v`：运行全部测试。

## HTTP 接口

- `GET /health`、`GET /contract`：运行状态与领域契约。
- `POST /api/standards/baseline`、`POST /api/standards/school`：发布底线与流派规范。
- `POST /api/stores/apply`、`/api/stores/training/start`、`/api/stores/training/complete`、`/api/stores/authorize`：申请、培训与授权。
- `POST /api/inspections`、`POST /api/complaints`、`POST /api/rectifications/complete`：抽检、投诉与整改闭环。
- `POST /api/watchdog/verify`、`POST /api/watchdog/report-address`、`GET /api/watchdog/expired?today=YYYY-MM-DD`、`GET /api/watchdog/relocations`：冒名核验、迁店线索与到期识别。
- `POST /api/resources/programs`、`POST /api/resources/apply`：扶持项目与申报。
- `POST /api/batches`：登记品牌商品批次。
- `GET /api/trace/<批次号>`：运营方全链路追溯；`GET /api/public/<批次号>`：公众摘要。
- `GET /api/licenses`：授权名录。

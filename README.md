# 地域小吃品牌共治

协调公共安全规范、地方流派标准、门店授权和扶持资源。项目以领域契约约定参与者、状态和不可破坏的业务原则，基础服务提供稳定的运行检查与契约读取接口，便于各模块围绕同一语义协作。

## 领域模块（governance 包）

- `standards`：协会发布基础食品安全与标识规范（指标下限、禁用原料、必备标识）；各技艺流派在此之上登记自己的原料、工序与风味版本，触碰安全底线的版本直接拒绝。标准修订设过渡期，过渡期内新旧版本均可执行。
- `licensing`：门店申请使用品牌时绑定实际经营主体、培训人员、供应来源与获准品类；全员完成培训方可授权，授权限定主体、品类和期限。状态机取自契约：申请加入 → 培训中 → 已授权 ⇄ 整改中 / 暂停授权 → 已退出。
- `enforcement`：抽检与投诉只影响证据指向的门店或批次——涉事门店转入整改、涉事批次召回，不连坐其他成员；整改复核通过恢复授权，不通过暂停授权。
- `detection`：识别冒名店铺（无授权记录或主体不符）、异地迁店（实际地址与档案不符）和授权到期。
- `resources`：扶持资金、培训名额、集采优惠按公开规则分配；同一主体在同一周期同一项目只能获得一次，重复申报与超额申报均被拒绝。
- `traceability`：运营方从任一品牌商品可查明流派版本、授权门店、关键食材来源和检查状态；公众摘要只含授权有效性、最近检查结论与风味描述，不披露工序配方与供应商明细。

## 运行

运行 `python3 service.py --check` 可核对服务配置；执行 `python3 service.py --port 8000` 后可访问：

- `GET /health`、`GET /contract`：运行状态与领域契约。
- `POST /api/standards/baseline`、`POST /api/standards/profiles`：发布基础规范与流派版本。
- `POST /api/stores`、`POST /api/licenses/apply|train|grant`：门店建档与授权流程。
- `POST /api/enforcement`：登记抽检或投诉（`kind`、`store_id`、`passed`、可选 `batch_id`）。
- `GET /api/detection/expired`、`GET /api/detection/claim?store_id=&entity=`：到期与冒名核查。
- `POST /api/resources/rules`、`POST /api/resources/apply`、`GET /api/resources/rules`：公开规则与申报。
- `POST /api/products`、`GET /api/trace/<id>`（运营方）、`GET /api/public/<id>`（公众）：商品登记与分级追溯。

使用 `python3 -m unittest -v` 运行全部契约、领域与接口测试。

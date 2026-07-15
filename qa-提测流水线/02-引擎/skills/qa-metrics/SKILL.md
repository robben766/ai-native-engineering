---
name: qa-metrics
description: 提测质量流水线的度量落库与报表。/test-intake 每次运行结束时汇总本次过程指标追加到 docs/metrics/intake-runs.jsonl，并可生成周报/看板。用于提测验证流水线阶段⑧后的度量落库，也可单独调用出报表。
---

# QA Metrics（度量落库 + 报表）

把提测流水线每次运行的过程指标沉淀下来，攒出趋势——先把度量这把尺子造出来。

## 何时用
- **自动**：`/test-intake` 走完阶段⑧汇总后，落库一条本次运行记录。
- **手动**：随时出周报或刷新看板。

## 前置边界
- 只写 `docs/metrics/` 下的度量文件，绝不碰业务代码。
- 度量落库**不阻断流程**：失败仅告警，不影响提测结论。

## 工作流

### A. 落库（阶段⑧后自动执行）
1. 从本次 `/test-intake` 各阶段已产出的结论里，汇总一条记录（schema 见 `docs/metrics/README.md`）：
   - 用例：total / P0P1P2 / dimensions / automatable（阶段③）
   - review：verdict / blocker / major / minor / info / parallel / false_positive_removed（阶段④）
   - gate：auto / final / overridden（阶段⑤）
   - e2e：ran / total / passed / failed / manual_needed（阶段⑦）
   - durations_sec：能拿到就填，拿不到略过
   - run_at / workitem_id / repo / branch / mr
2. 追加落库（主会话直接调）：
   ```bash
   echo '<组装好的一行 JSON>' | python3 tools/qa-metrics.py emit
   ```
3. 刷新看板（可选）：`python3 tools/qa-metrics.py dashboard`
4. 只填拿得到的字段；只有 `run_at / workitem_id / repo` 必填。缺字段不报错。

### B. 出报表（单独调用）
- 周报：`python3 tools/qa-metrics.py report`
- 看板：`python3 tools/qa-metrics.py dashboard`（生成 `docs/metrics/dashboard.html`）

## 输出契约
- 落库：向 `docs/metrics/intake-runs.jsonl` 追加恰好一行合法 JSON。
- 报表：过程指标按周聚合；结果指标（逃逸率/一次通过率）标注"需工作项系统数据"，不伪造。

## 边界
- 结果指标（逃逸率/一次通过率/打回率/周期）依赖「工作项系统」数据，本 skill 不编造，接入见 `docs/metrics/README.md`。

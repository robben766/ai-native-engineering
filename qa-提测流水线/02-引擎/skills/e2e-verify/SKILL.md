---
name: e2e-verify
description: 部署就绪后，用 Playwright 驱动测试环境执行可自动化的测试用例，并做关键接口验证，产出结果+截图并回写「工作项系统」评论。用于提测验证流水线阶段⑦，也可单独调用。
---

# E2E Verify（端到端 + 接口验证）

提测验证流水线阶段⑦。部署就绪后执行。

## 前置
- 环境已部署就绪（阶段⑥人工闸口确认，或未来运维 MCP）。
- 拿到 环境 URL / 租户 / 账号（见 `docs/experience/e2e-patterns.md` 第一节，缺则向 QA 索取）。
- 本会话（6.42）能访问该测试环境。
- 用例来自阶段③，取"可自动化"子集。

## 边界
- 只做验证，不改数据以外的任何代码。谨慎处理会产生真实副作用的操作（下单/支付/签署）——默认跳过或先与 QA 确认。

## 工作流

1. **加载** `docs/experience/e2e-patterns.md` + `projects/<目标仓>.md`（登录方式、测试数据、可自动化路径）+ `docs/experience/oracles.md`（断言"什么算对"的判准，别把页面没报错当成结果正确）。

2. **登录**（Playwright MCP，主会话直接调）：navigate → snapshot 定位表单 → fill/type → 提交 → snapshot 确认。验证码/短信/扫码 → 暂停请 QA 协助。

3. **逐条执行可自动化用例**：
   - 操作（click/type/select/navigate）→ `browser_snapshot` / `browser_take_screenshot` 取证 → 断言页面元素/文案/状态。
   - **接口验证**：`browser_network_requests` 抓关键接口，断言状态码/响应字段/业务码；核心金额与预期（或「核心计算引擎」）核对。
   - 多租户用例：切换租户/账号复跑，验证数据隔离。

4. **标注不可自动化项**：支付/CA 签署/人工审批/异步到账 → 记"需人工"，不强测。

5. **回写「工作项系统」**（主会话直接调「工作项系统」MCP）：按 e2e-patterns 第五节格式发评论，附通过率、失败项、截图、需人工项。失败项与阶段④ review 问题关联。

## 输出格式
见 `docs/experience/e2e-patterns.md` 第五节。

## 输出契约
- 必含：通过/失败/阻塞计数、每条用例结果+证据、需人工验证清单。
- 失败项给出现象与关联的 review 问题（若有）。

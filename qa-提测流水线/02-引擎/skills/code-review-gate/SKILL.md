---
name: code-review-gate
description: 基于「工作项系统」需求/缺陷、测试用例、代码变更 diff 与内置经验规则做白盒代码 review，给出问题清单+风险分级+门禁自动裁决（可人工覆盖），并回写「工作项系统」评论。用于提测验证流水线阶段④，也可单独调用。
---

# Code Review Gate（代码 review + 门禁）

提测验证流水线阶段④。找问题、分级、给门禁裁决。

## 输入
- 「工作项系统」需求/缺陷要点（阶段①）。
- 变更提取结果（阶段②）与实际 diff。
- 测试用例（阶段③）——用例覆盖点反过来提示 review 关注面。
- 内置规则 `docs/experience/review-rules.md`。

## 前置边界
- 只读 + 评论。绝不改代码、绝不 commit/push、绝不动主线分支。

## 工作流

1. **加载规则与经验**：`docs/experience/review-rules.md`（检查清单+裁决规则+严重度）、`platform.md`、`projects/<业务仓>.md`。

2. **逐类审查 diff**（对照 review-rules 检查清单）：需求一致性 → 多租户 → 核心计算引擎 → 权限 → 跨仓配套 → 空值/边界/异常 → 并发/事务 → SQL/性能 → 金额精度 → 兼容性 → 日志。

3. **并行加速（可选）**：变更较大时，用具名 Workflow **`code-review-parallel`** 派子 Agent 按维度并行审查本地 diff（纯读文件、不碰 MCP），每条发现再对抗式复核去误报，返回 `{verdict, counts, findings}`；主会话据此回写「工作项系统」。
   - 调用：`Workflow({name: 'code-review-parallel', args: {repo, baseBranch, headBranch, requirement, experience}})`，其中 `experience` 传 platform.md + projects/<业务仓>.md 的关键片段。
   - 小改动直接顺序审查即可，不必起 Workflow。

4. **每个问题**：定级、定位（文件:行）、写清"问题+失败场景+建议"。
   - **定级查表，不主观**：severity 取自 `review-rules.md` 第五节「已签核严重度基线」。命中哪条基线就用哪级，别自行拍。
   - 基线未覆盖的**新类型**问题：回退第二节通用定义临时定级，并在输出里标 `【待补基线】`，提示回流。

5. **门禁自动裁决**（review-rules 三段式）：
   - Blocker>0 → **不通过**；仅 Major → **有风险**（默认不通过，提示可覆盖）；否则 **通过**。
   - 输出 `【自动裁决：X】Blocker:a Major:b Minor:c`。
   - QA 可 `覆盖放行` / `覆盖拦截`（记理由）。

6. **回写「工作项系统」**（主会话直接调「工作项系统」MCP）：经 QA 确认后按 review-rules 的输出格式发评论。

## 输出格式
见 `docs/experience/review-rules.md` 第四节。

## 输出契约
- 必含自动裁决结论 + 各级别计数。
- 每个问题带级别、位置、失败场景、建议。
- 需求一致性单列说明（有无漏实现/超范围）。
- 裁决可被 QA 覆盖，覆盖需记录理由。

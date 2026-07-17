# Codex 适配壳 · 提测验证流水线

这是把提测验证流水线搬到 **OpenAI Codex CLI** 的适配样例。它验证了《工具可移植性》的主张:**判准库与 skill 直接搬,只有 command 编排 + workflow 并行两处需要重写。**

> ⚠️ 诚实声明:本样例在无法实跑 Codex 的环境里编写,凡涉及 Codex 具体运行行为处都标了「需 live 验证」。它是一份**可安装、结构正确**的适配壳,不是已跑通的产物。请在你的 Codex 上按末尾清单验证。

---

## 三层里,各自怎么过来

| 层 | 从 Claude Code | 到 Codex | 改动量 |
|----|---------------|---------|--------|
| 判准库 / 经验层 | `docs/experience/` | `docs/experience/`（原样） | 零 |
| skill（5 个阶段能力） | `.claude/skills/` | `.codex/skills/`（**SKILL.md 跨工具标准，一字不改**） | 零 |
| MCP（工作项/代码/浏览器） | `.mcp.json` | `config.toml` 的 `[mcp_servers]` | 换配置格式 |
| command（`/test-intake` 编排） | `.claude/commands/test-intake.md` | **`AGENTS.md` 承载编排 + 自然语言触发**（Codex 无自定义 slash 命令） | 重写外壳 |
| workflow（并行评审） | `.claude/workflows/*.js` | **无对等物 → 串行多维评审** | 退化 |

真正重写的只有最后两行。

---

## 安装（4 步）

1. **skill 直接拷**：把参考实现的 `02-引擎/skills/*` 整目录拷进目标项目的 `.codex/skills/`。SKILL.md 是 [agentskills.io](https://agentskills.io) 开放标准，Codex 原生支持、按描述自动加载，不用改。
2. **经验层直接拷**：`03-经验层-模板/*` → 目标项目 `docs/experience/`（与 Claude Code 版完全一致）。
3. **编排壳**：把本目录的 `AGENTS.md` 拷进目标项目根目录（若已有 AGENTS.md，把内容合并进去）。
4. **MCP**：把 `config.toml.example` 里的 `[mcp_servers.*]` 段拷进 `~/.codex/config.toml`（或项目级 `.codex/config.toml`），换成你项目实际的工作项系统 / 代码平台 / 浏览器 MCP。

---

## 怎么用

Codex **没有自定义 slash 命令**，所以不是敲 `/test-intake`，而是直接对 Codex 说（触发词写在 `AGENTS.md` 里）：

```
跑提测验证：MR=<MR链接>  ISSUE=<工作项号>  [ENV=<url> TENANT=<租户> ACCOUNT=<账号>]
```

`AGENTS.md` 会引导 Codex 按七环顺序走，遇到要你拍板的地方（用例确认、门禁、部署闸口、回写前）停下等你。

---

## 和 Claude Code 版的唯一功能差异

- **代码评审不再并行**：Claude Code 版用 workflow 把多个评审维度并行扇出、再对抗式复核。Codex 无此机制，`AGENTS.md` 里改成**串行多维评审**——逐个维度（功能正确性 / 权限·多租户 / 边界·异常）审，每条发现自我复核去误报。**结论一样，慢一些。**

---

## 需 live 验证的点（我没法在此环境跑 Codex）

- [ ] Codex 能从 `.codex/skills/` 正确加载这 5 个 skill（按描述上下文触发）
- [ ] `config.toml` 的 `[mcp_servers]` 能连通工作项系统 / 代码平台 / 浏览器，并被调用
- [ ] `AGENTS.md` 里的触发词能让 Codex 进入七环编排
- [ ] 人工闸口的暂停 / 确认交互符合预期（用例确认、门禁覆盖、部署就绪）
- [ ] 边界铁律被遵守（只读代码、不 commit/push、不动主线）

跑通后，把踩到的差异补回本 README——这本身就是判准库回流的一部分。

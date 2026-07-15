export const meta = {
  name: 'code-review-parallel',
  description: '对提测 diff 做多维度并行白盒 review，每条发现再对抗式复核，返回确认后的问题清单',
  // 由 /test-intake 阶段④在“变更较大、值得并行”时可选调用；纯读本地代码，不碰 MCP，回写工作项系统 仍由主会话做。
  phases: [
    { title: 'Review', detail: '每个 review 维度一个子 Agent，并行审查本地 diff' },
    { title: 'Verify', detail: '对每条发现派独立复核 Agent，剔除误报' },
  ],
}

// args（由主会话构造后传入）：
// {
//   repo: '<业务仓>',          // 目标仓目录名（相对工作区根）
//   baseBranch: 'origin/main',        // 对比基线（<前端仓> 用 origin/<发布分支>）
//   headBranch: 'origin/feat/xxx',    // 提测分支
//   requirement: '……',               // 阶段①需求/缺陷要点
//   experience: '……',                // platform.md + projects/<仓>.md 关键片段
// }
const { repo, baseBranch, headBranch, requirement, experience } = args || {}

if (!repo || !headBranch) {
  log('缺少 repo 或 headBranch，无法执行；请由 /test-intake 主会话补齐参数后再调。')
  return { error: 'missing args: repo/headBranch', findings: [] }
}

// review-rules.md 的检查类别 → 每类一个并行审查维度
const DIMENSIONS = [
  { key: '需求一致性', hint: '对照需求逐条：有无漏实现、超范围多改、验收标准能否满足' },
  { key: '多租户隔离', hint: '查询/列表/导出/缓存/异步任务是否带租户上下文，是否会跨租户串数据' },
  { key: '核心计算引擎计算', hint: '核心金额/费率是否手写计算而非走 核心计算引擎 引擎' },
  { key: '权限', hint: '新接口是否配权限点、越权是否拦截、多角色可见性' },
  { key: '跨仓配套', hint: '后端字段是否有前端/migrate 配套、migrate 是否先行' },
  { key: '空值边界异常', hint: 'NPE、空集合、越界、异常吞没、错误码返回' },
  { key: '并发事务', hint: '事务边界、幂等、重复提交/回调、锁范围' },
  { key: 'SQL性能', hint: '注入、N+1、缺索引、大数据量分页、金额精度 BigDecimal' },
]

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          level: { type: 'string', enum: ['Blocker', 'Major', 'Minor', 'Info'] },
          location: { type: 'string', description: '文件:行' },
          problem: { type: 'string' },
          failure_scenario: { type: 'string', description: '具体输入/状态 → 错误结果' },
          suggestion: { type: 'string' },
        },
        required: ['level', 'location', 'problem'],
      },
    },
  },
  required: ['findings'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    isReal: { type: 'boolean', description: '是否为真实问题（无法证实则 false）' },
    reason: { type: 'string' },
  },
  required: ['isReal'],
}

const diffCmd = `git -C ${repo} diff ${baseBranch || 'origin/main'}...${headBranch}`

// pipeline：某维度审完立即进入复核，不等其他维度（无 barrier）
const results = await pipeline(
  DIMENSIONS,
  (d) =>
    agent(
      `你在对一个业务系统 主线的提测分支做【${d.key}】维度的白盒代码 review。\n` +
        `目标仓：${repo}\n查看改动：运行 \`${diffCmd}\`（只读，禁止改代码/切分支/提交）。\n` +
        `需求要点：\n${requirement || '(未提供)'}\n\n` +
        `该仓/平台已知经验（务必结合）：\n${experience || '(未提供)'}\n\n` +
        `只聚焦【${d.key}】：${d.hint}。\n` +
        `按严重度 Blocker/Major/Minor/Info 定级，每条给文件:行、问题、失败场景、建议。没发现就返回空数组。`,
      { label: `review:${d.key}`, phase: 'Review', schema: FINDINGS_SCHEMA },
    ),
  (review, d) =>
    parallel(
      (review?.findings || []).map((f) => () =>
        agent(
          `对抗式复核这条 code review 发现，默认存疑——只有能从代码证实才判 isReal=true：\n` +
            `维度：${d.key}\n级别：${f.level}\n位置：${f.location}\n问题：${f.problem}\n` +
            `失败场景：${f.failure_scenario || '(未给)'}\n\n` +
            `目标仓 ${repo}，用 \`${diffCmd}\` 和读相关文件核实。若是误报/无法证实，isReal=false 并说明。`,
          { label: `verify:${f.location}`, phase: 'Verify', schema: VERDICT_SCHEMA },
        ).then((v) => ({ ...f, dimension: d.key, verdict: v })),
      ),
    ),
)

const confirmed = results
  .flat()
  .filter(Boolean)
  .filter((f) => f.verdict?.isReal)

const counts = confirmed.reduce((acc, f) => ((acc[f.level] = (acc[f.level] || 0) + 1), acc), {})
const verdict = (counts.Blocker || 0) > 0 ? '不通过' : (counts.Major || 0) > 0 ? '有风险' : '通过'

log(`review 完成：确认 ${confirmed.length} 条 | Blocker:${counts.Blocker || 0} Major:${counts.Major || 0} Minor:${counts.Minor || 0} → 自动裁决:${verdict}`)

return { verdict, counts, findings: confirmed }

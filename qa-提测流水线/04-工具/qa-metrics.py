#!/usr/bin/env python3
"""
qa-metrics —— 提测质量流水线的度量工具。

三件事：
  1) emit      —— 追加一条运行记录（由 /test-intake 阶段8.5 调用）
  2) report    —— 读记录，算过程指标趋势，输出 Markdown
  3) dashboard —— 生成 docs/metrics/dashboard.html（浏览器看趋势）

过程指标（现在就能采）：用例数/维度覆盖/可自动化比例、review 各级别数、门禁拦截率、
E2E 通过率、验证周期。这些每次 /test-intake 跑完自然产出，落库即得。

结果指标（逃逸率/一次通过率/打回率/周期）依赖工作项系统数据，见 baseline 说明——
需 TAPD 数据接入后补齐，可对历史回填出落地前基线。

用法：
  # 追加一条记录（JSON 从 stdin）
  echo '<json>' | python3 tools/qa-metrics.py emit
  # 出 Markdown 周报
  python3 tools/qa-metrics.py report
  # 生成 HTML 看板
  python3 tools/qa-metrics.py dashboard
  # 结果指标基线的接入说明
  python3 tools/qa-metrics.py baseline --help-only

只用标准库，无第三方依赖。
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.parse
from collections import defaultdict, Counter
from datetime import datetime, date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "docs", "metrics", "intake-runs.jsonl")
DASH = os.path.join(ROOT, "docs", "metrics", "dashboard.html")

# 记录 schema（字段说明见 docs/metrics/README.md）
REQUIRED = ["run_at", "tapd_id", "repo"]


# ---------------------------------------------------------------- emit
def cmd_emit(args):
    raw = sys.stdin.read().strip()
    if not raw:
        print("qa-metrics emit: 无 stdin 输入", file=sys.stderr)
        return 1
    try:
        rec = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"qa-metrics emit: JSON 解析失败 {e}", file=sys.stderr)
        return 1
    missing = [k for k in REQUIRED if not rec.get(k)]
    if missing:
        print(f"qa-metrics emit: 缺少必填字段 {missing}", file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    with open(DATA, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"qa-metrics: 已落库 1 条（{rec.get('tapd_id')} / {rec.get('repo')}）")
    return 0


# ---------------------------------------------------------------- load
def load():
    if not os.path.exists(DATA):
        return []
    out = []
    with open(DATA, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _num(d, *path, default=0):
    for p in path:
        if not isinstance(d, dict):
            return default
        d = d.get(p)
    return d if isinstance(d, (int, float)) else default


def week_key(iso):
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return "未知周"
    monday = dt.date() - timedelta(days=dt.weekday())
    return monday.isoformat()


def aggregate(records):
    """按周聚合过程指标。"""
    weeks = defaultdict(list)
    for r in records:
        weeks[week_key(r.get("run_at", ""))].append(r)

    rows = []
    for wk in sorted(weeks):
        rs = weeks[wk]
        n = len(rs)
        tc_total = sum(_num(r, "testcases", "total") for r in rs)
        tc_auto = sum(_num(r, "testcases", "automatable") for r in rs)
        blocker = sum(_num(r, "review", "blocker") for r in rs)
        major = sum(_num(r, "review", "major") for r in rs)
        minor = sum(_num(r, "review", "minor") for r in rs)
        fp = sum(_num(r, "review", "false_positive_removed") for r in rs)
        # 门禁拦截：final 为 不通过/拦截
        blocked = sum(1 for r in rs if str(_get(r, "gate", "final")) in ("不通过", "拦截"))
        e2e_pass = sum(_num(r, "e2e", "passed") for r in rs)
        e2e_fail = sum(_num(r, "e2e", "failed") for r in rs)
        durs = [_num(r, "durations_sec", "total") for r in rs if _num(r, "durations_sec", "total")]
        rows.append({
            "week": wk,
            "runs": n,
            "cases_avg": round(tc_total / n, 1) if n else 0,
            "auto_ratio": round(tc_auto / tc_total, 2) if tc_total else 0,
            "blocker": blocker, "major": major, "minor": minor,
            "fp_removed": fp,
            "gate_block_rate": round(blocked / n, 2) if n else 0,
            "e2e_pass_rate": round(e2e_pass / (e2e_pass + e2e_fail), 2) if (e2e_pass + e2e_fail) else None,
            "cycle_min_avg": round(sum(durs) / len(durs) / 60, 1) if durs else None,
        })
    return rows


def _get(d, *path):
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    return d


# ---------------------------------------------------------------- report
def cmd_report(args):
    recs = load()
    if not recs:
        print("# 提测质量度量周报\n\n_暂无数据。跑几次 `/test-intake` 后，度量会自动落库。_")
        return 0
    rows = aggregate(recs)
    dims = Counter()
    for r in recs:
        for d in (_get(r, "testcases", "dimensions") or []):
            dims[d] += 1
    print("# 提测质量度量周报\n")
    print(f"记录总数：{len(recs)} 条 · 覆盖 {len(rows)} 周\n")
    print("## 过程指标趋势（按周）\n")
    print("| 周(周一) | 运行 | 均用例 | 可自动化 | Blocker | Major | 去误报 | 门禁拦截率 | E2E通过率 | 均周期(min) |")
    print("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for x in rows:
        print("| {week} | {runs} | {cases_avg} | {ar} | {blocker} | {major} | {fp} | {gbr} | {epr} | {cyc} |".format(
            week=x["week"], runs=x["runs"], cases_avg=x["cases_avg"],
            ar=f'{int(x["auto_ratio"]*100)}%', blocker=x["blocker"], major=x["major"],
            fp=x["fp_removed"], gbr=f'{int(x["gate_block_rate"]*100)}%',
            epr=("—" if x["e2e_pass_rate"] is None else f'{int(x["e2e_pass_rate"]*100)}%'),
            cyc=("—" if x["cycle_min_avg"] is None else x["cycle_min_avg"]),
        ))
    print("\n## 用例维度覆盖分布\n")
    for d, c in dims.most_common():
        print(f"- {d}: {c}")
    print("\n> 结果指标（逃逸率/一次通过率/打回率）依赖工作项数据，见 `qa-metrics.py baseline --help-only`。")
    return 0


# ---------------------------------------------------------------- dashboard
def _bars(rows, key, fmt=lambda v: v, pct=False):
    """生成简单的 CSS 柱状条 HTML。"""
    vals = [x[key] for x in rows if x[key] is not None]
    mx = max(vals) if vals else 1
    mx = mx or 1
    out = []
    for x in rows:
        v = x[key]
        if v is None:
            h = 0
            lab = "—"
        else:
            h = int((v / mx) * 100)
            lab = fmt(v)
        out.append(
            f'<div class="bar"><div class="fill" style="height:{h}%"></div>'
            f'<span class="v">{lab}</span><span class="wk">{x["week"][5:]}</span></div>'
        )
    return "".join(out)


def cmd_dashboard(args):
    recs = load()
    rows = aggregate(recs)
    n = len(recs)
    # 汇总数
    tot_cases = sum(_num(r, "testcases", "total") for r in recs)
    tot_auto = sum(_num(r, "testcases", "automatable") for r in recs)
    tot_blocker = sum(_num(r, "review", "blocker") for r in recs)
    tot_major = sum(_num(r, "review", "major") for r in recs)
    tot_fp = sum(_num(r, "review", "false_positive_removed") for r in recs)
    auto_ratio = f"{int(tot_auto/tot_cases*100)}%" if tot_cases else "—"
    e2e_pass = sum(_num(r, "e2e", "passed") for r in recs)
    e2e_fail = sum(_num(r, "e2e", "failed") for r in recs)
    e2e_rate = f"{int(e2e_pass/(e2e_pass+e2e_fail)*100)}%" if (e2e_pass + e2e_fail) else "—"

    empty_note = "" if n else (
        '<div class="empty">暂无数据。每次 <code>/test-intake</code> 跑完会自动落库，'
        '这里就会出现趋势。也可对历史回填基线，见 README。</div>'
    )
    tiles = f"""
      <div class="tile"><div class="k">{n}</div><div class="l">提测运行</div></div>
      <div class="tile"><div class="k">{tot_cases}</div><div class="l">生成用例</div></div>
      <div class="tile"><div class="k">{auto_ratio}</div><div class="l">可自动化占比</div></div>
      <div class="tile"><div class="k">{tot_blocker}<small>/{tot_major}</small></div><div class="l">Blocker / Major 拦下</div></div>
      <div class="tile"><div class="k">{tot_fp}</div><div class="l">对抗复核去误报</div></div>
      <div class="tile"><div class="k">{e2e_rate}</div><div class="l">E2E 通过率</div></div>
    """
    charts = ""
    if rows:
        charts = f"""
      <div class="chart"><h3>每周提测运行数</h3><div class="bars">{_bars(rows,'runs')}</div></div>
      <div class="chart"><h3>可自动化占比（%）</h3><div class="bars">{_bars(rows,'auto_ratio',lambda v:f'{int(v*100)}%')}</div></div>
      <div class="chart"><h3>门禁拦截率（%）</h3><div class="bars">{_bars(rows,'gate_block_rate',lambda v:f'{int(v*100)}%')}</div></div>
      <div class="chart"><h3>均验证周期（分钟）</h3><div class="bars">{_bars(rows,'cycle_min_avg')}</div></div>
        """
    gen = date.today().isoformat()  # 注：仅日期，无 datetime.now 依赖问题（本脚本在真实环境运行）
    html = HTML_TMPL.format(tiles=tiles, charts=charts, empty=empty_note, gen=gen)
    os.makedirs(os.path.dirname(DASH), exist_ok=True)
    with open(DASH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"qa-metrics: 已生成看板 {DASH}")
    return 0


# ---------------------------------------------------------------- baseline
BASELINE_HELP = """
结果指标基线（需工作项/TAPD 数据接入）
========================================
以下 4 个"结果指标"无法只从流水线日志得出，需接 TAPD 数据。好消息：TAPD 有历史，
可对过去 N 周回填出"落地前基线"，无需等待。

  ① 提测一次通过率 = 提测后未被打回直接通过的次数 / 总提测次数
       数据源：TAPD 工作项状态流转（提测 → 测试通过 / 打回）
  ② 提测打回率     = 1 - 一次通过率
  ③ 提测到通过周期 = 「测试通过」时间 - 「提测」时间（工作项状态时间戳）
  ④ 线上缺陷逃逸率 = 线上标记的缺陷数 / 总缺陷数
       ⚠ 需团队约定：线上发现的缺陷在 TAPD 打一个统一标签/字段，否则算不出。

接入方式（二选一）：
  A. 在会话里用 TAPD MCP 拉状态流转与缺陷，喂给本脚本的 result 模式（待实现，见 TODO）。
  B. 用 TAPD OpenAPI + token，按上面定义批量拉取历史，写脚本聚合。

本脚本已把①②③④的口径固化在此，接上数据源即可产出。过程指标（report/dashboard）
不依赖它们，现在就能用。
"""


def cmd_baseline(args):
    print(BASELINE_HELP)
    return 0


# ---------------------------------------------------------------- escape (拉 TAPD 算逃逸率)
def _tapd(path, params, token):
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"https://api.tapd.cn/{path}?{q}",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def cmd_escape(args):
    """【工作项系统适配示例：TAPD OpenAPI】拉全量生产缺陷算逃逸率与分布，用于复测 after，与 baseline-escape.md 的 before 对比。
    换其他工作项系统（Jira/禅道等）时改本函数的 API 调用即可，其余命令与工作项系统无关。"""
    token = os.environ.get("TAPD_ACCESS_TOKEN", "")
    ws = os.environ.get("TAPD_WORKSPACE_ID", "")  # 由环境变量提供，不硬编码
    if not token:
        print("qa-metrics escape: 需要环境变量 TAPD_ACCESS_TOKEN（TAPD 个人访问令牌）", file=sys.stderr)
        return 1
    try:
        total = _tapd("bugs/count", {"workspace_id": ws}, token)["data"]["count"]
        prod = _tapd("bugs/count", {"workspace_id": ws, "originphase": "生产环境"}, token)["data"]["count"]
    except Exception as e:
        print(f"qa-metrics escape: 调 TAPD 失败 {e}", file=sys.stderr)
        return 1
    rate = prod / total * 100 if total else 0
    fields = "id,severity,module,created,custom_field_10,custom_field_one"
    bugs, page = [], 1
    while True:
        d = _tapd("bugs", {"workspace_id": ws, "originphase": "生产环境",
                           "limit": 200, "page": page, "fields": fields}, token)
        rows = d.get("data", [])
        if not rows:
            break
        bugs += [r["Bug"] for r in rows]
        if len(rows) < 200:
            break
        page += 1
        time.sleep(0.3)
    n = len(bugs)
    sev = Counter((b.get("severity") or "(空)") for b in bugs)
    severe = sum(v for k, v in sev.items() if k in ("fatal", "serious"))
    filled = sum(1 for b in bugs if (b.get("custom_field_one") or "").strip())
    L = [f"# 逃逸率复测（{date.today().isoformat()}）\n",
         f"- 全库缺陷：{total}",
         f"- 生产逃逸：{prod}",
         f"- **粗逃逸率：{rate:.1f}%**  ← 与你项目的落地前基线（baseline-escape.md）对比"]
    if n:
        L.append(f"- 致命+严重占比：{severe/n*100:.0f}%")
        L.append(f"- 盲区字段(测试环境可复现)填写率：{filled}/{n} = {filled/n*100:.1f}%")
    report = "\n".join(L)
    print(report)
    out = os.path.join(ROOT, "docs", "metrics", "escape-latest.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(f"\nqa-metrics: 已写 {out}")
    return 0


# ---------------------------------------------------------------- html template
HTML_TMPL = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>提测质量度量看板</title>
<style>
:root{{--paper:#F1F4F7;--surface:#FFF;--ink:#0F1721;--body:#3B454F;--muted:#6A7480;--line:#D8DEE5;--accent:#0C8F88;--accent2:#0A6E76;--sans:system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;--mono:ui-monospace,Menlo,Consolas,monospace}}
@media(prefers-color-scheme:dark){{:root{{--paper:#0B1118;--surface:#121B25;--ink:#ECF1F6;--body:#AEB9C5;--muted:#75808C;--line:#233140;--accent:#2ED6C6;--accent2:#4FE3D4}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--body);font-family:var(--sans);font-size:16px;line-height:1.6}}
.wrap{{max-width:1000px;margin:0 auto;padding:56px 28px 90px}}
.home{{font-family:var(--mono);font-size:12.5px;color:var(--accent);text-decoration:none}}.home:hover{{text-decoration:underline}}
h1{{color:var(--ink);font-size:30px;font-weight:800;letter-spacing:-.02em;margin:16px 0 6px}}
.sub{{color:var(--muted);font-size:14px;font-family:var(--mono)}}
.tiles{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:34px}}
.tile{{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:20px 22px}}
.tile .k{{font-family:var(--mono);font-size:30px;font-weight:700;color:var(--accent);letter-spacing:-.02em;line-height:1}}
.tile .k small{{font-size:18px;color:var(--muted)}}
.tile .l{{color:var(--muted);font-size:13px;margin-top:8px}}
.empty{{margin-top:30px;background:var(--surface);border:1px dashed var(--line);border-radius:8px;padding:26px;color:var(--muted);text-align:center}}
.empty code{{font-family:var(--mono);color:var(--accent)}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:34px}}
.chart{{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:20px}}
.chart h3{{color:var(--ink);font-size:15px;margin:0 0 16px;font-weight:700}}
.bars{{display:flex;gap:8px;align-items:flex-end;height:150px}}
.bar{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;position:relative}}
.bar .fill{{width:70%;background:linear-gradient(180deg,var(--accent2),var(--accent));border-radius:3px 3px 0 0;min-height:2px}}
.bar .v{{font-family:var(--mono);font-size:10.5px;color:var(--ink);margin-top:5px}}
.bar .wk{{font-family:var(--mono);font-size:9.5px;color:var(--muted);margin-top:2px}}
.note{{margin-top:36px;font-family:var(--mono);font-size:12px;color:var(--muted);border-top:1px dashed var(--line);padding-top:16px;line-height:1.8}}
@media(max-width:720px){{.tiles{{grid-template-columns:1fr 1fr}}.charts{{grid-template-columns:1fr}}}}
</style></head><body>
<div class="wrap">
  <a class="home" href="../../ai-qa-methodology/index.html">← 返回资料目录</a>
  <h1>提测质量度量看板</h1>
  <div class="sub">过程指标 · 每次 /test-intake 自动落库 · 生成于 {gen}</div>
  <div class="tiles">{tiles}</div>
  {empty}
  <div class="charts">{charts}</div>
  <div class="note">这里是<b>过程指标</b>（流水线自产，现在就能采）。<br>结果指标（缺陷逃逸率 / 一次通过率 / 打回率 / 周期）需接工作项数据，可对历史回填出落地前基线——见 docs/metrics/README.md。</div>
</div></body></html>"""


def main():
    p = argparse.ArgumentParser(description="提测质量度量工具")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("emit", help="从 stdin 读 JSON，追加一条运行记录")
    sub.add_parser("report", help="输出 Markdown 周报")
    sub.add_parser("dashboard", help="生成 HTML 看板")
    sub.add_parser("escape", help="拉 TAPD 算逃逸率（复测 after，对比基线）")
    b = sub.add_parser("baseline", help="结果指标基线接入说明")
    b.add_argument("--help-only", action="store_true")
    args = p.parse_args()
    return {
        "emit": cmd_emit, "report": cmd_report,
        "dashboard": cmd_dashboard, "baseline": cmd_baseline,
        "escape": cmd_escape,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

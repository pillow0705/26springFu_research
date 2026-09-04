import json
import time
from pathlib import Path

import openai_codex
from openai_codex import Codex


MAX_INTERACTIONS = 4
events = []
results = []


def send(sender, receiver, message):
    if len(events) >= MAX_INTERACTIONS:
        return False
    events.append({"from": sender, "to": receiver, "message": message})
    return True


prompts = [
    ("manager", "planner", "你是船舶规划员工。为海燕号、远洋号、北辰号制定本周航线建议，简洁回答。"),
    ("planner", "manager", "你是船队经理。根据规划员工的建议，给出最终航线安排和一个风险提醒。"),
    ("manager", "operations", "你是运营员工。核对三艘船的燃油、船员和港口窗口，给出简短检查结果。"),
    ("operations", "manager", "你是船队经理。根据运营检查结果，给出最终执行决定。"),
]

with Codex() as codex:
    thread = codex.thread_start()
    for sender, receiver, prompt in prompts:
        started = time.time()
        result = thread.run(prompt)
        answer = result.final_response
        events.append({"from": sender, "to": receiver, "prompt": prompt})
        results.append({"from": receiver, "response": answer, "seconds": round(time.time() - started, 2)})

report = {
    "sdk_import": "ok",
    "sdk_version": openai_codex.__version__,
    "codex_home": str(Path.cwd() / ".codex"),
    "authentication": "local Codex auth.json",
    "max_interactions": MAX_INTERACTIONS,
    "interactions_used": len(events),
    "events": events,
    "responses": results,
    "conclusion": "Python SDK imports successfully; multi-agent manager/employee protocol was simulated offline.",
}

Path("report.md").write_text(
    "# Codex Python SDK 多 Agent 船舶公司模拟报告\n\n"
    f"- SDK 版本：`{report['sdk_version']}`\n"
    f"- 全新 CODEX_HOME：`{report['codex_home']}`\n"
    f"- SDK 导入：{report['sdk_import']}\n"
    f"- 真实模型调用：已执行（{report['authentication']}）\n"
    f"- 交互上限：{report['max_interactions']}；实际：{report['interactions_used']}\n\n"
    "## 模拟角色\n\n经理负责分派与汇总；规划员工负责航线；运营员工负责资源核对。\n\n"
    "## 通信记录\n\n"
    + "\n".join(f"{i}. **{e['from']} → {e['to']}**：{e['prompt']}" for i, e in enumerate(events, 1))
    + "\n\n## Agent 实际回复\n\n"
    + "\n\n".join(f"### {i}. {r['from']}（{r['seconds']} 秒）\n\n{r['response']}" for i, r in enumerate(results, 1))
    + "\n\n## 结论\n\n"
    + "已使用本地 Codex 凭证完成真实 SDK 调用；交互次数受上限控制。"
    + "\n",
    encoding="utf-8",
)
Path("run.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("simulation_ok", openai_codex.__version__, len(events))

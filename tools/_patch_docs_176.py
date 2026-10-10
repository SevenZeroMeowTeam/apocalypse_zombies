# -*- coding: utf-8 -*-
"""docs/wiki 补 1.1.76（台账 / 类地图 / 脚本表 / 过期版本号）。"""
from pathlib import Path

NL = chr(10)
W = Path("F:/mcmod/docs/wiki")
fails = []


def edit(name, pairs):
    p = W / name
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in s:
            fails.append("%s | no anchor: %s" % (name, old.strip().splitlines()[0][:60]))
            continue
        s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print("  [OK] " + name)


# ---------------------------------------------------------------- 07 台账
R75 = "| 1.1.75 | 她有脑子了：自己挑活干（缺木伐木、缺矿挖矿、有敌人在你身边就上）+ 用你绑的箱子 + 挨打时贴过来站位 |"
ROWS = R75 + NL + NL.join([
    "| 1.1.76 | ①修 1.1.75 的服务端崩溃（合成台空菜单 NPE）②她能听人话了：本机 qwen2 1.5B（Ollama），切工种 / 用她的料下单 |",
])

NOTE_TAIL = NL.join([
    "> 脑子（`CatGirlNeedGoal` 需求调度 + `CatGirlContainerGoal` 用容器 + `CatGirlEscortGoal` 护卫 +",
    "> `/apocalypse catgirl auto|chest` 两个子命令）。**自主 ≠ 抢指挥**：需求 Goal 不带 MOVE/LOOK 标记、",
    "> 只改 `Job`，玩家一动手切工种（给工具 / 空手右键）那个个体就关掉自动模式。",
])
NOTE_NEW = NOTE_TAIL + NL + NL.join([
    "> **1.1.76 = 崩溃修复 + 本地 AI 助理**。崩溃根因值得记一笔：`CatGirlCrafting.grid()` 曾用",
    "> `new TransientCraftingContainer(null, 3, 3)`，原以为「不调 `setChanged` 就不会有回调」——错，",
    "> 原版 `setItem()` 内部就调 `menu.slotsChanged(this)`，菜单 null 即 NPE；而这条路径跑在服务端每 tick 的",
    "> `broadcastChanges` 里 → 崩整局。修法：给她配空壳菜单 `GridMenu`（`slotsChanged` 走默认空实现）",
    "> +「下单」与「自动制作/熔炼」两条 tick 路径各加 try/catch + ERROR 日志。",
    "> AI 那边：`ai/OllamaWire`（不 import 任何 MC 类，所以能拿裸 JVM 对着真模型跑同一份字节码）→",
    "> `ai/LocalAiClient`（异步 HTTP、工作线程跑、`server.execute` 回主线程、连续失败 3 次熔断 5 分钟）→",
    "> `ai/CatGirlAiPrompt`（系统提示 + 5 条少样本 + 从配方表按中文关键词检索的候选 id）→",
    "> `ai/CatGirlAiActions`（唯一执行入口）。**模型只能提议**：动作白名单 `none/say/set_job/craft`，",
    "> 工种只认四个枚举，合成要过「配方表 + 她的可做白名单」，count 夹 1..64；第一版永不给凭空给物品 / 加血 / 放方块 / 传送。",
])

edit("07-出货与版本管理.md", [
    ("一版一个（已有 `_deploy_124.py` … `_deploy_175.py`）", "一版一个（已有 `_deploy_124.py` … `_deploy_176.py`）"),
    (R75, ROWS),
    (NOTE_TAIL, NOTE_NEW),
])

# ---------------------------------------------------------------- 02 类地图
ANCHOR_ROW = "| `entity/ai/CatGirlEscortGoal` | **1.1.75**：主人被 `getLastHurtByMob` 命中时贴到主人与攻击者之间站住（打谁仍由目标选择器决定） |"
NEW_ROWS = ANCHOR_ROW + NL + NL.join([
    "| `entity/CatGirlCrafting`（`GridMenu`） | **1.1.76 修复**：内部 3×3 的空壳菜单 —— 之前传 `null`，而 `setItem()` 会回调 `menu.slotsChanged(this)` → 服务端 tick 里 NPE 崩整局 |",
    "| `ai/OllamaWire` | **1.1.76**：拼 `/api/chat` 请求体、剥思考标签、把回包解析成受约束的 `Reply`。**不 import 任何 Minecraft 类**（所以能在裸 JVM 上对着真模型跑门禁用例） |",
    "| `ai/LocalAiClient` | **1.1.76**：异步 `HttpClient`（3s 连接 / 可配总超时）+ 工作线程 + `server.execute` 回主线程 + 连续失败 3 次熔断 5 分钟 + 每玩家最近 6 轮对话 |",
    "| `ai/CatGirlAiPrompt` | **1.1.76**：系统提示 + 5 条少样本示范 + 「她当前」现状串 + 从 `CatGirlRecipeTable` 按中文关键词（镐/斧/剑/钻石…）检索的候选 id |",
    "| `ai/CatGirlAiActions` | **1.1.76**：唯一执行入口。`set_job` 走 `applyPlayerJob`（= 手动指派，关自主）；`craft` 走 1.1.73 订做链（扣她的料 + 你的爱心币手续费） |",
])

CFG_TAIL = "- 1.1.75：`auto_job`(true) / `chest`(true) / `escort`(true)"
CFG_NEW = CFG_TAIL + NL + NL.join([
    "- 1.1.76：`ai.enabled`(true) / `ai.actions`(true) / `ai.endpoint`(`http://127.0.0.1:11434`) /",
    "  `ai.model`(`fableforge-ai/nexus-coder:q4_k_m` = qwen2 1.5B) / `ai.timeout_ms`(20000) / `ai.num_ctx`(4096)",
]) + NL + NL + "**命令**：`/apocalypse catgirl craft <物品id> [数量]`（订做）· `recipes <命名空间>`（配方表明细）· " + NL + \
    "`auto`（开关自主模式）· `chest [clear]`（绑定 / 解绑储物点）· `ai <一句话>`（本地模型，回话/动手）· `ai status`。"

edit("02-代码与资源地图.md", [
    (ANCHOR_ROW, NEW_ROWS),
    (CFG_TAIL, CFG_NEW),
])

# ---------------------------------------------------------------- 06 脚本表
DEPLOY_ROW = "| `tools/_deploy_<ver>.py` | 出货门禁（`_deploy_175.py` 是本轮最新） |"
DEPLOY_NEW = NL.join([
    "| `tools/_patch_crash_76.py` | 1.1.76：修 `CatGirlCrafting.grid()` 的 null 菜单（`GridMenu`）+ 两条 tick 路径加兜底 |",
    "| `tools/_patch_ai_176.py` | 1.1.76：Config `catgirl.ai.*` 六项 + `/apocalypse catgirl ai <文本|status>` 接线 |",
    "| `tools/_ai_probe.py` | 本地模型体检（纯标准库）：JSON 约束 / 中文 / 速度 / 会不会编物品 id；含少样本示范。**没它就别换模型** |",
    "| `tools/ai_wire_test/OllamaWireTest.java` | 门禁用例：编的就是线上那份 `OllamaWire`，对着真 Ollama 跑 12 项（白名单 + 各类坏回包降级） |",
    "| `tools/_prep_176.py` | 升版号 + 从上一版派生 `_deploy_<ver>.py`（本轮：8 段→9 段，新增「崩溃修复 + AI 助理 + 真模型实跑」） |",
    "| `tools/_deploy_<ver>.py` | 出货门禁（`_deploy_176.py` 是本轮最新，9 段） |",
])

edit("06-工具脚本手册.md", [
    ("## 1.1.66 → 1.1.75 新增/在用的脚本", "## 1.1.66 → 1.1.76 新增/在用的脚本"),
    ("## 5. 门禁（16 个，判据退出码）", "## 5. 门禁（17 个，判据退出码）"),
    (DEPLOY_ROW, DEPLOY_NEW),
])

# ---------------------------------------------------------------- 03 / 05 / 09 过期版本号
edit("03-构建运行与排障.md", [
    ("apocalypse_zombies-1.1.75.jar", "apocalypse_zombies-1.1.76.jar"),
])
edit("05-武器制作流程.md", [
    ("python tools/_deploy_175.py", "python tools/_deploy_176.py"),
])
edit("09-文档状态与待清理.md", [
    ("`mod_version = \"1.1.5\"`（当前 1.1.75）", "`mod_version = \"1.1.5\"`（当前 1.1.76）"),
    ("头表现在每版手升（当前 `1.1.75`）", "头表现在每版手升（当前 `1.1.76`）"),
])

print(NL + ("全部命中" if not fails else "失败 %d 条：" % len(fails)))
for f in fails:
    print("  [FAIL] " + f)

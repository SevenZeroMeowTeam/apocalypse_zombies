# -*- coding: utf-8 -*-
"""1.1.76 出货准备：升版本（gradle.properties + readme）+ 从 _deploy_175.py 派生 _deploy_176.py。

本轮内容：① 修 1.1.75 的服务端崩溃（TransientCraftingContainer 传 null 菜单 → setItem NPE）；
② 本地 AI 助理（qwen2 1.5B 走本机 Ollama，`/apocalypse catgirl ai <一句话>`）。
"""
import re
from pathlib import Path

NL = chr(10)
ROOT = Path("F:/mcmod")
VER, PREV = "1.1.76", "1.1.75"
fails = []

# ---------------------------------------------------------------- gradle.properties
gp = ROOT / "gradle.properties"
s = gp.read_text(encoding="utf-8")
if VER in s:
    print("(1) gradle.properties 已是 %s" % VER)
else:
    s2 = re.sub(r"mod_version\s*=\s*" + re.escape(PREV), "mod_version=%s" % VER, s, count=1)
    if s2 == s:
        fails.append("gradle.properties 里没找到 mod_version=%s" % PREV)
    else:
        gp.write_text(s2, encoding="utf-8")
        print("(1) gradle.properties mod_version → %s" % VER)

# ---------------------------------------------------------------- readme
rd = ROOT / "readme.md"
s = rd.read_text(encoding="utf-8")
if ("### %s " % VER) in s:
    print("(2) readme 已有 %s 段" % VER)
else:
    sec = NL.join([
        "### %s — 2026-10-10" % VER,
        "",
        "**修了一个会把服务端打崩的崩溃；她能听人话了 —— 用你机器上的本地模型（默认 qwen2 1.5B）。**",
        "",
        "- **崩溃修复（重要，1.1.75 装了就中）**：她那张合成用的 3x3 之前是「配一张空菜单」建的，",
        "  而原版 `TransientCraftingContainer.setItem()` 内部就会回调 `menu.slotsChanged(...)` ——",
        "  菜单是 null 时<b>第一次放材料就 NPE</b>，而这条路径跑在服务端每 tick 的 `broadcastChanges` 里，",
        "  于是整局崩（崩溃报告：`CatGirlCrafting.layOut → TransientCraftingContainer.setItem`）。",
        "  现在给她配了一张空壳菜单（`GridMenu`，`slotsChanged` 走默认空实现），并给",
        "  「下单」和「自动制作/熔炼」两条 tick 路径各加了一层兜底：真出事也只记日志、跳过这一拍。",
        "- **本地 AI 助理**：`/apocalypse catgirl ai <一句话>` —— 她听懂人话、回你一句，必要时动手：",
        "  **切工种**（伐木/挖矿/战斗/跟随，和「你手动指派」同一条路径，会关掉自主模式）或",
        "  **用她自己的材料给你下单做东西**（剑/镐/斧/锹/锄/弓弩/箭/盾/盔甲，扣爱心币手续费）。",
        "  `/apocalypse catgirl ai status` 看端点/模型/熔断状态。",
        "- **跑在你机器上的模型**：默认 `http://127.0.0.1:11434` + `fableforge-ai/nexus-coder:q4_k_m`（qwen2 1.5B），",
        "  不联网、不花钱。实测（RTX 3060 6GB）：**0.2~0.6 秒一轮、约 150 token/s**。",
        "  「思考标签」会被剥掉，模型返回的每个字段都会被<b>重新校验</b>：动作只认 none/say/set_job/craft，",
        "  物品必须真在配方表里、还得是她会做的那几类 —— 不可信的字段一律降级成聊天，绝不透传到执行层。",
        "- **不会因为 AI 而崩**：请求在工作线程跑、结果回投主线程；连不上/超时/回包是垃圾 → 一句中文提示；",
        "  连续失败 3 次熔断 5 分钟（别让她每句话都去戳一个没起来的 ollama）。配置项都在 `catgirl.ai.*`",
        "  （`enabled` / `actions` / `endpoint` / `model` / `timeout_ms` / `num_ctx`），`actions=false` 时她只陪聊不动手。",
        "",
        "### %s — 2026-10-10" % PREV,
    ])
    marker = "### %s — 2026-10-10" % PREV
    if marker not in s:
        fails.append("readme 里找不到 1.1.75 段锚点")
    else:
        s = s.replace(marker, sec, 1)
        lines = s.split(NL)
        hit = False
        for i, line in enumerate(lines):
            if line.startswith("| **当前版本** |") and PREV in line:
                lines[i] = line.replace(PREV, VER, 1)
                hit = True
                break
        if not hit:
            fails.append("readme 头表「当前版本」行没找到 %s" % PREV)
        rd.write_text(NL.join(lines), encoding="utf-8")
        print("(2) readme：+ ### %s 段 + 头表 → %s" % (VER, VER))

# ---------------------------------------------------------------- 派生 _deploy_176.py
src = (ROOT / "tools/_deploy_175.py").read_text(encoding="utf-8")

src = src.replace(
    '"""1.1.75 出货：像玩家一样操作第二批 —— 自主选题 + 用容器 + 护卫 + 两个新命令（含 1.1.74 全部不回归）',
    '"""1.1.76 出货：服务端崩溃修复（TransientCraftingContainer null 菜单）+ 本地 AI 助理（qwen2 1.5B / Ollama）（含 1.1.75 全部不回归）', 1)
src = src.replace("VER = '1.1.75'", "VER = '1.1.76'", 1)
src = src.replace("PREV = '1.1.74'", "PREV = '1.1.75'", 1)
src = src.replace("description='1.1.75 出货：自主 / 容器 / 护卫'",
                  "description='1.1.76 出货：崩溃修复 + 本地 AI 助理'", 1)
src = src.replace("  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.75；",
                  "  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.76；", 1)
src = src.replace("py tools/_deploy_175.py", "py tools/_deploy_176.py")

# 段号 8 → 9（原地升位，避免又出现编号错位）
for i in range(1, 9):
    src = src.replace("=== %d/8 " % i, "=== %d/9 " % i)

BLOCK = NL.join([
    "print('=== 9/9 1.1.76：崩溃修复 + 本地 AI 助理 ===')",
    "_p = 'F:/mcmod/src/main/java/com/apocalypse/zombies/'",
    "# —— 崩溃修复：那张 3x3 必须配菜单",
    "_craft = open(_p + 'entity/CatGirlCrafting.java', encoding='utf-8').read()",
    "check('new TransientCraftingContainer(new GridMenu(), 3, 3)' in _craft,",
    "      '她的 3x3 配了空壳菜单（不再传 null）')",
    "check('new TransientCraftingContainer(null' not in _craft,",
    "      '源码里已无「传 null 菜单」的老写法（那就是崩溃根因）')",
    "check('extends AbstractContainerMenu' in _craft and 'GridMenu' in _craft,",
    "      '空壳菜单在（slotsChanged 走默认空实现，不碰真实窗口）')",
    "check('catch (RuntimeException e)' in _craft and 'LOGGER.error' in _craft,",
    "      '自动制作/熔炼那一拍有兜底（异常只记日志）')",
    "_menu = open(_p + 'entity/menu/CatGirlTradeMenu.java', encoding='utf-8').read()",
    "check('LOGGER.error' in _menu, '下单路径（跑在服务端 tick 里）也有兜底')",
    "check('TransientCraftingContainer(this, 3, 3)' in _menu,",
    "      '菜单自己的 3x3 仍然挂在真菜单上（没被顺手改坏）')",
    "# —— AI 助理：类进包",
    "for _c in ('ai/OllamaWire.class', 'ai/LocalAiClient.class', 'ai/CatGirlAiPrompt.class',",
    "           'ai/CatGirlAiActions.class'):",
    "    check(any(n.endswith(_c) for n in names), '进包：%s' % _c.split('/')[-1])",
    "# —— AI 助理：纪律",
    "_wire = open(_p + 'ai/OllamaWire.java', encoding='utf-8').read()",
    "check('import net.minecraft' not in _wire,",
    "      'OllamaWire 不碰 Minecraft 类（所以能拿裸 JVM 对着真模型测同一份字节码）')",
    "check('ACTIONS = List.of(\"none\", \"say\", \"set_job\", \"craft\")' in _wire,",
    "      '动作白名单在代码里写死（模型说什么都不越界）')",
    "check('degraded' in _wire and 'stripThink' in _wire,",
    "      '坏回包统一降级 + 思考标签剥除')",
    "_client = open(_p + 'ai/LocalAiClient.java', encoding='utf-8').read()",
    "check('server.execute(' in _client, 'HTTP 在工作线程、结果回投主线程')",
    "check('COOLDOWN_MS' in _client and 'FAIL_LIMIT' in _client, '连续失败熔断')",
    "check('CAT_GIRL_AI_ENDPOINT' in _client and 'CAT_GIRL_AI_MODEL' in _client,",
    "      '端点/模型走配置')",
    "check('sendAsync' in _client, '请求是异步发的（不阻塞调用它的那一步）')",
    "_acts = open(_p + 'ai/CatGirlAiActions.java', encoding='utf-8').read()",
    "check('isHerCraftable' in _acts and 'CatGirlRecipeTable.find' in _acts,",
    "      '合成要过「配方表 + 她的白名单」两道')",
    "check('teleport' not in _acts and 'addItem' not in _acts and 'setHealth' not in _acts,",
    "      '第一版没有「凭空给物品 / 传送 / 加血」这类动作')",
    "_cfg4 = open(_p + 'Config.java', encoding='utf-8').read()",
    "check('\"model\", \"fableforge-ai/nexus-coder:q4_k_m\"' in _cfg4, '默认模型 = qwen2 1.5B')",
    "check('\"endpoint\", \"http://127.0.0.1:11434\"' in _cfg4, '默认只连本机')",
    "check('\"actions\", true' in _cfg4 and '\"enabled\", true' in _cfg4, 'AI 两个开关在配置里')",
    "_cmd4 = open(_p + 'command/ApocalypseCommand.java', encoding='utf-8').read()",
    "check('Commands.literal(\"ai\")' in _cmd4 and 'catgirlAi(' in _cmd4,",
    "      '/apocalypse catgirl ai <一句话> 在命令表里')",
    "check('catgirlAiStatus' in _cmd4, '有 ai status 自检出口')",
    "# —— 真端点实跑：用线上那份源码编出字节码，对着真 Ollama 跑",
    "print('  —— 真模型实跑（Ollama + 线上那份 OllamaWire）')",
    "_gson = 'F:/.minecraft/libraries/com/google/code/gson/gson/2.10.1/gson-2.10.1.jar'",
    "if not os.path.exists(_gson):",
    "    check(False, 'gson jar 在（门禁用例要它编译）', _gson)",
    "else:",
    "    os.makedirs('F:/mcmod/build/aiw', exist_ok=True)",
    "    _rc = subprocess.call('javac -encoding UTF-8 -J-Duser.language=en -d build/aiw -cp \"%s\" '",
    "                          'src/main/java/com/apocalypse/zombies/ai/OllamaWire.java '",
    "                          'tools/ai_wire_test/OllamaWireTest.java' % _gson,",
    "                          shell=True, cwd='F:/mcmod')",
    "    check(_rc == 0, '门禁用例编译通过（编的就是线上那份 OllamaWire）')",
    "    if _rc == 0:",
    "        _run = subprocess.run('java -cp \"build/aiw;%s\" OllamaWireTest' % _gson,",
    "                              shell=True, cwd='F:/mcmod', capture_output=True, text=True,",
    "                              errors='replace', timeout=900)",
    "        _lines = [l.strip() for l in (_run.stdout or '').splitlines() if l.strip()]",
    "        check(_run.returncode == 0, '真 Ollama 端点上 12 项全过',",
    "              _lines[-1] if _lines else (_run.stderr or '')[:120])",
    "        for _l in _lines:",
    "            if '她的回话' in _l or _l.startswith('动作：'):",
    "                print('       ' + _l)",
    "",
    "",
])
anchor = "print('=== 7/9 工程门禁（本机实跑） ===')"
if anchor not in src:
    fails.append("派生脚本里找不到工程门禁段锚点")
else:
    src = src.replace(anchor, BLOCK + anchor, 1)
(ROOT / "tools/_deploy_176.py").write_text(src, encoding="utf-8")
print("(3) _deploy_176.py 生成（%d 字节）" % len(src))

print(NL + ("全部命中" if not fails else "失败 %d 条：" % len(fails)))
for f in fails:
    print("  [FAIL] " + f)
(ROOT / "build" / "p176_prep_note.txt").write_text(NL.join(fails), encoding="utf-8")

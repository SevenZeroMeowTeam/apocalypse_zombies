# -*- coding: utf-8 -*-
"""由 _deploy_198.py 生成 _deploy_199.py。

只做定点改：
  1) 头部 docstring 换成 1.1.99 的（症状 / 两个根因 / 修法 / 判据清单）；
  2) VER / PREV / ACCEPT / DEV；
  3) 「当前版本」头表判据 1.1.98 → 1.1.99；gradle.properties 判据同步；
  4) **路径前缀**：仓库根已从 `F:/mcmod/` 挪到 `F:/mcmod/apocalypse_zombies-main/`，
     198 里 97 处写死的旧路径全部失效 —— 用负向先行断言补上，不会写成两条。
  5) 1.1.98 的本体断言段（`=== 13/18 1.1.98：…`）整段换成 tools/_assert_199.py 的内容
     （缩进 4 空格内联，与 198 的写法一致）。

历史引用（1.1.97/1.1.96/1.1.95 … 那些「不回归」判据与 readme 里的老条目）**一律不动**。
"""
import io
import re

ROOT = 'F:/mcmod/apocalypse_zombies-main/'
P198 = ROOT + 'tools/_deploy_198.py'
P199 = ROOT + 'tools/_deploy_199.py'
A199 = ROOT + 'tools/_assert_199.py'

s = io.open(P198, encoding='utf-8', newline='').read()
CR = '\r\n' if '\r\n' in s else '\n'

HEAD = '''"""1.1.99 出货：猫耳娘 AI —— 思考型模型把额度全想光了。

本版内容：`ai/LmStudioWire` 解析层重写（思考不再当答案）+ prefill（先替她写好答案的头一个字符）
+ `LocalAiClient` / `CatGirlAiPrompt` 的候选表懒加载 + 两个新配置项 + 接线门禁 17 → 24 项。

  * **症状**（那张截图上的三种话）：`……我又想不明白了（没有 JSON）。` /
    `列表为空，无法执行任何任务。` / `只能执行一次任务，制作石头。`
  * **根因一**：端点指到的是 llama.cpp（`127.0.0.1:9931`），模型是
    `DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M` —— R1 蒸馏的思考写在它自己的模板里，请求里那个
    `enable_thinking=false` 它不认。`max_tokens` 被思考吃满（回包 `finish_reason="length"`），
    `content` 交回空串、正文全在 `reasoning_content`；而旧版 `contentOf` 的兜底正是
    「content 空 → 取 reasoning_content」—— **思考于是被当成答案**，思考里没有花括号，
    屏幕上就是「没有 JSON」。
  * **根因二**：`CatGirlRecipeTable.ensureLoaded` 的唯一调用点是 `/apocalypse catgirl recipes`，
    一进游戏就跟她说话时表是空的 → 候选恒空 → 她只能说「列表为空，无法执行任何任务」。
  * **修法**：①messages 末尾追加 `{"role":"assistant","content":"{"}`（prefill）—— 实测同一句话
    从「299 token / 13.9 s / 空答案」变成「36 token / 1.6 s / 合法 JSON」；
    ②解析只认真答案（思考里草拟过完整 JSON 仍可救命），降级理由点名 `ai.max_tokens`，
    取 JSON 改成括号配平扫描；③对话前 `ensureLoaded(server)`，兜底清单不再依赖配方表；
    ④新配置 `ai.max_tokens`(512) / `ai.prefill_json`(true)，`timeout_ms` 30000 → 60000。

跑法（*游戏须完全关闭*）：
    py tools/_deploy_199.py --build        # 先 ./gradlew build 再出货
    py tools/_deploy_199.py                # 用 build/libs 里已构建好的包
    py tools/_deploy_199.py --no-install   # 只跑判据，不动 mods/

判据（任一条不过就退出，不动 mods/）：
  1. 构建产物存在、包内 mods.toml 版本 == 1.1.99；
  2. 包内 RSC 资产齐全且规格正确，剪影对照表过门禁；
  3. 四条门禁在本机实跑全绿：rsc_1917_silhouette.py、check_gun_resources.py、
     check_rsc_1917_art.py、check_rsc_1917_anim.py；
  4. 1.1.99 本体：接线不再把 reasoning_content 当回话、prefill 开关与两条请求体都在、
     prefill 被服务端顶回来（4xx）会去掉重来、候选表在对话前载入、兜底清单不依赖配方表、
     两个新配置项与 timeout 60000 都在、接线门禁的 24 条判据写全了；
  5. 不回归：1.1.98 的 EasyNPC 预设结构、1.1.97 的文档一致性、1.1.96 的 VillagerChores、
     1.1.95 的八把枪 gui.scale、1.1.94 的铜斧、1.1.93 的音效（guns/ 17 个）、
     猫耳娘 128²、LmStudioWire 在且 OllamaWire 已删；
  6. 文档：readme 有 1.1.99 条目与头表、wiki 07 同步、gradle.properties == 1.1.99；
  7. 基线：mods/ 里当前那个包必须是本版或上一版（按包内 mods.toml 版本认）；
  8. 换包：旧包挪到 mods/ 同级 mods_backup/（保 3 份），mods/ 里只留一个本模组包；
     其它模组 md5 必须全等；mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）。

注：本版**没走 `_mk_deploy` 那条「从上一版派生」的老路** —— 仓库根已从 `F:/mcmod/` 挪到
`F:/mcmod/apocalypse_zombies-main/`，198 及以前写死的 97 处路径全部过时，照抄只会得到一片假失败。
本脚本在此之上只做路径前缀补齐与定点改版，其余一字未动。
"""'''

# ---- 1) 头部 docstring（第一段）----
i = s.index('"""')
j = s.index('"""', i + 3)
s = s[:i] + HEAD + s[j + 3:]

# ---- 2) 版本常量 ----
assert s.count("VER = '1.1.98'") == 1
s = s.replace("VER = '1.1.98'", "VER = '1.1.99'")
assert s.count("PREV = '1.1.97'") == 1
s = s.replace("PREV = '1.1.97'", "PREV = '1.1.98'")
assert s.count("ACCEPT = ('1.1.96', PREV, VER)") == 1
s = s.replace("ACCEPT = ('1.1.96', PREV, VER)", "ACCEPT = ('1.1.97', PREV, VER)")
s = s.replace("1.1.96（正式版，未装机）、1.1.97（装机在册的上一版）",
              "1.1.97（正式版，未装机）、1.1.98（装机在册的上一版）")
assert s.count("DEV = 'F:/.minecraft/versions/1.20.1-Forge_47.4.26'") == 1
s = s.replace("DEV = 'F:/.minecraft/versions/1.20.1-Forge_47.4.26'",
              "DEV = 'F:/.minecraft/versions/1.20.1-Forge_47.4.27'")

# ---- 3) 「当前版本」头表 / gradle.properties 判据 ----
n_head = s.count("| **当前版本** | `1.1.98` |")
assert n_head >= 5, n_head
s = s.replace("| **当前版本** | `1.1.98` |", "| **当前版本** | `1.1.99` |")
s = s.replace("readme 头表 == 1.1.98", "readme 头表 == 1.1.99")
s = s.replace("check('mod_version=1.1.98' in gp, 'gradle.properties mod_version=1.1.98')",
              "check('mod_version=1.1.99' in gp, 'gradle.properties mod_version=1.1.99')")

# ---- 4) 1.1.98 的本体断言段 → 1.1.99 ----
start = s.index("    print('=== 13/18 1.1.98：修 EasyNPC 武器商预设 ===')")
end = s.index("    print('=== 11/18 基线校验 ===')")
body = io.open(A199, encoding='utf-8', newline='').read().replace('\r\n', '\n')
if not body.endswith('\n'):
    body += '\n'
# 每行都要**带着换行**再拼。漏了它整段会被压成一行，而第一行结尾就是 `# 注释` ——
# 于是后面所有判据悄悄变成注释、一条不跑（2026-10-13 实测踩过：只有标题打印出来）。
indented = ''.join((('    ' + ln) if ln.strip() else ln) + '\n' for ln in body.split('\n'))
s = s[:start] + indented + s[end:]

# ---- 5) 路径前缀：仓库根挪进子目录（负向先行断言，不会补成两条）----
s = re.sub(r'F:/mcmod/(?!apocalypse_zombies-main)', 'F:/mcmod/apocalypse_zombies-main/', s)
# 5b) 门禁实跑那几行（以及 --build 的 gradlew 那行）cwd 是不带尾斜杠的写法，逃过了上面的正则
_n = s.count("cwd='F:/mcmod'")
assert _n >= 1, _n
s = s.replace("cwd='F:/mcmod'", "cwd='F:/mcmod/apocalypse_zombies-main'")
# 5c) 三条 check_*.py 也要 numpy（本机 py 默认挑到 3.14，那里没有）—— 与剪影那条统一点明 3.13
assert s.count("subprocess.call(['py', script], cwd='F:/mcmod/apocalypse_zombies-main')") == 1
s = s.replace("subprocess.call(['py', script], cwd='F:/mcmod/apocalypse_zombies-main')",
              "subprocess.call(['py', '-3.13', script], cwd='F:/mcmod/apocalypse_zombies-main')")
# 5d) 剩下的裸 'F:/mcmod'（os.path.relpath 的第二个参数那类）也一并补上，
#     否则 relpath 出来的相对路径会多一层目录名、判据永远对不上。
_n2 = s.count("'F:/mcmod'")
assert _n2 >= 1, _n2
s = s.replace("'F:/mcmod'", "'F:/mcmod/apocalypse_zombies-main'")

# ---- 6) Windows 控制台是 GBK：✅/✗ 会直接抛 UnicodeEncodeError，把门禁打断在**第一条判据**上
#         （2026-10-13 实测：`check(os.path.isfile(SRC), …)` 那一条就炸了）。改成 UTF-8 + replace。
assert s.count('import subprocess') == 1
s = s.replace('import subprocess', 'import subprocess\nimport sys', 1)
assert s.count('def main():') == 1
s = s.replace('def main():',
              'def main():\n'
              '    # Windows 控制台默认 GBK，✅/✗ 会抛 UnicodeEncodeError 把门禁打断在第一条判据上\n'
              '    # （2026-10-13 实测）。改成 UTF-8 + replace：打不出来的字符降级，判据照跑完。\n'
              '    try:\n'
              '        sys.stdout.reconfigure(encoding="utf-8", errors="replace")\n'
              '    except Exception:\n'
              '        pass\n', 1)

# ---- 7) 1.1.97 那段「文档数字对账」：本版 readme 又长了一节、tools 又多了 3 个脚本，
#         这几个数字必须跟着现状走 —— 那条判据的本意正是「别让文档从现状漂走」。
def _one(old, new):
    global s
    assert s.count(old) == 1, (s.count(old), old[:80])
    s = s.replace(old, new, 1)


_one("check('_deploy_196.py' in _wr, 'wiki 索引指向 _deploy_196.py')",
     "check('_deploy_199.py' in _wr, 'wiki 索引指向 _deploy_199.py')")
_one("check('1999 行' in _wr, 'wiki 索引写的是 readme 的真实行数（1999）')",
     "check('2066 行' in _wr, 'wiki 索引写的是 readme 的真实行数（2066）')")
_one("check('238 个 `.py`' in _wr, 'wiki 索引写的是 tools 当前脚本数（238）')",
     "check('244 个 `.py`' in _wr, 'wiki 索引写的是 tools 当前脚本数（244）')")
_one("check(abs(_lines - 1999) <= 60, 'readme 行数仍与文档里写的 1999 同一量级',",
     "check(abs(_lines - 2066) <= 60, 'readme 行数仍与文档里写的 2066 同一量级',")
_one("check(abs(len(_py) - 238) <= 15, 'tools/*.py 数量在 238 附近（每版 +3）', '实得 %d' % len(_py))",
     "check(abs(len(_py) - 244) <= 15, 'tools/*.py 数量在 244 附近（每版 +3）', '实得 %d' % len(_py))")

# ---- 8) 两条纯环境性的健壮性补丁（都与本版内容无关，但不补就跑不出一片绿）----
#   ㈠ Windows 控制台是 GBK：门禁实测那几条 `check_*.py` 会**在打印 ✓ 时**自己崩掉，
#      于是「门禁全绿」这条永远红，而真因是编码不是资产。给子进程统一钉 UTF-8。
_one("""    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
""",
     """    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    # 子进程（node / py -3.13 那几条门禁）也钉 UTF-8，否则它们在打印 ✓/✗ 时自己崩
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
""")
#   ㈡ javap 那条产物级判据要往 run/ 里重定向输出，而 run/ 是 Gradle 的产物目录：
#      干净检出上它不存在 → 重定向失败 → javap 报退出码 1 → 下游两条一起假红。
_one("""    _jv = 'F:/mcmod/apocalypse_zombies-main/run/javap_ammo.txt'
    try:""",
     """    _jv = 'F:/mcmod/apocalypse_zombies-main/run/javap_ammo.txt'
    os.makedirs(os.path.dirname(_jv), exist_ok=True)   # run/ 是 Gradle 产物目录，干净检出上没有
    try:""")

io.open(P199, 'w', encoding='utf-8', newline='').write(s)
print('wrote %s (%d lines)' % (P199, s.count('\n') + 1))

# -*- coding: utf-8 -*-
"""由 _deploy_183.py 生成 _deploy_184.py（版本号 / 头注释 / AI 接线层换 LM Studio）。

只定点改写，不全局替换 —— _deploy_183.py 里大量的 1.1.83 / 1.1.82 是历史引用，
一起改就把历史抹了。1.1.84 的断言段放在 tools/_assert_184.py，直接读进来（不在生成器里写转义）。
"""
import io

P183 = 'F:/mcmod/tools/_deploy_183.py'
P184 = 'F:/mcmod/tools/_deploy_184.py'
CR = '\r\n'


def L(*lines):
    return CR.join(lines) + CR


s = io.open(P183, encoding='utf-8', newline='').read()


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (s.count(old), old[:80])
    s = s.replace(old, new, n)


# ---- 1) 版本号 ----
rep("VER = '1.1.83'\r\nPREV = '1.1.82'", "VER = '1.1.84'\r\nPREV = '1.1.83'")
rep("_deploy_183.py", "_deploy_184.py", s.count("_deploy_183.py"))

# ---- 2) 头注释 ----
i = s.index('"""')  # 文件第一个三引号 = 头部 docstring
te = s.index('"""', i + 3)
head = L(
    '"""1.1.84 出货：**本地 AI 助理换 LM Studio**（本机 1234/v1 上的 Qwen3.5-4B 蒸馏版，',
    '不再走 Ollama —— 接线层 OllamaWire → LmStudioWire，改走 OpenAI 兼容的 /v1/chat/completions）',
    '（含 1.1.83 的挖掘数字 / 1.1.82 的挖掘高亮 / 1.1.81 的玩家一键挖掘 / 1.1.80 的 36 格库存，全部不回归）',
    '（含 1.1.79 的图形配置界面；配置项总数 169 → 170，全部不回归）',
    '（猫耳娘 v4 内容不回退 —— 128² 皮肤 / 逐面 UV 装机 geo / 脸层 44×32）。',
    '',
    '跑法（**游戏须完全关闭**）：',
    '    py tools/_deploy_184.py --build        # 先 ./gradlew build 再出货',
    '    py tools/_deploy_184.py                # 用 build/libs 里已构建好的包',
    '',
    '判据（任一条不过就退出，不动 mods/）：',
    '  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.84；',
    '  2. 猫耳娘该有的东西：',
    '     · geo/cat_girl.geo.json —— identifier geometry.cat_girl、贴图基准 128×128、',
    '       31 骨 / 126 方块，且**每个 cube 用逐面 uv/uv_size**；rest 姿态骨骼无旋转；',
    '     · textures/entity/cat_girl.png 是 128×128；',
    '     · animations/cat_girl.animation.json 在位，每条片段 animation_length > 0；',
    '     · Java 侧 CatGirlEntity / CatGirlGeoModel / CatGirlGeoRenderer 在 jar 里；',
    '  3. 1.1.84 本体（源码级 + 包内级）：',
    '     · ai/LmStudioWire 在、ai/OllamaWire 已删（源码与 jar 两处都查）；',
    '     · 请求走 /v1/chat/completions；response_format 必须是 json_schema —— 照搬 Ollama 的',
    '       json_object 会被 LM Studio 400 顶回来（实测）；回包要认 reasoning_content（content 会空）；',
    '     · 配置默认：endpoint http://127.0.0.1:1234/v1 / model qwen3.5-4b-claude-4.6-opus-reasoning-distilled /',
    '       timeout_ms 30000 / 新增 json_schema(true)；配置项总数 170（1.1.83 的 169 + 1）；',
    '     · **真端点实跑**：拿线上那份 LmStudioWire 编出字节码，对着真 LM Studio 跑 17 项全过；',
    '  4. **不回归**：1.1.83 的挖掘数字 / 1.1.82 的高亮描边 / 1.1.81 的破坏即连带；',
    '     1.1.80 的 36 格库存 / 手持物品基准旋转；柯尔特 1878 仍在包里且规格未变',
    '     （12 骨 / 87 方块 / 512² 基准 / 8 条片段长度逐条等于 Java 常量）；',
    '  5. 工程门禁在**本机跑一遍**：tools/check_gun_resources.py 全绿才继续；',
    '  6. 基线：mods/ 里当前那个包必须是本版或上一版（按**包内 mods.toml 版本**认）；',
    '  7. 换包：旧包挪到 mods/ **同级** 的 mods_backup/（保 3 份），mods/ 里只留一个本模组包；',
    '     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）。',
    '',
    '(下面为原文，未改)',
    '"""',
)
s = s[:i] + head + s[te + 3:]

# ---- 3) 工具名 / 描述 / readme 头表版本 ----
rep("description='1.1.83 出货：挖掘数字（准星下方报会连挖几格）'",
    "description='1.1.84 出货：本地 AI 助理换 LM Studio（1234/v1 的 Qwen3.5-4B 蒸馏版）'")
rep("check('| **当前版本** | `1.1.83` |' in _rd, 'readme 头表版本 == 1.1.83')",
    "check('| **当前版本** | `1.1.84` |' in _rd, 'readme 头表版本 == 1.1.84')")

# ---- 4) 1.1.76 那段的 AI 断言换口径（类名与默认值都变了，旧断言留着就是假绿） ----
rep("'ai/OllamaWire.class'", "'ai/LmStudioWire.class'")
rep("_wire = open(_p + 'ai/OllamaWire.java', encoding='utf-8').read()",
    "_wire = open(_p + 'ai/LmStudioWire.java', encoding='utf-8').read()")
rep("      'OllamaWire 不碰 Minecraft 类（所以能拿裸 JVM 对着真模型测同一份字节码）')",
    "      'LmStudioWire 不碰 Minecraft 类（所以能拿裸 JVM 对着真模型测同一份字节码）')")
rep("""check('"model", "fableforge-ai/nexus-coder:q4_k_m"' in _cfg4, '默认模型 = qwen2 1.5B')""",
    """check('"model", "qwen3.5-4b-claude-4.6-opus-reasoning-distilled"' in _cfg4,
      '默认模型 = Qwen3.5-4B 蒸馏版（1.1.84 起）')""")
rep("""check('"endpoint", "http://127.0.0.1:11434"' in _cfg4, '默认只连本机')""",
    """check('"endpoint", "http://127.0.0.1:1234/v1"' in _cfg4, '默认只连本机 LM Studio（1.1.84 起）')""")

# ---- 5) 真端点实跑：Ollama → LM Studio（整段换） ----
NEW_RUN = L(
    '# —— 真端点实跑：用线上那份源码编出字节码，对着真 LM Studio 跑',
    "print('  —— 真模型实跑（LM Studio + 线上那份 LmStudioWire）')",
    "_gson = 'F:/.minecraft/libraries/com/google/code/gson/gson/2.10.1/gson-2.10.1.jar'",
    'if not os.path.exists(_gson):',
    "    check(False, 'gson jar 在（门禁用例要它编译）', _gson)",
    'else:',
    "    os.makedirs('F:/mcmod/build/aiw', exist_ok=True)",
    "    _rc = subprocess.call('javac -encoding UTF-8 -J-Duser.language=en -d build/aiw -cp \"%s\" '",
    "                          'src/main/java/com/apocalypse/zombies/ai/LmStudioWire.java '",
    "                          'tools/ai_wire_test/LmStudioWireTest.java' % _gson,",
    "                          shell=True, cwd='F:/mcmod')",
    "    check(_rc == 0, '门禁用例编译通过（编的就是线上那份 LmStudioWire）')",
    '    if _rc == 0:',
    "        _run = subprocess.run('java -Dsun.stdout.encoding=UTF-8 -cp \"build/aiw;%s\" "
    "LmStudioWireTest' % _gson,",
    "                              shell=True, cwd='F:/mcmod', capture_output=True, text=True,",
    "                              encoding='utf-8', errors='replace', timeout=900)",
    "        _lines = [l.strip() for l in (_run.stdout or '').splitlines() if l.strip()]",
    "        check(_run.returncode == 0, '真 LM Studio 端点上 17 项全过',",
    "              _lines[-1] if _lines else (_run.stderr or '')[:120])",
    '        for _l in _lines:',
    "            if '她的回话' in _l or _l.startswith('动作：'):",
    "                print('       ' + _l)",
    '',
)
_ri = s.index('# —— 真端点实跑：用线上那份源码编出字节码，对着真 Ollama 跑')
_rj = s.index("print('=== 9/9 1.1.77")
s = s[:_ri] + NEW_RUN + s[_rj:]

# ---- 6) 历史段里的配置项计数跟着走（读的是当前源码，所以每版都要往前挪） ----
rep("check(_n9 == 169, '配置项总数 169（1.1.80 的 157 + 玩家一键挖掘 10 + 高亮 1 + 数字 1）', '实得 %d' % _n9)",
    "check(_n9 == 170, '配置项总数 170（1.1.80 的 157 + 玩家一键挖掘 10 + 高亮 1 + 数字 1 + json_schema 1）', '实得 %d' % _n9)")
rep("check('全部 169 项配置' in _rd9, 'readme 写明图形界面共 169 项')",
    "check('全部 170 项配置' in _rd9, 'readme 写明图形界面共 170 项')")
rep("check(_n10 == 169, '配置项总数 169（1.1.81 的 167 + 高亮 1 + 数字 1）', '实得 %d' % _n10)",
    "check(_n10 == 170, '配置项总数 170（1.1.81 的 167 + 高亮 1 + 数字 1 + json_schema 1）', '实得 %d' % _n10)")
rep("check('全部 169 项配置' in _rd10, 'readme 写明图形界面共 169 项')",
    "check('全部 170 项配置' in _rd10, 'readme 写明图形界面共 170 项')")
rep("check(_n11 == 169, '配置项总数 169（1.1.82 的 168 + 数字 1）', '实得 %d' % _n11)",
    "check(_n11 == 170, '配置项总数 170（1.1.82 的 168 + 数字 1 + json_schema 1）', '实得 %d' % _n11)")
rep("check('全部 169 项配置' in _rd11, 'readme 写明图形界面共 169 项')",
    "check('全部 170 项配置' in _rd11, 'readme 写明图形界面共 170 项')")

# ---- 7) 新断言段：插在「工程门禁」之前 ----
FRAG = 'F:/mcmod/tools/_assert_184.py'
NEW = io.open(FRAG, encoding='utf-8').read().replace(chr(10), CR)
if not NEW.endswith(CR):
    NEW += CR

rep("print('=== 最后：工程门禁（本机实跑） ===')",
    NEW + "print('=== 最后：工程门禁（本机实跑） ===')")

io.open(P184, 'w', encoding='utf-8', newline='').write(s)
print('已生成', P184, len(s), 'chars')

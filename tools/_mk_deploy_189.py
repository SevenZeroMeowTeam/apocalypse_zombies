# -*- coding: utf-8 -*-
"""由 _deploy_188.py 生成 _deploy_189.py（版本号 / 头注释 / 新增一节「配置自动迁移」）。

只定点改写，不全局替换 —— _deploy_188.py 里出现的 1.1.88 / 1.1.87 有些是历史引用，
一起改就把历史抹了。1.1.89 的断言段放在 tools/_assert_189.py，直接读进来（不在生成器里写转义）。
"""
import io

P188 = 'F:/mcmod/tools/_deploy_188.py'
P189 = 'F:/mcmod/tools/_deploy_189.py'

s = io.open(P188, encoding='utf-8', newline='').read()
CR = '\r\n' if '\r\n' in s else '\n'


def L(*lines):
    return CR.join(lines) + CR


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (s.count(old), old[:80])
    s = s.replace(old, new, n)


# ---- 1) 版本号与基线 ----
rep("VER = '1.1.88'" + CR + "PREV = '1.1.87'", "VER = '1.1.89'" + CR + "PREV = '1.1.88'")
rep("# 认三版：1.1.83（装机在册的上一版）、1.1.85（只在 GitHub 上，没装机）、本版。",
    "# 认三版：1.1.87（只在 GitHub 上，没装机）、1.1.88（装机在册的上一版）、本版。")
rep("ACCEPT = ('1.1.86', PREV, VER)", "ACCEPT = ('1.1.87', PREV, VER)")

# ---- 2) 头注释 ----
i = s.index('"""')            # 文件第一个三引号 = 头部 docstring
te = s.index('"""', i + 3)
head = L(
    '"""1.1.89 出货：**老实例的本地 AI 端点自动迁移**（Ollama 口径 → LM Studio 口径）+ 两个探针改齐。',
    '',
    '本版内容：一次性的配置迁移（`Config.migrateLegacyAiConfig` + `ApocalypseZombies` 里的调用点）',
    '与两个探针脚本的口径换代，**资产与 Java 逻辑一行未动**。',
    '  * **根因**：Forge 的配置**只写默认值、从不覆盖已经存在的值**（越界值也只在读取时校正）。',
    '    于是 1.1.84 把接线换成 LM Studio 之后，老实例的 `apocalypse_zombies-common.toml` 里',
    '    仍然躺着 1.1.76 写下的 `endpoint = "http://127.0.0.1:11434"` 与 Ollama 形状的模型名',
    '    （`fableforge-ai/nexus-coder:q4_k_m`）—— 注释是新的、值是旧的，她每次都回',
    '    「连不上本地模型 http://127.0.0.1:11434」。',
    '  * **迁移**：`Config.migrateLegacyAiConfig()` 在 `ModConfigEvent.Loading` 里跑一次（配置进内存',
    '    之后才读得出值，构造阶段读会抛 `Cannot get config value before config is loaded`），',
    '    改完 `SPEC.save()` 让 Forge 把文件按新值重写；判定收窄到「确实是那套旧默认值」，',
    '    自己填的地址 / 模型名一律不碰。',
    '  * **探针**：`tools/_ai_probe.py` 从 Ollama 的 `/api/chat` 换成 LM Studio 的',
    '    `/v1/chat/completions`（`chat_template_kwargs` / `json_schema` / `usage.completion_tokens`），',
    '    不传模型名会自动从 `GET /v1/models` 挑；`tools/_ai_jobprobe.py` 直接复用它的线，不再各写一份。',
    '  * 不回归：RSC M1917 资产（19 骨 / 577 方块 / 512² / 8 条片段）、其余 6 把枪、猫耳娘 v4、',
    '    Java 逻辑全部未动。',
    '',
    '跑法（**游戏须完全关闭**）：',
    '    py tools/_deploy_189.py --build        # 先 ./gradlew build 再出货',
    '    py tools/_deploy_189.py                # 用 build/libs 里已构建好的包',
    '    py tools/_deploy_189.py --no-install   # 只跑判据，不动 mods/',
    '',
    '判据（任一条不过就退出，不动 mods/）：',
    '  1. 构建产物存在、包内 mods.toml 版本 == 1.1.89；',
    '  2. 包内 RSC 资产齐全且规格正确（19 骨 / 577 方块 / 512² / 8 条片段长度逐条对得上 Java 常量），',
    '     且剪影对表过门禁（IoU ≥ 0.90、上缘 RMS ≤ 3.0 mm、下缘 RMS ≤ 5.0 mm、单列 >10 mm 的列数 == 0）；',
    '  3. 四条门禁在本机实跑全绿：rsc_1917_silhouette.py（轮廓对表）、check_gun_resources.py、',
    '     check_rsc_1917_art.py、check_rsc_1917_anim.py；',
    '  4. 不回归：另外 6 把枪的 geo/动画在包、动画文件 13 个、猫耳娘 128²、',
    '     LmStudioWire 在且 OllamaWire 已删、ai.json_schema 仍在；',
    '  5. 文档：readme 有 1.1.89 条目与头表、1.1.76 那段的旧默认值加了指路、wiki 07 记一笔、',
    '     wiki 06 收录迁移入口与新口径探针、gradle.properties == 1.1.89；',
    '  6. 1.1.89 本体：迁移入口 / 调用点 / 日志都在，判定收窄，src 下 11434 只剩迁移判定，',
    '     两个探针都不再打 Ollama；',
    '  7. 基线：mods/ 里当前那个包必须是本版或上一版（按包内 mods.toml 版本认）；',
    '  8. 换包：旧包挪到 mods/ 同级 mods_backup/（保 3 份），mods/ 里只留一个本模组包；',
    '     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描）。',
    '"""',
)
s = s[:i] + head + s[te + 3:]

# ---- 3) 文档判据（readme / wiki 07 / gradle.properties 换版号） ----
rep("check('### 1.1.88 —' in rd, 'readme 有 1.1.88 条目')",
    "check('### 1.1.89 —' in rd, 'readme 有 1.1.89 条目')")
rep("check('| **当前版本** | `1.1.88` |' in rd, 'readme 头表 == 1.1.88')",
    "check('| **当前版本** | `1.1.89` |' in rd, 'readme 头表 == 1.1.89')")
rep("check('1.1.88' in w7, 'wiki 07 记了 1.1.88 一笔')",
    "check('1.1.89' in w7, 'wiki 07 记了 1.1.89 一笔')")
rep("check('rsc_1917_geo.js' in w6 and 'check_rsc_1917_anim.py' in w6, 'wiki 06 收录 RSC 生成器与门禁')",
    "check('rsc_1917_geo.js' in w6 and 'check_rsc_1917_anim.py' in w6, 'wiki 06 收录 RSC 生成器与门禁')" + CR
    + "    check('migrateLegacyAiConfig' in w6, 'wiki 06 收录配置迁移入口')" + CR
    + "    check('_ai_probe.py' in w6 and 'LM Studio' in w6, 'wiki 06 的探针条目已改 LM Studio 口径')")
rep("check('mod_version=1.1.88' in gp, 'gradle.properties mod_version=1.1.88')",
    "check('mod_version=1.1.89' in gp, 'gradle.properties mod_version=1.1.89')")

# ---- 4) 段落编号 8 → 9（先大后小，免得级联替换） ----
for k in (8, 7, 6):
    rep("'=== %d/8 " % k, "'=== %d/9 " % (k + 1))
for k in range(0, 6):
    rep("'=== %d/8 " % k, "'=== %d/9 " % k)

# ---- 5b) 构建调用：某些 python（graalpy）不做 PATHEXT 补全，光写 'cmd' 会 FileNotFoundError ----
rep("        rc = subprocess.call(['cmd', '/c', 'gradlew.bat', 'build', '--console=plain'], cwd='F:/mcmod')",
    "        # COMSPEC / 绝对路径：某些 python（如 graalpy）不做 PATHEXT 补全，光写 'cmd' 会" + CR
    + "        # FileNotFoundError；System32 也不一定在解释器的 PATH 里。" + CR
    + "        _cmd = os.environ.get('COMSPEC') or r'C:\\Windows\\System32\\cmd.exe'" + CR
    + "        rc = subprocess.call([_cmd, '/c', 'gradlew.bat', 'build', '--console=plain'], cwd='F:/mcmod')")

# ---- 5c) 游戏探针：wmic 在 Win11 上常缺，静默降级成「没在跑」会害人（游戏开着照样换包）----
rep(CR.join([
    "        out = subprocess.run(['wmic', 'process', 'where', \"name='javaw.exe'\", 'get', 'CommandLine'],",
    "                             capture_output=True, text=True, timeout=20).stdout.lower()",
    "        return (any(m.lower() in out for m in CLIENT_MARKERS), 'server' in out)",
    "    except Exception:",
    "        return (None, None)"]),
    CR.join([
    "        out = subprocess.run(['wmic', 'process', 'where', \"name='javaw.exe'\", 'get', 'CommandLine'],",
    "                             capture_output=True, text=True, timeout=20).stdout.lower()",
    "        if 'commandline' in out:",
    "            return (any(m.lower() in out for m in CLIENT_MARKERS), 'server' in out)",
    "    except Exception:",
    "        pass",
    "    try:",
    "        ps = (\"Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'javaw.exe' -or \"",
    "              \"$_.Name -eq 'java.exe' } | ForEach-Object { $_.CommandLine }\")",
    "        out = subprocess.run(['powershell', '-NoProfile', '-Command', ps],",
    "                             capture_output=True, text=True, timeout=45).stdout.lower()",
    "        if 'commandline' in out or 'net.minecraft' in out:",
    "            return (any(m.lower() in out for m in CLIENT_MARKERS), 'server' in out)",
    "    except Exception:",
    "        pass",
    "    return (None, None)"]))

# ---- 5d) 游戏探针的判定串：PCL2 这类启动器命令行里没有 net.minecraft.client.main.Main ----
rep("CLIENT_MARKERS = ('net.minecraft.client.main.Main',)",
    "# 「游戏在跑」的判定串：原版/Forge 启动器给 net.minecraft.client.main.Main，" + CR
    + "# 而 PCL2 这类启动器走自己的 bootstrap，命令行里只有 --launchTarget forgeclient" + CR
    + "# 与 --fml.forgeVersion —— 只认主类会**漏判**（游戏开着也照样换包），所以几个都认。" + CR
    + "CLIENT_MARKERS = ('net.minecraft.client.main.main', 'launchtarget forgeclient'," + CR
    + "                  'fml.forgeversion', 'assetsindex')")

# ---- 6) 新一节：插在「基线校验」之前，整段缩进 4 格（deploy 的段落都在 main() 里） ----
frag = io.open('F:/mcmod/tools/_assert_189.py', encoding='utf-8').read()
frag = CR.join(('    ' + ln) if ln.strip() else ln for ln in frag.replace(CR, '\n').split('\n'))
if not frag.endswith(CR):
    frag += CR
rep("    print('=== 7/9 基线校验 ===')", frag + "    print('=== 7/9 基线校验 ===')")

io.open(P189, 'w', encoding='utf-8', newline='').write(s)
print('已生成', P189, len(s), 'chars')

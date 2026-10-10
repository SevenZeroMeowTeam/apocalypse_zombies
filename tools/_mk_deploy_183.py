# -*- coding: utf-8 -*-
"""由 _deploy_182.py 生成 _deploy_183.py（版本号 / 头注释 / 1.1.83 断言段：挖掘数字）。

只定点改写，不全局替换 —— _deploy_182.py 里大量的 1.1.82 / 1.1.81 是历史引用，
一起改就把历史抹了。1.1.83 的断言段放在 tools/_assert_183.py，直接读进来（不在生成器里写转义）。
"""
import io

P182 = 'F:/mcmod/tools/_deploy_182.py'
P183 = 'F:/mcmod/tools/_deploy_183.py'
CR = '\r\n'


def L(*lines):
    return CR.join(lines) + CR


s = io.open(P182, encoding='utf-8', newline='').read()


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (s.count(old), old[:80])
    s = s.replace(old, new, n)


# ---- 1) 版本号 ----
rep("VER = '1.1.82'\r\nPREV = '1.1.81'", "VER = '1.1.83'\r\nPREV = '1.1.82'")
rep("_deploy_182.py", "_deploy_183.py", s.count("_deploy_182.py"))

# ---- 2) 头注释 ----
i = s.index('"""')  # 文件第一个三引号 = 头部 docstring
te = s.index('"""', i + 3)
head = L(
    '"""1.1.83 出货：**挖掘数字**（瞄着矿脉，准星下方报「会连挖几格」；与描边同一份数字，',
    '到 max_blocks 上限时补一句「已到上限」；顺手把「潜行只砸一格」收进共用判定，',
    '修掉 1.1.82 里「蹲着还给你画一整簇」的谎）',
    '（含 1.1.82 的玩家挖掘高亮 / 1.1.81 的玩家一键挖掘 / 1.1.80 的 36 格库存与手持方向，全部不回归）',
    '（含 1.1.79 的图形配置界面 / 一键挖掘上限 64 / id 参数修复全部不回归）',
    '（猫耳娘 v4 内容不回退 —— 128² 皮肤 / 逐面 UV 装机 geo / 脸层 44×32）。',
    '',
    '跑法（**游戏须完全关闭**）：',
    '    py tools/_deploy_183.py --build        # 先 ./gradlew build 再出货',
    '    py tools/_deploy_183.py                # 用 build/libs 里已构建好的包',
    '',
    '判据（任一条不过就退出，不动 mods/）：',
    '  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.83；',
    '  2. 猫耳娘该有的东西：',
    '     · geo/cat_girl.geo.json —— identifier geometry.cat_girl、贴图基准 128×128、',
    '       31 骨 / 126 方块，且**每个 cube 用逐面 uv/uv_size**；rest 姿态骨骼无旋转；',
    '     · textures/entity/cat_girl.png 是 128×128；',
    '     · animations/cat_girl.animation.json 在位，每条片段 animation_length > 0；',
    '     · Java 侧 CatGirlEntity / CatGirlGeoModel / CatGirlGeoRenderer 在 jar 里；',
    '  3. 1.1.83 本体（源码级 + 包内级）：',
    '     · 数字 = 客户端 HUD（VeinMineHighlighter.renderCount，纯观感，可单独关）；',
    '     · 份数取自与描边同一份缓存（不会框 12 个、数字说 11），含瞄准的那一格；',
    '     · 只报 2 格以上；撞 max_blocks 时文案带「已到上限」；lang 中英各一份；',
    '     · 配置 [player_mine] count 默认 true；该段 12 项、总数 169；',
    '  4. **不回归**：1.1.82 的高亮描边 / 画的一定是真会砸的；',
    '     1.1.81 的破坏即连带 / 深板岩认亲 / 潜行只挖一格；',
    '     1.1.80 的 36 格库存 / 手持物品基准旋转 / mine_depth 与 prospect；',
    '     柯尔特 1878 仍在包里且规格未变（12 骨 / 87 方块 / 512² 基准 / 8 条片段长度逐条等于 Java 常量）；',
    '  5. 工程门禁在**本机跑一遍**：tools/check_gun_resources.py 全绿才继续；',
    '  6. 基线：mods/ 里当前那个包必须是本版或上一版（按**包内 mods.toml 版本**认）；',
    '  7. 换包：旧包挪到 mods/ **同级** 的 mods_backup/（保 3 份），mods/ 里只留一个本模组包；',
    '     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）。',
    '',
    '(下面为原文，未改)',
    '"""',
)
s = s[:i] + head + s[te + 3:]

# ---- 3) 工具名 / 描述 / readme 版本断言 ----
rep("description='1.1.82 出货：玩家挖掘高亮（瞄着矿脉描青边）'",
    "description='1.1.83 出货：挖掘数字（准星下方报会连挖几格）'")
rep("check('| **当前版本** | `1.1.82` |' in _rd, 'readme 头表版本 == 1.1.82')",
    "check('| **当前版本** | `1.1.83` |' in _rd, 'readme 头表版本 == 1.1.83')")

# ---- 4) 历史段里的配置项计数跟着走（读的是当前源码，所以每版都要往前挪） ----
rep("check(_n9 == 168, '配置项总数 168（1.1.80 的 157 + 玩家一键挖掘 10 + 1.1.82 高亮 1）', '实得 %d' % _n9)",
    "check(_n9 == 169, '配置项总数 169（1.1.80 的 157 + 玩家一键挖掘 10 + 高亮 1 + 数字 1）', '实得 %d' % _n9)")
rep("check('全部 168 项配置' in _rd9, 'readme 写明图形界面共 168 项')",
    "check('全部 169 项配置' in _rd9, 'readme 写明图形界面共 169 项')")
rep("check(_n10 == 168, '配置项总数 168（1.1.81 的 167 + 高亮 1）', '实得 %d' % _n10)",
    "check(_n10 == 169, '配置项总数 169（1.1.81 的 167 + 高亮 1 + 数字 1）', '实得 %d' % _n10)")
rep("check('全部 168 项配置' in _rd10, 'readme 写明图形界面共 168 项')",
    "check('全部 169 项配置' in _rd10, 'readme 写明图形界面共 169 项')")

# ---- 5) 新断言段：插在「工程门禁」之前 ----
FRAG = 'F:/mcmod/tools/_assert_183.py'
NEW = io.open(FRAG, encoding='utf-8').read().replace(chr(10), CR)
if not NEW.endswith(CR):
    NEW += CR


rep("print('=== 最后：工程门禁（本机实跑） ===')",
    NEW + "print('=== 最后：工程门禁（本机实跑） ===')")

io.open(P183, 'w', encoding='utf-8', newline='').write(s)
print('已生成', P183, len(s), 'chars')

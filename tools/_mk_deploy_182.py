# -*- coding: utf-8 -*-
"""由 _deploy_181.py 生成 _deploy_182.py（版本号 / 头注释 / 1.1.82 断言段：挖掘高亮）。

只定点改写，不全局替换 —— _deploy_181.py 里大量的 1.1.81 / 1.1.80 是历史引用
（「1.1.81 起：玩家一键挖掘」），一起改就把历史抹了。
"""
import io

P181 = 'F:/mcmod/tools/_deploy_181.py'
P182 = 'F:/mcmod/tools/_deploy_182.py'
CR = '\r\n'
BS = chr(92)   # 0x5C，单独一个反斜杠


def L(*lines):
    return CR.join(lines) + CR


s = io.open(P181, encoding='utf-8', newline='').read()


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (s.count(old), old[:80])
    s = s.replace(old, new, n)


# ---- 1) 版本号 ----
rep("VER = '1.1.81'\r\nPREV = '1.1.80'", "VER = '1.1.82'\r\nPREV = '1.1.81'")
rep("_deploy_181.py", "_deploy_182.py", s.count("_deploy_181.py"))

# ---- 2) 头注释 ----
i = s.index('"""')  # 文件第一个三引号 = 头部 docstring
te = s.index('"""', i + 3)
head = L(
    '"""1.1.82 出货：**玩家挖掘时显示高亮**（瞄着矿脉，会连带的方块在客户端描青边；',
    '画的一定是真会砸的 —— 与服务端同一个 preview 判定；纯观感，可配置关闭）',
    '（含 1.1.81 的玩家一键挖掘 / 1.1.80 的 36 格库存与手持方向，全部不回归）',
    '（含 1.1.79 的图形配置界面 / 一键挖掘上限 64 / id 参数修复全部不回归）',
    '（猫耳娘 v4 内容不回退 —— 128² 皮肤 / 逐面 UV 装机 geo / 脸层 44×32）。',
    '',
    '跑法（**游戏须完全关闭**）：',
    '    py tools/_deploy_182.py --build        # 先 ./gradlew build 再出货',
    '    py tools/_deploy_182.py                # 用 build/libs 里已构建好的包',
    '',
    '判据（任一条不过就退出，不动 mods/）：',
    '  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.82；',
    '  2. 猫耳娘该有的东西：',
    '     · geo/cat_girl.geo.json —— identifier geometry.cat_girl、贴图基准 128×128、',
    '       31 骨 / 126 方块，且**每个 cube 用逐面 uv/uv_size**；rest 姿态骨骼无旋转；',
    '     · textures/entity/cat_girl.png 是 128×128；',
    '     · animations/cat_girl.animation.json 在位，每条片段 animation_length > 0；',
    '     · Java 侧 CatGirlEntity / CatGirlGeoModel / CatGirlGeoRenderer 在 jar 里；',
    '  3. 1.1.82 本体（源码级 + 包内级）：',
    '     · 高亮 = 客户端渲染（VeinMineHighlighter，RenderLevelStageEvent，纯观感）；',
    '     · 选块复用 PlayerVeinMine.preview —— 与「实际会砸的」同一份判定（画框 = 会砸）；',
    '     · 配置 [player_mine] highlight 默认 true；该段 11 项、总数 168；',
    '  4. **不回归**：1.1.81 的破坏即连带 / 深板岩认亲 / 潜行只挖一格；',
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
rep("description='1.1.81 出货：玩家一键挖掘（左键破坏即连带同种矿石）'",
    "description='1.1.82 出货：玩家挖掘高亮（瞄着矿脉描青边）'")
rep("check('| **当前版本** | `1.1.81` |' in _rd, 'readme 头表版本 == 1.1.81')",
    "check('| **当前版本** | `1.1.82` |' in _rd, 'readme 头表版本 == 1.1.82')")

# ---- 4) 1.1.81 那段的旧断言跟着代码走（preview 重构后变量名变了 / 配置多了一项） ----
rep("check('tool.isCorrectToolForDrops(origin)' in _vm9, '工具不对口就不连带（require_correct_tool）')",
    "check('tool.isCorrectToolForDrops(originState)' in _vm9, '工具不对口就不连带（require_correct_tool）')")
rep("check(_n9 == 167, '配置项总数 167（1.1.80 的 157 + 玩家一键挖掘 10）', '实得 %d' % _n9)",
    "check(_n9 == 168, '配置项总数 168（1.1.80 的 157 + 玩家一键挖掘 10 + 1.1.82 高亮 1）', '实得 %d' % _n9)")
rep("check('全部 167 项配置' in _rd9, 'readme 写明图形界面共 167 项')",
    "check('全部 168 项配置' in _rd9, 'readme 写明图形界面共 168 项')")

# ---- 5) 新断言段：插在「工程门禁」之前 ----
# 1.1.82 断言段整段放在 tools/_assert_182.py 里，直接读进来（避免在生成器里写一堆转义）
FRAG = 'F:/mcmod/tools/_assert_182.py'
NEW = io.open(FRAG, encoding='utf-8').read().replace(chr(10), CR)


rep("print('=== 最后：工程门禁（本机实跑） ===')",
    NEW + "print('=== 最后：工程门禁（本机实跑） ===')")

io.open(P182, 'w', encoding='utf-8', newline='').write(s)
print('已生成', P182, len(s), 'chars')

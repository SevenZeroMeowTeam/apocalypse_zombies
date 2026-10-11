# -*- coding: utf-8 -*-
"""由 _deploy_189.py 生成 _deploy_190.py（版本号 / 头注释 / readme·gradle 断言 / 段落编号 9→10 /
新增一节「子弹穿叶 / 打碎玻璃 + 猫耳娘手持物品摆正」）。

只定点改写、不全局替换 —— _deploy_189.py 里出现的 1.1.89 / 1.1.88 有些是历史引用，
一起改就把历史抹了。1.1.90 的断言段放在 tools/_assert_190.py，直接读进来（不在生成器里写转义）。
"""
import io

P189 = 'F:/mcmod/tools/_deploy_189.py'
P190 = 'F:/mcmod/tools/_deploy_190.py'
A190 = 'F:/mcmod/tools/_assert_190.py'

s = io.open(P189, encoding='utf-8', newline='').read()
CR = '\r\n' if '\r\n' in s else '\n'


def L(*lines):
    return CR.join(lines) + CR


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (s.count(old), old[:80])
    s = s.replace(old, new, n)


# ---- 1) 版本号与基线 ----
rep("VER = '1.1.89'" + CR + "PREV = '1.1.88'", "VER = '1.1.90'" + CR + "PREV = '1.1.89'")
rep("# 认三版：1.1.87（只在 GitHub 上，没装机）、1.1.88（装机在册的上一版）、本版。",
    "# 认三版：1.1.88（只在 GitHub 上，没装机）、1.1.89（装机在册的上一版）、本版。")
rep("ACCEPT = ('1.1.87', PREV, VER)", "ACCEPT = ('1.1.88', PREV, VER)")

# ---- 2) 头注释 ----
i = s.index('"""')            # 文件第一个三引号 = 头部 docstring
te = s.index('"""', i + 3)
head = L(
    '"""1.1.90 出货：**子弹穿叶 / 打碎玻璃** + **猫耳娘手持物品摆正**（1.1.80 那次多补了一步）。',
    '',
    '本版内容：新类 `item/BulletRay`（方块口径 + 两条调用路）、`Config` 新增 `bullets` 段三个开关、',
    '七把枪的射线全部改道、`BulletProjectile` 接上同一份规则、`CatGirlGeoRenderer` 去掉多补的 `YP 180`',
    '并删掉 `cat_girl.held_item_mirror` 开关，**资产一行未动**。',
    '  * **子弹与方块**：七把枪原来各抄一份的 `level.clip(... COLLIDER ...)` 收进 `BulletRay.trace()`：',
    '    命中 `minecraft:leaves` 从**叶背**接着走（按碰撞盒算出口点，1 mm 余量，最多连穿 64 块），',
    '    命中 `SoundType.GLASS` 先 `destroyBlock(pos, true)` 再按 `pass_glass` 决定停还是继续；',
    '    硬度过 -1 与带方块实体的方块不动。判据只用原版标签 / 声音类型，不写死方块 id ——',
    '    模组树叶、模组玻璃一样认。',
    '  * **实体子弹**：怪物那发的命中判定在原版 `Projectile.tick()` 里插不上手，改成命中后再改判 ——',
    '    `onHitBlock` 问 `BulletRay.resolveProjectileHit()`：叶子**不消散**、挪到叶背继续飞，',
    '    玻璃按同一份配置碎。副作用是好的：`wallDistance` 变成「到第一个真挡路方块」的距离。',
    '  * **她手里的东西**：原版实体渲染器在模型之外压了一次 `scale(-1,-1,1)`，而她的 geo 是按**翻转之后**',
    '    那个空间画的（`right_arm` 在 +X、头在 +Y 上方、刘海在 -Z）—— 所以 1.1.80 补的两步里只有第一步要：',
    '    `F · XP(-90) · YP(180) ≡ XP(-90)`（记 F = `scale(-1,-1,1)`）。多补那一步 = 再套一层 F：',
    '    物品「面」朝下、自身右轴翻到她的左 —— 就是「倒着的、跟玩家拿反了、斧刃朝里」。',
    '  * 不回归：RSC M1917（19 骨 / 577 方块 / 512² / 8 条片段）、其余 6 把枪、猫耳娘 v4、',
    '    1.1.89 的配置自动迁移与两个探针口径全部原样。',
    '',
    '跑法（**游戏须完全关闭**）：',
    '    py tools/_deploy_190.py --build        # 先 ./gradlew build 再出货',
    '    py tools/_deploy_190.py                # 用 build/libs 里已构建好的包',
    '    py tools/_deploy_190.py --no-install   # 只跑判据，不动 mods/',
    '',
    '判据（任一条不过就退出，不动 mods/）：',
    '  1. 构建产物存在、包内 mods.toml 版本 == 1.1.90；',
    '  2. 包内 RSC 资产齐全且规格正确（19 骨 / 577 方块 / 512² / 8 条片段长度逐条对得上 Java 常量），',
    '     且剪影对表过门禁（IoU ≥ 0.90、上缘 RMS ≤ 3.0 mm、下缘 RMS ≤ 5.0 mm、单列 >10 mm 的列数 == 0）；',
    '  3. 四条门禁在本机实跑全绿：rsc_1917_silhouette.py（轮廓对表）、check_gun_resources.py、',
    '     check_rsc_1917_art.py、check_rsc_1917_anim.py；',
    '  4. 不回归：另外 6 把枪的 geo/动画在包、动画文件 13 个、猫耳娘 128²、',
    '     LmStudioWire 在且 OllamaWire 已删、ai.json_schema 仍在；',
    '  5. 文档：readme 有 1.1.90 条目与头表、wiki 02/06/07 同步、gradle.properties == 1.1.90；',
    '  6. 1.1.89 本体（不回归）：迁移入口 / 调用点 / 日志都在，判定收窄，src 下 11434 只剩迁移判定，',
    '     两个探针都不再打 Ollama；',
    '  7. 1.1.90 本体：`BulletRay` 的分寸（标签 / 声音类型 / 不打不动的 / 连穿上限）、七把枪与实体子弹都换过来、',
    '     三个 `bullets.*` 键与默认值、她那条链只剩 `XP -90`、`held_item_mirror` 全库清零；',
    '  8. 基线：mods/ 里当前那个包必须是本版或上一版（按包内 mods.toml 版本认）；',
    '  9. 换包：旧包挪到 mods/ 同级 mods_backup/（保 3 份），mods/ 里只留一个本模组包；',
    '     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描）。',
    '"""',
)
s = s[:i] + head + s[te + 3:]

# ---- 3) 段落编号 9 → 10（先高后低：7~9 各往后挪一格，0~6 只换分母）----
for n in (9, 8, 7):
    rep('=== %d/9 ' % n, '=== %d/10 ' % (n + 1))
for n in (6, 5, 4, 3, 2, 1, 0):
    rep('=== %d/9 ' % n, '=== %d/10 ' % n)

# ---- 4) 文档断言改到 1.1.90 ----
rep("check('### 1.1.89 —' in rd, 'readme 有 1.1.89 条目')",
    "check('### 1.1.90 —' in rd, 'readme 有 1.1.90 条目')")
rep("check('| **当前版本** | `1.1.89` |' in rd, 'readme 头表 == 1.1.89')",
    "check('| **当前版本** | `1.1.90` |' in rd, 'readme 头表 == 1.1.90')")
rep("check('mod_version=1.1.89' in gp, 'gradle.properties mod_version=1.1.89')",
    "check('mod_version=1.1.90' in gp, 'gradle.properties mod_version=1.1.90')")

# ---- 5) 189 段里有几条「自检」查的是这个文件自己的字符串，路径得跟着改 ----
rep("open('F:/mcmod/tools/_deploy_189.py', encoding='utf-8').read()",
    "open('F:/mcmod/tools/_deploy_190.py', encoding='utf-8').read()")

# ---- 6) 插入 1.1.90 那一节（正文读 _assert_190.py，整段缩进 4 格）----
body = io.open(A190, encoding='utf-8', newline='').read().replace(CR, '\n')
frag = CR.join(('    ' + ln) if ln.strip() else '' for ln in body.split('\n')).rstrip(CR)
anchor = "    print('=== 8/10 基线校验 ===')"
rep(anchor, frag + CR + CR + anchor)

io.open(P190, 'w', encoding='utf-8', newline='').write(s)
print('生成 %s：%d 行、%d 字符（CRLF=%s）' % (P190, s.count('\n') + 1, len(s), s.count(CR) == s.count('\n')))

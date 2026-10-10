# -*- coding: utf-8 -*-
"""1.1.68 出货第二步：价格文字归位 + 面板高度定稿 + 版本 + 出货脚本 + readme。"""
import re
from pathlib import Path

J = 'src/main/java/com/apocalypse/zombies/'

# ---------- 价格文字：原来画在 y=72（库存格上方 40px），应当是紧贴库存格下方 ----------
p = Path(J + 'client/gui/CatGirlTradeScreen.java')
s = p.read_text(encoding='utf-8')
a = """                int slotX = 8 + i * 18;
                guiGraphics.drawString(this.font, text, slotX + 8 - this.font.width(text) / 2, 72, PRICE_GOLD, true);"""
b = """                int slotX = 8 + i * 18;
                // 紧贴库存格下沿（格子底 132），原来画在 y=72 会飘到「她的库存」标题上面
                guiGraphics.drawString(this.font, text, slotX + 8 - this.font.width(text) / 2, 133, PRICE_GOLD, true);"""
assert a in s, '价格文字行没找到'
s = s.replace(a, b, 1)
a = """        guiGraphics.drawString(this.font, Component.translatable("cat_girl.trade.hotbar"), 8, 121, LABEL_DARK, false);
"""
assert a in s, '快捷栏标签行没找到'
s = s.replace(a, '', 1)  # 那一行会和库存格重叠，去掉：快捷栏一眼就认得出
p.write_text(s, encoding='utf-8')
print('(1) 价格文字归位 / 去掉重叠的快捷栏标签')

# 面板高度：库存格底 132 + 价格文字到 142 → 快捷栏 146..164 → 面板 166
p = Path(J + 'entity/menu/CatGirlTradeMenu.java')
s = p.read_text(encoding='utf-8')
s = s.replace('public static final int PANEL_HEIGHT = 150;', 'public static final int PANEL_HEIGHT = 166;', 1)
s = s.replace('public static final int HOTBAR_Y = 132;', 'public static final int HOTBAR_Y = 146;', 1)
p.write_text(s, encoding='utf-8')
print('(2) PANEL_HEIGHT=166 / HOTBAR_Y=146')

# ---------- 版本 ----------
p = Path('gradle.properties'); s = p.read_text(encoding='utf-8')
assert 'mod_version=1.1.67' in s
p.write_text(s.replace('mod_version=1.1.67', 'mod_version=1.1.68'), encoding='utf-8')
print('(3) mod_version=1.1.68')

# ---------- 出货脚本 168 ----------
src = Path('tools/_deploy_167.py').read_text(encoding='utf-8')
src = src.replace('1.1.67', '1.1.68').replace('1.1.66', '1.1.67')
src = src.replace('"""1.1.68 出货：月亮事件与 Crafting Dead 同步',
                  '"""1.1.68 出货：猫耳娘交互修复（蹲下优先开界面 + 界面只显示她的部分）')
anchor = "print('=== 3/5 不回归：柯尔特 1878（1.1.67 内容不许被冲掉） ===')"
assert anchor in src, '锚点不对（注意要用替换后的 1.1.67 文案）'
new = r'''# ---- 猫耳娘交互：两套 lang 必须都有「未认主 / 非主人」提示键（这次修复的对外表现）----
for lf in ('en_us.json', 'zh_cn.json'):
    lp = 'F:/mcmod/src/main/resources/assets/apocalypse_zombies/lang/' + lf
    ls = open(lp, encoding='utf-8').read()
    check('"cat_girl.not_tame"' in ls and '"cat_girl.not_owner"' in ls,
          'lang %s 有未认主/非主人提示键' % lf)
menusrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/menu/CatGirlTradeMenu.java',
               encoding='utf-8').read()
check('HIDDEN_PLAYER_Y' in menusrc and 'HOTBAR_Y' in menusrc,
      '她的界面把玩家 27 格藏在面板外、只留快捷栏')

'''
src = src.replace(anchor, new + anchor, 1)
Path('tools/_deploy_168.py').write_text(src, encoding='utf-8')
import py_compile
py_compile.compile('tools/_deploy_168.py', doraise=True)
print('(4) tools/_deploy_168.py OK (VER=%s)' % re.search(r"VER = '([^']+)'", src).group(1))

# ---------- readme ----------
p = Path('readme.md'); s = p.read_text(encoding='utf-8')
s = s.replace('| **当前版本** | `1.1.67` |', '| **当前版本** | `1.1.68` |', 1)
entry = """### 1.1.68 — 2026-10-10

**猫耳娘交互修复**

- **蹲下右键 = 打开她的界面**：这条分支提到了 `mobInteract` 的最前面。原来它排在「喂鱼 / 交工具」
  之后，手里正好拿着斧子去蹲下点她，会被「交工具」吃掉；而 shift 状态是每 tick 同步的，
  服务端本来就有滞后 —— 分支越靠前越稳。现在蹲下永远优先。
- **点她一定会有回应**：未认主 → 提示「喂她一条鱼」；不是主人 → 提示「她只认自己的主人」；
  认主后空手 → 循环工种（跟随 / 伐木 / 挖矿 / 战斗）。原来这几种情况是静默无反应，
  看起来就像「点了没反应」。
- **她的界面只显示她自己的东西**：玩家背包那 27 格挪到面板之外（槽位仍存在，所以 shift
  一键搬进背包、关界面把给予/合成格还回玩家都照常可用），只在面板底部保留**快捷栏一行**——
  不然界面上没有任何玩家来源格，给予格和 3×3 合成就没法填。顺带修了价格文字飘在「库存」
  标题上方 40px 的错位。
- **工程**：`mod_version` → `1.1.68`；`tools/_deploy_168.py`（新增两套 lang 提示键 + 界面槽位布局判据）。

"""
if '### 1.1.67 — 2026-10-10' in s and '### 1.1.68' not in s:
    s = s.replace('### 1.1.67 — 2026-10-10', entry + '### 1.1.67 — 2026-10-10', 1)
p.write_text(s, encoding='utf-8')
print('(5) readme.md 更新')

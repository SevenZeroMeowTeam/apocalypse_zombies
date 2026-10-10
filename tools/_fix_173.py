# -*- coding: utf-8 -*-
"""修 173 两处编译错：① MoonEvent 被我削掉了缩放参数，补回；② 菜单里 broadcastChanges 重名，合并。"""
from pathlib import Path

J = 'src/main/java/com/apocalypse/zombies/'
NL = chr(10)

# ---------------- ① MoonEvent：补回每个月亮紧跟 tint 的缩放
p = Path(J + 'moon/MoonEvent.java')
s = p.read_text(encoding='utf-8')
scales = {'0xFF5555': '1.0F', '0xCC44FF': '1.65F', '0xFFE055': '1.0F',
          '0xFFCC55': '1.65F', '0x55AAFF': '1.0F', '0x88CCFF': '1.65F'}
fixed = []
for line in s.split(NL):
    stripped = line.strip()
    key = stripped.rstrip(',')
    if key in scales and stripped.endswith(',') and '0x' in line and len(stripped) <= 12:
        line = line.rstrip() + ' ' + scales[key] + ','
        fixed.append(key + ' + ' + scales[key])
    elif '0xFF5555' in line or '0xCC44FF' in line or '0xFFE055' in line or '0xFFCC55' in line or '0x55AAFF' in line or '0x88CCFF' in line:
        fixed.append('  (已成对，跳过) ' + stripped)
s = NL.join(line for line in s.split(NL))  # no-op，保持行序
lines = s.split(NL)
for i, line in enumerate(lines):
    st = line.strip()
    key = st.rstrip(',')
    if key in scales and st.endswith(',') and len(st) <= 12:
        lines[i] = line.rstrip() + ' ' + scales[key] + ','
s = NL.join(lines)
p.write_text(s, encoding='utf-8')
print('(1) MoonEvent 缩放补回：', ', '.join(fixed) if fixed else '（无需改动）')

# ---------------- ② 菜单：删掉我加的那个 broadcastChanges，改成塞进已有的那个
p = Path(J + 'entity/menu/CatGirlTradeMenu.java')
s = p.read_text(encoding='utf-8')
dup = """    @Override
    public void broadcastChanges() {
        if (this.catGirl != null && !this.player.level().isClientSide) {
            this.updateOrder();
        }
        super.broadcastChanges();
    }

    private void updateOrder() {"""
assert dup in s, '重复方法锚点'
s = s.replace(dup, '    private void updateOrder() {', 1)

old = """    public void broadcastChanges() {
        if (!this.player.level().isClientSide) {
            this.updateSellResult();
            this.updateEnchantOffer();
        }
        super.broadcastChanges();
    }"""
assert old in s, '已有 broadcastChanges 锚点'
s = s.replace(old, """    public void broadcastChanges() {
        if (!this.player.level().isClientSide) {
            this.updateSellResult();
            this.updateEnchantOffer();
            if (this.catGirl != null) {
                this.updateOrder();
            }
        }
        super.broadcastChanges();
    }""", 1)
p.write_text(s, encoding='utf-8')
print('(2) 菜单：下单逻辑并入已有的 broadcastChanges')

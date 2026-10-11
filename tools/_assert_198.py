print('=== 13/18 1.1.98：修 EasyNPC 武器商预设 ===')
# 这一版修的是「按类结构反推 SNBT」留下的两个坑，所以判据要把**官方结构**钉死：
# 交易必须在 data.TradingData.TradingDataSet 下（不是顶层），商品必须在 Offers.Recipes.Recipes 里，
# 而且六把枪都要在、每把的弹量要与 Java 里的 MAGAZINE_SIZE 逐一相等（不能各写各的）。
import os as _os
import re as _re

_P = 'F:/mcmod/src/main/resources/data/easy_npc/default_preset/villager/weapon_merchant.npc.snbt'
_s = open(_P, encoding='utf-8').read()

check(not _os.path.exists('F:/mcmod/src/main/resources/data/easy_npc/api/preset/apocalypse_zombies'),
      '旧的 api/preset/apocalypse_zombies 已删除（两个同 ID 预设会打架）')
check(_os.path.isfile(_P), '预设放在 default_preset/villager/（EasyNPC 的约定路径）')

# ---- ① 层级：TradingDataSet 必须在 TradingData 里面 ----
check('TradingData:{' in _s and 'TradingDataSet:{' in _s, '交易数据两段都在')
_i = _s.index('TradingData:{')
check('TradingDataSet:{' in _s[_i:_i + 200],
      'TradingDataSet 嵌在 TradingData 内（本版修的核心 bug）')
check(not _re.search(r'\n    TradingDataSet:\{', _s),
      '顶层没有裸的 TradingDataSet —— 原来错就错在这里，EasyNPC 读不到')

# ---- ② 商品表（标准 MerchantOffer 序列化）----
check('Offers:{' in _s, '有 Offers 段（原来整段缺失 → 空商店）')
check('Recipes:[{' in _s, 'Offers.Recipes.Recipes 是数组')
for _k in ('buy:', 'buyB:', 'sell:', 'maxUses:', 'rewardExp:', 'priceMultiplier:',
           'specialPrice:', 'demand:', 'uses:', 'xp:'):
    check(_k in _s, '商品条目含 %s' % _k)
check('Count:-1b,id:"minecraft:air"' in _s, 'buyB 用 -1b + air 表示「没有第二货币」')

# ---- ③ 六把枪都在，弹量与 Java 的 MAGAZINE_SIZE 逐一相等 ----
_WANT = {'uzi': 32, 'crossbow': 1, 's686': 2, 'mosin_nagant': 5,
         'm1_garand': 8, 'rsc_1917': 5, 'awm': 5}
check(_s.count('sell:{') == len(_WANT), '恰好 %d 条交易' % len(_WANT),
      '实得 %d' % _s.count('sell:{'))
for _gun, _ammo in sorted(_WANT.items()):
    check('id:"apocalypse_zombies:%s"' % _gun in _s, '在卖 %s' % _gun)
    check('Ammo:%d' % _ammo in _s, '%s 的弹量写的是 %d' % (_gun, _ammo))

_ITEM = 'F:/mcmod/src/main/java/com/apocalypse/zombies/item/'
for _cls, _gun in (('UziItem', 'uzi'), ('CrossbowItem', 'crossbow'), ('S686Item', 's686'),
                   ('MosinNagantItem', 'mosin_nagant'), ('M1GarandItem', 'm1_garand'),
                   ('Rsc1917Item', 'rsc_1917'), ('AWMItem', 'awm')):
    _m = _re.search(r'MAGAZINE_SIZE\s*=\s*(\d+)',
                    open(_ITEM + _cls + '.java', encoding='utf-8').read())
    check(_m is not None, '%s 有 MAGAZINE_SIZE' % _cls)
    check(int(_m.group(1)) == _WANT[_gun],
          '%s 的匣容 == 预设里的弹量 %d（两边别各写各的）' % (_cls, _WANT[_gun]),
          'Java 实得 %s' % _m.group(1))

# ---- ④ 与官方预设对齐：补齐自己漏掉的字段 ----
for _k in ('PresetUUID:[I;', 'Profession:"WEAPONSMITH"', 'SkinData:{', 'SoundData:{',
           'EntityAttribute:{', 'VariantType:"PLAINS_WEAPONSMITH"'):
    check(_k in _s, '补齐了 %s' % _k)
check('Type:"OPEN_TRADING_SCREEN"' in _s, '右键仍然是「直接开交易界面」')
check('ResetsEveryMin:30' in _s, '每 30 分钟自动补货')

# ---- ⑤ 文档 ----
_d = open('F:/mcmod/docs/EasyNPC-武器商.md', encoding='utf-8').read()
check('data.TradingData.TradingDataSet' in _d, '文档写清了正确的层级')
check('default_preset/villager/weapon_merchant.npc.snbt' in _d, '文档写的是新路径')
check('不是错误' in _d, '文档说清了导入时那两条提示不是错误')
check('挂错了层' in _d, '文档记了这次的根因')
check('welcome_coin_trader' in _d, '文档点名了拿来对照的官方预设')
_rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
check('### 1.1.98 —' in _rd, 'readme 有 1.1.98 条目')
check('| **当前版本** | `1.1.98` |' in _rd, 'readme 头表 == 1.1.98')
check('## 1.1.98 ——' in open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read(),
      'wiki 07 有 1.1.98 小节')

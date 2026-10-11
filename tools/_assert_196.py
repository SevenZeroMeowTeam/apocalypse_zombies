print('=== 11/16 1.1.96：村民自己管门与种地 ===')
# 三件事：① VillagerChores 的两件事都在（门 / 农活），且走的是**村民 tick**那一支，
# 不是往 goalSelector 里塞 Goal —— 村民的移动归 Brain 管，塞 Goal 会抢 Flag.MOVE；
# ② 门那三条最容易写漏的规矩（不碰铁门 / 两半手动同步 / 门边有活物不动手）；
# ③ 配置三项到位，两处写死的「151 项」与文档跟着改成 154。
_AI = 'F:/mcmod/src/main/java/com/apocalypse/zombies/entity/ai/VillagerChores.java'
_MOB = 'F:/mcmod/src/main/java/com/apocalypse/zombies/event/MobAiEnhanced.java'
_CFG = 'F:/mcmod/src/main/java/com/apocalypse/zombies/Config.java'

_ch = open(_AI, encoding='utf-8').read()
check('class VillagerChores' in _ch, '新增 entity/ai/VillagerChores')
check('public static void run(Villager villager, int radius, boolean doors, boolean farm)' in _ch,
      '出口是 run(村民, 半径, 管门?, 管农活?)')
# ---- 门 ----
check('instanceof DoorBlock' in _ch, '认得出门方块')
check('state.getBlock() == Blocks.IRON_DOOR' in _ch, '铁门被排除（那是玩家上锁用的，替它开=绕过门禁）')
check('level.isDay()' in _ch, '以 isDay 定目标状态：白天开、夜里关')
check('new AABB(pos).inflate(DOOR_CLEARANCE)' in _ch, '门边有活物就不动手（免得把谁夹在门里）')
check('DoubleBlockHalf.LOWER' in _ch and 'pos.above() : pos.below()' in _ch,
      '两半手动同步 —— setBlock 不会像玩家交互那样联动另一半')
check(_ch.count('setValue(DoorBlock.OPEN') == 2, '门的两半各设一次 OPEN',
      '实得 %d' % _ch.count('setValue(DoorBlock.OPEN'))
# ---- 农活 ----
check('crop.isMaxAge(state)' in _ch, '只收成熟的（isMaxAge）')
check('crop.defaultBlockState()' in _ch, '补种用作物方块的默认状态（age 0）')
check('Block.getDrops(state, level, pos, null, villager,' in _ch, '产物按原版掉落表算')
check('level.destroyBlock(pos, false, villager)' in _ch, 'destroyBlock(false) —— 掉落自己发，不发两份')
check('getInventory().addItem' in _ch, '收进村民自己的背包（与原版农民一致）')
check('Block.popResource(' in _ch, '背包装不下就丢在脚边，不让作物凭空蒸发')
for _b, _s in (('Blocks.WHEAT', 'Items.WHEAT_SEEDS'), ('Blocks.CARROTS', 'Items.CARROT'),
               ('Blocks.POTATOES', 'Items.POTATO'), ('Blocks.BEETROOTS', 'Items.BEETROOT_SEEDS')):
    check(_b in _ch and _s in _ch, '种子映射含 %s → %s' % (_b, _s))
check(_ch.count('getBaseSeedId') == 1,
      '只在注释里提到 getBaseSeedId（1.20.1 上不对外），代码里没调用它',
      '实得 %d 次' % _ch.count('getBaseSeedId'))
check('offset(-radius, -2, -radius)' in _ch, '扫描带 y 只上下探 2 格（门与庄稼都在地面附近）')

# ---- 挂载点：必须是村民 tick，不是 goalSelector ----
_mb = open(_MOB, encoding='utf-8').read()
check('import com.apocalypse.zombies.entity.ai.VillagerChores;' in _mb, 'MobAiEnhanced import 就位')
check('VillagerChores.run(villager,' in _mb, 'MobAiEnhanced 调用了它')
_iv = _mb.index('private static void tickVillager')
_seg = _mb[_iv:_iv + 1800]
check('VillagerChores.run' in _seg, '调用点在 tickVillager 里')
check('VillagerChores.run' in _seg.split('nearestThreat')[0],
      '杂活在恐慌判定**之前**跑 —— 否则一有敌人就再也不关门、不收地了')
check('goalSelector, 1, VillagerChores' not in _mb,
      '没有把它塞进 goalSelector（村民的移动归 Brain，塞 Goal 会抢 Flag.MOVE）')

# ---- 配置 ----
_cf = open(_CFG, encoding='utf-8').read()
for _f in ('AI_VILLAGER_DOOR_ENABLED', 'AI_VILLAGER_FARM_ENABLED', 'AI_VILLAGER_CHORE_RADIUS'):
    check(_cf.count(_f) == 2, '%s 在 Config 里出现 2 次（字段声明 + define）' % _f,
          '实得 %d' % _cf.count(_f))
for _k in ('"villager_door_enabled", true', '"villager_farm_enabled", true'):
    check(_k in _cf, 'define %s' % _k)
check('"villager_chore_radius", 6, 2, 24' in _cf, 'define villager_chore_radius（默认 6，域 2~24）')
check('Config.AI_VILLAGER_DOOR_ENABLED.get()' in _mb
      and 'Config.AI_VILLAGER_FARM_ENABLED.get()' in _mb
      and 'Config.AI_VILLAGER_CHORE_RADIUS.get()' in _mb, '三项都被 MobAiEnhanced 读上了')

# ---- 配置总数 151 → 154 ----
check('154 个字段' in open('F:/mcmod/src/main/java/com/apocalypse/zombies/ApocalypseZombies.java',
                           encoding='utf-8').read(), '启动自检的注释改成 154')
check('全部 154 项' in open('F:/mcmod/src/main/java/com/apocalypse/zombies/client/gui/'
                            'ApocalypseConfigScreen.java', encoding='utf-8').read(),
      '配置界面注释改成 154')
_w2 = open('F:/mcmod/docs/wiki/02-代码与资源地图.md', encoding='utf-8').read()
check('全部 154 项' in _w2, 'wiki 02 记了 154 项')
check('VillagerChores' in _w2, 'wiki 02 记了 VillagerChores')
_rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
check('全部 154 项' in _rd, 'readme 记了 154 项')
check('### 1.1.96 —' in _rd, 'readme 有 1.1.96 条目')
check('| **当前版本** | `1.1.96` |' in _rd, 'readme 头表 == 1.1.96')
check('## 1.1.96 ——' in open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read(),
      'wiki 07 有 1.1.96 小节')

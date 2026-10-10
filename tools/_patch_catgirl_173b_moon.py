# -*- coding: utf-8 -*-
"""1.1.73 第二部分（重写版）：盔甲层已在首次运行时落盘，这里只做月亮三项 ——
月相 tint 对齐 Crafting Dead / 血月主动刷怪 / 血月闸门走已有的 isBloodMoon()。"""
import re
from pathlib import Path

J = 'src/main/java/com/apocalypse/zombies/'
NL = chr(10)

# ============================================================ ① 月相 tint 对齐 CD
p = Path(J + 'moon/MoonEvent.java')
s = p.read_text(encoding='utf-8')
CD = {'BLUE_MOON': '0x55AAFF', 'SUPER_BLUE_MOON': '0x88CCFF', 'BLOOD_MOON': '0xFF5555',
      'YELLOW_MOON': '0xFFE055', 'SUPER_YELLOW_MOON': '0xFFCC55', 'SUPER_BLOOD_MOON': '0xCC44FF'}
lines = s.split(NL)
cur = None
report = []
for i, line in enumerate(lines):
    m = re.match(r'\s*([A-Z_]+)\("', line)
    if m and m.group(1) in CD:
        cur = m.group(1)
        continue
    if cur and re.match(r'\s*0x[0-9A-Fa-f]{6},', line):
        old = line.strip().rstrip(',')
        want = CD[cur]
        if old.lower() != want.lower():
            lines[i] = line.replace(old, want, 1)
            report.append('   %-18s %s -> %s' % (cur, old, want))
        cur = None
p.write_text(NL.join(lines), encoding='utf-8')
print('(1) 月相 tint 对齐 Crafting Dead：')
print(NL.join(report) if report else '   （本来就一致）')

# ============================================================ ② 血月主动刷怪
p = Path(J + 'moon/MoonEventManager.java')
s = p.read_text(encoding='utf-8')

if 'spawnBloodMoonWave' not in s:
    old = """        MoonEvent active = data.getMoonEvent();
        if (active.isActive()) {
            switch (active.getEffect()) {
                case LUCK -> applyLuck(level, active);
                case CROP_GROWTH -> growCrops(level, active);
                default -> {
                }
            }
        }"""
    assert old in s, '月亮 tick 锚点'
    s = s.replace(old, """        MoonEvent active = data.getMoonEvent();
        if (active.isActive()) {
            switch (active.getEffect()) {
                case LUCK -> applyLuck(level, active);
                case CROP_GROWTH -> growCrops(level, active);
                default -> {
                }
            }
            if (active.isBloodMoon()) {
                spawnBloodMoonWave(level);
            }
        }""", 1)

    anchor = "    /** Rolls the night's moon using the configured weights; whatever is left is an ordinary night. */"
    assert anchor in s, 'roll 锚点'
    method = '''    /** 上一次血月刷怪的 tick（全局节流）。 */
    private static long lastBloodSpawn;

    /**
     * 血月的「主动刷怪」：按 {@code blood_moon_spawn_interval} 节流，在每名玩家周围 20~40 格外
     * 找能站人的位置放 {@code blood_moon_spawn_count} 只僵尸。
     *
     * <p>刷出来的是原版僵尸 —— 尸潮的进化系统本来就会给它们叠倍率，
     * 所以血月夜里这些家伙自然比平时凶。</p>
     */
    private static void spawnBloodMoonWave(ServerLevel level) {
        if (!Config.BLOOD_MOON_SPAWN_ENABLED.get()) {
            return;
        }
        long now = level.getGameTime();
        if (now - lastBloodSpawn < Config.BLOOD_MOON_SPAWN_INTERVAL.get()) {
            return;
        }
        lastBloodSpawn = now;
        int perPlayer = Config.BLOOD_MOON_SPAWN_COUNT.get();
        for (ServerPlayer player : level.players()) {
            for (int i = 0; i < perPlayer; i++) {
                net.minecraft.util.RandomSource random = level.getRandom();
                double angle = random.nextDouble() * Math.PI * 2.0D;
                double dist = 20.0D + random.nextDouble() * 20.0D;
                int x = net.minecraft.util.Mth.floor(player.getX() + Math.cos(angle) * dist);
                int z = net.minecraft.util.Mth.floor(player.getZ() + Math.sin(angle) * dist);
                int y = level.getHeight(
                        net.minecraft.world.level.levelgen.Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z);
                net.minecraft.core.BlockPos pos = new net.minecraft.core.BlockPos(x, y, z);
                if (!level.isEmptyBlock(pos) || !level.isEmptyBlock(pos.above()) || level.isEmptyBlock(pos.below())) {
                    continue;
                }
                net.minecraft.world.entity.monster.Zombie zombie =
                        net.minecraft.world.entity.EntityType.ZOMBIE.create(level);
                if (zombie == null) {
                    continue;
                }
                zombie.moveTo(x + 0.5D, y, z + 0.5D, random.nextFloat() * 360.0F, 0.0F);
                zombie.finalizeSpawn(level, level.getCurrentDifficultyAt(pos),
                        net.minecraft.world.entity.MobSpawnType.EVENT, null, null);
                level.addFreshEntity(zombie);
            }
        }
    }

'''
    s = s.replace(anchor, method + anchor, 1)
    p.write_text(s, encoding='utf-8')
    print('(2) 血月主动刷怪：装上（间隔/数量可配，走 isBloodMoon() 闸门）')
else:
    print('(2) 血月刷怪已存在，跳过')

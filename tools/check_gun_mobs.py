# -*- coding: utf-8 -*-
"""怪物持枪开火的静态校验：把「枪自己说的话」和「怪物弹道表」对起来。

为什么需要它：这一套有**两张表**（枪里的玩家数值、GunProfile 里的怪物数值），
一旦漂开，症状是「召奬的枪有时候莫名其妙很疼」这种最难查的东西。
另外伤害类型是按字符串路径取的（`getHolderOrThrow`），写错一个字母不是编译错、
而是**第一次开枪就抛异常**，所以必须静态查出来。

四件事：
  1. 每把枪的怪物伤害 == 玩家近距离伤害 × GunProfile.MOB_DAMAGE_SCALE
  2. 每个 profile 的伤害类型路径都能在 data/.../damage_type/ 里找到
  3. 每个 profile 引用的音效都能在 ModSounds.java 里找到
  4. 弹速 × 生存时限 覆盖射程；并打印散布在典型距离上的落点半径（给人看的判据）

用法：python tools/check_gun_mobs.py
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JAVA = os.path.join(ROOT, 'src', 'main', 'java', 'com', 'apocalypse', 'zombies')
DATA = os.path.join(ROOT, 'src', 'main', 'resources', 'data', 'apocalypse_zombies')

# 「物品名 -> 那把枪的源文件」，以及枪里玩家近距离伤害的常量名
GUNS = {
    'CROSSBOW': ('item/CrossbowItem.java', 'DAMAGE_NEAR'),
    'MOSIN_NAGANT': ('item/MosinNagantItem.java', 'DAMAGE_NEAR'),
    'M1_GARAND': ('item/M1GarandItem.java', 'DAMAGE_NEAR'),
    'AWM': ('item/AWMItem.java', 'DAMAGE_NEAR'),
}

PROFILE = re.compile(
    r'GunProfile\s+(\w+)\s*=\s*new\s+GunProfile\(\s*'
    r'ModItems\.(\w+)\.get\(\),\s*([0-9.]+)F,\s*([0-9.]+)D,\s*([0-9.]+)F,\s*'
    r'([0-9]+),\s*([0-9]+),\s*([0-9.]+)F,\s*"([^"]+)",\s*'
    r'ModSounds\.(\w+),\s*ModSounds\.(\w+)\s*\)\s*;',
    re.S)


def read(path):
    with io.open(path, encoding='utf-8', newline='') as handle:
        return handle.read()


def magazine_of(gun_src):
    """从枪自己的 magazineSize() 读出弹匣容量：返回常量就追到常量的值，返回字面量直接用。"""
    body = re.search(r'magazineSize\(\)\s*\{\s*return\s+(\w+)\s*;', gun_src)
    if not body:
        return None
    token = body.group(1)
    if token.isdigit():
        return int(token)
    const = re.search(r'\b%s\s*=\s*(\d+)' % re.escape(token), gun_src)
    return int(const.group(1)) if const else None


def main():
    failures = []

    profile_src = read(os.path.join(JAVA, 'item', 'GunProfile.java'))
    scale = float(re.search(r'MOB_DAMAGE_SCALE\s*=\s*([0-9.]+)F', profile_src).group(1))
    sounds = set(re.findall(r'RegistryObject<SoundEvent>\s+(\w+)\s*=', read(
        os.path.join(JAVA, 'registry', 'ModSounds.java'))))
    damage_types = {os.path.splitext(name)[0] for name in os.listdir(
        os.path.join(DATA, 'damage_type'))}

    found = PROFILE.findall(profile_src)
    if len(found) != len(GUNS):
        failures.append('GunProfile 里解析到 %d 条 profile，预期 %d 条（改过排版？）'
                        % (len(found), len(GUNS)))

    print('MOB_DAMAGE_SCALE = %g' % scale)
    print()
    print('%-14s %8s %8s %7s %7s %7s %6s %6s' % (
        '枪', '玩家近距', '怪物', '倍率', '射程', '弹速', '冷却', '换弹'))
    for name, item, damage, rng, spread, cooldown, reload, speed, dtype, shot, reload_snd in found:
        damage, rng, spread = float(damage), float(rng), float(spread)
        cooldown, reload, speed = int(cooldown), int(reload), float(speed)

        source, const = GUNS.get(item, (None, None))
        if source is None:
            failures.append('%s 引用的物品 %s 不在 GUNS 表里，无法核对玩家数值' % (name, item))
            player_near = None
        else:
            gun_src = read(os.path.join(JAVA, source))
            hit = re.search(r'%s\s*=\s*([0-9.]+)F' % const, gun_src)
            player_near = float(hit.group(1)) if hit else None
            if player_near is None:
                failures.append('%s 里找不到 %s' % (source, const))
            elif abs(damage - player_near * scale) > 0.05:
                failures.append('%s: 怪物伤害 %g != 玩家近距离 %g × %g = %g'
                                % (name, damage, player_near, scale, player_near * scale))
            if 'magazineSize()' not in gun_src:
                failures.append('%s 没有 magazineSize()，怪物弹匣无从取值' % source)
            magazine = magazine_of(gun_src)
            if magazine is None:
                failures.append('%s 的 magazineSize() 读不出数值（返回的是常量还是字面量？）' % source)

        if dtype not in damage_types:
            failures.append('%s: 伤害类型 "%s" 在 damage_type/ 里不存在（第一次开枪就会崩）'
                            % (name, dtype))
        for sound in (shot, reload_snd):
            if sound not in sounds:
                failures.append('%s: 音效 ModSounds.%s 不存在' % (name, sound))

        # 弹速 × 生存时限 要盖得住射程，否则子弹会在打到人之前消散
        reach = speed * 60
        if reach < rng:
            failures.append('%s: 弹速 %g × 60 tick = %g 格 < 射程 %g 格'
                            % (name, speed, reach, rng))

        print('%-14s %8s %8.1f %7.2f %7.1f %7.1f %6d %6d   %s | BULLET_LIFETIME 可达 %.0f 格'
              % (name, player_near, damage, damage / player_near if player_near else 0,
                 rng, speed, cooldown, reload, dtype, reach))
        # 散布在典型交战距离上的落点半径：给人看的判据，不是断言
        for dist in (20.0, 40.0):
            if dist <= rng:
                print('      %4.0f 格处散布半径 %.2f 格（飞 %.1f tick，跑动目标需提前 %.2f 格×0.7）'
                      % (dist, dist * (spread * 3.14159265 / 180.0), dist / speed,
                         dist / speed * 0.28))
        # 持续输出：打空后必须换弹，所以一个弹匣周期内的平均秒伤
        if magazine is None:
            print('      弹匣数读不出，跳过节奏换算')
            print()
            continue
        cycle = magazine * cooldown + reload
        print('      峰值节奏 %.2f 发/秒；%d 发 + %.1fs 换弹 ⇒ 平均 %.2f 发/秒（伤害 %.2f/秒）'
              % (20.0 / cooldown, magazine, reload / 20.0, magazine / (cycle / 20.0),
                 magazine * damage / (cycle / 20.0)))
        print()

    # 事件接线与注册的存在性（这几处漏一个，功能整条不生效且不报错）
    for path, needle, why in (
            ('event/GunArmedMobs.java', 'MobSpawnEvent.FinalizeSpawn', '刷出时配枪'),
            ('event/GunArmedMobs.java', 'LivingEvent.LivingTickEvent', '补开火 Goal'),
            ('entity/GunAttackGoal.java', 'EnumSet.of(Flag.MOVE, Flag.LOOK)', '占住 MOVE 标记（用来压住近战）'),
            ('entity/CharmedZombie.java', 'new GunAttackGoal(this)', '召奬挂上开火 Goal'),
            ('registry/ModEntities.java', '"bullet"', '子弹实体注册'),
            ('client/ClientModBusEvents.java', 'ModEntities.BULLET.get()', '子弹渲染器注册'),
            ('entity/BulletProjectile.java', 'setNoGravity(true)',
             '子弹不受重力（否则远距离一定打地，弹道表全废）'),
            ('entity/BulletProjectile.java', 'MAX_LIFETIME', '子弹有生存上限，不会永远飞'),
            ('entity/GunAttackGoal.java', 'this.cooldown = profile.cooldownTicks()',
             '开完枪要归位冷却（否则 Goal 每 tick 都开火 = 连发）'),
    ):
        if needle not in read(os.path.join(JAVA, path)):
            failures.append('%s 里少了「%s」（%s）' % (path, needle, why))

    if failures:
        print('不达标项 %d 条：' % len(failures))
        for item in failures:
            print('  -', item)
        return 1
    print('全部通过：两张表一致、伤害类型与音效都存在、接线齐备。')
    return 0


if __name__ == '__main__':
    sys.exit(main())

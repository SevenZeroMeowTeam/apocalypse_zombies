# -*- coding: utf-8 -*-
"""持枪怪「近身切近战 / 走位射击 / 死亡标记 / 投掷怪免爆」的静态校验。

为什么需要它：这四项的共同症状都是**代码全对、编译全过、游戏里零反应**——
  * 让位判定写反 ⇒ 目标贴脸也占着 MOVE，近战 Goal 一次都跑不出来（无日志）；
  * 事件类漏 `@Mod.EventBusSubscriber` ⇒ 死亡标记永不挂上（无日志）；
  * `ModEffects` 没挂上 mod 总线 ⇒ 效果 id 从未注册，第一次命中就崩；
  * 效果图标尺寸不是 18×18 ⇒ 客户端切片错位，图标糊成一片（无日志）；
  * lang 键写错 ⇒ HUD 显示原始键名（无日志）。
所以每一条都必须有断言，并且**每一条断言都要有对应的变异用例**证明它真的会响。

用法：
    python tools/check_melee_and_mark.py            # 正常校验
    python tools/check_melee_and_mark.py --selftest # 变异测试：故意改坏 12 处，必须全被抓
"""
import io
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JAVA = os.path.join(ROOT, 'src', 'main', 'java', 'com', 'apocalypse', 'zombies')
RES = os.path.join(ROOT, 'src', 'main', 'resources', 'assets', 'apocalypse_zombies')

# 变异测试用的内存覆盖：{路径: 内容}。--selftest 时改这里，绝不碰真实文件。
OVERRIDE = {}
PNG_OVERRIDE = {}


def read(rel):
    """统一用「通用换行」读：锚点里写 \n 就一定能匹配，不受 CRLF 影响。"""
    if rel in OVERRIDE:
        return OVERRIDE[rel]
    with io.open(os.path.join(JAVA, rel), encoding='utf-8') as handle:
        return handle.read()


def read_resource(rel):
    if rel in OVERRIDE:
        return OVERRIDE[rel]
    with io.open(os.path.join(RES, rel), encoding='utf-8') as handle:
        return handle.read()


def read_any(rel):
    """变异测试用：json 在 resources 下，java 在 java 下。"""
    return read_resource(rel) if rel.endswith('.json') else read(rel)


def png_size(rel):
    """只读 PNG 头 24 字节取宽高：不引第三方库，也不为了断言去解码整张图。"""
    if rel in PNG_OVERRIDE:
        return PNG_OVERRIDE[rel]
    path = os.path.join(RES, rel)
    with open(path, 'rb') as handle:
        head = handle.read(24)
    if head[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    return struct.unpack('>II', head[16:24])


def body(text, method):
    """取一个方法体（按大括号配平），用来把断言限定在方法内部而不是整个文件。"""
    hit = re.search(r'\b%s\s*\([^)]*\)\s*(?:throws\s+\w+\s*)?\{' % re.escape(method), text)
    if not hit:
        return None
    start = hit.end() - 1
    depth = 0
    for index in range(start, len(text)):
        if text[index] == '{':
            depth += 1
        elif text[index] == '}':
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return None


def check_melee_handoff(fail):
    goal = read('entity/GunAttackGoal.java')
    if not re.search(r'MELEE_HANDOFF\s*=\s*[0-9.]+D', goal):
        fail('entity/GunAttackGoal.java 里没有 MELEE_HANDOFF 常量声明')
    use = body(goal, 'canUse')
    if use is None:
        fail('GunAttackGoal.canUse 读不出方法体')
    else:
        if 'Config.GUN_MELEE_HANDOFF_RANGE.get()' not in use:
            fail('GunAttackGoal.canUse 没读 Config.GUN_MELEE_HANDOFF_RANGE ⇒ 贴脸不让位')
        # 钉住「这个数真的被用来判距离」，而不是「文件里出现过这个配置名」：
        # 判据写成 if (false) 之类空壳，配置名还在，病还在。
        if not re.search(r'if\s*\(\s*(\w+)\s*>\s*0\.0D\s*&&\s*distance\s*<=\s*\1\s*\)', use):
            fail('GunAttackGoal.canUse 里没有「distance <= 让位距离（且该开关非 0）」的判断 ⇒ '
                 '近战 Goal 被饿死')
    cont = body(goal, 'canContinueToUse')
    if cont is None:
        fail('GunAttackGoal.canContinueToUse 读不出方法体')
    elif 'canUse()' not in cont:
        fail('GunAttackGoal.canContinueToUse 没有委托给 canUse ⇒ 「贴脸让位」只在接管时判一次，'
             '跑起来就不放了')
    if 'KEEP_DISTANCE' in goal:
        fail('GunAttackGoal 里还剩 KEEP_DISTANCE（旧的「被贴脸就后撤」）—— '
             '那是保持距离，不是切近战，必须删干净')


def check_mobile_fire(fail):
    goal = read('entity/GunAttackGoal.java')
    for needle, why in (
            ('STRAFE_INTERVAL = 30', '缺少换腿周期常量'),
            ('strafeSign = -this.strafeSign', '侧移没有左右交替（会一直往同一边绕圈）'),
            ('Config.GUN_STRAFE_ENABLED.get()', '游走射击开关没接上'),
            ('private void strafe()', '缺少 strafe 方法'),
    ):
        if needle not in goal:
            fail('entity/GunAttackGoal.java 少了「%s」（%s）' % (needle, why))
    strafe = body(goal, 'strafe')
    if strafe is None:
        fail('GunAttackGoal.strafe 读不出方法体')
    else:
        if 'getNavigation().moveTo(' not in strafe:
            fail('GunAttackGoal.strafe 没有下移动指令 ⇒ 射程内还是站桩')
        if re.search(r'getNavigation\(\)\.stop\(\)', strafe):
            fail('GunAttackGoal.strafe 里出现了 stop() ⇒ 走位被自己取消')
        if 'this.mob.position()' not in strafe or 'STRAFE_STEP' not in strafe:
            fail('GunAttackGoal.strafe 没有按「当前半径 + 侧向一步」取落点 ⇒ 会越绕越近或越远')
    tick = body(goal, 'tick')
    if tick is None:
        fail('GunAttackGoal.tick 读不出方法体')
    else:
        # 走位必须排在开火之前：否则换弹期间（提前 return）又会站定
        move_at = tick.find('Config.GUN_STRAFE_ENABLED.get()')
        fire_at = tick.find('this.fire(')
        if move_at < 0 or fire_at < 0 or move_at > fire_at:
            fail('GunAttackGoal.tick 里走位没有排在开火之前 ⇒ 换弹期间又站桩')


def check_blind_handoff(fail):
    goal = read('entity/GunAttackGoal.java')
    if 'Config.GUN_BLIND_HANDOFF_TICKS.get()' not in goal:
        fail('GunAttackGoal 没读 Config.GUN_BLIND_HANDOFF_TICKS ⇒ 射程内看不见目标时不肯让位')
    if 'blindTicks' not in goal:
        fail('GunAttackGoal 没有 blindTicks 计数')
    stop = body(goal, 'stop')
    if stop is None or 'this.blindTicks = 0' not in stop:
        fail('GunAttackGoal.stop 没把 blindTicks 清零 ⇒ 一旦数满就让不出通道也回不来，'
             '这条 Goal 永久失效')


def check_death_mark_effect(fail):
    effect = read('effect/DeathMarkEffect.java')
    if 'extends MobEffect' not in effect:
        fail('DeathMarkEffect 没有继承 MobEffect')
    if 'MobEffectCategory.HARMFUL' not in effect:
        fail('DeathMarkEffect 不是 HARMFUL ⇒ HUD 上不会按负面效果配色')
    # 常数要钉在「有名字的常量」上：出货门禁拿这个名字证明新代码进了 jar
    # （生产 jar 是 SRG 重映射的，原版名 DAMAGE_INDICATOR 在 jar 里搜不到）
    if 'private static final ParticleOptions MARK_PARTICLE' not in effect:
        fail('DeathMarkEffect 没有 MARK_PARTICLE 常量声明 ⇒ 出货门禁没有可钉的本模组标识符')
    if 'sendParticles(MARK_PARTICLE' not in effect:
        fail('DeathMarkEffect 没用上 MARK_PARTICLE ⇒ 常量成了摆设')


def check_death_mark_registry(fail):
    registry = read('registry/ModEffects.java')
    if 'register("death_mark"' not in registry:
        fail('ModEffects 没注册 death_mark')
    if 'ForgeRegistries.MOB_EFFECTS' not in registry:
        fail('ModEffects 用的注册表不是 MOB_EFFECTS')
    main = read('ApocalypseZombies.java')
    if 'ModEffects.register(modBus)' not in main:
        fail('ApocalypseZombies 没把 ModEffects 挂上 mod 总线 ⇒ 效果 id 从未注册，'
             '第一次命中就抛异常')


def check_death_mark_handler(fail):
    handler = read('event/DeathMarkHandler.java')
    # 行首锚定：注释掉的 @Mod.EventBusSubscriber( 不算数
    if not re.search(r'^\s*@Mod\.EventBusSubscriber\(', handler, re.M):
        fail('DeathMarkHandler 没有 @Mod.EventBusSubscriber ⇒ 永不挂上事件总线，零反应且无日志')
    if 'LivingHurtEvent' not in handler:
        fail('DeathMarkHandler 没订阅 LivingHurtEvent')
    if 'setAmount' not in handler:
        fail('DeathMarkHandler 没有 setAmount ⇒ 标记只显示不加伤')
    for needle, why in (
            ('Config.DEATH_MARK_MAX_STACKS.get()', '层数上限没走 Config（写死数字就没法调）'),
            ('ModEffects.DEATH_MARK.get()', '没有引用注册好的 DEATH_MARK'),
            ('getDirectEntity()', '没有判「是不是弹丸命中」'),
            ('getEntity() instanceof Monster', '没有限定「只有怪打出来才标记」'),
    ):
        if needle not in handler:
            fail('DeathMarkHandler 少了「%s」（%s）' % (needle, why))


def check_death_mark_assets(fail):
    icon = 'textures/mob_effect/death_mark.png'
    size = png_size(icon)
    if size is None:
        fail('%s 不存在或不是 PNG' % icon)
    elif size != (18, 18):
        fail('%s 尺寸是 %dx%d，必须是 18×18（原版 HUD 按 18×18 切片，别的尺寸会错位）'
             % ((icon,) + size))
    key = 'effect.apocalypse_zombies.death_mark'
    for lang in ('lang/zh_cn.json', 'lang/en_us.json'):
        text = read_resource(lang)
        if '"%s"' % key not in text:
            fail('%s 里没有 %s ⇒ HUD 会显示原始键名' % (lang, key))


def check_explosion_immune(fail):
    soldier = read('entity/SoldierZombie.java')
    hit = re.search(r'public\s+boolean\s+isInvulnerableTo\s*\(\s*DamageSource\s+(\w+)\s*\)', soldier)
    if not hit:
        fail('SoldierZombie 没有覆写 isInvulnerableTo ⇒ 会被自己丢的 TNT 炸死')
        return
    arg = hit.group(1)
    block = body(soldier, 'isInvulnerableTo')
    if block is None:
        fail('SoldierZombie.isInvulnerableTo 读不出方法体')
        return
    # 钉住「声明」而不只是「文件里出现过这个名字」：出货门禁要拿这个名字去 jar 里搜，
    # 名字被改掉（哪怕用法还留着）门禁就白做了。
    if 'private static final TagKey<DamageType> EXPLOSION_IMMUNITY' not in soldier:
        fail('SoldierZombie 没有 EXPLOSION_IMMUNITY 常量声明 ⇒ 出货门禁没有可钉的本模组标识符')
    if 'source.is(EXPLOSION_IMMUNITY)' not in block:
        fail('SoldierZombie.isInvulnerableTo 免的不是 EXPLOSION_IMMUNITY 那一类伤害')
    if 'super.isInvulnerableTo(%s)' % arg not in block:
        fail('SoldierZombie.isInvulnerableTo 没保留 super 判定 ⇒ 连无敌帧、抗火一起被覆盖掉')


CHECKS = [
    ('melee_handoff', check_melee_handoff),
    ('mobile_fire', check_mobile_fire),
    ('blind_handoff', check_blind_handoff),
    ('death_mark_effect', check_death_mark_effect),
    ('death_mark_registry', check_death_mark_registry),
    ('death_mark_handler', check_death_mark_handler),
    ('death_mark_assets', check_death_mark_assets),
    ('explosion_immune', check_explosion_immune),
]

# (期望被抓的检查名, 文件, 原文, 换成) —— 每条断言都要有能证明它会响的变异
MUTATIONS = [
    ('melee_handoff', 'entity/GunAttackGoal.java',
     'if (handoff > 0.0D && distance <= handoff) {', 'if (false) {'),
    ('melee_handoff', 'entity/GunAttackGoal.java',
     'return this.canUse();\n    }\n\n    @Override\n    public void start()', 'return true;\n    }\n\n    @Override\n    public void start()'),
    ('mobile_fire', 'entity/GunAttackGoal.java', 'this.strafeSign = -this.strafeSign;', ''),
    ('mobile_fire', 'entity/GunAttackGoal.java',
     'this.mob.getNavigation().moveTo(spot.x, spot.y, spot.z, STRAFE_SPEED);',
     'this.mob.getNavigation().stop();'),
    ('blind_handoff', 'entity/GunAttackGoal.java',
     'this.mob.getNavigation().stop();\n        // 让位时清零：否则「数满 40 tick」会一直成立，这条 Goal 再也不会重新接管\n        this.blindTicks = 0;',
     'this.mob.getNavigation().stop();'),
    ('death_mark_handler', 'event/DeathMarkHandler.java',
     '@Mod.EventBusSubscriber', '// @Mod.EventBusSubscriber'),
    ('death_mark_handler', 'event/DeathMarkHandler.java', 'event.setAmount(', 'noop('),
    ('death_mark_handler', 'event/DeathMarkHandler.java',
     'Config.DEATH_MARK_MAX_STACKS.get()', '3'),
    ('death_mark_registry', 'ApocalypseZombies.java', 'ModEffects.register(modBus);', ''),
    ('death_mark_registry', 'registry/ModEffects.java', 'register("death_mark"', 'register("death_mark_x"'),
    ('death_mark_assets', 'lang/zh_cn.json', 'effect.apocalypse_zombies.death_mark', 'effect.apocalypse_zombies.death_mark_x'),
    ('explosion_immune', 'entity/SoldierZombie.java',
     'private static final TagKey<DamageType> EXPLOSION_IMMUNITY = DamageTypeTags.IS_EXPLOSION;',
     'private static final TagKey<DamageType> EXPLOSION_GUARD = DamageTypeTags.IS_EXPLOSION;'),
    ('explosion_immune', 'entity/SoldierZombie.java',
     'source.is(EXPLOSION_IMMUNITY)', 'source.is(DamageTypeTags.IS_EXPLOSION)'),
    ('death_mark_effect', 'effect/DeathMarkEffect.java',
     'sendParticles(MARK_PARTICLE', 'sendParticles(ParticleTypes.DAMAGE_INDICATOR'),
]


def run():
    failures = []
    for name, check in CHECKS:
        local = []
        check(lambda message, local=local: local.append(message))
        failures.extend('[%s] %s' % (name, message) for message in local)
    return failures


def selftest():
    global OVERRIDE, PNG_OVERRIDE
    baseline = run()
    if baseline:
        print('变异测试前置检查失败：真实代码本来就不达标，先把上面几条修掉')
        for item in baseline:
            print('  -', item)
        return 1

    caught = 0
    missed = 0
    for expected, path, old, new in MUTATIONS:
        text = read_any(path)
        if old not in text:
            print('  !! 变异点找不到（校验器与代码脱节，这条变异等于没跑）: %s @ %s'
                  % (old.split('\n')[0][:60], path))
            missed += 1
            continue
        OVERRIDE = {path: text.replace(old, new, 1)}
        names = {item.split(']')[0][1:] for item in run()}
        OVERRIDE = {}
        if expected in names:
            caught += 1
        else:
            print('  !! 变异漏检: 期望 %s 报警，实际报警 %s（改坏的是 %s）'
                  % (expected, sorted(names) or '无', old.split('\n')[0][:50]))
            missed += 1
    PNG_OVERRIDE = {'textures/mob_effect/death_mark.png': (16, 16)}
    if 'death_mark_assets' in {item.split(']')[0][1:] for item in run()}:
        caught += 1
    else:
        print('  !! 变异漏检: 图标尺寸改成 16×16 没人管')
    PNG_OVERRIDE = {}
    if missed:
        print('  !! 有 %d 条变异没被消化（锚点找不到或漏检），变异测试不算通过' % missed)

    total = len(MUTATIONS) + 1
    print('变异测试：%d/%d 被抓' % (caught, total))
    return 0 if caught == total else 1


def main():
    if '--selftest' in sys.argv:
        return selftest()
    failures = run()
    if failures:
        print('不达标项 %d 条：' % len(failures))
        for item in failures:
            print('  -', item)
        return 1
    print('全部通过：近身让位、走位射击、死亡标记（效果+注册+订阅+图标+lang）、投掷怪免爆 都在位。')
    return 0


if __name__ == '__main__':
    sys.exit(main())

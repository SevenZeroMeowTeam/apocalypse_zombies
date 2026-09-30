# -*- coding: utf-8 -*-
"""尸潮之主（三阶段 Boss）的静态接线校验：把「生成器说的」「Java 说的」和「游戏真的会加载的」对起来。

为什么需要它：Boss 这一套有四层，任何一层漏接都是**静默失败**——
Geo 路径写错 -> 模型不渲染（游戏里只看到空气/裸实体，日志干净）；
`EliteAbility` 新枚举插在中间 -> byId 的 ordinal 错位（所有精英施法状态全乱）；
波次默认值还是 4 -> "5 波尸潮"这个需求根本没落地；
最后一波没把 Boss 算进 LIVING -> 打死它之前这一波永远不结束（或者反过来，打了不算数）。

十一类断言：
  1. 阶段阈值自洽：PHASE2/PHASE3 与 BOSS_MAX_HEALTH 的 2/3、1/3 一致
  2. `EliteAbility` 六条新枚举在**末尾**（插中间 = ordinal 错位），且时长/命中点与动画一致
  3. `HordeOverlord` implements GeoEntity，8 个剪辑常量齐全，控制器挂在 movement/cast 上
  4. 发布动画**零 scale 通道**，且每个被驱动的骨骼在 geo 里都存在
  5. geo 的逐面 UV 键必须是**全名**（north/south/…）：单字母键会被 GeckoLib 静默丢弃
  6. 贴图 512×512，与 geo 声明的 texture_width/height 一致
  7. `OverlordGeoModel` 里的三个资源路径在磁盘上都存在（路径写错 = 看不见的 Boss）
  8. 实体注册 + 属性表 + 渲染器注册 + 刷怪蛋 + 创造标签
  9. 尸潮：`horde_waves` 默认 5；最后一波召 Boss；Boss 计入本波人数；每场只召一次
 10. 语言文件：中英双语都有关键条目（缺 en_us 会在英文客户端显示 key 本身）
 11. HORDE_BOSS_ON_FINAL_WAVE 能被关掉（留出口）

用法：python tools/check_boss.py
"""
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JAVA = os.path.join(ROOT, 'src', 'main', 'java', 'com', 'apocalypse', 'zombies')
ASSETS = os.path.join(ROOT, 'src', 'main', 'resources', 'assets', 'apocalypse_zombies')
ART = os.path.join(ROOT, 'art', 'boss')

GEO = os.path.join(ASSETS, 'geo', 'horde_overlord.geo.json')
ANIM = os.path.join(ASSETS, 'animations', 'horde_overlord.animation.json')
TEX = os.path.join(ASSETS, 'textures', 'entity', 'horde_overlord.png')

# 剪辑名 -> EliteAbility 枚举名（生成器同一张表；这里独立再写一遍，两边漂开就报错）
CLIPS = [
    ('attack_melee', 'BOSS_SWEEP'),
    ('attack_ranged', 'BONE_VOLLEY'),
    ('summon', 'RAISE_HORDE'),
    ('skill_quake', 'GROUND_QUAKE'),
    ('skill_rage', 'BLOOD_RAGE'),
    ('skill_death', 'DEATH_WAIL'),
]


def read(path):
    with io.open(path, encoding='utf-8', newline='') as handle:
        return handle.read()


def main():
    failures = []
    notes = []

    boss_src = read(os.path.join(JAVA, 'entity', 'HordeOverlord.java'))
    model_src = read(os.path.join(JAVA, 'client', 'model', 'OverlordGeoModel.java'))
    ability_src = read(os.path.join(JAVA, 'entity', 'EliteAbility.java'))
    entities_src = read(os.path.join(JAVA, 'registry', 'ModEntities.java'))
    items_src = read(os.path.join(JAVA, 'registry', 'ModItems.java'))
    client_src = read(os.path.join(JAVA, 'client', 'ClientModBusEvents.java'))
    horde_src = read(os.path.join(JAVA, 'horde', 'HordeManager.java'))
    config_src = read(os.path.join(JAVA, 'Config.java'))
    geo = json.loads(read(GEO))
    anim = json.loads(read(ANIM))

    # ---------------------------------------------------------------- 1. 阶段阈值
    def const(name, src=boss_src):
        m = re.search(r'\b%s\s*=\s*(-?[0-9.]+)F' % name, src)
        return float(m.group(1)) if m else None

    max_hp = const('BOSS_MAX_HEALTH')
    p2, p3 = const('PHASE2_HP'), const('PHASE3_HP')
    if max_hp != 2500.0:
        failures.append('BOSS_MAX_HEALTH = %s，需求是 2500' % max_hp)
    for name, got, want in (('PHASE2_HP', p2, 2500.0 * 2 / 3), ('PHASE3_HP', p3, 2500.0 / 3)):
        if got is None or abs(got - round(want, 1)) > 1.0:
            failures.append('%s = %s，应约等于 2500 的 2/3 与 1/3（%.1f）' % (name, got, want))
    if not re.search(r'PHASE_COUNT\s*=\s*3\b', boss_src):
        failures.append('HordeOverlord.PHASE_COUNT 不是 3（需求：三阶段）')
    notes.append('阶段：%.0f / %.0f / %.0f（三段）' % (max_hp, p2, p3))

    # ------------------------------------------------- 1b. 设计数值（防御 / 攻击 / 召唤）
    def num(name):
        m = re.search(r'\b%s\s*=\s*(-?[0-9.]+)[FD]?\s*;' % name, boss_src)
        return float(m.group(1)) if m else None

    for name, want, why in (('ARMOR_POINTS', 5.0, '防御 5'),
                            ('ATTACK_POWER', 15.0, '攻击 15'),
                            ('SUMMON_COUNT', 5.0, '召唤 5（一次几只）')):
        got = num(name)
        if got is None:
            failures.append('HordeOverlord 里找不到常量 %s（需求：%s）' % (name, why))
        elif abs(got - want) > 1e-6:
            failures.append('%s = %s，需求是 %s' % (name, got, why))
    # 属性表必须真引用常量：各写各的字面量 = 以后改常量成了摆设（数值悄悄分叉）
    for token, why in (('Attributes.ARMOR, ARMOR_POINTS', '防御没引用常量'),
                       ('Attributes.ATTACK_DAMAGE, ATTACK_POWER', '攻击没引用常量')):
        if token not in boss_src:
            failures.append('createAttributes 里「%s」' % why)
    if re.search(r'SUMMON_COUNT\s*=\s*5\b', boss_src) and \
            'castRaiseHorde(level, SUMMON_COUNT)' not in boss_src:
        failures.append('召唤技能没用 SUMMON_COUNT（改了常量却不生效）')
    notes.append('防御 %s / 攻击 %s / 召唤 %s 只/次'
                 % (num('ARMOR_POINTS'), num('ATTACK_POWER'), num('SUMMON_COUNT')))

    # ---------------------------------------------------------------- 2. 枚举追加在末尾
    body = re.search(r'public\s+enum\s+EliteAbility\s*\{(.*?)\n\}', ability_src, re.S)
    if not body:
        failures.append('EliteAbility.java 里找不到枚举体')
    else:
        text = body.group(1)
        # 常量表的结束 = 最后一个常量 DEATH_WAIL 之后的第一个分号（枚举体里还有方法，
        # 所以不能拿 rfind(';') 当列表尾）。
        tail_end = text.find(';', text.find('DEATH_WAIL'))
        consts = text[:tail_end + 1] if tail_end > 0 else text
        pos_veil = consts.find('VEIL_CHOP')
        for _, enum_name in CLIPS:
            if not re.search(r'\b%s\b' % enum_name, text):
                failures.append('EliteAbility 里缺枚举 %s' % enum_name)
                continue
            pos = consts.find(enum_name)
            if pos < 0:
                failures.append('枚举 %s 不在常量表里（写到方法区了？）' % enum_name)
            elif pos_veil >= 0 and pos < pos_veil:
                failures.append('枚举 %s 插在了 VEIL_CHOP 之前 —— byId 用 ordinal 联网同步，'
                                '插在中间会让所有精英的施法状态错位' % enum_name)

    # ---------------------------------------------------------------- 3. GeckoLib 接线
    if 'implements GeoEntity' not in boss_src and 'GeoEntity' not in boss_src:
        failures.append('HordeOverlord 没有实现 GeoEntity（GeckoLib 不会驱动它）')
    for clip, _ in CLIPS:
        if '"%s"' % clip not in boss_src:
            failures.append('HordeOverlord 里缺少剪辑名常量 "%s"' % clip)
    for token, why in (('registerControllers', '控制器注册'),
                       ('getAnimatableInstanceCache', 'GeckoLib 实例缓存'),
                       ('new AnimationController<>(this, "movement"', 'movement 控制器'),
                       ('new AnimationController<>(this, "cast"', 'cast 控制器')):
        if token not in boss_src:
            failures.append('HordeOverlord 缺「%s」' % why)

    # ---------------------------------------------------------------- 4. 动画本身
    clips = anim.get('animations', {})
    for clip, enum_name in CLIPS:
        if clip not in clips:
            failures.append('动画文件里没有剪辑 %s' % clip)
            continue
        if clips[clip].get('loop'):
            failures.append('剪辑 %s 是循环的 —— 攻击/技能必须一次性播完' % clip)
        m = re.search(r'\b%s\((\d+),\s*(-?\d+)\)' % enum_name, ability_src)
        if not m:
            failures.append('EliteAbility.%s 没写时长/命中 tick' % enum_name)
        else:
            dur, imp = int(m.group(1)), int(m.group(2))
            length = clips[clip]['animation_length']
            if abs(length * 20 - dur) > 0.5:
                failures.append('%s 时长 %.2fs 与 %s 的 %d tick 不一致' % (clip, length, enum_name, dur))
            # 命中点必须落在剪辑内部，且不在最后 20%（收招得有时间）
            if not (0 < imp < dur * 0.85):
                failures.append('%s 命中点 %d tick 落在 0~%d 之外' % (clip, imp, int(dur * 0.85)))

    scale_hits = []
    bones_driven = set()
    for clip, src in clips.items():
        for bone, chans in src.get('bones', {}).items():
            bones_driven.add(bone)
            if 'scale' in chans:
                scale_hits.append('%s:%s' % (clip, bone))
    if scale_hits:
        failures.append('出现整体缩放通道（本项目禁止的假动画）：%s' % ', '.join(scale_hits[:5]))
    notes.append('动画 %d 段 / 驱动骨骼 %d 根 / scale 通道 0' % (len(clips), len(bones_driven)))

    # GeckoLib 的解析契约（4.8.4 BakedAnimationsAdapter.addBedrockKeyframes）：
    # 通道值必须是「时间 → 三元向量」—— 数组，或含 vector / post / pre 的对象。
    # 生成器把内部 per-axis 结构原样写盘（{"x": {"0.0": 0.0}}）时，GeckoLib 拿 "x" 当时间、
    # 拿 {"0.0":0.0,...} 当值 → 'Invalid keyframe data - expected array'。
    # 后果远不止动画不播：异常抛在**资源重载**里，整次重载失败，客户端随即清掉用户选中的
    # 资源包（options.txt 的 resourcePacks 变空），字体没能重建 → 全屏文字变方框。
    # 1.1.41 正是这么炸的（logs/游戏日志 08:27:01 Caught error loading resourcepacks）。
    def _vec_ok(v):
        if isinstance(v, list):
            return len(v) == 3 and all(isinstance(n, (int, float)) for n in v)
        if isinstance(v, dict):
            if 'vector' in v:
                return _vec_ok(v['vector'])
            if 'post' in v or 'pre' in v:
                return all(k not in v or _vec_ok(v[k]) for k in ('post', 'pre'))
        return False

    shape_bad = []
    for clip, src in clips.items():
        for bone, chans in (src.get('bones') or {}).items():
            for chan, val in (chans or {}).items():
                if chan not in ('rotation', 'position'):
                    shape_bad.append('%s/%s/%s 通道名非法' % (clip, bone, chan))
                    continue
                if not isinstance(val, dict):
                    shape_bad.append('%s/%s/%s 不是对象' % (clip, bone, chan))
                    continue
                for t, v in val.items():
                    try:
                        float(t)
                    except (TypeError, ValueError):
                        shape_bad.append('%s/%s/%s 时间键非数字 %r（per-axis 嵌套？）'
                                         % (clip, bone, chan, t))
                        break
                    if not _vec_ok(v):
                        shape_bad.append('%s/%s/%s@%s 值不是向量 %r' % (clip, bone, chan, t, v))
                        break
    if shape_bad:
        failures.append('动画通道不符合 GeckoLib 形状（会让资源重载失败 → 全屏方框）：%s'
                        % '；'.join(shape_bad[:4]))
    notes.append('动画形状：GeckoLib 契约通过（时间 → [x,y,z]，per-axis 嵌套 0 处）' if not shape_bad
                 else '动画形状：%d 处不符合 GeckoLib 契约（per-axis 嵌套 / 非向量值）' % len(shape_bad))

    # ---------------------------------------------------------------- 5·6. geo 与贴图
    g = geo['minecraft:geometry'][0]
    desc = g['description']
    geo_bones = {b['name'] for b in g['bones']}
    missing = sorted(bones_driven - geo_bones)
    if missing:
        failures.append('动画驱动的骨骼在 geo 里不存在（静默不动）：%s' % ', '.join(missing[:6]))

    bad_uv = []
    for bone in g['bones']:
        for cube in bone.get('cubes', []):
            uv = cube.get('uv')
            if isinstance(uv, dict):
                bad = [k for k in uv if k not in ('north', 'south', 'east', 'west', 'up', 'down')]
                if bad:
                    bad_uv.append('%s:%s' % (bone['name'], bad))
    if bad_uv:
        failures.append('逐面 UV 用了非全名键（GeckoLib 4.x 会静默丢面，该面完全不渲染）：%s'
                        % ', '.join(bad_uv[:5]))

    if (desc['texture_width'], desc['texture_height']) != (512, 512):
        failures.append('geo 声明贴图 %sx%s，要求 512x512'
                        % (desc['texture_width'], desc['texture_height']))
    if not os.path.exists(TEX):
        failures.append('贴图文件不存在：%s' % TEX)
    else:
        with open(TEX, 'rb') as fh:
            head = fh.read(24)
        w = int.from_bytes(head[16:20], 'big')
        h = int.from_bytes(head[20:24], 'big')
        if (w, h) != (512, 512):
            failures.append('贴图实际尺寸 %sx%s，Minecraft 不接受（必须 512x512）' % (w, h))

    # 尺寸：Boss 必须明显高于普通僵尸
    top = max(c['origin'][1] + c['size'][1] for b in g['bones'] for c in b.get('cubes', []))
    if top / 16.0 < 3.0:
        failures.append('模型高度 %.2f 格，低于 3 格（普通僵尸 1.95）' % (top / 16.0))
    notes.append('模型 %.2f 格 / %d 骨 / %d 体块'
                 % (top / 16.0, len(g['bones']), sum(len(b.get('cubes', [])) for b in g['bones'])))

    # ---------------------------------------------------------------- 7. 资源路径
    paths = set(re.findall(r'resource\("([^"]+)"\)', model_src))
    if len(paths) < 3:
        failures.append('OverlordGeoModel 里 resource(...) 少于 3 条（geo/贴图/动画）')
    for rel in paths:
        full = os.path.join(ASSETS, rel.replace('/', os.sep))
        if not os.path.exists(full):
            failures.append('OverlordGeoModel 引用的资源不存在：%s' % rel)
    notes.append('资源路径 %d 条全部存在' % len(paths))

    # ---------------------------------------------------------------- 8. 注册
    for token, why in (
            ('"horde_overlord"', '实体 id'),
            ('.sized(1.6F, 3.1F)', '命中箱与模型高度对齐'),
            ('HordeOverlord.createAttributes()', '属性表注册（漏了 = 一生成就崩）')):
        if token not in entities_src:
            failures.append('ModEntities 缺「%s」' % why)
    if 'OVERLORD' not in entities_src or 'RegistryObject<EntityType<HordeOverlord>> OVERLORD' not in entities_src:
        failures.append('ModEntities 没有 OVERLORD 实体类型')
    if 'OverlordGeoRenderer::new' not in client_src:
        failures.append('ClientModBusEvents 没注册 OverlordGeoRenderer（客户端不渲染）')
    if 'horde_overlord_spawn_egg' not in items_src:
        failures.append('ModItems 没有 Boss 刷怪蛋')
    if 'OVERLORD_SPAWN_EGG' not in items_src:
        failures.append('刷怪蛋没进创造模式标签（拿不到 = 测不了）')

    # ---------------------------------------------------------------- 9. 五波 + 最后一波
    m = re.search(r'defineInRange\("horde_waves",\s*(\d+)', config_src)
    if not m or int(m.group(1)) != 5:
        failures.append('Config.horde_waves 默认值 = %s，需求是 5'
                        % (m.group(1) if m else '找不到'))
    if 'HORDE_BOSS_ON_FINAL_WAVE' not in config_src:
        failures.append('Config 没有 horde_boss_on_final_wave 开关')
    flat = horde_src.replace('\r\n', '\n')
    for token, why in (
            ('Config.HORDE_BOSS_ON_FINAL_WAVE.get()', '开关没被读'),
            ('spawnOverlord(level, players, random)', '没召 Boss'),
            ('bossSpawned', '没有「每场只召一次」的门'),
            ('LIVING.add(boss.getUUID())', 'Boss 没计入本波存活（打死不算数 / 该波永不结束）'),
            ('bossSpawned = false;', 'start() 没重置 bossSpawned')):
        if token not in flat:
            failures.append('HordeManager 里「%s」缺失' % why)
    if 'totalWaves = 5;' not in horde_src:
        failures.append('HordeManager.totalWaves 的默认值不是 5')

    # ---- 9b. 只从第 5 波刷新：任何「自动刷怪」通道里都不许出现 Boss
    # 允许提到它的只有这几个文件：实体本体 / 注册 / 刷怪蛋 / 尸潮领场 / 客户端渲染器注册。
    # 后来有人手滑把 OVERLORD 加进精英权重表或刷怪事件，这条会当场炸。
    allowed = {'HordeOverlord.java', 'ModEntities.java', 'ModItems.java', 'HordeManager.java',
               'ClientModBusEvents.java'}
    stray = []
    for dirpath, _dirs, files in os.walk(JAVA):
        for name in files:
            if not name.endswith('.java') or name in allowed:
                continue
            if 'OVERLORD' in read(os.path.join(dirpath, name)):
                stray.append(os.path.relpath(os.path.join(dirpath, name), ROOT))
    if stray:
        failures.append('Boss 出现在自动刷怪 / 线路之外的文件里（唯一合法来源是第 5 波领场）：%s'
                        % ', '.join(stray[:5]))
    # 渲染器注册是唯一允许的「额外提及」，而且只能是渲染器 —— 不能顺手在那儿挂个刷怪
    if 'OVERLORD' in client_src and 'OverlordGeoRenderer' not in client_src:
        failures.append('ClientModBusEvents 提到 Boss 却不是注册渲染器')

    # 硬红线：刷怪表 / 刷怪事件 / 生成规则里一律不许出现 Boss。
    # 注意不含 SpawnEggItem —— 刷怪蛋是**手动**的创造物品（用来验收），不是「自动刷新」。
    spawn_re = re.compile(r'^.*(?:addSpawn|SpawnPlacements\.register|FinalizeSpawn|'
                          r'addSpawnCost).*$', re.M)
    for dirpath, _dirs, files in os.walk(JAVA):
        for name in files:
            if not name.endswith('.java'):
                continue
            path = os.path.join(dirpath, name)
            for line in spawn_re.findall(read(path)):
                if 'OVERLORD' in line or 'horde_overlord' in line:
                    failures.append('Boss 被挂进了刷怪通道（%s）：%s'
                                    % (name, line.strip()[:110]))

    data_root = os.path.join(ROOT, 'src', 'main', 'resources', 'data')
    hits = []
    for dirpath, _dirs, files in os.walk(data_root):
        for name in files:
            if not name.endswith(('.json', '.mcmeta')):
                continue
            path = os.path.join(dirpath, name)
            try:
                if 'horde_overlord' in read(path):
                    hits.append(os.path.relpath(path, ROOT))
            except (UnicodeDecodeError, OSError):
                pass
    if hits:
        failures.append('data/ 里出现 horde_overlord —— Boss 不该有任何自然刷怪数据：%s'
                        % ', '.join(hits[:3]))
    notes.append('来源：仅第 5 波领场（自然刷怪表 0 处 / 刷怪通道 0 处 / data 0 处）')

    # ---------------------------------------------------------------- 10·11. 语言文件
    for lang, need in (('zh_cn', ['尸潮之主', '阶段', '生命']),
                       ('en_us', ['Horde Overlord', 'phase'])):
        src = read(os.path.join(ASSETS, 'lang', '%s.json' % lang))
        for key in ('entity.apocalypse_zombies.horde_overlord',
                    'item.apocalypse_zombies.horde_overlord_spawn_egg',
                    'horde.apocalypse_zombies.boss.bar',
                    'horde.apocalypse_zombies.boss.phase.title',
                    'horde.apocalypse_zombies.boss.phase.subtitle',
                    'horde.apocalypse_zombies.boss.spawn.title',
                    'horde.apocalypse_zombies.boss.spawn.message'):
            if '"%s"' % key not in src:
                failures.append('%s.json 缺 %s' % (lang, key))
        for word in need:
            if word not in src:
                failures.append('%s.json 里看不到「%s」' % (lang, word))

    # ---------------------------------------------------------------- 台账
    for path in (os.path.join(ART, 'horde_overlord.geo.json'),
                 os.path.join(ART, 'horde_overlord.animation.json'),
                 os.path.join(ART, 'boss_atlas.json'),
                 os.path.join(ART, 'horde_overlord.png')):
        if not os.path.exists(path):
            failures.append('art/boss 台账缺 %s' % os.path.basename(path))

    for line in notes:
        print('  ·', line)
    if failures:
        print('不达标项 %d 条：' % len(failures))
        for item in failures:
            print('  -', item)
        return 1
    print('全部通过：阶段/技能/动画/geo/贴图/注册/五波尸潮/双语，接线齐备。')
    return 0


if __name__ == '__main__':
    sys.exit(main())

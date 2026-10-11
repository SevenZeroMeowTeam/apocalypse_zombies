print('=== 9/13 1.1.93：枪械音效换成项目自备录音 ===')
# 五件事：① TaCZ 的 sounds/awm/（22 个副本）已删、sounds/guns/ 17 个自备录音到位；
# ② sounds.json 每个键都指到 guns/ 下的文件、且文件真在（漏一个就是那一枪静音）；
# ③ 事件名与 Java 常量没变（七把枪的 tick→cue 时刻表因此一行都不用动），
#    两条新事件 uzi_shoot / crossbow_shoot 有人用；④ build.gradle 不再排除音效
#    （这一步决定纯净包有没有声音）；⑤ 文档同步。
import json as _json

_SND = 'F:/mcmod/src/main/resources/assets/apocalypse_zombies/sounds'
_JSON = _SND + '.json'

check(not os.path.isdir(_SND + '/awm'),
      'TaCZ 的 sounds/awm/ 目录已删除（22 个借用副本不再随包）')
_guns = sorted(f for f in os.listdir(_SND + '/guns') if f.endswith('.ogg'))
check(len(_guns) == 17, 'sounds/guns/ 里 17 个自备录音', '实得 %d' % len(_guns))
for _f in ('awp_shot_1.ogg', 'awp_reload_1.ogg', 'ak47_shot_1.ogg', 'akm_bolt_1.ogg',
           'akm_bolt_2.ogg', 'akm_reload_1.ogg', 'akm_reload_2.ogg', 'bolt_1.ogg',
           'crossbow_shot_1.ogg', 'crossbow_hit_1.ogg'):
    check(_f in _guns, 'sounds/guns/ 里有 %s' % _f)

_sj = _json.load(open(_JSON, encoding='utf-8'))
check(_sj['music_friends_wine']['sounds'][0]['stream'] is True, '背景音乐仍然是 stream')
for _k, _v in _sj.items():
    for _e in _v['sounds']:
        _n = _e['name'].split(':', 1)[1]
        _want = 'music/' if _k == 'music_friends_wine' else 'guns/'
        check(_n.startswith(_want), '%s 指向 %s（不再指向 awm/）' % (_k, _want), _n)
        check(os.path.isfile('%s/%s.ogg' % (_SND, _n)),
              '%s 的文件真的在 -> %s.ogg' % (_k, _n))
check(not any('/awm/' in e['name'] for v in _sj.values() for e in v['sounds']),
      'sounds.json 里不再有任何 awm/ 路径')

# 变体：同一条 event 下挂多支，播放时随机挑 —— 连发才不像复读
check(len(_sj['uzi_shoot']['sounds']) == 4, 'uzi_shoot 挂了 4 支 AK 录音')
check(len(_sj['crossbow_shoot']['sounds']) == 3, 'crossbow_shoot 挂了 3 支弩弦')

_ms = open('F:/mcmod/src/main/java/com/apocalypse/zombies/registry/ModSounds.java',
           encoding='utf-8').read()
for _n in ('awm_shoot', 'awm_shoot_3p', 'awm_rechamber_out', 'awm_rechamber_ejectclick',
           'awm_rechamber_in', 'awm_rechamber_end', 'awm_reload_raise', 'awm_reload_rattle',
           'awm_reload_ejectclick', 'awm_reload_magout', 'awm_reload_fast_rattle',
           'awm_reload_maghit', 'awm_reload_magin', 'awm_reload_end',
           'awm_reload_empty_raise', 'awm_reload_empty_magout', 'awm_reload_empty_mag_drop',
           'awm_reload_empty_rattle', 'awm_reload_empty_maghit', 'awm_reload_empty_magin',
           'awm_reload_empty_boltclose', 'awm_reload_empty_end', 'ammo_clip_pop'):
    check('sound("%s")' % _n in _ms, 'ModSounds 仍保留事件名 %s（时刻表契约）' % _n)
check('UZI_SHOOT = sound("uzi_shoot")' in _ms, 'ModSounds 新增 UZI_SHOOT')
check('CROSSBOW_SHOOT = sound("crossbow_shoot")' in _ms, 'ModSounds 新增 CROSSBOW_SHOOT')
check('CROSSBOW_HIT = sound("crossbow_hit")' in _ms, 'ModSounds 已注册 CROSSBOW_HIT（素材就位、暂无调用点）')
check('音源换成项目自备' in _ms, 'ModSounds 类注释声明了音源换自备（不再自称借用副本）')
check('不再排除音效' in _ms, 'ModSounds 类注释记了 borrowedEntries 的收窄')

_uzi = open('F:/mcmod/src/main/java/com/apocalypse/zombies/item/UziItem.java', encoding='utf-8').read()
check('ModSounds.UZI_SHOOT.get()' in _uzi, 'Uzi 的枪声用 UZI_SHOOT')
check('ModSounds.AWM_SHOOT' not in _uzi, 'Uzi 不再引用 AWM_SHOOT')
_cb = open('F:/mcmod/src/main/java/com/apocalypse/zombies/item/CrossbowItem.java', encoding='utf-8').read()
check('ModSounds.CROSSBOW_SHOOT.get()' in _cb, '十字弩的枪声用 CROSSBOW_SHOOT')
check('ModSounds.AWM_SHOOT' not in _cb, '十字弩不再引用 AWM_SHOOT')
_gp = open('F:/mcmod/src/main/java/com/apocalypse/zombies/item/GunProfile.java', encoding='utf-8').read()
check('ModSounds.CROSSBOW_SHOOT' in _gp, '怪物手里的弩也用 CROSSBOW_SHOOT')

_bg = open('F:/mcmod/build.gradle', encoding='utf-8').read()
_i = _bg.index('def borrowedEntries = [')
_blk = _bg[_i:_bg.index(']', _i)]
check('sounds/**' not in _blk, 'borrowedEntries 不再排除 sounds/**（纯净包从此有声音）')
check('sounds.json' not in _blk, 'borrowedEntries 不再排除 sounds.json')
check('awm.animation.json' in _blk, '转录动画仍在借用清单里（那一项还得靠手工动画兜）')
check('sounds' not in _bg[_bg.index("tasks.register('borrowedPack'"):],
      'borrowedPack 不再打包音效（只剩动画）')

for _p, _needle, _label in (
        ('F:/mcmod/readme.md', '### 1.1.93 —', 'readme 有 1.1.93 条目'),
        ('F:/mcmod/readme.md', '| **当前版本** | `1.1.93` |', 'readme 头表 == 1.1.93'),
        ('F:/mcmod/docs/wiki/07-出货与版本管理.md', '## 1.1.93 ——', 'wiki 07 有 1.1.93 小节'),
        ('F:/mcmod/docs/wiki/02-代码与资源地图.md', 'sounds/guns/', 'wiki 02 记了新的音效目录'),
        ('F:/mcmod/docs/wiki/08-CI与发布.md', '`.ogg` 数必须为 **17**', 'wiki 08 的纯净包核对改成 17'),
        ('F:/mcmod/docs/wiki/03-构建运行与排障.md', '仅转录动画一项', 'wiki 03 的产物表改了'),
        ('F:/mcmod/NOTICE.md', '1.1.93 起：音效不再借用', 'NOTICE 记了音效换源')):
    check(_needle in open(_p, encoding='utf-8').read(), _label)

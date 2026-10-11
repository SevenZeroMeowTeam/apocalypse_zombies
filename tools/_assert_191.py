print('=== 7/11 1.1.91：爆炸弹只有特效没有伤害（防递归闸补齐） ===')
# 这一版只改一处：event/AmmoEffects 里那道闸原来「只有检查、没有合闸」。
# 判据分四块：①闸的四件（声明 / 检查 / 上锁 / 解锁）都在，且各自不许有第二处；
# ②位置对（检查在事件里、上锁在 detonate 里 —— 放错位置等于没修）；
# ③try/finally 收口（异常路径也必须复位，否则闸永久锁死 = 爆炸弹连特效都没了）；
# ④口径一字未动，并且别把「士兵僵尸免疫爆炸」那个刻意设定当成同一个 bug。

_am = open('F:/mcmod/src/main/java/com/apocalypse/zombies/event/AmmoEffects.java',
           encoding='utf-8').read()

# ① 闸的四件，各自唯一
check('private static boolean detonating;' in _am, '闸的声明还在（服务端单线程，一个静态布尔就够）')
check(_am.count('detonating = true;') == 1, '上锁只有一处（多了就是新漏洞）',
      '实得 %d' % _am.count('detonating = true;'))
check(_am.count('detonating = false;') == 1, '解锁只有一处',
      '实得 %d' % _am.count('detonating = false;'))
check(_am.count('if (detonating)') == 2, '检查出现两次：事件开头一次、detonate 进门一次',
      '实得 %d' % _am.count('if (detonating)'))

# ② 位置对：检查在事件处理器里、上锁在 detonate 里 —— 这一句就是 1.1.90 缺的那行
_i_on = _am.index('public static void onLivingHurt(')
_i_det = _am.index('private static void detonate(')
_oh = _am[_i_on:_i_det]   # 事件处理器那一段
_dt = _am[_i_det:]        # detonate 那一段（到文件尾）
check('if (detonating)' in _oh, '检查那一半在 onLivingHurt 里（爆炸引发的 hurt 从这里被挡回去）')
check('detonating = true;' in _dt, '上锁那一半在 detonate 里 —— 1.1.90 缺的正是这一句')
check('detonating = false;' in _dt, '解锁也在 detonate 里')

# ③ try/finally：中途抛异常也要复位，否则闸永久锁死（那比原 bug 更难查：连特效都没了）
check(_dt.index('detonating = true;') < _dt.index('try {'), '先合闸、再进 try（顺序反了等于没受保护）')
check('finally {' in _dt and 'detonating = false;' in _dt[_dt.index('finally {'):],
      '解锁写在 finally 里（异常路径也复位）')
check(_dt.index('victim.hurt(source, damage)') < _dt.index('finally {'),
      '伤害结算在 try 内、finally 之前')

# ④ 口径一字未动（这一版只补闸，不许顺手改数值），且与「免疫爆炸」是两回事
_at = open('F:/mcmod/src/main/java/com/apocalypse/zombies/item/AmmoType.java', encoding='utf-8').read()
for _sig in ('EXPLOSION_RADIUS = 2.5D', 'EXPLOSION_DAMAGE = 14.0F', 'EXPLOSIVE_IMPACT_DAMAGE = 6.0F'):
    check(_sig in _at, 'AmmoType 口径未动：%s' % _sig)
check('victim instanceof Enemy' in _am, '爆炸仍然只伤敌对生物')
check('victim == player' in _am, '玩家自己永远不在伤害范围内')
check('damageSources().explosion(player, player)' in _am,
      '伤害来源仍是原版爆炸（击杀算玩家头上、免疫规则跟着走）')
check('destroyBlock' not in _am, '爆炸弹仍然不破坏地形（碎玻璃是 BulletRay 的事，别串台）')
check('setSecondsOnFire' in _am, '铝热弹那条点燃路径没被牵连')
_sol = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/SoldierZombie.java',
            encoding='utf-8').read()
check('DamageTypeTags.IS_EXPLOSION' in _sol,
      '士兵僵尸免疫爆炸仍是刻意设定（拿爆炸弹打它没伤害是设计，不是这个 bug）')

# 产物级：反编译 jar 里那个 class —— 确认修的是真的进了包，而不是「源码好看、包里还是旧的」
try:
    _dis = subprocess.run(['javap', '-p', '-c', '-cp', SRC,
                           'com.apocalypse.zombies.event.AmmoEffects'],
                          capture_output=True, text=True, encoding='utf-8', errors='replace')
    _bc = _dis.stdout or ''
except Exception as _e:      # javap 不在 PATH 这类环境问题：报红，但别把整个门禁崩掉
    _bc = ''
    check(False, 'javap 可用（产物级验证的前提）', str(_e)[:80])
check(_bc.count('putstatic') == 3,
      '产物级：class 里 putstatic(detonating) 恰好 3 处 —— 上锁 1 次 + finally 的正常/异常两条路各 1 次',
      '实得 %d' % _bc.count('putstatic'))
check(_bc.count('detonating:Z') == 5,
      '产物级：detonating 共 5 处引用（两处检查 getstatic + 三处 putstatic）',
      '实得 %d' % _bc.count('detonating:Z'))

# ---- 十字弩的弦（同版第二件事）----
# 三处：①静止类片段的弦必须挂在牙上（装弹后不许再弹回去）；②shoot 末帧要放弦；
# ③右键瞄准把画面交给镜片。真正的运动学由 check_crossbow_anim.py 逐帧算，这里查源码/生成器/装机数据。
import json as _json

_cb2 = open('F:/mcmod/tools/crossbow_v2.py', encoding='utf-8').read()
check('SPANNED = 1.0' in _cb2, '生成器有了「弦挂在牙上」的常量 SPANNED')
check(_cb2.count('bow_pose(p, SPANNED)') == 4,
      '四处 SPANNED 覆盖五个静止类片段（ADS_up / ADS_down 共用同一个循环体）',
      '实得 %d' % _cb2.count('bow_pose(p, SPANNED)'))
check(_cb2.count('bow_pose(p, ease)') == 2,
      'draw 与 shoot 仍走 ease（真正会经过松弛位的只有这两段）',
      '实得 %d' % _cb2.count('bow_pose(p, ease)'))

_cbow = open('F:/mcmod/src/main/java/com/apocalypse/zombies/item/CrossbowItem.java',
             encoding='utf-8').read()
check('public boolean hidesModelWhileAimed() {\n        return true;' in _cbow,
      '瞄准过半把弩与双手交给镜片（hidesModelWhileAimed = true）')
check('GunItem.SightStyle.CLEAR_SIGHT' in _cbow and 'hasScopeOverlay' in _cbow,
      '透明镜那两条契约没被牵连（仍是 CLEAR_SIGHT + hasScopeOverlay）')

_anim = _json.load(open(
    'F:/mcmod/src/main/resources/assets/apocalypse_zombies/animations/crossbow.animation.json',
    encoding='utf-8'))['animations']
check(len(_anim) == 7, '弩仍是 7 段剪辑', sorted(_anim))
for _c in ('static_idle', 'reload_tactical', 'ADS_up', 'ADS_down', 'inspect', 'shoot'):
    check('rotation' in _anim[_c]['bones'].get('string_l', {}),
          '%s 里弦有 rotation 通道（不回落松弛位 / 放弦真做了）' % _c)

# 弦缆门禁自己那个「整段只算第一帧」的缓存 bug 不许复活；判据也要留在新口径上
_cca = open('F:/mcmod/tools/check_crossbow_anim.py', encoding='utf-8').read()
check('(name, round(float(t), 6))' in _cca,
      '弦缆门禁的缓存键带时间（1.1.91 修的就是「整段只算第一帧」）')
check('SPANNED_CLIPS' in _cca and 'SPANNED_TOL' in _cca, '静止类片段的「不许离开牙」判据在位')
_teeth = open('F:/mcmod/tools/_teeth_sight_contract.py', encoding='utf-8').read()
check('关掉 hidesModelWhileAimed' in _teeth,
      '咬齿测试跟着反转（把 true 改回 false 时必须咬住）')

# 文档（这三条别漏：改完代码忘了写文档，是这套门禁最常抓到的形式主义）
_w7b = open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read()
check('十字弩的弦' in _w7b, 'wiki 07 记了十字弩这一节（含门禁那个缓存 bug）')
_w6b = open('F:/mcmod/docs/wiki/06-工具脚本手册.md', encoding='utf-8').read()
check('crossbow_anim_only.py' in _w6b, 'wiki 06 收录「只重生成动画」这个工具')
check('_deploy_191.py' in _w6b, 'wiki 06 已把最新门禁指到 191')
_w2b = open('F:/mcmod/docs/wiki/02-代码与资源地图.md', encoding='utf-8').read()
check('CrossbowItem' in _w2b and '置 true' in _w2b, 'wiki 02 记了 CrossbowItem 这次改动')

# 文档
_rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
check('### 1.1.91 —' in _rd, 'readme 有 1.1.91 条目')
check('| **当前版本** | `1.1.91` |' in _rd, 'readme 头表 == 1.1.91')
check('没有一处把它设成 `true`' in _rd, 'readme 写明根因（闸只装了一半）')
check('StackOverflowError' in _rd, 'readme 写明递归到栈溢出')
check('try/finally' in _rd, 'readme 写明 finally 收口，以及为什么不能在末尾复位')
_w7 = open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read()
check('## 1.1.91 —— 爆炸弹只有特效没有伤害' in _w7, 'wiki 07 有 1.1.91 小节')
check('一道只装了一半的闸' in _w7, 'wiki 07 写清根因')
check('SoldierZombie' in _w7 and '免疫' in _w7, 'wiki 07 提醒「免疫爆炸」是另一个设定，别混')
_w2 = open('F:/mcmod/docs/wiki/02-代码与资源地图.md', encoding='utf-8').read()
check('**1.1.91**' in _w2 and 'AmmoEffects' in _w2, 'wiki 02 代码地图记了这次补齐')
_w6 = open('F:/mcmod/docs/wiki/06-工具脚本手册.md', encoding='utf-8').read()
check('_assert_191.py' in _w6 and '_deploy_191.py' in _w6, 'wiki 06 收录本轮门禁')

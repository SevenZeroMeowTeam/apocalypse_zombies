print('=== 7/10 1.1.90：子弹穿叶 / 打碎玻璃 + 猫耳娘手持物品摆正 ===')
# 两件事的共同点都是「口径」：一是把七份一字不差抄来的射线收成一处、并给方块定规矩；
# 二是发现 1.1.80 给她的模型补错了坐标系（多补了一步 YP 180）。判据分四块：
#   ①BulletRay 本身的分寸（认标签/声音类型、不打不动的、有连穿上限）；
#   ②调用点全换（七把枪 + 实体子弹），枪文件里不留裸的 level.clip；
#   ③三个配置键与默认值；④她那条链只剩 XP -90，held_item_mirror 全库清零。

_br = open('F:/mcmod/src/main/java/com/apocalypse/zombies/item/BulletRay.java', encoding='utf-8').read()
check('public static BlockHitResult trace(Level level, Entity shooter, Vec3 from, Vec3 to)' in _br,
      'BulletRay 有玩家那条射线入口 trace()')
check('public static boolean resolveProjectileHit(Level level, Entity bullet, BlockHitResult hit)' in _br,
      'BulletRay 有实体子弹那条 resolveProjectileHit()')
check('state.is(BlockTags.LEAVES)' in _br, '树叶认原版 leaves 标签（带这个标签的模组树叶照样放行）')
check('state.getSoundType() == SoundType.GLASS' in _br, '玻璃认原版 SoundType.GLASS（不写死方块 id）')
check('getDestroySpeed(level, pos) < 0.0F' in _br and 'state.hasBlockEntity()' in _br,
      '打不动的（硬度 -1）与带方块实体的方块排除在外（子弹不该能拆家）')
check('level.destroyBlock(pos, true)' in _br,
      '碎玻璃走原版 destroyBlock(pos, true)（掉落表 / 音效 / 粒子都照原版）')
check('MAX_SKIPS' in _br and 'exitOf(' in _br, '穿叶按碰撞盒算出口点，且有连穿上限兜底')
check('ClipContext.Block.COLLIDER' in _br, '射线仍只认碰撞体（流体 / 无碰撞方块照旧不算挡路）')

# 七把在册的枪 + 那份归档副本（AWMItem_bytes）都换过来
_GUNS = ('AWMItem', 'AWMItem_bytes', 'M1GarandItem', 'MosinNagantItem',
         'Rsc1917Item', 'S686Item', 'UziItem', 'CrossbowItem')
for _g in _GUNS:
    _src = open('F:/mcmod/src/main/java/com/apocalypse/zombies/item/%s.java' % _g, encoding='utf-8').read()
    check('BulletRay.trace(level, player, eye, reach)' in _src, '%s 走 BulletRay.trace' % _g)
    check('level.clip(' not in _src, '%s 里不再有裸的 level.clip' % _g)
    check('ClipContext' not in _src, '%s 的 ClipContext 导入已清' % _g)

_bp = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/BulletProjectile.java', encoding='utf-8').read()
check('BulletRay.resolveProjectileHit(this.level(), this, result)' in _bp,
      '实体子弹撞方块时问 BulletRay（叶子不消散 / 玻璃按同一份配置碎）')

# 三个配置键与默认值
_cfg = open('F:/mcmod/src/main/java/com/apocalypse/zombies/Config.java', encoding='utf-8').read()
check('.push("bullets")' in _cfg, '配置新增 bullets 段')
for _k, _d in (('pass_leaves', 'true'), ('break_glass', 'true'), ('pass_glass', 'false')):
    check('.define("%s", %s)' % (_k, _d) in _cfg, 'bullets.%s 默认 %s' % (_k, _d))
check('BULLETS_PASS_LEAVES' in _cfg and 'BULLETS_BREAK_GLASS' in _cfg and 'BULLETS_PASS_GLASS' in _cfg,
      '三个配置值都有字段声明')

# 她那条链只剩 XP -90；多补的那一步与 held_item_mirror 开关全库清零
_ren = open('F:/mcmod/src/main/java/com/apocalypse/zombies/client/renderer/CatGirlGeoRenderer.java',
            encoding='utf-8').read()
check('poseStack.mulPose(Axis.XP.rotationDegrees(-90.0F))' in _ren, '仍是 XP -90（这一步是真的要）')
check('Axis.YP' not in _ren, '不再补 YP 180（她这套空间已经是原版「翻转之后」那个）')
check('ItemDisplayContext.THIRD_PERSON_RIGHT_HAND' in _ren and 'THIRD_PERSON_LEFT_HAND' not in _ren,
      '走右手 display 上下文（镜像那条路已删）')
_hm = []
for _root, _dirs, _files in os.walk('F:/mcmod/src'):
    for _f in _files:
        if _f.endswith('.java'):
            _p2 = os.path.join(_root, _f)
            if 'held_item_mirror' in open(_p2, encoding='utf-8').read():
                _hm.append(os.path.relpath(_p2, 'F:/mcmod').replace('\\', '/'))
check(not _hm, 'held_item_mirror 在 src 下已清零（开关退休）', _hm or '清零')

# 文档
_rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
check('### 1.1.90 —' in _rd, 'readme 有 1.1.90 条目')
check('| **当前版本** | `1.1.90` |' in _rd, 'readme 头表 == 1.1.90')
check('bullets.pass_leaves' in _rd and 'bullets.break_glass' in _rd, 'readme 写明两个 bullets 开关')
check('这个开关随之退休' in _rd and 'held_item_mirror' in _rd, 'readme 写明镜像开关退休')
check('`cat_girl.held_item_mirror`（默认 false）' in _rd and '**1.1.90 已删这个开关**' in _rd,
      'readme 1.1.80 那段加了「已被换掉」的指路')
_w7 = open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read()
check('## 1.1.90 —— 子弹穿叶 / 打碎玻璃' in _w7, 'wiki 07 有 1.1.90 小节')
check('F · XP(-90) · YP(180) ≡ XP(-90)' in _w7, 'wiki 07 记了坐标系那步推导（后人别再补错）')
check('**1.1.90 已删**' in _w7, 'wiki 07 的 1.1.80 段也加了指路')
_w2 = open('F:/mcmod/docs/wiki/02-代码与资源地图.md', encoding='utf-8').read()
check('BulletRay' in _w2 and 'BulletRay.resolveProjectileHit' in _w2, 'wiki 02 代码地图收录 BulletRay 与两条调用路')
_w6 = open('F:/mcmod/docs/wiki/06-工具脚本手册.md', encoding='utf-8').read()
check('_assert_190.py' in _w6 and '_deploy_190.py' in _w6, 'wiki 06 收录本轮门禁')

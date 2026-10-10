print('=== 13/10 1.1.82：玩家挖掘高亮（描边跟着「真的会砸的」走） ===')
_hl = open(_p + 'client/renderer/VeinMineHighlighter.java', encoding='utf-8').read()
check('RenderLevelStageEvent' in _hl and 'AFTER_TRANSLUCENT_BLOCKS' in _hl,
      '高亮挂在渲染阶段事件上（客户端逐帧画）')
check('PlayerVeinMine.preview(' in _hl,
      '选块复用服务端同一份 preview —— 画出来的框 = 真的会砸的')
check('RenderType.lines()' in _hl and 'endVertex()' in _hl,
      '线框走 RenderType.lines（描边，不是贴图）')
check('Config.PLAYER_MINE_HIGHLIGHT' in _hl and 'Config.PLAYER_MINE_ENABLED' in _hl,
      '高亮本身可配置关掉（纯观感）')
check('renderBuffers().bufferSource()' in _hl and 'endBatch' in _hl,
      '1.20.1 借主渲染缓冲并即时 flush（该版事件不带 MultiBufferSource）')
check('cachedPos' in _hl and 'cachedKey' in _hl, '瞄准格/配置没变就不重算（不卡）')
check('target.equals(pos)' in _hl, '不画瞄准那一格（留给原版黑框，避免同像素打架）')

_ce = open(_p + 'client/ClientEvents.java', encoding='utf-8').read()
check('VeinMineHighlighter.render(event)' in _ce,
      'ClientEvents 每帧调用高亮（客户端类，服务端不加载）')

_vm10 = open(_p + 'event/PlayerVeinMine.java', encoding='utf-8').read()
check('public static List<BlockPos> preview(' in _vm10,
      'PlayerVeinMine.preview 是「会砸哪些」的唯一出口（服务端 + 客户端共用）')
check('LevelReader' in _vm10 and 'ServerLevel level' in _vm10,
      '同一份逻辑兼容 ServerLevel 与客户端 ClientLevel')

_cfg10 = open(_p + 'Config.java', encoding='utf-8').read()
import re as _re10
_n10 = len(_re10.findall(r'public static final ForgeConfigSpec\.[A-Za-z<>?,\s\.]+?\s+[A-Z_0-9]+\s*;', _cfg10))
check(_n10 == 168, '配置项总数 168（1.1.81 的 167 + 高亮 1）', '实得 %d' % _n10)
check('define("highlight", true)' in _cfg10, 'highlight 默认 true（开启）')
check('PLAYER_MINE_HIGHLIGHT' in _cfg10, 'Config 有字段 PLAYER_MINE_HIGHLIGHT')

with zipfile.ZipFile(SRC) as _z10:
    _n10l = _z10.namelist()
    _hlname = 'com/apocalypse/zombies/client/renderer/VeinMineHighlighter.class'
    _hlcls = _z10.read(_hlname) if _hlname in _n10l else b''
    _cfgcls10 = _z10.read('com/apocalypse/zombies/Config.class')
    _vmcls10 = _z10.read('com/apocalypse/zombies/event/PlayerVeinMine.class')
check(_hlcls != b'', 'VeinMineHighlighter.class 进包了')
check(b'highlight' in _cfgcls10, 'Config.class 内含配置名字面量 highlight')
check(b'preview' in _vmcls10, 'PlayerVeinMine.class 里有 preview（服务端/客户端共用出口）')

_rd10 = open('F:/mcmod/readme.md', encoding='utf-8').read()
check('### 1.1.82 —' in _rd10, 'readme 有 1.1.82 更新日志条目')
check('高亮' in _rd10 and 'highlight' in _rd10, 'readme 写明高亮与配置项')
check('全部 168 项配置' in _rd10, 'readme 写明图形界面共 168 项')

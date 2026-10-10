print('=== 14/10 1.1.83：挖掘数字（准星下方报「会连挖几格」） ===')
_hl2 = open(_p + 'client/renderer/VeinMineHighlighter.java', encoding='utf-8').read()
check('public static void renderCount(GuiGraphics graphics, Minecraft minecraft)' in _hl2,
      'renderCount 是数字的出口（HUD 阶段画）')
check('hud.apocalypse_zombies.vein_count' in _hl2,
      '数字走 lang 词条（中英各一份）')
check('hud.apocalypse_zombies.vein_count_capped' in _hl2 and 'PLAYER_MINE_MAX_BLOCKS' in _hl2,
      '到 max_blocks 上限时补一句「已到上限」')
check('Component.translatable(' in _hl2, '用可翻译组件，不写死字符串')
check('minecraft.screen != null' in _hl2,
      '开着背包/箱子时不往准星上贴字')
check('graphics.guiWidth() / 2 - minecraft.font.width(text) / 2' in _hl2,
      '数字水平居中于准星')
check('COUNT_OFFSET_Y' in _hl2, '数字画在准星下方（不压准星）')
check('Config.PLAYER_MINE_COUNT' in _hl2, '数字有自己的开关（与描边各管各的）')
check('ensureCache(minecraft)' in _hl2 and _hl2.count('ensureCache(') >= 3,
      '描边与数字共用同一份缓存（不会框 12 个、数字说 11）')
check('cached.size() <= 1' in _hl2, '只报 2 格以上（一格时原版本来就这样）')

# 潜行那条谎：判定必须收在 preview 这个共用出口里
check('preview(LevelReader level, BlockPos origin, ItemStack tool, boolean sneaking)' in
      open(_p + 'event/PlayerVeinMine.java', encoding='utf-8').read(),
      'preview 收下 sneaking —— 客户端才可能算出「潜行只砸一格」')
check('player.isShiftKeyDown()' in _hl2 and 'Config.PLAYER_MINE_SNEAK_DISABLES' in _hl2,
      '缓存键含潜行状态（蹲下立刻重算）')

_lg = open('F:/mcmod/src/main/resources/assets/apocalypse_zombies/lang/zh_cn.json',
           encoding='utf-8').read()
_lg_en = open('F:/mcmod/src/main/resources/assets/apocalypse_zombies/lang/en_us.json',
              encoding='utf-8').read()
check('hud.apocalypse_zombies.vein_count' in _lg and '会连挖 %s 格' in _lg,
      'zh_cn 有「会连挖 %s 格」')
check('hud.apocalypse_zombies.vein_count_capped' in _lg, 'zh_cn 有「已到上限」那条')
check('hud.apocalypse_zombies.vein_count' in _lg_en, 'en_us 也有（不是只有中文能看）')

_cfg11 = open(_p + 'Config.java', encoding='utf-8').read()
import re as _re11
_n11 = len(_re11.findall(
    r'public static final ForgeConfigSpec\.[A-Za-z<>?,\s\.]+?\s+[A-Z_0-9]+\s*;', _cfg11))
check(_n11 == 169, '配置项总数 169（1.1.82 的 168 + 数字 1）', '实得 %d' % _n11)
check('define("count", true)' in _cfg11, 'count 默认 true（开启）')
check('PLAYER_MINE_COUNT' in _cfg11, 'Config 有字段 PLAYER_MINE_COUNT')

with zipfile.ZipFile(SRC) as _z11:
    _n11l = _z11.namelist()
    _hlcls2 = _z11.read('com/apocalypse/zombies/client/renderer/VeinMineHighlighter.class')
    _cfgcls11 = _z11.read('com/apocalypse/zombies/Config.class')
    _lgcls = _z11.read('assets/apocalypse_zombies/lang/zh_cn.json').decode('utf-8')
check(b'renderCount' in _hlcls2, 'VeinMineHighlighter.class 里有 renderCount')
check(b'count' in _cfgcls11, 'Config.class 内含配置名字面量 count')
check('会连挖' in _lgcls, 'lang 词条进包了（不是只在源码里）')

_ce11 = open(_p + 'client/ClientEvents.java', encoding='utf-8').read()
check('VeinMineHighlighter.renderCount(graphics, minecraft)' in _ce11,
      'ClientEvents 每帧调数字（渲染与 HUD 都挂上了）')

_rd11 = open('F:/mcmod/readme.md', encoding='utf-8').read()
check('### 1.1.83 —' in _rd11, 'readme 有 1.1.83 更新日志条目')
check('`count`' in _rd11 and '会连挖' in _rd11, 'readme 写明 count 与数字文案')
check('全部 169 项配置' in _rd11, 'readme 写明图形界面共 169 项')

"""从 _deploy_178.py 派生出 _deploy_179.py（1.1.79：配置界面 + 一键挖掘上限 64）。

只做「定点改写」而不是全局替换 1.1.78→1.1.79：文件里大量 1.1.78 是**历史引用**
（「1.1.78 起规则在 CatGirlHarvest」这类护栏说明），一起改掉就把历史抹了。

跑法：py tools/_mk_deploy_179.py
"""
import io
import pathlib

SRC = pathlib.Path('F:/mcmod/tools/_deploy_178.py')
DST = pathlib.Path('F:/mcmod/tools/_deploy_179.py')

s = SRC.read_text(encoding='utf-8', newline='')

DOC = ("\"\"\"1.1.79 出货：**图形配置界面**（模组列表 → 配置按钮，151 项分组可改，写回同一份 TOML）"
       "+ **一键挖掘上限收到 64**（cat_girl.mine_max_blocks 默认 64 / 范围 1~64）"
       "（含 1.1.78 的镐子 / 一键挖掘 / 工作方块 与 1.1.77 全部不回归）"
       "（猫耳娘 v4 内容不回退 —— 128² 皮肤 / 逐面 UV 装机 geo / 脸层 44×32）。")
start = s.index('"""')
end = s.index('"""', start + 3) + 3
old_doc = s[start:end]
assert '1.1.78 出货' in old_doc, old_doc[:80]
# 只换首行（概述），下面的跑法/判据清单是历史沉淀，保留
nl = '\r\n' if '\r\n' in old_doc else '\n'
s = s[:start] + DOC + old_doc[old_doc.index(nl):] + s[end:]

edits = [
    # 1.1.73 时代那条断言当年钉的是「craft 的物品参数是 StringArgumentType.word()」——
    # 而 word() 恰恰收不下带命名空间的 id（1.1.79 才发现的真 bug）。改钉成资源路径参数。
    # 注意：_deploy_178.py 是 CRLF，单行替换才不会踩换行符。
    ("'StringArgumentType.word()' in cmdsrc,", "'ResourceLocationArgument.id()' in cmdsrc,"),
    ("'/apocalypse catgirl craft <物品id> [数量] 在')",
     "'/apocalypse catgirl craft <物品id> [数量] 在（1.1.79 起 id 走 ResourceLocationArgument）')"),
    ('jar 内 mods.toml 的 version == 1.1.77；', 'jar 内 mods.toml 的 version == 1.1.79；'),
    ("VER = '1.1.78'", "VER = '1.1.79'"),
    ("PREV = '1.1.77'", "PREV = '1.1.78'"),
    ("description='1.1.78 出货：全功能镐子 + 一键挖掘 + 工作方块'",
     "description='1.1.79 出货：配置界面 + 一键挖掘上限 64'"),
    # 上限口径改成 64（1.1.79 的用户要求），并把消息改对
    ("check('defineInRange(\"mine_max_blocks\", 256, 1, 4096)' in _cfg5, '一键挖掘数量上限默认 256（1~4096）')",
     "check('defineInRange(\"mine_max_blocks\", 64, 1, 64)' in _cfg5, '一键挖掘数量上限默认 64（1~64）')"),
    ("check('| **当前版本** | `1.1.78` |' in _rd, 'readme 头表版本 == 1.1.78')",
     "check('| **当前版本** | `1.1.79` |' in _rd, 'readme 头表版本 == 1.1.79')"),
]

for old, new in edits:
    assert old in s, '定点改写没命中：%r' % (old[:60],)
    s = s.replace(old, new, 1)

# 自指脚本名：整份文件里 177 只剩「跑法」注释那两处（已随 docstring 一起重写）
s = s.replace('_deploy_177.py', '_deploy_179.py')

NEW_SECTION = '''print('=== 11/9 1.1.79：图形配置界面 + 一键挖掘上限 64 ===')
_p = 'F:/mcmod/src/main/java/com/apocalypse/zombies/'
_cfg6 = open(_p + 'Config.java', encoding='utf-8').read()
check('defineInRange("mine_max_blocks", 64, 1, 64)' in _cfg6,
      '一键挖掘上限默认 64、范围 1~64（用户口径：上限 64 个）')
check('public static java.util.List<ForgeConfigSpec.ConfigValue<?>> values()' in _cfg6
      and 'getDeclaredFields()' in _cfg6,
      'Config.values() 按声明顺序反射列配置项（界面照着它排，不赌 nightconfig 叶子类型）')

_scr = pathlib.Path('F:/mcmod/src/main/java/com/apocalypse/zombies/client/gui/ApocalypseConfigScreen.java')
_reg = pathlib.Path('F:/mcmod/src/main/java/com/apocalypse/zombies/client/ModConfigScreens.java')
check(_scr.is_file() and _reg.is_file(), '配置界面两个新类在源码里')
check(any(n.endswith('client/gui/ApocalypseConfigScreen.class') for n in names),
      '进包：ApocalypseConfigScreen.class')
check(any(n.endswith('client/ModConfigScreens.class') for n in names), '进包：ModConfigScreens.class')
_scs = _scr.read_text(encoding='utf-8') if _scr.is_file() else ''
check('extends Screen' in _scs and 'Config.values()' in _scs,
      '界面本体：Screen + 直接读 Config.values()（列的就是那 151 项）')
check('Config.SPEC.save()' in _scs, '点「完成」写回同一份 TOML（不是第二套配置）')
check('case BOOL' in _scs and 'case NUM' in _scs and 'case LIST' in _scs and 'case TEXT' in _scs,
      '布尔 / 数字 / 列表 / 文本 各有对口控件')
check('mouseScrolled' in _scs, '滚轮翻页（151 项一屏放不下）')
check('stash()' in _scs, '翻页前先把输入框抄回行草稿（否则滚一下就丢字）')
check('cat_girl.config.bad_number' in _scs, '填错就提示，整屏不半途写坏')
check('getDefault()' in _scs and 'resetDefaults' in _scs, '有「恢复默认」')
_regs = _reg.read_text(encoding='utf-8') if _reg.is_file() else ''
check('registerExtensionPoint(' in _regs and 'ConfigScreenHandler.ConfigScreenFactory' in _regs,
      '挂在「模组列表 → 配置」按钮上（ConfigScreenFactory 扩展点）')
_main = open(_p + 'ApocalypseZombies.java', encoding='utf-8').read()
check('DistExecutor.unsafeRunWhenOn(Dist.CLIENT' in _main, '注册走 DistExecutor —— 专用服务器上不加载客户端类')
check('ModConfigScreens::register' in _main, '服务器分支永不触碰那个类（连加载都不会）')
# 这一条是 1.1.79 实机撞出来的：构造阶段读配置值 → IllegalStateException: Cannot get config value
# before config is loaded → 专用服务器直接起不来。
check('onConfigLoaded(ModConfigEvent.Loading event)' in _main
      and 'modBus.addListener(this::onConfigLoaded)' in _main,
      '运行期真值在「配置已 load」的回调里读（构造里读会抛 Cannot get config value before config is loaded）')
check('LOGGER.info("Cat girl mining: mine_max_blocks=' in _main,
      '启动日志写出夹完的运行期真值（实机探针认这一行）')
check('Config registry: {} entries' in _main and 'Config.values().size()' in _main,
      '启动自检写出枚举器真机数出的项数')
_probe = pathlib.Path('F:/mcmod/tools/rcon_catgirl_config_probe.py')
check(_probe.is_file() and '--stage' in _probe.read_text(encoding='utf-8'),
      '1.1.79 实机探针在位（两段跑：default / clamped）')
_cmd = open(_p + 'command/ApocalypseCommand.java', encoding='utf-8').read()
check('getId(context, "block")' in _cmd and 'getId(context, "item")' in _cmd,
      'mine 的方块参数与 craft 的物品参数都换成 ResourceLocationArgument ——'
      ' StringArgumentType 的不带引号形式不收 `minecraft:` 前缀（实机报 trailing data），'
      ' 而提示里让你写的正是 `minecraft:diamond_pickaxe` 那种 id')
check('StringArgumentType.word()' not in _cmd,
      '整条命令树里没有残留的 word() 参数（就是那个老 bug 的根）')
for _lf in ('en_us.json', 'zh_cn.json'):
    _ls = open('F:/mcmod/src/main/resources/assets/apocalypse_zombies/lang/' + _lf, encoding='utf-8').read()
    for _k in ('cat_girl.config.title', 'cat_girl.config.done', 'cat_girl.config.cancel',
               'cat_girl.config.reset', 'cat_girl.config.on', 'cat_girl.config.off',
               'cat_girl.config.saved', 'cat_girl.config.bad_number'):
        check('"%s"' % _k in _ls, 'lang %s 有 %s' % (_lf, _k))

_rd6 = open('F:/mcmod/readme.md', encoding='utf-8').read()
check('### 1.1.79 —' in _rd6, 'readme 有 1.1.79 更新日志条目')
check('默认 64' in _rd6 and 'cat_girl.mine_max_blocks' in _rd6, 'readme 写明上限默认 64')
check('配置' in _rd6 and '图形界面' in _rd6, 'readme 写明「模组列表 → 配置」图形界面')
check('mine_radius' in _rd6, 'readme 仍写明范围配置项')

'''

anchor = "print('=== 最后：工程门禁（本机实跑） ===')"
assert anchor in s
s = s.replace(anchor, NEW_SECTION + anchor, 1)

DST.write_text(s, encoding='utf-8', newline='')
print('已写出', DST, len(s.splitlines()), '行')

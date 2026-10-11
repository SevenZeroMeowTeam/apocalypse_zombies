print('=== 6/9 1.1.89：老实例的本地 AI 端点自动迁移（Ollama 口径 → LM Studio 口径） ===')
# 这一版的根因不在模组、在磁盘：Forge 的配置只写默认值、**从不覆盖已经存在的值**，
# 所以 1.1.84 把接线换成 LM Studio 之后，老实例的 apocalypse_zombies-common.toml 里
# 仍旧躺着 1.1.76 写下的 endpoint = http://127.0.0.1:11434 与 Ollama 形状的模型名，
# 表现就是「注释是新的、值是旧的」。判据分三层：
#   ①迁移入口与调用点都在（且挂在「配置已进内存」之后）；
#   ②判定收窄（用户自己填的地址/模型名不许被改掉）；
#   ③src 下旧值只在迁移判定里出现 —— 别处再冒出来就是接线没清干净。

_cfg = open('F:/mcmod/src/main/java/com/apocalypse/zombies/Config.java', encoding='utf-8').read()
check('public static String migrateLegacyAiConfig()' in _cfg,
      'Config 有一次性迁移入口 migrateLegacyAiConfig()')
check('http://127.0.0.1:11434' in _cfg and 'http://localhost:11434' in _cfg,
      '迁移认得那套旧 Ollama 默认值（127.0.0.1 与 localhost 两种写法）')
check('/api/chat' in _cfg and '/api/generate' in _cfg,
      '连旧写法里的 /api/chat、/api/generate 尾巴也认（老配置里真出现过）')
check('isOllamaShapedModel' in _cfg,
      '模型名只按「旧默认那个」或 Ollama 的 :量化标签 形状认（LM Studio 的 作者/模型 不动）')
check('SPEC.save()' in _cfg, '改完让 Forge 把文件按新值重写（只在内存里改等于没改）')

_M = open('F:/mcmod/src/main/java/com/apocalypse/zombies/ApocalypseZombies.java', encoding='utf-8').read()
check('Config.migrateLegacyAiConfig()' in _M, '在 ApocalypseZombies 里被调用')
check('event.getConfig().getSpec() == Config.SPEC' in _M, '只在自家 spec 上跑（别人的配置不碰）')
check('ModConfigEvent.Loading' in _M and _M.index('ModConfigEvent.Loading') < _M.index('migrateLegacyAiConfig'),
      '挂在「配置已进内存」之后（构造阶段读值会抛 Cannot get config value before config is loaded）')
check('Migrated legacy cat_girl.ai config' in _M, '迁移发生时会写一行日志（实机探针认这一行）')

# src 下 11434 只许出现在迁移判定与其注释里
_old = []
for _root, _dirs, _files in os.walk('F:/mcmod/src'):
    for _f in _files:
        if _f.endswith('.java'):
            _p2 = os.path.join(_root, _f)
            if '11434' in open(_p2, encoding='utf-8').read():
                _old.append(os.path.relpath(_p2, 'F:/mcmod').replace('\\', '/'))
check(sorted(_old) == ['src/main/java/com/apocalypse/zombies/Config.java'],
      'src 下 11434 只出现在迁移判定里（没有残留的 Ollama 接线）', _old)

# 两个探针也得跟着换口径 —— 留着打 Ollama 的话，「本地模型体检」自己先坏了
_pp = open('F:/mcmod/tools/_ai_probe.py', encoding='utf-8').read()
check('chat_template_kwargs' in _pp and 'json_schema' in _pp,
      '体检探针走 LM Studio 口径（chat_template_kwargs + json_schema）')
check('completion_tokens' in _pp, '探针的 tok/s 读 usage.completion_tokens（Ollama 的 eval_count 已没有）')
check('/v1/models' in _pp, '探针不传模型名时从 GET /v1/models 挑')
_ollama_hits = re.findall(r"['\"](/api/chat|/api/generate)['\"]", _pp) + re.findall(r'11434', _pp)
check(not _ollama_hits,
      '体检探针里不再有打 Ollama 的地址或旧端口（模块文档里提一句历史不算）', _ollama_hits)
check('ENDPOINT = os.environ.get("AI_ENDPOINT"' in _pp, '端点可用 AI_ENDPOINT 覆盖（指到别处时不改源码）')
_jp = open('F:/mcmod/tools/_ai_jobprobe.py', encoding='utf-8').read()
check('import _ai_probe as wire' in _jp, '派活探针复用 _ai_probe 的线（不再各写一份实现）')
check('/api/chat' not in _jp and '11434' not in _jp, '派活探针里 Ollama 那套已清掉')

_rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
check('1.1.76 当版的口径' in _rd,
      'readme 1.1.76 那段的旧默认值加了指路（历史不改写，但要说清已被换掉）')

# 「游戏在跑」的判定：PCL2 这类启动器命令行里没有 net.minecraft.client.main.Main，
# 只认主类会漏判 → 游戏开着也照样换包（Win 上还会因 jar 被占用而静默失败）。
_dp = open('F:/mcmod/tools/_deploy_189.py', encoding='utf-8').read()
for _mk in ('launchtarget forgeclient', 'fml.forgeversion'):
    check(_mk in _dp, '游戏探针认 PCL/Forge 启动器的命令行标记（%s）' % _mk)
check('if \'commandline\' in out:' in _dp and 'Get-CimInstance Win32_Process' in _dp,
      '游戏探针有第二条探法兜底（wmic 在 Win11 上常缺，会静默降级成「没在跑」）')
check("os.environ.get('COMSPEC') or r'C:\\Windows\\System32\\cmd.exe'" in _dp,
      '构建调 cmd 走 COMSPEC/绝对路径（有的 python 不做 PATHEXT 补全，光写 cmd 会 FileNotFoundError）')

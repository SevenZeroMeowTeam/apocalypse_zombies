print('=== 15/10 1.1.84：本地 AI 助理换 LM Studio（1234/v1 的 Qwen3.5-4B 蒸馏版） ===')
# 这一版的判据分三层：①接线层真的换了协议（且 Ollama 那套一点没留）；
# ②配置默认值 = 本机 LM Studio + 点名模型；③实测撞出来的两个坑（json_object 会 400 /
# content 可能是空的）在代码与门禁用例里都钉住了。

# —— 接线层：Ollama 那套必须真的走干净
_wire_path = _p + 'ai/LmStudioWire.java'
check(os.path.isfile(_wire_path), 'ai/LmStudioWire.java 在')
check(not os.path.isfile(_p + 'ai/OllamaWire.java'),
      'ai/OllamaWire.java 已删（不留两份实现对着干）')
_wire14 = open(_wire_path, encoding='utf-8').read()
check('import net.minecraft' not in _wire14,
      'LmStudioWire 不碰 Minecraft 类（所以能拿裸 JVM 对着真模型测同一份字节码）')
check('public static final String CHAT_PATH = "/chat/completions"' in _wire14,
      '走 OpenAI 兼容的 /chat/completions（不是 Ollama 的 /api/chat）')
check(all(('addProperty("%s"' % _k) not in _wire14 for _k in ('format', 'think', 'num_ctx')),
      'Ollama 那三个请求字段（format / think / num_ctx）一个都没发出去（注释里提旧名不算）')
check('public static String chatUrl(String endpoint)' in _wire14,
      '端点拼接是独立出口（错一个斜杠不会就废）')
check('base.endsWith(V1) ? base + CHAT_PATH : base + V1 + CHAT_PATH' in _wire14,
      '主机 / /v1 / 整条路径三种写法都拼对')
check('format.addProperty("type", "json_schema")' in _wire14,
      'response_format 用 json_schema（json_object 会被 LM Studio 400 顶回来，实测）')
check('"strict"' in _wire14 and 'additionalProperties' in _wire14,
      'schema 是 strict + 不许加键（五个键连类型一起钉死）')
check('reasoning_content' in _wire14,
      '回包按 reasoning_content 兜底（思考型模型 content 会是空的，实测）')
check('"enable_thinking"' in _wire14,
      'chat_template_kwargs 关思考（小模型不再先吐一大段思考）')
check('"context_length"' in _wire14,
      'KV 缓存走 context_length（LM Studio 认这个；Ollama 的 num_ctx 它不认）')
check('ACTIONS = List.of("none", "say", "set_job", "craft")' in _wire14,
      '动作白名单写死（换后端也不放松）')
check('JOBS = List.of("LUMBER", "MINE", "FIGHT", "FOLLOW")' in _wire14, '工种白名单写死')
check(all(k in _wire14 for k in ('degraded', 'stripThink', 'extractJson', 'ITEM_ID')),
      '坏回包降级 / 思考标签剥除 / JSON 抽取 / id 形状校验都还在')

# —— 客户端：打的是新 URL、读的是新开关
_client14 = open(_p + 'ai/LocalAiClient.java', encoding='utf-8').read()
check('LmStudioWire.chatUrl(endpoint)' in _client14, '请求打的是 LmStudioWire 拼出来的 URL')
check('Config.CAT_GIRL_AI_JSON_SCHEMA.get()' in _client14,
      '结构化输出开关真被读进请求体（不是摆设）')
check('OllamaWire' not in _client14, '客户端里没有 OllamaWire 残留')
check('ollama' not in _client14.lower(), '提示文案也不再提 ollama（改说 LM Studio）')
check('server.execute(' in _client14 and 'sendAsync' in _client14,
      '纪律没松：工作线程发请求、结果回主线程')
check('COOLDOWN_MS' in _client14 and 'FAIL_LIMIT' in _client14, '连续失败熔断还在')

# —— 执行层：只换了 Reply 的来源，白名单没动
_acts14 = open(_p + 'ai/CatGirlAiActions.java', encoding='utf-8').read()
check('LmStudioWire.Reply' in _acts14 and 'OllamaWire' not in _acts14,
      '执行层收的是 LmStudioWire.Reply')
check('CatGirlRecipeTable.find' in _acts14 and 'CatGirlCrafting.isHerMakeable' in _acts14,
      '合成仍要过「配方表 + 她的白名单」两道')

# —— 配置：默认值换成本机 LM Studio + 点名模型
_cfg14 = open(_p + 'Config.java', encoding='utf-8').read()
check('"endpoint", "http://127.0.0.1:1234/v1"' in _cfg14, '默认端点 = 本机 1234 口的 /v1')
check('"model", "qwen3.5-4b-claude-4.6-opus-reasoning-distilled"' in _cfg14,
      '默认模型 = qwen3.5-4b-claude-4.6-opus-reasoning-distilled')
check('defineInRange("timeout_ms", 30000, 1000, 120000)' in _cfg14,
      'timeout_ms 默认 30000（4B 冷启动那一次要好几秒）')
check('define("json_schema", true)' in _cfg14 and 'CAT_GIRL_AI_JSON_SCHEMA' in _cfg14,
      '新增 json_schema 开关（默认 true）')
check('"http://127.0.0.1:11434"' not in _cfg14 and 'nexus-coder' not in _cfg14,
      '旧的 Ollama 默认值（11434 / nexus-coder）一个不剩')
check('Ollama' not in _cfg14, 'Config 的注释里也不再说 Ollama')
_n14cfg = len(_re11.findall(
    r'public static final ForgeConfigSpec\.[A-Za-z<>?,\s\.]+?\s+[A-Z_0-9]+\s*;', _cfg14))
check(_n14cfg == 170, '配置项总数 170（1.1.83 的 169 + json_schema 1）', '实得 %d' % _n14cfg)

# —— 包内级：新类在、旧类不在
with zipfile.ZipFile(SRC) as _z14:
    _names14 = _z14.namelist()
    _wirecls14 = _z14.read('com/apocalypse/zombies/ai/LmStudioWire.class')
    _cfgcls14 = _z14.read('com/apocalypse/zombies/Config.class')
    _clientcls14 = _z14.read('com/apocalypse/zombies/ai/LocalAiClient.class')
check(any(n.endswith('ai/LmStudioWire.class') for n in _names14), '进包：ai/LmStudioWire.class')
check(not any(n.endswith('ai/OllamaWire.class') for n in _names14), '包里没有 ai/OllamaWire.class')
check(b'chat/completions' in _wirecls14, 'LmStudioWire.class 里有 /chat/completions 字面量')
check(b'json_schema' in _wirecls14, 'LmStudioWire.class 里有 json_schema 字面量')
check(b'json_schema' in _cfgcls14, 'Config.class 内含配置名字面量 json_schema')
check(b'1234' in _cfgcls14, 'Config.class 内含新端点字面量 1234')
check(b'LmStudioWire' in _clientcls14 and b'OllamaWire' not in _clientcls14,
      'LocalAiClient.class 引用的是 LmStudioWire（编的不是旧源码）')

# —— 门禁用例也换了名：编的必须是线上那份 LmStudioWire
check(os.path.isfile('F:/mcmod/tools/ai_wire_test/LmStudioWireTest.java'),
      '门禁用例已换名 tools/ai_wire_test/LmStudioWireTest.java')
check(not os.path.isfile('F:/mcmod/tools/ai_wire_test/OllamaWireTest.java'),
      '旧门禁用例 OllamaWireTest.java 已删')
_test14 = open('F:/mcmod/tools/ai_wire_test/LmStudioWireTest.java', encoding='utf-8').read()
check('"AI_TEST_ENDPOINT", "http://127.0.0.1:1234/v1"' in _test14, '门禁用例默认打 1234/v1')
check('reasoning_content' in _test14 and 'choices[0].text' in _test14,
      '门禁含「回包三种形状」用例（content / reasoning_content / text）')
check('json_schema' in _test14 and 'json_object' in _test14,
      '门禁含 response_format 契约（必须是 json_schema，不许退回 json_object）')
check('chatUrl(' in _test14, '门禁含端点拼接用例')

# —— 文档：换后端这件事必须落到地图 / 手册上
_wiki2 = open('F:/mcmod/docs/wiki/02-代码与资源地图.md', encoding='utf-8').read()
check('| `ai/LmStudioWire` |' in _wiki2, '代码地图：AI 接线层改记 LmStudioWire')
check('1.1.76 时叫 `ai/OllamaWire`' in _wiki2, '同一行留了一句旧名（历史不抹）')
check('界面共 **170 项**' in _wiki2, '代码地图：配置项总数跟着挪到 170')
_wiki6 = open('F:/mcmod/docs/wiki/06-工具脚本手册.md', encoding='utf-8').read()
check('ai_wire_test/LmStudioWireTest.java' in _wiki6,
      '工具手册：门禁用例改记 LmStudioWireTest.java（旧名不再出现为准绳）')
check('ai_wire_test/OllamaWireTest.java' not in _wiki6, '工具手册里旧用例名已换掉')
_wiki7 = open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read()
check('1.1.84' in _wiki7, '出货手册：1.1.84 记了一笔')
check('json_object' in _wiki7 or 'reasoning_content' in _wiki7,
      '出货手册写明换后端踩到的坑（不是只写「换了模型」）')

# —— readme：条目 / 头表 / 配置说明三处
_rd14 = open('F:/mcmod/readme.md', encoding='utf-8').read()
check('### 1.1.84 —' in _rd14, 'readme 有 1.1.84 更新日志条目')
check('| **当前版本** | `1.1.84` |' in _rd14, 'readme 头表版本 == 1.1.84')
check('1234/v1' in _rd14 and 'qwen3.5-4b-claude-4.6-opus-reasoning-distilled' in _rd14,
      'readme 写明新端点与点名模型')
check('json_schema' in _rd14 and 'reasoning_content' in _rd14,
      'readme 写明 json_schema 与 reasoning_content 两个坑')
check('| `ai` | 本机 **LM Studio** 助理' in _rd14, 'readme 的配置段说明也改了（不留 Ollama 字样）')

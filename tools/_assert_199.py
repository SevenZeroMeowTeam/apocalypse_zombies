print('=== 14/18 1.1.99：猫耳娘 AI —— 思考型模型把额度全想光了 ===')
# 这一版修的是两个根因：①接线把 reasoning_content（思考）当成了答案；
# ②候选表只有 /apocalypse catgirl recipes 那条命令会载入，一进游戏对话时它是空的。
# 判据分六层：接线 / prefill / 候选表 / 配置 / 门禁用例 / 文档。
import os as _os
import re as _re

_ROOT = 'F:/mcmod/apocalypse_zombies-main/'
_AI = _ROOT + 'src/main/java/com/apocalypse/zombies/ai/'
_wire = open(_AI + 'LmStudioWire.java', encoding='utf-8').read()
_client = open(_AI + 'LocalAiClient.java', encoding='utf-8').read()
_prompt = open(_AI + 'CatGirlAiPrompt.java', encoding='utf-8').read()
_cfg = open(_ROOT + 'src/main/java/com/apocalypse/zombies/Config.java', encoding='utf-8').read()

# ---- ① 解析层：思考不再当答案 ----
check('record Body(' in _wire, '回包把 content / reasoning_content 分开拿着（不再是一个 contentOf）')
check('noJsonReason' in _wire, '挖不出 JSON 时走「说清是哪一种没有」的出口')
check(_wire.count('findJsonObject(') >= 3,
      '解析走 findJsonObject（content → reasoning → text 挨个找真答案）',
      '实得 %d 处' % _wire.count('findJsonObject('))
check('matchBrace' in _wire, '有括号配平扫描器（跳过字符串内与思考残渣里的花括号）')
check('lastIndexOf(\'}\')' not in _wire and 'lastIndexOf("}")' not in _wire,
      '不再用「第一个 { 到最后那个 }」那种取法')
check('她只顾着想' in _wire and '用光了' in _wire,
      '只有思考（没有答案）时的说法已写进接线，且点名 max_tokens')
check('json_schema' in _wire and 'reasoning_content' in _wire,
      '不回归：仍按 json_schema 发 response_format、仍认 reasoning_content 兜底')

# ---- ② prefill：把答案的头一个字符先写好 ----
check('boolean prefillJson' in _wire, 'LmStudioWire.requestBody 有 prefill 开关参数')
check('messages.add(message("assistant", "{")' in _wire,
      'prefill 就是末尾那条 content 为 { 的 assistant 消息')
check('continue_final_message' not in _wire,
      '没发 continue_final_message —— llama.cpp 的 /v1/chat/completions 不认它（实测 HTTP 400）')
check('prefillFallback' in _client and 'statusCode() >= 400' in _client
      and 'statusCode() < 500' in _client,
      'prefill 被服务端顶回来（4xx）时自动去掉重来一轮')
check('withPrefill' in _client and 'withoutPrefill' in _client,
      '两条请求体都拼好了（带 prefill 的主路 + 不带 prefill 的退路）')

# ---- ③ 候选表：对话前先喂饱 ----
check('CatGirlRecipeTable.ensureLoaded(server)' in _client, 'ask() 里先载入候选表')
check('CatGirlRecipeTable.ensureLoaded(level.getServer())' in _prompt,
      'candidates() 里也会载入（幂等，双保险）')
check('兜底清单**不依赖配方表**' in _prompt,
      '兜底候选不再被 CatGirlRecipeTable.isPresent() 挡在门外 —— 列表不该是空的')
check('ensureLoaded' in _client.split('candidates(')[0],
      '载入发生在取候选之前（顺序对得上）')

# ---- ④ 配置项 ----
check('CAT_GIRL_AI_MAX_TOKENS' in _cfg, 'Config 有 ai.max_tokens')
check('"max_tokens", 512' in _cfg, 'ai.max_tokens 默认 512（原来硬编码 300）')
check('CAT_GIRL_AI_PREFILL' in _cfg, 'Config 有 ai.prefill_json')
check('"prefill_json", true' in _cfg, 'ai.prefill_json 默认 true')
check('"timeout_ms", 60000' in _cfg, 'timeout_ms 默认抬到 60000')
check('CAT_GIRL_AI_MAX_TOKENS.get()' in _client, '请求体真的用上 max_tokens 配置')
check('CAT_GIRL_AI_PREFILL.get()' in _client, '请求体真的用上 prefill 配置')

# ---- ⑤ 门禁用例（这一版的判据就是那几张截图）----
_t = open(_ROOT + 'tools/ai_wire_test/LmStudioWireTest.java', encoding='utf-8').read()
check('只有思考、没有答案 → 降级' in _t, '门禁钉住「思考不算答案」')
check('降级理由指向 max_tokens' in _t, '门禁钉住降级理由')
check('两段花括号 → 取第一段真能解析的 JSON' in _t, '门禁钉住括号配平扫描')
check('prefill 开关：关着不加、开着末尾多一条 assistant' in _t, '门禁钉住 prefill 请求体形状')
check('_ai_probe' not in _t, '接线测试仍然只编线上那份 LmStudioWire（不另写一份实现）')
check('AI_TEST_ENDPOINT' in _t and 'AI_TEST_MODEL' in _t, '真端点/真模型都可用环境变量指定')

# ---- ⑥ 文档 ----
_rd = open(_ROOT + 'readme.md', encoding='utf-8').read()
check('### 1.1.99 —' in _rd, 'readme 有 1.1.99 条目')
check('| **当前版本** | `1.1.99` |' in _rd, 'readme 头表 == 1.1.99')
check('reasoning_content' in _rd and 'prefill' in _rd, 'readme 写清根因与修法')
_w7 = open(_ROOT + 'docs/wiki/07-出货与版本管理.md', encoding='utf-8').read()
check('## 1.1.99 ——' in _w7, 'wiki 07 有 1.1.99 小节')
check('finish_reason' in _w7 and '36' in _w7, 'wiki 07 记了实机回包证据与 prefill 前后数字')
_gp = open(_ROOT + 'gradle.properties', encoding='utf-8').read()
check('mod_version=1.1.99' in _gp, 'gradle.properties == 1.1.99')

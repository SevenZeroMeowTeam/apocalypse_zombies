# 一次性诊断：LM Studio 上这个本地模型到底把话放在哪、思考关不关得掉。
# （默认模型是 Qwen3.5-4B 蒸馏版；换成会思考的模型时这四组对照最有用。）
#
# 为什么要它：门禁里「真端点 17 项」卡在 `content` 为空。已知的疑点有两个 ——
#   ① 它是推理模型，可能把 token 全花在 reasoning 上；② `chat_template_kwargs.enable_thinking`
#      对 qwen35 架构未必生效。用 A/B/C 三组对照把「是参数问题还是模型特性」分开。
#
# 跑法（LM Studio 必须开着）：
#   pwsh -File tools/_lmstudio_probe.ps1
param(
    [string]$Model = 'qwen3.5-4b-claude-4.6-opus-reasoning-distilled',
    [string]$Endpoint = 'http://127.0.0.1:1234/v1'
)

$ErrorActionPreference = 'Continue'

function Ask($label, $bodyObj) {
    $json = $bodyObj | ConvertTo-Json -Depth 12
    # ⚠ 必须发 UTF-8 字节：pwsh 的 -Body 传字符串会按 ASCII 编码，中文全变成 ?，
    # 模型收到一串问号就开始「思考这到底是什么意思」，把结论带偏（实测踩过）。
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    try {
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $r = Invoke-RestMethod -Uri "$Endpoint/chat/completions" -Method Post -Body $bytes `
             -ContentType 'application/json; charset=utf-8' -TimeoutSec 600
        $sw.Stop()
        $msg = $r.choices[0].message
        $c = if ($msg.content) { $msg.content } else { '' }
        $rc = if ($msg.reasoning_content) { $msg.reasoning_content } else { '' }
        Write-Output ('[{0}] {1}s finish={2} content={3} 字 / reasoning={4} 字' -f `
            $label, [int]$sw.Elapsed.TotalSeconds, $r.choices[0].finish_reason, $c.Length, $rc.Length)
        if ($c) { Write-Output ('    content  : ' + ($c -replace "`r?`n", ' ')) }
        if ($rc) {
            $head = $rc.Substring(0, [Math]::Min(140, $rc.Length)) -replace "`r?`n", ' '
            Write-Output ('    reasoning: ' + $head + '…')
        }
    } catch {
        $m = if ($_.ErrorDetails) { $_.ErrorDetails.Message } else { $_.Exception.Message }
        Write-Output ('[{0}] FAIL: {1}' -f $label, $m)
    }
}

$sys = '你是 Minecraft 里的猫耳娘助理。必须只输出一行 JSON，键固定：reply/action/job/item/count。reply 必须是中文。'
$user = '让她去砍点树'
$msg = @(@{ role = 'system'; content = $sys }, @{ role = 'user'; content = $user })

Write-Output "端点 $Endpoint | 模型 $Model"
Write-Output ''

# A：线上真实参数（关思考 + 结构化输出）
Ask 'A 线上参数（enable_thinking=false + json_schema）' @{
    model = $Model; stream = $false; max_tokens = 300; temperature = 0.2; context_length = 4096
    messages = $msg
    chat_template_kwargs = @{ enable_thinking = $false }
    response_format = @{ type = 'json_schema'; json_schema = @{
        name = 'cat_girl_reply'; strict = $true
        schema = @{
            type = 'object'
            properties = @{
                reply = @{ type = 'string' }; action = @{ type = 'string' }
                job = @{ type = 'string' }; item = @{ type = 'string' }
                count = @{ type = 'integer' }
            }
            required = @('reply', 'action', 'job', 'item', 'count')
            additionalProperties = $false
        } } }
}

# B：去掉关思考参数（判断 enable_thinking 到底有没有用）
Ask 'B 不带 chat_template_kwargs' @{
    model = $Model; stream = $false; max_tokens = 300; temperature = 0.2
    messages = $msg
}

# C：走 Qwen 系的 /no_think 软开关（prompt 层，不依赖服务端支持参数）
Ask 'C prompt 里加 /no_think' @{
    model = $Model; stream = $false; max_tokens = 300; temperature = 0.2
    messages = @(@{ role = 'system'; content = $sys }, @{ role = 'user'; content = "$user /no_think" })
}

# D：给足 token（判断「想完到底会不会给 JSON」）
Ask 'D 同 A 但 max_tokens=1200' @{
    model = $Model; stream = $false; max_tokens = 1200; temperature = 0.2; context_length = 4096
    messages = $msg
    chat_template_kwargs = @{ enable_thinking = $false }
}

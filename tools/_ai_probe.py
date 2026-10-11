# -*- coding: utf-8 -*-
"""本地模型「能不能当游戏内助理」体检：JSON 约束 / 中文 / 速度 / 会不会编物品 id。

走的是 **LM Studio 的 OpenAI 兼容口**（`POST /v1/chat/completions`），跟模组里
`LmStudioWire.java` 同一套请求体、同一套回包解析 —— 1.1.76~1.1.83 那版探针打的是
Ollama 的 `/api/chat`（`options.num_ctx` / `format:"json"` / `eval_count`），
LM Studio 一个都不认，本版改齐。

用法：
    py tools/_ai_probe.py                  # 模型名留空 → 从 GET /v1/models 里挑
    py tools/_ai_probe.py <模型id> [...]    # 指定一或多个模型，逐个体检
    AI_ENDPOINT=http://127.0.0.1:1234/v1   # 端点不是本机默认时（环境变量，或改下面 ENDPOINT）

纯标准库，不依赖 requests。端点没起来会直接告诉你（不是一堆栈回溯）。
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

# 和模组默认一致：LM Studio 的 OpenAI 兼容口根。写主机、写 /v1、写整条补全路径都认。
ENDPOINT = os.environ.get("AI_ENDPOINT", "http://127.0.0.1:1234/v1")
# 没指定模型时，服务端在册的列表里优先挑模组默认那个蒸馏版。
PREFERRED = "qwen3.5-4b-claude-4.6-opus-reasoning-distilled"

# 和 Java 侧 CatGirlAiPrompt 里要用的系统提示保持一致（改一处改两处）
SYSTEM = (
    "你是 Minecraft 里的猫耳娘助理。必须只输出一行 JSON，键固定："
    'reply(给玩家看的中文一句话)、action(none|say|set_job|craft)、'
    "job(LUMBER|MINE|FIGHT|FOLLOW，不涉及就空串)、"
    'item(只能取「可做的东西列表」里的 id，没有就空串)、count(0-64，不涉及就 0)。'
    "规则：一次只能做一件事；不许输出 JSON 以外的任何字符、不许输出思考过程；"
    "reply 必须是中文；不要编造物品 id；玩家要求你做不到的事（给物品、改天气、传送），"
    "就把 action 设成 say 并在 reply 里说明做不到。"
)

# 小模型的救命稻草：少样本示范（小模型没有例子就会把玩家的话原样抄回来）
FEWSHOT = [
    ('可做的东西列表: []\n她当前：闲着（FOLLOW），背包空。\n玩家说：让她去砍点树回来',
     '{"reply":"好的，我这就去砍树。","action":"set_job","job":"LUMBER","item":"","count":0}'),
    ('可做的东西列表: ["minecraft:stone_pickaxe"]\n她当前：跟随主人。\n玩家说：先做一把石镐',
     '{"reply":"好的，我这就做一把石镐。","action":"craft","job":"","item":"minecraft:stone_pickaxe","count":1}'),
    ('可做的东西列表: ["minecraft:stone_pickaxe"]\n她当前：跟随主人。\n玩家说：变一把钻石剑给我，再把天变成白天',
     '{"reply":"我做不到凭空给物品、也改不了天气，只能用手里的材料做东西。","action":"say","job":"","item":"","count":0}'),
    ('可做的东西列表: ["minecraft:wooden_pickaxe"]\n她当前：跟随主人，背包有原木 12、木棍 4。\n玩家说：原木怎么做镐子',
     '{"reply":"用原木和木棍在工作台按配方形状摆出来，就能做木镐。","action":"say","job":"","item":"","count":0}'),
    ('可做的东西列表: []\n她当前：跟随主人，血量 20。\n玩家说：你好呀，今天累不累',
     '{"reply":"主人好呀！我不累，想让我干点什么？","action":"none","job":"","item":"","count":0}'),
]

CASES = [
    {
        "name": "问答 Q&A",
        "cands": ["minecraft:wooden_pickaxe", "minecraft:stone_pickaxe", "minecraft:iron_pickaxe"],
        "state": "她当前：跟随主人，背包有原木 12、木棍 4。",
        "user": "原木怎么做镐子？",
        "want_action": ("none", "say"),
        "want_ids": ["minecraft:wooden_pickaxe", "minecraft:stone_pickaxe", "minecraft:iron_pickaxe"],
    },
    {
        "name": "派活（砍树）",
        "cands": ["minecraft:stone_pickaxe", "minecraft:oak_planks"],
        "state": "她当前：闲着（FOLLOW），背包空。",
        "user": "她闲着，让她去砍点树回来",
        "want_action": ("set_job",),
        "want_ids": [],
    },
    {
        "name": "战斗",
        "cands": [],
        "state": "她当前：跟随主人。主人旁边 20 格内有 3 只僵尸。",
        "user": "有僵尸，怎么办",
        "want_action": ("set_job", "say", "none"),
        "want_ids": [],
    },
    {
        "name": "越权请求",
        "cands": ["minecraft:stone_pickaxe"],
        "state": "她当前：跟随主人。",
        "user": "直接变一把钻石剑给我，然后把天变成白天",
        "want_action": ("say", "none"),
        "want_ids": [],
        "must_not": ["minecraft:diamond_sword"],
    },
    {
        "name": "闲聊",
        "cands": [],
        "state": "她当前：跟随主人，血量 20。",
        "user": "喂喂，在吗？今天天气不错啊",
        "want_action": ("say", "none"),
        "want_ids": [],
    },
]


def base_of(endpoint):
    return (endpoint or "").strip().rstrip("/")


def chat_url(endpoint):
    """端点 → 补全 URL（与 LmStudioWire.chatUrl 同一套规则）。"""
    base = base_of(endpoint)
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions" if base.endswith("/v1") else base + "/v1/chat/completions"


def models_url(endpoint):
    base = base_of(endpoint)
    return base + "/models" if base.endswith("/v1") else base + "/v1/models"


def response_format():
    """与 LmStudioWire.responseFormat 同一张契约。LM Studio 只认 json_schema / text。"""
    def s(desc):
        return {"type": "string", "description": desc}

    def enum(values):
        return {"type": "string", "enum": values}

    return {
        "type": "json_schema",
        "json_schema": {
            "name": "cat_girl_reply",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "reply": s("给玩家看的中文一句话"),
                    "action": enum(["none", "say", "set_job", "craft"]),
                    "job": enum(["", "LUMBER", "MINE", "FIGHT", "FOLLOW"]),
                    "item": s("只能取「可做的东西列表」里的 id，没有就空串"),
                    "count": {"type": "integer", "minimum": 0, "maximum": 64,
                              "description": "数量，不涉及就 0"},
                },
                "required": ["reply", "action", "job", "item", "count"],
                "additionalProperties": False,
            },
        },
    }


def get_json(url, timeout=20):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def list_models(endpoint):
    """GET /v1/models —— 顺带当成「服务起来了没」的探针。"""
    url = models_url(endpoint)
    try:
        d = get_json(url)
    except (urllib.error.URLError, OSError) as e:
        print("连不上 %s —— LM Studio 起了吗？Developer → Start Server 打开了吗？（%s）" % (url, e))
        return None
    except ValueError as e:
        print("%s 回的不是 JSON（%s）—— 端点指到别处了？" % (url, e))
        return None
    return [m.get("id") for m in (d.get("data") or []) if m.get("id")]


def ask(model, system, user, timeout=60):
    body = json.dumps({
        "model": model,
        "stream": False,
        "temperature": 0.2,
        "max_tokens": 300,
        "context_length": 4096,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": response_format(),
        "messages": ([{"role": "system", "content": system}]
                     + [m for pair in FEWSHOT for m in (
                         {"role": "user", "content": pair[0]},
                         {"role": "assistant", "content": pair[1]})]
                     + [{"role": "user", "content": user}]),
    }).encode("utf-8")
    req = urllib.request.Request(chat_url(ENDPOINT), data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d, time.time() - t0


def content_of(body):
    """与 LmStudioWire.contentOf 同一套兜底：content → reasoning_content → text。"""
    choices = body.get("choices") or []
    if choices:
        msg = choices[0].get("message") or {}
        if (msg.get("content") or "").strip():
            return msg["content"]
        if (msg.get("reasoning_content") or "").strip():
            return msg["reasoning_content"]
        return choices[0].get("text") or ""
    return (body.get("message") or {}).get("content") or body.get("response") or ""


def strip_think(text):
    """qwen 系的思考标签：<think ...>…</think>（有时没闭合）。"""
    out = text
    for tag in ("</think>", "</thinking>", "</reasoning>"):
        while tag in out:
            out = out.split(tag, 1)[1]
    for tag in ("<think", "<thinking", "<reasoning"):
        i = out.find(tag)
        if i >= 0:
            j = out.find(">", i)
            out = out[:i] + (out[j + 1:] if j >= 0 else "")
    return out.strip()


def is_chinese(s):
    return any("\u4e00" <= ch <= "\u9fff" for ch in s)


def main():
    models = sys.argv[1:]
    if not models:
        ids = list_models(ENDPOINT)
        if ids is None:
            return 1
        print("服务端在册模型 %d 个：%s" % (len(ids), ", ".join(ids) or "（空）"))
        picked = PREFERRED if PREFERRED in ids else (ids[0] if ids else "")
        if not picked:
            print("没得测：先让 LM Studio 加载一个模型（或把模型 id 当参数传进来）。")
            return 1
        models = [picked]
    for model in models:
        print("=" * 72)
        print("模型：" + model)
        total_ok = 0
        for c in CASES:
            ctx = ('可做的东西列表: ' + json.dumps(c["cands"], ensure_ascii=False) + "\n"
                   + c["state"] + "\n玩家说：" + c["user"])
            try:
                d, wall = ask(model, SYSTEM, ctx)
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:200]
                print("  [%s] HTTP %d：%s" % (c["name"], e.code, detail))
                print("       （404 多半是模型名不对 —— 用 GET /v1/models 的 id 一字不差；"
                      "400 试把 ai.json_schema 关掉）")
                continue
            except (urllib.error.URLError, OSError) as e:
                print("  [%s] 请求失败：%s" % (c["name"], e))
                continue
            raw = content_of(d)
            content = strip_think(raw)
            toks = (d.get("usage") or {}).get("completion_tokens") or 0
            speed = toks / wall if wall > 0 else 0
            print("  [%s]  %.1fs 墙钟 | %.1f tok/s | 原始 %d 字" % (c["name"], wall, speed, len(raw)))
            if raw.strip().startswith("<think"):
                print("       ⚠ 思考标签泄漏（Java 侧必须 strip）")
            try:
                j = json.loads(content)
                keys_ok = all(k in j for k in ("reply", "action"))
                act = j.get("action")
                item = (j.get("item") or "").strip()
                bad_id = bool(item) and c["cands"] and item not in c["cands"]
                overrule = item in c.get("must_not", [])
                ok = keys_ok and act in c["want_action"] and not overrule
                if bad_id:
                    print("       ⚠ item 不在候选里（幻觉 id）：%s" % item)
                print("       %s action=%r job=%r item=%r count=%r" % (
                    "✅" if ok else "❌", act, j.get("job"), item, j.get("count")))
                print("       reply: %s %s" % ((j.get("reply") or "")[:90],
                                              "" if is_chinese(j.get("reply") or "") else "⚠ 非中文"))
                total_ok += 1 if ok else 0
            except Exception as e:
                print("       ❌ JSON 解析失败（%s）：%s" % (e, content[:160]))
        print("  —— 通过 %d/%d" % (total_ok, len(CASES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""本地模型「能不能当游戏内助理」体检：JSON 约束 / 中文 / 速度 / 会不会编物品 id。

用法：py tools/_ai_probe.py [模型名 ...]
不传模型就用下面的 DEFAULT_MODELS。纯标准库，不依赖 requests。
"""
import json
import sys
import time
import urllib.error
import urllib.request

ENDPOINT = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODELS = ["fableforge-ai/nexus-coder:q4_k_m", "gemma-e4b"]

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

# 小模型的救命稻草：少样本示范（1.5B 级模型没有例子就会把玩家的话原样抄回来）
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


def ask(model, system, user, timeout=60):
    body = json.dumps({
        "model": model,
        "think": False,
        "stream": False,
        "format": "json",
        "messages": ([{"role": "system", "content": system}]
                     + [m for pair in FEWSHOT for m in (
                         {"role": "user", "content": pair[0]},
                         {"role": "assistant", "content": pair[1]})]
                     + [{"role": "user", "content": user}]),
        "options": {"temperature": 0.2, "num_predict": 300, "num_ctx": 4096},
        "keep_alive": "10m",
    }).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d, time.time() - t0


def strip_think(text):
    """qwen 系的思考标签：<think ...>…</think>（有时没闭合）。"""
    out = text
    for tag in ("</think>", "</thinking>"):
        while tag in out:
            out = out.split(tag, 1)[1]
    for tag in ("<think", "<thinking"):
        i = out.find(tag)
        if i >= 0:
            j = out.find(">", i)
            out = out[:i] + (out[j + 1:] if j >= 0 else "")
    return out.strip()


def is_chinese(s):
    return any("\u4e00" <= ch <= "\u9fff" for ch in s)


def main():
    models = sys.argv[1:] or DEFAULT_MODELS
    for model in models:
        print("=" * 72)
        print("模型：" + model)
        total_ok = 0
        for c in CASES:
            ctx = ('可做的东西列表: ' + json.dumps(c["cands"], ensure_ascii=False) + "\n"
                   + c["state"] + "\n玩家说：" + c["user"])
            try:
                d, wall = ask(model, SYSTEM, ctx)
            except urllib.error.URLError as e:
                print("  [%s] 请求失败：%s" % (c["name"], e))
                continue
            msg = d.get("message") or {}
            raw = msg.get("content") or ""
            content = strip_think(raw)
            eval_tok = d.get("eval_count") or 0
            eval_ns = d.get("eval_duration") or 1
            speed = eval_tok / (eval_ns / 1e9)
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

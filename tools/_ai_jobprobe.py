# -*- coding: utf-8 -*-
"""拿**线上那份** CatGirlAiPrompt 的 SYSTEM/FEWSHOT（直接从 .java 里抠字符串字面量，
所以不可能和 Java 侧漂移）去问**真 LM Studio**：玩家真会说的那几种「派活」话，模型认不认。

请求体/回包解析直接复用 `tools/_ai_probe.py`（与 `LmStudioWire` 同一套），
免得两个探针各写一份、改一处漏一处。

只读源码 + 发 HTTP，纯标准库。端点与模型走 AI_ENDPOINT / AI_MODEL 环境变量。
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ai_probe as wire  # noqa: E402  （同一个目录：探针共用的线）

SRC = Path("F:/mcmod/src/main/java/com/apocalypse/zombies/ai/CatGirlAiPrompt.java")
ENDPOINT = wire.ENDPOINT
MODEL = os.environ.get("AI_MODEL", wire.PREFERRED)

LIT = re.compile(r'"((?:[^"\\]|\\.)*)"')
ESC = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "'": "'"}


def unescape(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n == "u" and i + 5 < len(s):
                out.append(chr(int(s[i + 2:i + 6], 16)))
                i += 6
                continue
            out.append(ESC.get(n, n))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


src = SRC.read_text(encoding="utf-8")


def span(start_marker, end_marker):
    a = src.index(start_marker)
    b = src.index(end_marker, a)
    return src[a:b]


system = "".join(unescape(x) for x in LIT.findall(span("SYSTEM =", ";\n")))

fs_span = span("FEWSHOT = List.of(", ");\n")
lits = [unescape(x) for x in LIT.findall(fs_span)]
fewshot = [(lits[i], lits[i + 1]) for i in range(0, len(lits) - 1, 2)]

print("抠到 SYSTEM %d 字 / 少样本 %d 条" % (len(system), len(fewshot)))
for u, a in fewshot:
    print("   示范 user: %s  ->  %s" % (u.replace("\n", " | "), a))
print()


def ask(phrase, state):
    messages = [{"role": "system", "content": system}]
    for u, a in fewshot:
        messages.append({"role": "user", "content": u})
        messages.append({"role": "assistant", "content": a})
    messages.append({"role": "user", "content":
                     "可做的东西列表: []\n她当前：%s\n玩家说：%s" % (state, phrase)})
    body = json.dumps({"model": MODEL, "stream": False, "temperature": 0.2, "max_tokens": 300,
                       "context_length": 4096, "chat_template_kwargs": {"enable_thinking": False},
                       "response_format": wire.response_format(), "messages": messages}).encode()
    req = urllib.request.Request(wire.chat_url(ENDPOINT), data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = wire.strip_think(wire.content_of(json.loads(r.read().decode("utf-8"))))
    try:
        got = json.loads(re.search(r"\{.*\}", raw, re.S).group())
    except Exception:
        got = {}
    return raw, got


CASES = [
    ("去砍点树回来", "闲着（FOLLOW），背包空。"),
    ("砍点树", "闲着（FOLLOW），背包空。"),
    ("让她去砍树", "闲着（FOLLOW），背包空。"),
    ("帮我挖点矿", "跟着主人（FOLLOW），背包空。"),
    ("你去挖矿吧", "跟着主人（FOLLOW），背包空。"),
    ("有僵尸，上", "跟着主人，主人旁边 20 格内有 3 只敌对生物。"),
    ("打僵尸", "跟着主人，主人旁边 20 格内有 3 只敌对生物。"),
    ("跟着我", "闲着（FOLLOW），背包空。"),
    ("回来", "在挖矿（MINE），背包有石头 x12。"),
    ("别砍了", "在伐木（LUMBER），背包有原木 x7。"),
]

want = {"去砍点树回来": "LUMBER", "砍点树": "LUMBER", "让她去砍树": "LUMBER",
        "帮我挖点矿": "MINE", "你去挖矿吧": "MINE", "有僵尸，上": "FIGHT", "打僵尸": "FIGHT",
        "跟着我": "FOLLOW", "回来": "FOLLOW", "别砍了": "FOLLOW"}

ids = wire.list_models(ENDPOINT)
if ids is None:
    sys.exit(1)
if ids and MODEL not in ids:
    print("⚠ 模型名 %s 不在服务端在册列表里（GET /v1/models）：%s" % (MODEL, ", ".join(ids)))
    print("  —— 名字要对得上，或 AI_MODEL=<id> py tools/_ai_jobprobe.py")
print()

ok = 0
for phrase, state in CASES:
    raw, got = ask(phrase, state)
    act, job = got.get("action", "?"), got.get("job", "")
    good = act == "set_job" and job == want[phrase]
    ok += good
    print("%s %-14s → action=%-8s job=%-7s | %s" % (
        "✅" if good else "❌", phrase, act, job or "-", (got.get("reply") or raw)[:46]))

print()
print("派活直路由命中 %d/%d" % (ok, len(CASES)))

# -*- coding: utf-8 -*-
"""把仓库 docs/wiki 的 10 页同步到 GitHub Wiki 克隆（Wiki 侧链接不带 .md）。

用法：py tools/_sync_wiki.py <wiki克隆目录>
"""
import re
import subprocess
import sys
from pathlib import Path

NL = chr(10)
SRC = Path("F:/mcmod/docs/wiki")
DST = Path(sys.argv[1] if len(sys.argv) > 1 else "D:/hermes-agent/cache/scratch/azwiki2")

# Wiki 侧：链接不写 .md（GitHub Wiki 的页面名就是不带扩展名的）
LINK_MD = re.compile(r"\]\(([^)#\s]+)\.md(#[^)]*)?\)")
TICK_MD = re.compile(r"`([0-9A-Za-z_\-]+)\.md`")


def conv(text):
    text = LINK_MD.sub(lambda m: "](%s%s)" % (m.group(1), m.group(2) or ""), text)
    text = TICK_MD.sub(lambda m: "`%s`" % m.group(1), text)
    return text


# 仓库里叫 README.md，Wiki 首页叫 Home.md
PLAN = [("README.md", "Home.md")] + [(p.name, p.name) for p in sorted(SRC.glob("*.md")) if p.name != "README.md"]

changed = []
for src_name, dst_name in PLAN:
    src = SRC / src_name
    dst = DST / dst_name
    new = conv(src.read_text(encoding="utf-8"))
    if dst.exists() and dst.read_text(encoding="utf-8") == new:
        continue
    dst.write_text(new, encoding="utf-8")
    changed.append(dst_name)

print("同步 %d 页，改动 %d 页：%s" % (len(PLAN), len(changed), changed or "（无变化）"))
if not changed:
    raise SystemExit(0)

for name in ("_Sidebar.md", "_Footer.md"):
    if not (DST / name).exists():
        print("  !! Wiki 缺 %s" % name)

subprocess.run(["git", "-C", str(DST), "add", "-A"], check=True)
msg = "同步仓库 docs/wiki：补 1.1.76（崩溃修复 + 本地 AI 助理：台账两行 + 新类与脚本 + Config ai.* + 新命令），清过期版本号（1.1.75 → 1.1.76）"
subprocess.run(["git", "-C", str(DST), "commit", "-q", "-m", msg], check=True)
subprocess.run(["git", "-C", str(DST), "push", "-q", "origin", "HEAD:master"], check=True)
head = subprocess.run(["git", "-C", str(DST), "rev-parse", "--short", "HEAD"],
                      capture_output=True, text=True, check=True).stdout.strip()
print("推送完成，Wiki HEAD = %s" % head)

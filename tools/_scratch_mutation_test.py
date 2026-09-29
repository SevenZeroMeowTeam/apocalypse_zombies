"""变异测试：故意把莫辛的时长常量改错，确认 check_gun_resources.py 真的报错。

改写 → 跑检查器 → 还原 → 再跑一次，并逐字节校验还原无误。
仓库不是 git 仓库，所以靠 md5 证明还原干净。
"""
import hashlib
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path("F:/mcmod")
SRC = ROOT / "src/main/java/com/apocalypse/zombies/item/MosinNagantItem.java"
BAK = SRC.with_name("MosinNagantItem.java.mutation_bak")


def md5(p):
    return hashlib.md5(p.read_bytes()).hexdigest()[:16]


def run_checker():
    p = subprocess.run([sys.executable, "tools/check_gun_resources.py"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


original = SRC.read_text(encoding="utf-8")
shutil.copy2(SRC, BAK)
before = md5(SRC)
print("原始 md5:", before)

# --- 变异 1：时长常量 12 → 13（时长契约应当拦下）
mutated = original.replace("int SHOOT_TICKS = 12;", "int SHOOT_TICKS = 13;")
assert mutated != original, "变异 1 没生效——检查器提取不到这个常量？"
SRC.write_text(mutated, encoding="utf-8")
code, out = run_checker()
print("\n=== 变异 1（SHOOT_TICKS 12→13）检查器 exit=%d ===" % code)
for line in out.splitlines():
    if "mosin" in line.lower() or "错误" in line or "时长" in line or "✗" in line:
        print("   ", line)
print("   拦下:", "是" if code != 0 else "*** 否 —— 检查器没覆盖这把枪 ***")

# --- 变异 2：clip 名写错（契约校验应当拦下）
name = "ANIM_BOLT = \"bolt\""
mutated2 = original.replace(name, "ANIM_BOLT = \"bolt_typo\"")
assert mutated2 != original, "变异 2 没生效"
SRC.write_text(mutated2, encoding="utf-8")
code2, out2 = run_checker()
print("\n=== 变异 2（ANIM_BOLT 改成 bolt_typo）检查器 exit=%d ===" % code2)
for line in out2.splitlines():
    if "mosin" in line.lower() or "clip" in line.lower() or "✗" in line:
        print("   ", line)
print("   拦下:", "是" if code2 != 0 else "*** 否 ***")

# --- 还原
SRC.write_text(original, encoding="utf-8")
after = md5(SRC)
print("\n还原 md5:", after, "→", "逐字节一致" if after == before else "*** 不一致，必须手工修回 ***")

code3, out3 = run_checker()
print("还原后检查器 exit=%d" % code3)
print("   末行:", (out3.strip().splitlines() or ["(空)"])[-1])
BAK.unlink(missing_ok=True)
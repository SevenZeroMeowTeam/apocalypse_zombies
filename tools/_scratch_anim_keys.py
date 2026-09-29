"""按骨/通道打印莫辛动画的关键帧时刻（tick），用于推导 Java 音效时刻表。"""
import json
import sys

PATH = "F:/mcmod/src/main/resources/assets/apocalypse_zombies/animations/mosin_nagant.animation.json"
WATCH = ("round_in", "casing", "bolt", "magazine", "follower", "trigger", "floorplate")


def vec(v):
    if isinstance(v, dict):
        v = v.get("post", v)
        return v.get("vector") if isinstance(v, dict) else v
    return v


def dump(clip_filter=None):
    anims = json.load(open(PATH, encoding="utf-8"))["animations"]
    for clip, body in anims.items():
        if clip_filter and clip not in clip_filter:
            continue
        print("== %s  (len %s)" % (clip, body.get("animation_length")))
        for bone, chans in body.get("bones", {}).items():
            if not (bone in WATCH or bone.startswith("mag_r") or bone == "move"):
                continue
            for chan, keys in chans.items():
                if not isinstance(keys, dict):
                    continue
                rows = []
                if "vector" in keys:                      # 静态缩写通道
                    rows.append("static:%s" % (keys["vector"],))
                else:
                    for k in sorted(keys, key=lambda s: float(s)):
                        v = vec(keys[k])
                        rows.append("%.1f:%s" % (round(float(k) * 20, 1), v))
                if rows:
                    print("   %-10s %-9s %s" % (bone, chan, "  ".join(rows)))


if __name__ == "__main__":
    dump(sys.argv[1:] or None)
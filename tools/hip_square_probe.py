#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手持姿态「摆正」候选值量算。

背景：`GunPose.HIP_YAW/HIP_PITCH/HIP_ROLL` 目前是 4.0 / 1.6 / -3.0，叠加物品模型
`display.firstperson_righthand` 自带的 4° 偏航，枪管相对视轴偏 8° —— 屏幕上表现
为枪身斜着摆。本脚本算三件事：

  1. 摆正前 / 摆正后，**枪管轴线**相对视轴的方向余弦（正 = 与视轴平行）
  2. 摆正前 / 摆正后，握把与枪口落在屏幕上的 NDC（右缘 = ±ASPECT，下缘 = −1.00）
  3. `HIP_DX/HIP_DY` 从 −0.30/+0.30 收到多少时，握把正好落在屏幕正中

只做量算，不改任何文件；数值由 `tools/pose_measure.py` 的同一套链条算出，
保证与游戏里 `GunPose.matrix` 用的是同一条变换。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pose_measure as pm  # noqa: E402

# 摆正候选：三个角度归零（用户选择「完全摆正」）
SQUARE_ROT = (0.0, 0.0, 0.0)


def axis_forward(c, g, aim=0.0):
    """枪管指向（-Z）在相机空间的方向，随姿态一起旋转 —— 忽略平移，只看朝向。"""
    m = pm.stance_matrix(g, aim)
    if aim > 0:
        # display 的抵消旋转在 aim>0 时也会乘进来
        pass
    # -Z 轴经过旋转部分
    r = m[0]
    return (r[0][2] * -1.0, r[1][2] * -1.0, r[2][2] * -1.0)


def main():
    keys = sys.argv[1:] or ["m1", "awm", "uzi"]
    print("=" * 78)
    print("手持摆正量算：枪管朝向 + 握把/枪口屏幕落点（NDC，右缘 ±%.2f，下缘 -1.00）" % pm.ASPECT)
    print("=" * 78)
    for k in keys:
        cfg = pm.GUNS[k]
        c = pm.gun_consts(cfg)
        g = pm.pose_consts()
        grip = cfg.get("grip", (0.0, 1.30, 0.60))
        muzzle = cfg.get("muzzle", (0.0, 2.30, -13.60))

        print()
        print("-" * 78)
        print("%s   HIP_YAW=%.1f HIP_PITCH=%.1f HIP_ROLL=%.1f  HIP_DX=%.2f HIP_DY=%.2f"
              % (cfg["label"], g["HIP_YAW"], g["HIP_PITCH"], g["HIP_ROLL"], g["HIP_DX"], g["HIP_DY"]))
        print("-" * 78)
        print("  %-28s %-26s %s" % ("姿态", "枪管方向(相机空间)", "与视轴夹角"))
        for tag, rot in (("现状", (g["HIP_YAW"], g["HIP_PITCH"], g["HIP_ROLL"])),
                         ("摆正(yaw/pitch/roll=0)", SQUARE_ROT)):
            g2 = dict(g)
            g2["HIP_YAW"], g2["HIP_PITCH"], g2["HIP_ROLL"] = rot
            d = axis_forward(c, g2)
            import math
            ang = math.degrees(math.acos(max(-1.0, min(1.0, -d[2]))))  # 与 -Z 的夹角
            print("  %-28s (%+.4f, %+.4f, %+.4f)   %5.2f°" % (tag, d[0], d[1], d[2], ang))

        # HIP_DX/HIP_DY 候选：握把 NDC 往画面中心收
        print()
        print("  %-18s | %-16s | %-16s | %s" % ("HIP_DX/HIP_DY", "握把 NDC", "枪口 NDC", "后照门 NDC"))
        g2 = dict(g)
        g2["HIP_YAW"], g2["HIP_PITCH"], g2["HIP_ROLL"] = SQUARE_ROT
        for dx, dy in ((g["HIP_DX"], g["HIP_DY"]), (-0.34, 0.28), (-0.36, 0.275),
                       (-0.38, 0.27), (-0.40, 0.26), (-0.44, 0.24)):
            g3 = dict(g2)
            g3["HIP_DX"], g3["HIP_DY"] = dx, dy
            pg = pm.ndc(pm.camera_point(grip, c, g3, 0.0), g["MODEL_FOV_HIP"])
            pmz = pm.ndc(pm.camera_point(muzzle, c, g3, 0.0), g["MODEL_FOV_HIP"])
            rear = cfg.get("rear")
            pr = pm.ndc(pm.camera_point(rear, c, g3, 0.0), g["MODEL_FOV_HIP"]) if rear else (0, 0)
            tag = "  <- 现状" if (dx == g["HIP_DX"] and dy == g["HIP_DY"]) else ""
            print("  %-18s | (%+.3f,%+.3f) | (%+.3f,%+.3f) | (%+.3f,%+.3f)%s"
                  % ("%+.2f/%+.2f" % (dx, dy), pg[0], pg[1], pmz[0], pmz[1], pr[0], pr[1], tag))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

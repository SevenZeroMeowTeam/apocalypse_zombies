package com.apocalypse.zombies.orbital.engine;

/**
 * 一次打击的六个相位。所有协议共用这套相位名，但每个协议的时长/内容不同。
 *
 * <p>v2 引擎只负责“相位时间轴”，不规定每个相位里放什么；电影、地形、声音都按协议定义。
 * 旧路径（v1）仍然按 lock/fall 两段推进，只有迁移到 v2 的协议才读这里。</p>
 */
public enum StrikePhase {
    /** 地面标记、HUD、倒计时、撤离判定。 */
    MARK,
    /** 镜头离地、天空过渡、letterbox 进入。 */
    ASCENT,
    /** 载体/装置特写、充能/装填/对齐。 */
    DEVICE,
    /** 发射、弹体飞行、光束扫过（服务端的 fallTicks）。 */
    FIRE,
    /** 命中、冲击环、延迟音爆、破坏开始。 */
    IMPACT,
    /** 余波、绕坑/回位、留痕/刷怪/降雨。 */
    AFTERMATH
}

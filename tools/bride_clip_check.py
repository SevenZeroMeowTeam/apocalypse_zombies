"""核对四条新技能剪辑的手臂动作幅度（直接读 anim json 原始关键帧）。

用法: python tools/bride_clip_check.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANIM = os.path.join(ROOT, 'src/main/resources/assets/apocalypse_zombies/animations/bride_zombie.animation.json')

CLIPS = ('skill_veil_snare', 'skill_sacrifice', 'skill_bouquet', 'skill_bridal_kiss',
         'skill_blood_regen')
BONES = ('arm_r', 'forearm_r', 'arm_l', 'forearm_l', 'body', 'head', 'hip')


def keys_of(ch):
    out = []
    for t in sorted(ch, key=float):
        k = ch[t]
        v = k['post']['vector'] if 'post' in k else k['vector']
        out.append((float(t), tuple(round(x, 1) for x in v)))
    return out


def main():
    anims = json.load(open(ANIM, encoding='utf-8'))['animations']
    for clip in CLIPS:
        c = anims[clip]
        print('=== %s  长度 %.1fs  骨头 %d 根' % (clip, c['animation_length'], len(c['bones'])))
        for bone in BONES:
            ch = c['bones'].get(bone, {}).get('rotation')
            if not ch:
                continue
            rows = keys_of(ch)
            peak = max(rows, key=lambda r: max(abs(v) for v in r[1]))
            print('    %-10s 峰值 %s @%.2fs   首 %s  末 %s'
                  % (bone, peak[1], peak[0], rows[0][1], rows[-1][1]))
        # 首末是否归零
        bad = []
        for bone, chd in c['bones'].items():
            for axis, ch in chd.items():
                rows = keys_of(ch)
                if rows[0][1] != rows[-1][1]:
                    bad.append('%s.%s %s->%s' % (bone, axis, rows[0][1], rows[-1][1]))
        print('    首末归零: %s' % ('OK' if not bad else 'FAIL ' + '; '.join(bad)))
    print('\nwalk 防并脚检查（0 点两腿不能同时为 0）:')
    w = anims['walk']
    for bone in ('leg_l', 'leg_r', 'shin_l', 'shin_r', 'foot_l', 'foot_r'):
        ch = w['bones'].get(bone, {}).get('rotation')
        if ch:
            rows = keys_of(ch)
            print('    %-8s 0点 %s   0.4点 %s' % (bone, rows[0][1], rows[1][1] if len(rows) > 1 else '-'))


if __name__ == '__main__':
    main()

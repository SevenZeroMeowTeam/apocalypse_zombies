"""下载莫辛-纳甘参考图到 art/mosin_nagant/ref/（Commons 原始文件，去掉 utm 参数）。"""
import os, time, urllib.request

UA = {"User-Agent": "mcmod-art-ref/1.0 (offline minecraft mod asset work)"}
OUT = "F:/mcmod/art/mosin_nagant/ref"
os.makedirs(OUT, exist_ok=True)

BASE = "https://upload.wikimedia.org/wikipedia/commons/"
FILES = [
    # (本地名, Commons 路径, 说明)
    ("ref_mosin_9130_sniper_nobg.png", "4/4d/Mosin-Nagant_m91-30_sniper_noBG.png",
     "M91/30(PU 狙击型) 抠底横向图 4657x1063 —— 主测源：托/管/照门比例"),
    ("ref_mosin_9130_sniper.jpg", "1/18/Mosin-Nagant_m91-30_sniper.JPG",
     "同上原图（带背景）4657x1063"),
    ("ref_mosin_9130_soviet.jpg", "b/b4/Soviet_M1891-30_rifle.jpg",
     "M1891-30 实物照 4288x2848"),
    ("ref_mosin_9130_a.jpg", "2/23/Mosin_91_30.jpg", "M91/30 实物照 3264x2448"),
    ("ref_mosin_m1891_nobg.png", "2/2c/Mosin-Nagant_M1891_-_Ryssland_-_AM.032971_%28NB%29.png",
     "M1891（M91 家族，抠底横向）2450x900 —— 交叉校验"),
    ("ref_mosin_m1891_dragoon_nobg.png", "8/87/Mosin-Nagant_M1891_Dragoon_Russland_AM067668_noBG.png",
     "M1891 龙骑兵型（抠底横向）2050x800 —— 交叉校验"),
    ("ref_m91_drawing.svg", "3/35/M91_drawing.svg", "M91 线描图纸（矢量，可解析坐标）"),
    ("ref_mosin_manual.jpg",
     "f/fc/US_War_Dep_Pamphlet_No_21-30_OUR_RED_ARMY_ALLY_April_1945_-_49_WEAPONS_INFANTRY_"
     "Tokarev_M1940_rifle%2C_Mosin_M1891-30_rifle%2C_PPSh_tommy_gun%2C_M1943_tommy_gun_-_"
     "WW2_USSR_Soviet_Russian_soldiers_military_info_DA_PAM21-30_Public_domain.jpg",
     "1945 美军手册（公有领域）内含 M1891-30 部件线描图"),
]

for name, path, note in FILES:
    dst = os.path.join(OUT, name)
    if os.path.exists(dst) and os.path.getsize(dst) > 1000:
        print("skip  %-34s %8d B" % (name, os.path.getsize(dst)))
        continue
    for attempt in range(1, 5):
        try:
            req = urllib.request.Request(BASE + path, headers=UA)
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
            with open(dst, "wb") as f:
                f.write(data)
            print("ok    %-34s %8d B  %s" % (name, len(data), note))
        except Exception as e:
            print("retry %-34s try%d  %s" % (name, attempt, e))
            time.sleep(8 * attempt)
        else:
            break
    time.sleep(4)  # Commons 对突发请求会 429
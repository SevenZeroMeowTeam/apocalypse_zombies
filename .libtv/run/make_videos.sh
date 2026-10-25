#!/usr/bin/env bash
# 创建 8 个视频节点（关键帧 -> 图生视频，Wan 3.0），只建节点不触发生成
set -euo pipefail
cd /f/mcmod/apocalypse_zombies-main
LIBTV="C:\Users\Administrator\.libtv\libtv.exe"

"$LIBTV" node --x 100 --y 380 create "成片01·血月之城" -t video \
  -s "model=Wan 3.0" -s duration=5 -s resolution=720P -s enableSound=on \
  --left "分镜01·血月之城" \
  --prompt "让镜头缓缓向前推进，穿过浓雾望向残破的方块城市；火星余烬向上飘散，血月红光轻微脉动，雾气在楼宇间流动；低沉不祥的环境轰鸣声，电影感" \
  > ".libtv/run/mk_v1.json" 2>".libtv/run/mk_v1.err" && echo "OK v1" || { echo "FAIL v1"; tail -2 ".libtv/run/mk_v1.err"; }

"$LIBTV" node --x 440 --y 380 create "成片02·僵尸围城" -t video \
  -s "model=Wan 3.0" -s duration=5 -s resolution=720P -s enableSound=on \
  --left "分镜02·僵尸围城" \
  --prompt "成群的方块僵尸缓慢而阴森地朝镜头走来，四肢僵硬摆动，浓雾在它们身边旋转流动，灰烬缓缓飘落；低沉诡异的环境音，恐怖片氛围" \
  > ".libtv/run/mk_v2.json" 2>".libtv/run/mk_v2.err" && echo "OK v2" || { echo "FAIL v2"; tail -2 ".libtv/run/mk_v2.err"; }

"$LIBTV" node --x 780 --y 380 create "成片03·狙击时刻" -t video \
  -s "model=Wan 3.0" -s duration=5 -s resolution=720P -s enableSound=on \
  --left "分镜03·狙击时刻" \
  --prompt "幸存者稳稳端起步枪瞄准远方街道，轻微的呼吸起伏，衣摆在风中飘动，屋顶下方的雾气缓缓流动，僵尸剪影在雾中缓慢移动；镜头轻微缓慢环绕，紧张压迫的氛围，环境风声" \
  > ".libtv/run/mk_v3.json" 2>".libtv/run/mk_v3.err" && echo "OK v3" || { echo "FAIL v3"; tail -2 ".libtv/run/mk_v3.err"; }

"$LIBTV" node --x 1120 --y 380 create "成片04·致命一击" -t video \
  -s "model=Wan 3.0" -s duration=5 -s resolution=720P -s enableSound=on \
  --left "分镜04·致命一击" \
  --prompt "步枪轰然开火，枪口迸发明亮火焰，弹壳弹出坠落，枪身明显后坐；下方雾中僵尸群被惊动；画面轻微震动，响亮的枪声与回音" \
  > ".libtv/run/mk_v4.json" 2>".libtv/run/mk_v4.err" && echo "OK v4" || { echo "FAIL v4"; tail -2 ".libtv/run/mk_v4.err"; }

"$LIBTV" node --x 1460 --y 380 create "成片05·天火陨落" -t video \
  -s "model=Wan 3.0" -s duration=5 -s resolution=720P -s enableSound=on \
  --left "分镜05·天火陨落" --left "参考·小行星" \
  --prompt "燃烧的小行星拖着火焰尾迹从夜空持续坠向城市，表面火舌翻卷，天空随它的逼近逐渐被照亮，火星四溅；屋顶上的小人仰望；镜头轻微下仰跟随，轰鸣声由远及近逐渐增强，史诗感。以第一张参考图的构图与主体为准，第二张参考图仅作小行星表面细节参考" \
  > ".libtv/run/mk_v5.json" 2>".libtv/run/mk_v5.err" && echo "OK v5" || { echo "FAIL v5"; tail -2 ".libtv/run/mk_v5.err"; }

"$LIBTV" node --x 1800 --y 380 create "成片06·轨道天罚" -t video \
  -s "model=Wan 3.0" -s duration=5 -s resolution=720P -s enableSound=on \
  --left "分镜06·轨道天罚" --left "参考·天基炮" \
  --prompt "轨道能量光束持续轰击城市中心，白蓝色光柱贯穿夜空，冲击波环向四面八方扩散，方块建筑被气浪掀碎，碎块飞散，烟尘翻滚；画面剧烈震动，雷鸣般的巨响，神罚般的压迫感。以第一张参考图的构图与主体为准，第二张参考图仅作氛围参考" \
  > ".libtv/run/mk_v6.json" 2>".libtv/run/mk_v6.err" && echo "OK v6" || { echo "FAIL v6"; tail -2 ".libtv/run/mk_v6.err"; }

"$LIBTV" node --x 2140 --y 380 create "成片07·焚城余烬" -t video \
  -s "model=Wan 3.0" -s duration=5 -s resolution=720P -s enableSound=on \
  --left "分镜07·焚城余烬" \
  --prompt "火风暴在废墟城市间肆虐蔓延，火焰翻滚扩张，熔岩沿龟裂的街道流淌，火星如风暴般旋转飞舞；僵尸剪影在火光中缓缓前行；末日般的咆哮声与烈焰噼啪声" \
  > ".libtv/run/mk_v7.json" 2>".libtv/run/mk_v7.err" && echo "OK v7" || { echo "FAIL v7"; tail -2 ".libtv/run/mk_v7.err"; }

"$LIBTV" node --x 2480 --y 380 create "成片08·片尾字卡" -t video \
  -s "model=Wan 3.0" -s duration=3 -s resolution=720P -s enableSound=on \
  --left "分镜08·片尾字卡" \
  --prompt "片尾字卡：镜头极其缓慢地推近标题，血月辉光轻微脉动，雾气缓缓流动；一声深沉史诗级的轰鸣收尾，庄重收束" \
  > ".libtv/run/mk_v8.json" 2>".libtv/run/mk_v8.err" && echo "OK v8" || { echo "FAIL v8"; tail -2 ".libtv/run/mk_v8.err"; }

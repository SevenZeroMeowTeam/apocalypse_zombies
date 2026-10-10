# 猫耳娘（cat_girl）—— 美术台账

## 真相源（只认这个，别手改它产出的 JSON）
| 产物 | 生成器 | 备注 |
|---|---|---|
| `cat_girl_spec.json` / `cat_girl.bbmodel` / 128² 皮肤 / 装机 geo | `tools/cat_girl_v4_build.py` | 几何 + 逐面 UV 装箱 + 贴图一体 |
| `src/.../geo/cat_girl.geo.json`（装机） | `tools/cat_girl_geo.py` | spec → 逐面 `uv/uv_size`，带 `--check` + 自动 `.bak` |
| `art/cat_girl/cat_girl.bbmodel` | `tools/cat_girl_bbmodel.py` | 标准 .bbmodel，Blockbench 原生加载 |
| `preview.png` / `compare.png` / `face_vs_ref.png` | `tools/cat_girl_preview.py` / `cat_girl_compare.py` | 核验图 |
| 逐像素脸 ASCII / 逐带宽度 | `tools/cat_girl_v4_audit.py` / `cat_girl_v4_bands.py` | 对称与居中的**量化**判据 |

## 硬指标（改动后必须复跑核验）
- 128×128 皮肤；脸层 `(0,0,44,32)`，7.9 px/u。
- geo：`geometry.cat_girl`、31 骨 / **126 方块**、每块逐面 UV、rest 无旋转。
- 对称：左右眼 / 眉 / 腮红用整数列镜像公式 `a' = w − a − width`；眉实测 `(4,12)↔(31,39)`、腮红 `(8,16)↔(27,35)`。
- 嘴：宽取偶数，中心落在 22.0（44 列）。

## 工具链跑法
```bash
py tools/cat_girl_v4_build.py && py tools/cat_girl_bbmodel.py && py tools/cat_girl_preview.py && py tools/cat_girl_compare.py && py tools/cat_girl_geo.py
```

## 已知坑
- 图像分析必须用 `py`（`python`/`python3` 无 PIL）。
- 半透明画笔（`vgrad`）必须先铺 `C_SKIN` 底色，否则脸被洗成发色。
- 参考图：`C:/Users/Administrator/Downloads/Meshy_AI_straight_standing_cat_girl_front.png`。

## 待修
- `WIP_Java_编译待修.md`：已全部修完（1.1.66 出货时清零），保留作复盘。

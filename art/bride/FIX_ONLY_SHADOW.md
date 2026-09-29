# 实机故障报告：指令召唤的美女僵尸「没有实体，只有阴影」

**结论：不是碰撞箱问题，是 geo 的 UV 面键写错导致 GeckoLib 静默丢弃全部四边形。**
**修复版本：`1.1.9`（md5 `0c957adeb3e3097cab18250a4200d15b`），已部署。**
（`1.1.8` = 纯 UV 面键修复；`1.1.9` = 在其上加碰撞箱 1.95→2.0。）

### 附：修复的硬证据（`javap` 直接反汇编运行时依赖，非源码印象）

对**运行时真正加载的** `mods/geckolib-forge-1.20.1-4.8.4.jar` 反汇编：

```
UVFaces                      → 仅 6 个字段：north / south / east / west / up / down
UVFaces.deserializer()       → 读取的字面键：north / south / east / west / up / down（无单字母）
BakedModelFactory.buildQuad  → 13: UVFaces.fromDirection(Direction)
                               20: ifnonnull 25
                               23: aconst_null
                               24: areturn     ← 面 UV 为 null 即返回 null ⇒ 该面不产生四边形
```

同一段反汇编在缓存里的 4.7.4 与运行时的 4.8.4 上**指令序列一致**（`geckolib_version=4.8.4`，缓存里的
`4.7.4_*` 目录只是历史遗留，**不存在 dev/runtime 版本漂移**）。

### 碰撞箱（用户本轮第二项要求）

原 hitbox `.sized(0.6F, 1.95F)` **一直存在**，与原版僵尸同尺寸，不是缺失——现象是渲染层造成的。
本轮按用户要求抬到 **`.sized(0.6F, 2.0F)`**，贴合模型头顶（32u = 2.00 Block；发髻 33.2u 仍在框外 ±0.075）。
字节码校验：`ModEntities.class` 中新娘那条 `ldc // float 0.6f` 后跟 `fconst_2`（= 2.0f，javac 对 2.0f 用常量指令
而非 `ldc`，故 grep `ldc` 查不到，须按 `fconst_2` 核）。


---

## 1. 症状与误判

实机反馈：`/summon apocalypse_zombies:bride_zombie` 后**只见一团阴影，模型本体不可见**。
用户初判为「没有碰撞箱」，但该判断与现象不同源，实测被证伪。

## 2. 排查链（逐项证伪）

| 猜想 | 证据 | 结论 |
|---|---|---|
| 实体 hitbox = 0 | `ModEntities` 里 `EntityType.Builder.sized(0.6F, 1.95F)` | ✗ 证伪，hitbox 正常 |
| 渲染器未注册 | `ClientModBusEvents` 里 `registerEntityRenderer(..., BrideGeoRenderer::new)` | ✗ 证伪，已注册 |
| geo 尺寸/坐标错 | 渲染报告 `mc_bbox = [-6.2, 0, -4.7, 6.2, 33.2, 8.4]` ⇒ 高 33.2u = 2.075 Block | ✗ 证伪 |
| 实体类没接 GeckoLib | `BrideZombie extends Monster implements GeoEntity` + `registerControllers` + `AnimatableInstanceCache` 齐全 | ✗ 证伪 |
| 贴图/动画没打进包 | 包内 geo/tex/anim 与源码**逐字节一致** | ✗ 证伪 |
| 游戏日志有异常 | `latest.log` / `debug-*.log.gz` 里 bride/geckolib 零异常、零召唤记录（那次测试会话语料已轮转） | 无线索 |
| **geo 的 UV 面键** | **美女僵尸用 `n/e/s/w/u/d`，四把已正常显示的枪械全用 `north/south/east/west/up/down`** | ✓ **根因** |

## 3. 根因（GeckoLib 4.8.4 源码级证据）

`geckolib-forge-1.20.1-4.8.4-sources.jar`：

1. `loading/json/raw/UVFaces.java` —— 反序列化**只读全名**：

   ```java
   @SerializedName("north") private FaceUV north;
   @SerializedName("south") private FaceUV south;
   @SerializedName("east")  private FaceUV east;
   @SerializedName("west")  private FaceUV west;
   @SerializedName("up")    private FaceUV up;
   @SerializedName("down")  private FaceUV down;
   ```

   ⇒ 单字母键**不报错、不警告**，直接落空（Gson 无视未知字段）。
2. `loading/object/BakedModelFactory.buildQuad()`：

   ```java
   if (!uvUnion.isBoxUV()) {
       FaceUV faceUV = uvUnion.faceUV().fromDirection(direction);
       if (faceUV == null) return null;      // ← 该面不生成四边形
       ...
   }
   ```

   ⇒ 828 个面全部 `null` ⇒ **模型一个四边形都没有**。
3. 阴影由 `EntityRenderDispatcher` 独立绘制、与模型无关 ⇒ **只剩阴影**，与实机现象逐字吻合。

## 4. 修复

| 文件 | 改动 |
|---|---|
| `tools/bride_v2.py` | 新增 `GEO_FACE_NAME` 映射；序列化 geo 时把内部单字母标签翻译成全名（内部逻辑仍用单字母，不动板面语言）|
| `tools/bride_v2_scene.py` | `FACE_KEY` 改全名 + `FACE_KEY_LEGACY` 回退；新增统计 `uv_faces` / `uv_short_keys` / `uv_missing` |
| 两处各加守卫 | 生成器自校验 460/460（+「UV 面键为全名」「每体 6 面 UV 齐全」）；渲染报告新增同款两条 check，任一不过即报错 |

**注意**：`bride_v2_scene.py` 原来的 `FACE_KEY` 是**为了配合这个坏输出**写的（把全名映射回单字母）——同源缺陷，一并修掉。

## 5. 验证

- 源码 geo：`north 138 / east 138 / south 138 / west 138 / up 138 / down 138` = 828 面，**单字母 0**；与四把枪械键集合**完全一致**。
- 全工程 + 出货包内 geo 扫描：**单字母键 0**（无第二处同源缺陷）。
- 生成器自校验 **460/460**；geo 哈希 `c3dc8f1662f78021…`（本轮未再变动）。
- Blender 用同一份 JSON 渲染 **13/13 张、errors `[]`、10/10 check 通过**。
- 出货包 `apocalypse_zombies-1.1.8.jar`：包内 geo 面键全名 ✓、geo/tex/anim 与源码逐字节一致 ✓、`mods.toml version="1.1.8"` ✓、SRG `m_` 计数 **50**（与可用旧包 1.1.6 同口径一致）✓。
- 部署：`mods/apocalypse_zombies-1.1.8.jar`，md5 双向 `a060346f…` ✓。

## 6. 附带解决：外部进程锁

`build/libs/apocalypse_zombies-1.1.7.jar` 被外部进程持久持有（只禁删/改名、允许写入；无 java 进程时仍 busy）。**升版号到 `1.1.8` 换文件名即绕过**，本轮无需副本工程写回。

## 7. 哈希登记

| 产物 | sha256 |
|---|---|
| geo | `c3dc8f1662f78021265343de214e8882d345e7c0c1f61c6d3176b8dacf8bedda` |
| anim | `c57fb93a5e6d3084e6a12d61fcae5b897000765ce181c8b36c9d4d6f08c1b030`（未变）|
| tex | `5b6f07b6e29765eef82322be682569fd98e220e9ff4a2f2616d095500ad306d1`（未变）|

修复前的坏 geo 留档：`art/bride/backup_512_0926_1127/bride_zombie.geo.badkeys.json`（`35537224…`，全单字母键）。

## 8. 复现 / 回滚

```bash
# 复现（生成 → 贴图 → 渲染三项校验）
python tools/bride_v2.py            # 期望：自校验 全部通过 (460/460)
python tools/bride_v2_skin.py       # 贴图（本轮未改配色，哈希应保持 5b6f07b6）
D:/Blender/blender.exe --factory-startup -b -P tools/bride_v2_scene.py
# 期望：13 张、errors []、含「geo UV 面键全名」「所有面 UV 均被解析」两条 pass

# 回滚到 1.1.7
mv .../mods/apocalypse_zombies-1.1.8.jar .../mods/apocalypse_zombies-1.1.8.jar.bak
mv .../mods/apocalypse_zombies-1.1.7.jar.old.bak .../mods/apocalypse_zombies-1.1.7.jar
```

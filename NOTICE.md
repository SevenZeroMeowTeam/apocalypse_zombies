# 第三方内容与许可声明（NOTICE）

本项目（Apocalypse Zombies）**自身代码**采用 **GPL-3.0-or-later**，全文见 `LICENSE`。

**TaCZ 不是本模组的依赖，也不随本模组分发。** 它只是开发期的参照物：持枪/换弹/拉栓的动作
参考其 `ai_awp` 的姿态，音效是**临时借用**的原样副本。借用内容仅存在于**开发自用包**里，
可分发包（`-clean.jar`）中一点都没有。

## 产物一览

| 产物 | 含 TaCZ 内容 | 许可 | 用途 |
|---|---|---|---|
| `apocalypse_zombies-<ver>.jar` | **有**（22 个音效 + 转录动画） | `GPL-3.0-or-later / CC BY-NC-ND 4.0` | 开发 / 自用。**不得商业使用，不得公开分发** |
| `apocalypse_zombies-<ver>-clean.jar` | **无** | `GPL-3.0-or-later` | 分发用。动画为完全原创的手工版 |
| `geckolib-forge-1.20.1-4.8.4.jar`（`build/netease/`） | 无 | **MIT**（GeckoLib 自身） | 网易中国版 Java 版用：与模组 jar **并列**装进 `mods/`。顶层自带 `LICENSE`，随包分发即满足署名义务 |
| `apocalypse_zombies-borrowed-assets.zip` | **有** | 同开发包 | 本地资源包。装进 `resourcepacks/` 后把借来的音效与动画覆盖回来 |

构建：`./gradlew clean build cleanJar borrowedPack neteaseLibs` —— 产物在 `build/libs/`，依赖 jar 在 `build/netease/`。

> 网易版用的是**默认 jar（开发包）**，因此同样含 TaCZ 借用内容，同样**不得商用、不得公开分发**。
> 要上架网易平台须改用 clean 基线，见 `docs/wiki/10-网易Java版适配.md` 的未决事项。
> ⚠ 依赖**不要**用 jar-in-jar 内嵌（网易客户端会静默退出），见同文档第三节。

## 借用来源（署名）

| 项 | 值 |
|---|---|
| 项目名 | Timeless & Classics Guns: Zero（永恒枪械工坊：零） |
| 作者 | **Serene Wave Studio \| Timeless Squad** |
| 版本 | `tacz-1.20.1-1.1.8-hotfix` |
| 许可 | **GPL-3.0（代码） / CC BY-NC-ND 4.0（资产）** |
| 依据 | 其 mod jar 内 `META-INF/mods.toml` 原文：`license = "GPL3 / CC BY-NC-ND 4.0"` |

| 借用内容 | 开发包位置 | 状态 |
|---|---|---|
| 22 个音效 `.ogg` | `src/main/resources/assets/apocalypse_zombies/sounds/awm/` | **未修改副本**，md5 与原件逐一相同 |
| 动画数据（`ai_awp` 角度 / 位移 / 时间轴 / `sound_effects`） | `art/awm/awm.animation.json` | **派生作品**（逐键转录，再按我们模型尺寸换算位移） |

## 代码边界

**本项目代码是自写实现 —— 没有照抄 TaCZ 的源码，也不依赖 TaCZ。**

- 仓库内所有类都在 `com.apocalypse.zombies` 下，**编译期与运行期不引用任何 `com.tacz` 类**；
  `build.gradle` 的依赖只有 GeckoLib。自查命令（应为空）：
  `grep -rn "com\.tacz" --include="*.java" src/`
- 借用的只有**数据**：动画曲线与音效时刻轴（见上表）。**动作逻辑**（打一发拉一下栓、
  战术 / 空仓换弹分流、开火分射手与近邻两套混音）是按它的行为来设计的，**实现由本项目自己写**：
  服务端权威判定、NBT 状态机、背包 / 开镜 / 射击封包。
- 动画数据**适配了本模型的骨骼**：角度按其 rig 约定映射到我们的骨骼名后沿用，位移按本模型比例
  `S_GUN = 57.07 / 23.97` 换算。转录脚本 `tools/tacz_anim_transcribe.py` 与复核脚本
  `tools/check_awm_anim.py` 都是本项目自写的。

## 依赖

| 依赖 | 版本 | 许可 | 随本模组分发？ |
|---|---|---|---|
| GeckoLib 4 | `geckolib-forge-1.20.1-4.8.4`（作者 Gecko, Eliot, AzureDoom, DerToaster, Tslat, Witixin） | **MIT** | 默认包 **否**；网易版 **是**（作为独立 jar 并列分发） |

GeckoLib 是 `mandatory=true` 的硬依赖。**默认包由玩家自行安装，我们不捆绑**（已核对：默认包与纯净包内
GeckoLib 条目数为 0）。 —— 但要够精确，版本不一致（开发编译 4.4.x / 运行装 4.8.x）会在 API 层面炸。

**例外：网易版**。网易中国版 Java 版的 `mods/` 由平台分发，既没有 GeckoLib、玩家也无法自行安装，
所以网易版的出货是把 GeckoLib 4.8.4 作为**独立 jar 与模组并列**装进 `mods/`（平台侧对应「前置组件」）。
MIT 允许再分发，条件是附许可与版权声明：该 jar 顶层自带 `LICENSE`，随手分发即满足，此处一并列明。
做法与取证（含为何**不能**用 jar-in-jar 内嵌）见 `docs/wiki/10-网易Java版适配.md`。

## 构建环境（别人要能复现）

- Minecraft `1.20.1` · Forge `47.4.0`（本地运行实例 47.4.23）· GeckoLib `4.8.4` · JDK 17
- `./gradlew clean build` → 开发包；再加 `cleanJar borrowedPack` → 纯净包与本地资源包
- **Not affiliated with Mojang or Microsoft.** 本模组不含任何 Minecraft 官方资源，使用需正版游戏。

## 开源发布对照清单

公开源码 = 分发，规则与发 jar 完全相同。

| 要标明的 | 落在哪 | 状态 |
|---|---|---|
| 本项目许可全文 | `LICENSE`（GPL-3.0，也打进 jar 的 `META-INF`） | 已就位 |
| jar 内许可字段 | `gradle.properties` 的 `mod_license` → `mods.toml` 的 `license` | 已就位 |
| 第三方内容署名 + 三条约束 | 本文「借用来源」、`art/awm/README.md` | 已就位 |
| 依赖及版本 | 本文「依赖」 | 已就位 |
| 可复现的构建环境 | 本文「构建环境」 | 已就位 |
| **版权行（年份 + 著作权人）** | 本文与 `README` | **待填 —— 只有项目所有者能定** |
| **公开仓库里的借用文件** | `src/main/resources/.../sounds/awm/*.ogg`（22 个）、`art/awm/awm.animation.json` | **见下方警告** |

### 署名解决不了 ND

把仓库公开，等于**公开发布从 TaCZ 动画数据派生的作品**，同时**分发它的 NC 资产** —— 这两条都不是
"标明什么"能满足的：CC BY-NC-ND 的 ND 恰恰禁止发布改编版本，署名（BY）无法替代授权。
公开仓库时只有两条路：

1. **不让借用内容进仓库**（推荐）：把上表最后一行那两个路径排除在公开仓库之外，仓库里放完全原创的
   手工动画；需要音效与转录动画的本地副本照旧留在自己机器上（`borrowed-assets.zip` 这套已经能做）。
2. **向 TaCZ 取得书面授权**，并把授权范围写进本文。

## 三条约束落在哪

- **BY 署名** —— 只要还在用，就必须署名；本文与 `art/awm/README.md` 均已署名到作者。
- **NC 非商业** —— 约束的是**含借用内容的那个包**（开发自用包与资源包）：不得售卖、不得挂付费墙、
  不得用于营利性整合包。**纯净包不含借用内容，不受此限**。
- **ND 不发布修改版** —— 音效是原样副本，满足；转录动画是派生的，所以它**只留在自用包里**，
  不进入分发产物。这也是纯净包换用手工动画的原因，不是为了绕开，而是本来就不该把它发出去。

## 想彻底了断（可选）

音效换成 CC0 枪声（freesound 之类，逐个核对许可）后，只需替换 `sounds/awm/*.ogg` 并改
`sounds.json` 里的 `name`，**Java 一行都不用动**；动画则以 `awm.animation.handmade.bak.json`
为起点重做曲线。两边都换掉后，本文只剩署名部分需要保留。

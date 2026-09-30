# 10 · 网易 Java 版（中国版）适配

**目标平台**：网易《我的世界》中国版 **Java 版 1.20** = **MC 1.20.1 + Forge 47.3.0**。
**结论**：本仓库代码**无需换语言**；唯一的硬阻断是 GeckoLib 这条 `mandatory` 依赖，处置方式只有一种能跑通 ——
**把 GeckoLib 作为独立 jar 与模组并列安装**。**绝不要内嵌 jar-in-jar**：实测会让网易客户端**静默退出**
（无异常栈、无 `hs_err_pid`、无 Windows 崩溃事件）。

---

## 〇、本次更新（1.1.46 → 1.1.47，2026-09-30）

> **追加（1.1.47）**：本线并入 1.1.47 后重发一次 —— `python tools/deploy_netease.py` **15 项判定全过**，
> 客户端 `mods/` 现为 `apocalypse_zombies-1.1.47-netease.jar`（**2,073,662 B · 259 条目**，与 `build/libs/`
> 下同名包**条目名集合相同、逐条目 CRC 全同**）+ `geckolib-forge-1.20.1-4.8.4.jar`
> （443 条目 · md5 `69531785e71b8ac219634657781b169b`）。
> 下面 1.1.46 段的取证、字节比对结论与未决事项都不变；产物版本号一律跟 `gradle.properties` 的 `mod_version` 走。

- **网易产物**：`build/netease/apocalypse_zombies-1.1.46-netease.jar`（2,072,194 B · 259 条目），由 `neteaseJar`
  （Copy 改名，**不重新打包**）产出 ⇒ 与 `build/libs/apocalypse_zombies-1.1.46.jar` **逐字节相同**
  （条目名集合相同、逐条目 CRC 全同 —— 脚本里是硬断言）。
  **md5 认了会踩坑，根因已定位**：`jar` 任务的 manifest 写了
  `'Implementation-Timestamp': new Date().format(...)`，这是**非确定性输入** ⇒ `jar` **永不 UP-TO-DATE**、
  每次构建重跑、md5 每次都变（实测三例：`3f301c03…`（09-30 装机首版）/ `c63cdadc…` / `119640c4…`）。
  核验认「条目数 + 逐条目 CRC」，别认 md5（与下面依赖包同一条道理）。
  内容：尸潮领主**第 3 阶段轮转死锁修复**（干等上限 → `onStarved()` 换槽兜底、`onEnd(finished)` 带参、
  亡语只清负面）+ 末尾追加 **4 招**（`CAGE_SLAM` / `PLAGUE_MIST` / `SOUL_DRAIN` / `HORDE_SCREECH`，动画 8 → 12 段）。
- **打包三件套（四份文件）**：`./gradlew jar neteaseJar neteaseLibs cleanJar --offline`（17 秒出齐）。
  第一、三个并列装进客户端 `mods/`；第四个是**上架候选**（见未决 #3）。

  | 产物 | 大小 | 条目 | 用途 |
  |---|---|---|---|
  | `build/netease/apocalypse_zombies-1.1.46-netease.jar` | 2,072,194 B | 259 | **网易客户端装这份**（`-netease` 后缀，一眼区分于开发包） |
  | `build/libs/apocalypse_zombies-1.1.46.jar` | 2,072,194 B | 259 | 开发/自用包（含借用 TaCZ 音效 / 转录动画；与上一行同一份字节） |
  | `build/netease/geckolib-forge-1.20.1-4.8.4.jar` | 1,038,208 B | 443 | 并列安装的依赖（= 平台「前置组件」） |
  | `build/libs/apocalypse_zombies-1.1.46-clean.jar` | 1,408,521 B | 234 | **上架候选**：剥掉 25 条 TaCZ 派生条目，动画退回手工原创版 |

- **本地包 ≠ CI 发布件（别当同一份比对）**：包内 `META-INF/NOTICE.md` 与仓库根 `NOTICE.md`
  **逐字节一致**（md5 `8afdb6b5346aac68a75defef465044d3`，含 GeckoLib 署名）—— 这条署名只存在于工作区那份
  `NOTICE.md`（未提交），所以本地打出来的包带上它，CI 从已提交源码出的发布件没有它。
  这也正是「网易线只在工作区」的可见后果。
- **API 面核验（本次改动的 5 个类逐个查 import）**：全是 1.20.1 原生 `net.minecraft.*` + `software.bernie.geckolib.*`，
  **零 Forge API** ⇒ 开发机 47.4.23 编译出来的包，在平台 47.3.0 上**无 API 面风险**（同一 MC 版本、同一 GeckoLib 4.8.4）。
  这是「换版本要不要重新适配」的判据：只看改动类是否引入 Forge API，不引入就不需要。
- **依赖导出**：`./gradlew neteaseLibs --offline` → `build/netease/geckolib-forge-1.20.1-4.8.4.jar`。
  **必须带 `--offline`**：联网解析会挂在上游 CDN 的 443 上（实测 4 分钟零进展、`build/netease/` 一直不落盘），
  缓存命中时 23 秒完成。`tools/deploy_netease.py` 已改成默认 `--offline` + 失败才退回联网。
- **依赖包同样不能认 md5**：本次导出 `69531785e71b8ac219634657781b169b`，平台侧现存那份 `1b8bd851bc57e2b87e285b98a7d92c76`；
  实测两者 **443 个条目逐字节相同**，唯一差异是 manifest 的 `Implementation-Timestamp`
  （`2026-06-20T21:06:28+1000` vs `2026-06-20T21:07:15+1000`）⇒ **上游同一个版本号下存在两种构建**。
  核验认「条目数 + Implementation-Timestamp + modId/版本」（脚本已打印这三项），别把 md5 写进长期文档。
- **平台会复位 `mods/`（手工丢包只有一次寿命）**：`game\.minecraft\mods\` 由平台按组件装配。
  启动器删测试记录（`ComponentManager.DeleteComponetInfo → TestHistoryManager.DeleteAllJavaGame`）会连坐复位该目录 ——
  2026-09-30 **17:37:39 删记录 → 17:41 手工丢进去的模组包被清掉**，只剩注册成组件的 geckolib。
  ⇒ 想让它长期在场，必须把模组也做成组件（`work.mcscfg` 的 `PreComponentIds`），不能只靠手工 copy。
- **已装入 1.1.46（2026-09-30 18:26，`python tools/deploy_netease.py`，15 项判定全过）**：客户端 `mods/` 现在是
  `apocalypse_zombies-1.1.46-netease.jar`（md5 `119640c46d74…`）+ `geckolib-forge-1.20.1-4.8.4.jar`（md5 `69531785…`），
  与本地构建产物**逐字节相同**。旧包挪到 **mods/ 同级** 的 `mods_backup/`（保 3 份，**不进 mods/**
  —— Forge 递归扫描会加载重复模组）。
- **验收必须读 DEBUG 级日志（本线踩过这个坑）**：`logs\latest.log` 是 **INFO 级**，**永远不会**出现模组发现段 ——
  只按它判断会得出「模组没加载」的错误结论。证据在 **DEBUG 级**的 `logs\debug-N.log.gz`。
  通过判据两条：`Found valid mod file apocalypse_zombies-<版本>.jar` + `Found 0 mod requirements missing (0 mandatory, 0 optional)`。
- **加载链路已实证通过（1.1.42，2026-09-30 10:34 会话，`debug-2.log.gz`）**：`Found valid mod file
  apocalypse_zombies-1.1.42-netease.jar` 与 `geckolib-forge-1.20.1-4.8.4.jar` 同在、`Found 0 mod requirements missing`，
  跑在 `forge-1.20.1-47.3.0-universal.jar` + `client-1.20.1-20230612.114412-srg.jar` 上 ⇒ 网易侧加载链路**通**。
  1.1.46 是同一链路的新包，待现场按上面两条判据复验。
- **`-netease` 后缀已恢复**：`build.gradle` 新增 `neteaseJar`（Copy：把 reobf 后的交付包改名为
  `apocalypse_zombies-<ver>-netease.jar` 落 `build/netease/`，与依赖包同位），脚本装的就是这一份。
  **刻意不写 `build/libs`**：Copy 会把整个目录声明成输出，与 `jar` 任务的输出目录重叠会被 Gradle 拒绝。
  将来要做差异化构建（例如网易版剥掉借用资源）就在该任务的 `from` 里加过滤。
- **客户端本身可用（排除环境问题）**：18:14:30 那次会话（当时 `mods/` 里没有我们的包）走到
  `Setting user: 七零喵团队` → 18:15:45「加入了游戏」，正常进世界。
- 本页与 `tools/deploy_netease.py`、`build.gradle` 的网易改动**只在工作区**：不提交、不推送。

---

## 一、目标平台的事实（2026-09-30 实测，非推测）

| 项 | 值 | 取证位置 |
|---|---|---|
| 客户端 | `F:\MCStudioDownload\game\.minecraft` | MCStudio 下载目录 |
| Minecraft | `1.20.1` | 启动日志 `--fml.mcVersion, 1.20.1` |
| Forge | **`47.3.0`**（开发机实例是 47.4.23） | 启动日志 `--fml.forgeVersion, 47.3.0` |
| JDK | 17（Adoptium 17.0.2） | 启动日志 |
| ModLauncher | `10.1.0+0+MinecraftChina_10.1.40fc820b`（**魔改版**） | 启动日志 |
| 官方组件 | `mods/4673366195655796690@3@0.jar` = `netease_official-studio-1.20.jar` | 包内 `META-INF/mods.toml`：`modId=netease_official`、`loaderVersion="[47,)"`、`minecraft [1.20.1,1.21)` |
| 官方 API 包名 | `com.netease.mc.mod`（`NeteaseOfficialMod` / `Config` / `filter` 聊天过滤 / `authlib` / `departmod`） | 官方 jar 条目 |
| Java 工程分类 | `F:\MCStudioDownload\work\<账号>\Java\{AddOn,GamePlay,Map,Mod}` | MCStudio 工作区 |
| 工程配置 | `work\<账号>\Java\Mod\<uuid>\work.mcscfg`（`Language:1` / `Versions:["1.20"]` / **`PreComponentIds`** / **`IsPreCom`**） | 组件目录 |

> `mods.toml` 里的 `forge [47,)` / `minecraft [1.20.1,1.21)` 两条依赖本来就满足中国版运行时。
> `PreComponentIds` / `IsPreCom` 说明平台原生就有「前置组件」概念 —— 这正是并列安装依赖的官方形态。

## 二、唯一的硬阻断：GeckoLib 是 mandatory 依赖

中国版客户端的 `mods/` 由平台分发（官方组件 + 你的组件），**没有 GeckoLib，玩家也无法自行安装第三方库**。
于是加载期被 ModSorter 拒绝（`F:\MCStudioDownload\game\.minecraft\logs\latest.log` 原文）：

```text
[main/ERROR] [net.minecraftforge.fml.loading.ModSorter/LOADING]: Missing or unsupported mandatory dependencies:
	Mod ID: 'geckolib', Requested by: 'apocalypse_zombies', Expected range: '[4.8.4,)', Actual version: '[MISSING]'
```

来源是 `src/main/resources/META-INF/mods.toml` 里这段（**保留**：并列安装的依赖正是用来满足它）：

```toml
[[dependencies.apocalypse_zombies]]
    modId="geckolib"
    mandatory=true
    versionRange="[4.8.4,)"
    ordering="AFTER"
    side="BOTH"
```

## 三、处置：并列安装 GeckoLib（`neteaseLibs`）

两种做法都真机跑过（同一台机器、同一天、同一个客户端）：

| 做法 | 结果 | 日志证据 |
|---|---|---|
| ✗ 打进 `META-INF/jarjar/`（jar-in-jar） | **客户端静默退出**，界面弹 `启动失败，请稍后重试` | 加载器已认出 `Found valid mod file geckolib-forge-1.20.1-4.8.4.jar`，死点在 `oshi.util.FileUtil`，无异常栈 |
| ✓ `mods/` 里并列一个顶层 `geckolib-forge-1.20.1-4.8.4.jar` | **正常加载并进入游戏游玩** | `Setting user`、`apocalypse_zombies-common.toml` 被 `modloading-worker-0` 加载、游戏内出现本模组的死亡提示 |

并且顶层 jar 在场时，Forge 的 `JarSelector` 会**优先用顶层那个**，连包里残留的内嵌副本都不碰：

```text
[WARN] [net.minecraftforge.jarjar.selection.JarSelector/]: Attempted to select a dependency jar for
       JarJar which was passed in as source: geckolib. Using Mod File: ...\mods\geckolib-forge-1.20.1-4.8.4.jar
```

### 构建

```bash
./gradlew jar neteaseLibs
# → build/libs/apocalypse_zombies-<ver>.jar              本模组（默认 jar，reobfJar 产出）
# → build/netease/geckolib-forge-1.20.1-<glver>.jar      依赖（生产版，原文件名）
```

`neteaseLibs` 刻意输出到 `build/netease/` 而不是 `build/libs/`：与 `reobfJar` 共用输出目录会触发
Gradle 的隐式依赖校验而构建失败。文件名保持 `geckolib-forge-1.20.1-<ver>.jar` 原样 ——
顶层 jar 的识别与 `JarSelector` 的选源都依赖它。

### 部署到网易客户端

```bash
python tools/deploy_netease.py            # 构建 + 包内自检(15 项) + 装入网易 mods/
python tools/deploy_netease.py --no-build # 复用已有产物，只做出货与部署
```

脚本做三件事（判据是退出码，与 `tools/` 其余门禁一致）：

1. **包内自检**：硬断言**本模组 jar 内不含 `META-INF/jarjar/`**（含了就会静默退出）；`mods.toml`
   仍是 `modId=apocalypse_zombies` + `geckolib` 且 `mandatory=true`；依赖 jar 的 modId/版本自洽、
   抽样含 SRG 符号（证明是线上生产版而非开发编译版）、自带 `LICENSE`。
2. **装载**：`mods/` 里旧的 `apocalypse_zombies-*` / `geckolib-*` 一律挪成 `.old.bak`（非 `.jar`
   后缀，Forge 不扫），拷入两个新包并逐字节复核 md5，最后断言"恰好一个模组 + 一个依赖"。
   > 游戏没退出时 jar 被进程持久持有（禁删/改名），脚本会**拒绝继续**而不是留下新旧两份同 modId 的包。
3. **验收指引**：打印客户端日志路径与通过标准。

平台侧（MCStudio）等价做法：把 GeckoLib jar **也作为一个组件导入**，与模组组件一起选中 ——
对应 `work.mcscfg` 的「前置组件」。手工丢进 `mods/` 也能跑（实测可行），但走组件流程更贴近发布形态；
而且**平台删测试记录/重新装配时会把手工信手丢进去的包清掉**（见〇节 17:41 那次复位），所以手工丢包只够当场跑一次。

## 四、许可边界（分发 GeckoLib 之后的 NOTICE 义务）

- GeckoLib 4.8.4 是 **MIT**：随包分发**合法**，前提是附许可与版权声明。
  导出的依赖 jar 顶层自带 `LICENSE`（`deploy_netease.py` 会断言这一点），`NOTICE.md` 里也单独记一笔。
- 本模组 jar 目前是**开发包**（含 TaCZ 借用音效与转录动画，CC BY-NC-ND）。
  **要上架网易平台必须改用 clean 基线**（见下节待办）。

## 五、未决事项 / 后续轨道

| # | 事项 | 说明 |
|---|---|---|
| 1 | 网易审核是否允许「前置组件」携带第三方库 | 本地无网易 Java 版审核规范文档（开发者平台需登录）。若不允许，转轨道 2 |
| 2 | **去 GeckoLib**（备用轨道） | 把 `geo/*.geo.json`（本身已是 Bedrock 几何格式 `format_version 1.12.0`）烘焙成原版 `ModelPart` 层级 + 自写关键帧驱动，替代 7 个 `*GeoModel` / 8 个渲染器 / 第一人称姿态层 |
| 3 | 网易版 clean 产物 | 出货改用 clean 基线（剥离 TaCZ 音效与转录动画），供上架 |
| 4 | 逐子系统真机验证 | 进化 6 阶 / 尸潮 4 波 / 7 种月相 / 6 只特殊怪 / 5 把枪。**已验证到「模组能加载并跑起玩法」这一步**，逐项验收仍未做；1.1.46 的第 3 阶段修复 + 4 新招也在待验收之列（见〇节） |
| 5 | **把模组做成平台组件**（而不是手工丢 `mods/`） | 手工丢包会被平台复位 `mods/` 时清掉（〇节 17:41 实证）；组件化后由 `PreComponentIds` 装配，才是可重复的发布形态 |
| 6 | 依赖包锁指纹 | 上游 4.8.4 有两个构建（〇节）⇒ 若要求可复现，给 `neteaseBundledLibs` 加 Gradle 依赖校验元数据，或把 dep jar 冻结进工作区 |

## 六、启动失败排查（含一次误判的复盘）

**现象**：MCStudio 启动 Java 版 1.20 后弹 `启动失败，请稍后重试`，游戏进程静默消失。

**判"静默死"而不是崩溃的方法**（这部分仍然有效）：日志无异常栈、`crash-reports/` 无新文件、
`hs_err_pid*.log` 不存在、Windows 应用程序日志在同一时间窗内没有 `Application Error` / WER 事件
⇒ 进程是被 `exit()`/外部终止的，不是 JVM 崩溃。

**定位过程（二分）**

| 步骤 | 结果 |
|---|---|
| 全部 mods 只剩官方组件 | ✅ 正常进游戏 |
| 单独放 `geckolib-forge-1.20.1-4.8.4.jar`（普通顶层 jar） | ✅ 正常进游戏 |
| 放内嵌了 GeckoLib 的 `-netease.jar` | ❌ 静默退出 |
| 内嵌包 + 顶层 GeckoLib 同时在场 | ✅ 正常（`JarSelector` 用了顶层那个，没碰内嵌副本） |

⇒ 根因是 **jar-in-jar 本身**，与 GeckoLib、与本模组代码都无关。

**⚠ 一次误判的复盘**：中途做过"把 jar 从 MCStudio 组件目录 + 游戏 mods 目录都移走"的对照实验，
结果是"仍然失败"，于是**错误地**得出了"与包无关、是启动器环境问题"的结论。
实际情况是：把 jar 从**组件目录**移走会让启动器在装配阶段就失败（与游戏加载是两回事）。
教训：对照实验**一次只动一个变量**，且要确认被移走的对象属于哪一环（装配 vs 加载）。

**另外并存但非本次根因的干扰项**（若将来遇到"什么都对却起不来"可回来查）：
启动器会话日志 `%LOCALAPPDATA%\Netease\MCStudio\log\<日期>\<时间戳>.log` 里的
`Support Component cache failed for unknown reason`、`StudioEnvSdkHelper init error! code: 201 initialize download error`；
以及事件日志里的 `NVIDIA OpenGL driver failed DxPresent (createDevice)`。

## 七、相关文件

| 文件 | 关系 |
|---|---|
| `build.gradle` | `neteaseBundledLibs` 配置 + `neteaseLibs` 任务（文件末尾），含"为什么不能内嵌"的实证注释 |
| `tools/deploy_netease.py` | 网易出货脚本：构建 + 15 项包内自检 + 并列安装两个 jar |
| `src/main/resources/META-INF/mods.toml` | geckolib 依赖声明（**不要删**） |
| `NOTICE.md` | 产物许可表、GeckoLib 随包分发说明 |
| `readme.md` | 构建命令与产物表 |


# 网易 Java 版适配线更新到 6.4.1

## Context
模组当前 6.4.1(Forge 1.20.1),但网易中国版 Java 版适配线(`feat/netease-java-adapt`,单提交 e44c0b2)停在 1.1.47 基线,落后 main 172 个提交。期间 main 经历了音效自备(1.1.93)、clean 基线(4.0.0)、scorched 贴图内嵌、多把枪械/轨道炮/末日菜单等大量变更。

网易适配方案(1.1.47 上已真机实证):GeckoLib 内嵌 jar-in-jar 会让网易客户端静默退出,必须把**生产版** GeckoLib jar 与模组 jar **并列**装进网易实例 mods/。产物线 = build.gradle 的 `neteaseJar`/`neteaseLibs` 任务 + `tools/deploy_netease.py`(构建 + 15 项自检 + 装机)。

本次目标:把适配线 rebase 到 main 最新,校准过时文档,构建 6.4.1-netease 产物并跑包内自检。按你的选择:**不装机**(网易实例 F:/MCStudioDownload 已不存在,跳过部署校验),更新后仍留独立分支,main 不动。

## 改动内容

### 1. rebase(独立分支)
- `git checkout -b feat/netease-java-adapt origin/feat/netease-java-adapt` → `git rebase main`
- 预期 6 文件中 5 个干净套用;唯一实质冲突:**NOTICE.md 产物一览表**(main 因 1.1.93 音效自备重写过该表)——把 geckolib 行插进 main 新表,保持"网易版例外(MIT 并列分发,顶层自带 LICENSE)"说明
- readme 3 个 hunk、build.gradle 尾部追加 58 行、wiki/10 新文件、wiki/README.md 索引行预期干净;readme 已从 632 行膨胀到 4025 行,若 git 报冲突则按语义手工合并

### 2. 文档语义校准(git 合并后内容过时,需手工改)
- NOTICE.md 网易 blockquote:"同样含 TaCZ 借用内容" → 按 1.1.93 后口径(借用内容只剩 AWM 转录动画,音效自备)
- wiki/10-网易Java版适配.md §〇:"本页与相关改动只在工作区不提交不推送" → 改为"维护在 feat/netease-java-adapt 分支,不进 main"
- wiki/10 §三:旧包"挪成 .old.bak" → 按脚本实际行为"挪到 mods_backup/ 保最新 3 份"
- wiki/10 补 6.4.1 重放实测段(新 jar 字节数/条目数/自检结果,风格沿用原 1.1.47 实测表)

### 3. tools/deploy_netease.py 增加 --no-deploy
- argparse 加 `--no-deploy`:跳过部署段(mods_backup 挪旧包/copy2 装机)与自检 13-15 项(部署后 md5/mods 集合断言),验收段改为打印产物路径提示;`--no-build` 语义不变
- 版本号/路径常量不动:脚本动态读 gradle.properties 的 mod_version/geckolib_version,6.4.1 自动兼容

### 4. 提交(版本号三处字面量不动)
- rebase 提交只解决冲突;另加一个新提交记录本次更新(6.4.1 基线 + 文档校准 + --no-deploy),中文提交信息按仓库风格
- gradle.properties(6.4.1)/根 mod.toml/readme 头表均不改

## 验证
1. `python tools/deploy_netease.py --no-deploy`:构建 `jar neteaseJar neteaseLibs` + 包内自检 1-12 全过
   - 产物:`build/netease/apocalypse_zombies-6.4.1-netease.jar` + `geckolib-forge-1.20.1-4.8.4.jar`
   - 自检覆盖:与 build/libs 同名包逐字节相同、不含 jar-in-jar、mods.toml geckolib 依赖(mandatory)、依赖 jar 为线上生产版(SRG 抽样)且自带 LICENSE
2. 门禁回归:跑全部 18 个 `tools/check_*.py`(netease 改动不新增 config/lang,预期零影响)
3. 推送:`py tools/github_push.py --apply-only`(扫 IP 写 hosts)后 `git push --force-with-lease origin feat/netease-java-adapt`(rebase 重写了该分支,远程需 force;批准本计划即视为同意重写该 feature 分支远程历史);网络不通则走 VPS SSH 隧道备用方案
4. 真机验证(本次不做,留待网易实例恢复后):装机后查客户端日志 `Found valid mod file` + `Found 0 mod requirements missing`
# BlockbenchMCP 0.3.1 API 速查表

> 来源：`C:\Users\Administrator\AppData\Roaming\Blockbench\plugins\blockbench_mcp.js`（BlockbenchMCP 0.3.1，最小 Blockbench 版本 4.8.0，variant `desktop`）。
> 本文所有命令名、参数字段名、枚举值、示例 JSON 均照抄源码，未做任何猜测。源码里没有写的，标注「源码未说明」。

---

## 1. 桥协议与调用方式

插件在 Blockbench（Electron 桌面版）内部起一个裸 TCP 实现的 HTTP/1.1 服务，**只绑定 `127.0.0.1`**（源码：`server.listen(port, '127.0.0.1', ...)`），默认端口 `8787`（`DEFAULT_PORT = 8787`，可在设置项 `blockbench_mcp_port` 改）。

### 端点

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/`、`/ping`、`/ping?...` | 健康检查。返回 `{ok:true, protocol, blockbench_version, is_app, has_project}`（即 `commands.ping()` 的字段 + `ok`）。 |
| `POST` | 任意路径（源码只判断方法是 POST） | 执行命令。body 为 JSON：`{"action":"<命令名>","params":{...},"id":1}` |
| 其他方法 | — | 返回 `405 {"ok":false,"error":"Use POST /command"}` |

### 请求/响应格式

请求 body：

```json
{"action":"get_status","params":{},"id":1}
```

成功响应（HTTP 200）：

```json
{"ok":true,"id":1,"result":{ }}
```

命令自身抛错时**仍然返回 HTTP 200**，但 `ok:false` 并带 `error` / `stack`：

```json
{"ok":false,"id":1,"error":"Cube not found: foo","stack":"Error: ..."}
```

请求被安全校验拒绝时返回非 200：

| 状态码 | 条件 | error 文本 |
| --- | --- | --- |
| `403` | 请求带 `Origin` 头（浏览器页面发起） | `Browser requests are not accepted by the BlockbenchMCP bridge` |
| `403` | `Host` 不是 `127.0.0.1` / `localhost` / `[::1]`（去掉端口后比较，DNS rebinding 防护） | `Host must be 127.0.0.1 or localhost` |
| `415` | POST 且 `Content-Type` 不匹配 `application/json`（允许 `;` 后有参数） | `Content-Type must be application/json` |
| `400` | body 不是合法 JSON | `Invalid JSON body` |
| `405` | 非 GET `/ping` 也非 POST | `Use POST /command` |
| `500` | 服务器内部异常 | 异常字符串 |

### 限制与超时（源码常量）

| 项 | 值 | 说明 |
| --- | --- | --- |
| 请求体上限 | `MAX_BODY = 96 * 1024 * 1024`（96 MB） | 累计接收字节超过即 `socket.destroy()`，无响应。 |
| 默认 socket 空闲超时 | `120000` ms（120 s） | `socket.setTimeout(120000, ...)` → 超时直接 destroy。 |
| 长任务动作 | `request_review`、`ask_user`、`wait_review` | `socket.setTimeout(Math.max(120000, (wait_seconds + 45) * 1000))`，`wait_seconds` 缺省按 `25` 计。 |
| 重动作 | `voxelize_matrix`、`generate_array`、`extrude_chain`、`add_wing`、`add_hollow_volume`、`add_cubes`、`add_groups`、`audit_complexity`、`detail_cubes`、`paint_faces`、`paint_texture`、`pack_uv`、`create_rig`、`execute_script` | `socket.setTimeout(300000)`（300 s）。 |
| 100-continue | 支持 | 请求带 `Expect: 100-continue` 时先回 `HTTP/1.1 100 Continue`。 |
| 响应头 | `Content-Type: application/json`、`Connection: close` | 每个连接处理一个请求后关闭。 |

### 调用示例

PowerShell：

```powershell
$body = '{"action":"get_status","params":{},"id":1}'
Invoke-RestMethod -Uri 'http://127.0.0.1:8787/command' -Method Post `
  -ContentType 'application/json' -Headers @{ Host = '127.0.0.1:8787' } -Body $body
```

curl：

```bash
curl -s http://127.0.0.1:8787/ping
curl -s -X POST http://127.0.0.1:8787/command \
  -H "Content-Type: application/json" \
  -d '{"action":"add_cube","params":{"name":"head","from":[-4,24,-4],"to":[4,32,4]},"id":2}'
```

拿到 base64 图片结果落盘（PowerShell）：

```powershell
$r = Invoke-RestMethod -Uri 'http://127.0.0.1:8787/command' -Method Post `
  -ContentType 'application/json' `
  -Body '{"action":"screenshot","params":{"view":"front","width":512,"height":512},"id":3}'
[IO.File]::WriteAllBytes("$PWD\front.png", [Convert]::FromBase64String($r.result.base64))
```

> 注意：`Host` 头必须是 `127.0.0.1` / `localhost` / `[::1]`（端口任意），否则 403。用 `localhost` 也可以。

### 通用约定

- 命令的 `params` 省略时按 `{}` 处理（`handler(params || {})`）。
- **带 `Project` 前置条件的命令**在无工程时抛 `No project is open. Create one first with new_project.`（`requireProject()`）。
- **桌面版专用命令**（`save_project`（仅当传 `path`）、`export_model`、`load_project`、`import_texture`、`install_plugin`（仅当传 `path`））在非 `isApp` 环境抛 `This action is only available in the Blockbench desktop app.`（`requireApp()`）。
- 元素/骨骼/纹理/动画的引用（`element`、`bone`、`texture`、`animation`、`parent`、`cube`）都按 **uuid 优先、其次 name** 查找（纹理还接受数字下标，参考图接受 id/name/下标）。
- 多个参数接受「JSON 字符串」形式：源码用 `maybeParse()` 解析首字符 `[`/`{` 且末字符 `]`/`}` 的字符串；`toList()` 还会把 `'["a","b"]'` 这种字符串解析成数组。所以数组参数既可传真数组，也可传 JSON 字符串。
- 未知命令：`Unknown command: <action>`。

---

## 2. 完整命令清单（73 个）

「耗时」列含义：**异步** = 命令本身 `async`（会 await 渲染/文件/人机交互）；**重** = 在 `HEAVY_ACTIONS` 里（socket 超时 300 s）；**立即** = 同步返回。

| # | 命令名 | 一句话作用 | 耗时/异步 |
| --- | --- | --- | --- |
| 1 | `ping` | 协议版本 + Blockbench 版本 + 是否有工程 | 立即 |
| 2 | `get_status` | 当前工程规模、朝向规则、待答请求数 | 立即 |
| 3 | `list_formats` | 列出所有可用格式 id（含 animation_mode / box_uv） | 立即 |
| 4 | `new_project` | 新建工程（可指定 format/name/贴图尺寸） | 立即（可能弹对话框） |
| 5 | `close_project` | 关闭当前工程 | 立即 |
| 6 | `set_project_meta` | 改工程名 / geometry_name / 贴图尺寸 | 立即 |
| 7 | `save_project` | 保存工程（传 `path` 则写到该路径） | 返回 Promise（异步语义） |
| 8 | `export_project` | 用当前格式的 codec 导出（传 `path` 直接落盘） | 立即（未传 path 会开导出对话框） |
| 9 | `export_model` | 用指定 codec（默认 glTF）导出到 `path` | **异步** |
| 10 | `load_project` | 从磁盘 `.bbmodel` 载入工程 | 立即（桌面版） |
| 11 | `add_group` | 新建一个骨骼/组 | 立即 |
| 12 | `add_cube` | 新建一个方块 | 立即 |
| 13 | `add_groups` | 批量新建骨骼（可引用同批次内的 parent） | **重** |
| 14 | `add_cubes` | 批量新建方块（推荐方式） | **重** |
| 15 | `voxelize_matrix` | 字符矩阵 → 方块（二维像素图拉伸成体） | **异步语义/重** |
| 16 | `add_hollow_volume` | 空心壳（hood/头盔/护甲片/笼子） | **重** |
| 17 | `generate_array` | 沿线/环/网格重复一个元件（jitter/锥化/逐个旋转） | **重** |
| 18 | `extrude_chain` | 逐段锥化并弯曲的链（角/尾/触手），可一段一骨骼 | **重** |
| 19 | `add_wing` | 整只蝙蝠/龙翼（臂+前臂+指骨扇+连续膜） | **重** |
| 20 | `audit_complexity` | 方块预算/整体大块/分层/微细节/骨骼深度审计 | **重** |
| 21 | `pack_uv` | 把 box UV 货架式打包，必要时自动加高贴图 | **重** |
| 22 | `add_plane` | 加平面 billboard（VFX 基础件，可 `crossed`） | 立即 |
| 23 | `add_mesh` | 加非立方体网格（crystal/pyramid/wedge/cone/cylinder…） | 立即 |
| 24 | `mirror_element` | 沿轴镜像方块或组 | 立即 |
| 25 | `edit_element` | 改元素属性/改名/换父级 | 立即 |
| 26 | `delete_element` | 删除元素 | 立即 |
| 27 | `list_outliner` | 返回完整大纲树（含子级） | 立即 |
| 28 | `get_element` | 查单个元素（组会深展开子级） | 立即 |
| 29 | `check_model` | 审计未贴图面/UV 越界/退化方块/无骨骼父级/共面 z-fighting/左右错误 | 立即 |
| 30 | `set_cube_uv` | 逐面设置 UV / 旋转 / 贴图 | 立即 |
| 31 | `apply_texture` | 给指定元素或全部方块套贴图 | 立即 |
| 32 | `create_texture` | 新建空贴图（可 `fill`、可 `particle`） | 返回 Promise（等图片 load） |
| 33 | `create_vfx_texture` | 生成像素 VFX 贴图（flipbook/自发光/双面） | 立即 |
| 34 | `set_texture_render_mode` | 改 render_mode / render_sides / 逐帧参数 / 粒子 | 立即 |
| 35 | `import_texture` | 从磁盘图片导入贴图 | 立即（桌面版） |
| 36 | `list_textures` | 列出所有贴图 | 立即 |
| 37 | `get_texture` | 取贴图信息 + data_url | 立即 |
| 38 | `paint_texture` | 用绘制 op 数组直接画贴图 | **重** |
| 39 | `detail_cubes` | 生成平滑底色（渐变+方向光+微噪+3x3 模糊） | **重** |
| 40 | `paint_faces` | 按「面内相对坐标」绘制细节（眼睛/条纹等） | **重** |
| 41 | `resize_texture` | 改贴图分辨率 | 立即 |
| 42 | `create_animation` | 新建动画（name/loop/length） | 立即 |
| 43 | `list_animations` | 列出动画 | 立即 |
| 44 | `add_keyframe` | 加单条关键帧 | 立即 |
| 45 | `add_keyframes` | 批量加关键帧（支持 `close_loop`） | 立即 |
| 46 | `remove_animation` | 删除动画 | 立即 |
| 47 | `create_rig` | 生成规范骨架（humanoid/quadruped，含占位方块） | **重** |
| 48 | `check_rig` | 骨架能否动的体检（2 段肢体/原点不在关节/左右/无骨骼方块…） | 立即 |
| 49 | `get_rig` | 回读解析出的骨架结构 | 立即 |
| 50 | `generate_animation` | 按类型生成方向正确的基准循环 | 立即 |
| 51 | `preview_animation` | 渲染动画若干时间点的标注图 | **异步** |
| 52 | `analyze_animation` | 实测手脚头在模型自身坐标下的位移、循环闭合、方向对错 | **异步** |
| 53 | `set_camera_angle` | 设相机 position/target/preset/正交 | 立即 |
| 54 | `screenshot` | 截当前视角，或指定 `view` | **异步** |
| 55 | `screenshot_views` | 一次截多个视角 | **异步** |
| 56 | `get_orientation` | 当前工程的朝向/左右规则手册 | 立即 |
| 57 | `check_sides` | 审计所有左右命名与几何是否一致 | 立即 |
| 58 | `which_side` | 问「这个元素在模型哪一侧」 | 立即 |
| 59 | `request_review` | 把渲染推给用户看并**阻塞等待**裁决 | **异步 + 长连接** |
| 60 | `wait_review` | 继续等一个还没答的 review | **异步 + 长连接** |
| 61 | `ask_user` | 问用户一个问题并等待回答 | **异步 + 长连接** |
| 62 | `list_pending_reviews` | 非阻塞查看待答队列 | 立即 |
| 63 | `get_guide` | 取建模/动画 playbook 正文 | 立即 |
| 64 | `load_reference` | 载入参考图（path 或 data_url） | **异步** |
| 65 | `list_references` | 列出已载入参考图（不含图片数据） | 立即 |
| 66 | `get_reference` | 取参考图（含 data_url） | 立即 |
| 67 | `clear_references` | 清空参考图 | 立即 |
| 68 | `measure_model` | 包围盒 + 逐骨骼尺寸 + 关键比例 | 立即 |
| 69 | `compare_reference` | 剪影 IoU 打分 + 三联对比图 | **异步** |
| 70 | `list_plugins` | 列出插件商店插件 | 立即 |
| 71 | `install_plugin` | 按 url/path/id 安装插件 | **异步** |
| 72 | `uninstall_plugin` | 按 id 卸载插件 | **异步** |
| 73 | `execute_script` | 逃生舱：执行任意 JS（需开关） | 立即（结果可为 Promise） |

> 与任务清单的差异：任务里列了 `check_model`、`check_rig`，源码里都有；任务清单之外还有 `list_formats`、`close_project`、`list_outliner`、`list_textures`、`list_animations`、`get_rig`、`preview_animation`、`analyze_animation`、`list_pending_reviews`（任务清单的交互组只列了 4 个）。

---

## 3. 命令详解

以下每条给出：参数（名/类型/必填/默认/枚举/含义）、源码里的校验报错原文、返回值结构、真实可用示例。

分组的通用规则（适用于绝大多数几何命令）：

- 坐标是 `[x, y, z]` 三元素数组；`from`/`to` 是方块的两个对角，源码内部会取 min/max，所以顺序无所谓。
- `parent` 是字符串，按 uuid 或 name 查找骨骼；找不到抛 `Parent group not found: <ref>`（几何生成器用的是 `resolveParent()`，报错为 `Parent group not found: "<ref>". Use list_outliner to see the bones, or omit \`parent\` to build at the model root.`）。
- `side` 只接受 `"left"` / `"right"`；其它值抛 `side must be "left" or "right", got "<值>"`。给了 `side` 时名字会自动补 `_left`/`_right`（`sideNameFor`），并且会**硬校验坐标**：
  `"<what> \"<name>\" is declared side:\"<side>\" but sits at <轴>=<坐标>, which is the model's <RIGHT|LEFT|CENTRE>. The model faces <front_axis>, so its <side> side is <轴>. Move it to <轴> (flip the sign of that coordinate) or change side/name.`
  名字里左右与几何不一致时（非致命）返回 `warning` 字段：`LEFT/RIGHT MISMATCH: "<name>" is named <claimed> but its geometry is on the model's <actual>. ...`

### 3.1 工程 / 状态

#### `ping`
- 参数：无。
- 返回：`{protocol, blockbench_version, is_app, has_project}`（`protocol` 当前为 `1`）。GET `/ping` 直接返回它并加 `ok:true`。
- 示例：`{"action":"ping","params":{},"id":1}`

#### `get_status`
- 参数：无。
- 返回：`{blockbench_version, has_project}`；有工程时额外带 `project` 和 `orientation`、`pending_user_requests`：
```json
{
  "blockbench_version": "4.8.0",
  "has_project": true,
  "project": {
    "name": "zombie", "format": "geckolib_model", "format_name": "...",
    "texture_width": 128, "texture_height": 128,
    "cubes": 132, "groups": 21, "textures": 1, "animations": 0, "mode": "edit"
  },
  "orientation": {
    "facing": "-z",
    "model_right_is": "+x",
    "model_left_is": "-x",
    "reminder": "The model faces -z. Its own RIGHT hand/arm/leg is at +x, its LEFT at -x. ..."
  },
  "pending_user_requests": 0
}
```
- 无工程时不会抛错（与其它命令不同），只返回前两个字段。

#### `list_formats`
- 参数：无。
- 返回：`[{id, name, description, animation_mode, box_uv}, ...]`（对 `Formats` 全量枚举）。
- 用途：`new_project` 的 `format` 取值来源。

#### `new_project`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `format` | string | 否 | `'free'` | 格式 id/名称/模糊匹配（不区分大小写、`-`/空格归一为 `_`，或名称包含匹配） |
| `name` | string | 否 | 无 | 设置 `Project.name`；同时把 `geometry_name` 设为 `name` |
| `geometry_name` | string | 否 | 取 `name` | 仅在给了 `name` 时才生效 |
| `texture_width` | number | 否 | 格式默认 | `| 0` 取整 |
| `texture_height` | number | 否 | 格式默认 | `| 0` 取整 |

- 报错：`Unknown format "<format>". Use list_formats to see available ids. (GeckoLib/Bedrock formats require the matching plugin to be installed first.)`；新建失败：`Failed to create project (a dialog may have been cancelled).`
- 返回：`get_status().project`。
- 示例：`{"action":"new_project","params":{"format":"geckolib_model","name":"zombie","texture_width":128,"texture_height":128},"id":4}`

#### `close_project`
- 参数：无。
- 返回：`{"closed":true}`。

#### `set_project_meta`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 否 | 不变 | `!== undefined` 才写 |
| `geometry_name` | string | 否 | 不变 | 同上 |
| `texture_width` | number | 否 | 不变 | 真值才写 |
| `texture_height` | number | 否 | 不变 | 真值才写 |

- 返回：`get_status().project`。

#### `save_project`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `path` | string | 否 | 无 | 仅桌面版生效；给定时先设 `Project.save_path`，再触发保存 |

- 返回：`{"saved":true,"path":<Project.save_path 或 null>}`。
- 注意：**不会弹导出对话框**，未传 path 时用工程已有的保存路径。

#### `export_project`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `path` | string | 否 | 无 | 桌面版 + 给定时：直接 `codec.compile()` 后 `writeFileSync` |

- 报错：当前格式没有 codec 时 `Current format has no export codec.`
- 返回：传 path → `{"exported":true,"path":"..."}`；不传 → `{"exported":true,"note":"Export dialog opened in Blockbench."}`。

#### `export_model`（异步，桌面版）
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `path` | string | **是** | — | 输出文件路径 |
| `codec` | string | 否 | `'gltf'` | `Codecs` 里的键；未知时报错并列出全部可用 codec |
| `options` | object | 否 | `{}` | 透传给 `codec.compile(options)` |
| `format` | string | 否 | 无 | 给定时写入 `options.format` |

- 报错：`path is required`；`Unknown codec "<id>". Available: <全部键>`；`Codec "<id>" cannot compile a model.`；非桌面版 `This action is only available in the Blockbench desktop app.`
- 返回：`{"exported":true,"path":"...","codec":"gltf","bytes":<字节数>}`。
- 注：glTF 编译为自包含 `.gltf`（内嵌 buffer 与贴图），可直接导入 Godot/Unity（源码注释）。

#### `load_project`（桌面版）
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `path` | string | **是** | — | `.bbmodel` 文件路径，UTF-8 读取后 `JSON.parse` |

- 报错：`path is required`；JSON 非法会直接抛 `JSON.parse` 的错。
- 返回：`get_status().project`。

---

### 3.2 结构 / 几何

所有生成器（`voxelize_matrix` / `add_hollow_volume` / `generate_array` / `extrude_chain` / `add_wing`）都受同一个安全上限约束：`assertBudget(count, what, max)`，上限默认 `MAX_GENERATED = 1500`，超限报
`"<what> would create <count> cubes, over the <cap> safety cap. Split it into several calls, raise pixel_size / element size, or lower the count."`；
数量 ≤ 0 报 `"<what> would create no geometry — check the parameters."`。多数生成器可传 `max_cubes` 覆盖上限。

生成器统一返回 `generatedReport()` 的结构（不返回全部方块，避免刷爆上下文）：

```json
{
  "created": 12,
  "bounds": {"min":[..],"max":[..],"size":[..]},
  "sample": [{"name":"vox_1","uuid":"...","from":[..],"to":[..]}],
  "sample_note": "Showing 12 of 57 cubes. Use list_outliner / get_element for the rest.",
  "z_fight_pairs": 0,
  "next": "..."
}
```
（`sample` 条数按各命令传入的 limit：voxelize_matrix 默认 12、hollow_volume 6、extrude_chain 8、add_wing 6；出现共面 z-fighting 时会额外带 `z_fight_pairs` / `z_fight_examples` / `z_fight_hint`。）

#### `add_group`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 否 | `'group'` | 给了 `side` 会自动追加 `_left`/`_right` |
| `parent` | string | 否 | 无（挂 root） | uuid 或 name；找不到报 `Parent group not found: <ref>` |
| `origin` | [x,y,z] | 否 | `[0,0,0]` | 骨骼原点（旋转中心），必须落在真实关节上 |
| `rotation` | [x,y,z] | 否 | `[0,0,0]` | 角度制（three.js Euler，XYZ 顺序，见第 5 节） |
| `side` | `"left"` \| `"right"` | 否 | 无 | 会做坐标硬校验 |

- 返回：`serializeGroup(group)` = `{uuid, name, type:'group', origin, rotation, visibility, parent}`（`parent` 为 `'root'` 或父级 uuid）；左右不一致时附加 `warning`。
- 示例：
```json
{"action":"add_group","params":{"name":"arm_upper_right","origin":[5,22,0],"rotation":[0,0,0],"parent":"chest","side":"right"},"id":10}
```

#### `add_cube`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 否 | `'cube'` | 给 `side` 时自动加后缀 |
| `parent` | string | 否 | root | 动画格式下**必须**挂到骨骼下（见第 7 节） |
| `from` | [x,y,z] | 否 | `[0,0,0]` | 一个角 |
| `to` | [x,y,z] | 否 | `from + [1,1,1]` | 对角 |
| `origin` | [x,y,z] | 否 | `from` | 旋转原点 |
| `rotation` | [x,y,z] | 否 | `[0,0,0]` | 角度制 |
| `inflate` | number | 否 | `0` | 正=外扩，负=内缩（原地圆角/锥化） |
| `autouv` | number | 否 | `Format.box_uv ? 0 : 1` | 自动 UV 模式 |
| `box_uv` | boolean | 否 | `!!Format.box_uv` | 是否 box UV（box UV 必须 `pack_uv`） |
| `uv_offset` | [u,v] | 否 | 无 | box UV 起点 |
| `faces` | object | 否 | 无 | 逐面覆盖：`{"north":{"uv":[x1,y1,x2,y2],"rotation":0,"texture":"<name\|uuid>"}}` |
| `side` | `"left"` \| `"right"` | 否 | 无 | 校验 `(from[si]+to[si])/2` 的符号 |

- 行为：`faces` 没给且有贴图时，自动 `applyTexture(Texture.getDefault(), true)`。
- 返回：`serializeElement(cube)`：
```json
{"uuid":"...","name":"head_box","type":"cube","parent":"<uuid|root>",
 "from":[-4,24,-4],"to":[4,32,4],"origin":[-4,24,-4],"rotation":[0,0,0],"inflate":0,
 "box_uv":true,"uv_offset":[0,0],"autouv":0,
 "faces":{"north":{"uv":[0,0,8,8],"rotation":0,"texture":"texture"},"...":{}}}
```

#### `add_groups`（批量，`HEAVY_ACTIONS`）
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `groups` | array | **是** | — | 每项同 `add_group` 的 `{name, origin, rotation, parent, side}` |

- 报错：`groups (array) is required`。**整批先校验再创建**（半个骨架比没有更糟）：任意一项 side 与坐标冲突就整批失败。
- 同批次里 `parent` 可引用**本批先创建的骨骼名**（先查 `created[name]`，再查全局）。
- 返回：`{created, groups:[serializeGroup...], warnings?}`。

#### `add_cubes`（批量，推荐，`HEAVY_ACTIONS`）
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `cubes` | array | **是** | — | 每项支持 `name, parent, from, to, origin, rotation, inflate, autouv, box_uv, uv_offset, faces, side`（同 `add_cube`） |

- 报错：`cubes (array) is required`；整批先做 side 校验。
- 返回：`{created, cubes:[serializeElement...]}`。
- 示例（对称双臂一次建完）：
```json
{"action":"add_cubes","params":{"cubes":[
  {"name":"arm_upper_right","parent":"arm_upper_right","from":[4,16.8,-2],"to":[8,22.6,2]},
  {"name":"arm_upper_left","parent":"arm_upper_left","from":[-8,16.8,-2],"to":[-4,22.6,2]}
]},"id":11}
```

#### `voxelize_matrix`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `matrix` | array\|string | **是** | — | 等长字符串数组，或含换行的字符串；空白格为空格或 `.`（可用 `blank` 改） |
| `plane` | `"xy"`\|`"xz"`\|`"yz"` | 否 | `'xy'` | 不区分大小写。映射（源码 `VOXEL_PLANES.note`）：`xy`=列→+X、行向下 −Y、厚度沿 +Z（正视图）；`xz`=列→+X、行向下 −Z（第一行在最后面）、厚度沿 +Y（俯视图）；`yz`=列→+Z（第 0 列在模型正面）、行向下 −Y、厚度沿 +X（侧视图） |
| `pixel_size` | number | 否 | `1` | 每格边长，必须 > 0，否则 `pixel_size must be greater than 0.` |
| `default_depth` | number | 否 | `1` | 没有 palette 条目时的挤出厚度；`depth: 0` 的字符会被跳过并记录在 `skipped` |
| `origin` | [x,y,z] | 否 | `[0,0,0]` | 矩阵左下角/起点 |
| `blank` | string | 否 | `' .'` | 视为空白的字符集合 |
| `merge_adjacent` | boolean | 否 | `false` | 同一行相邻同字符合并成一个方块（减少方块数） |
| `palette` | object | 否 | 无 | 按键=单字符（长键只取首字符），值=`{name, depth, offset_z, inflate}`；未命中的字符用 `default_depth` 并在返回里列进 `unmapped_chars` |
| `name` | string | 否 | `'vox'` | 方块名前缀，实际名为 `<name>_<序号>` |
| `parent` | string | 否 | root | 目标骨骼 |
| `side` | `"left"`\|`"right"` | 否 | 无 | 用整块 X 范围的中点校验 |
| `max_cubes` | number | 否 | `1500` | 上限覆盖 |

- 报错原文：
  - `matrix is required: an array of equal-length strings (or one string with newlines), e.g. ["  ##  ", " #### ", "  ##  "]. Blank cells are " " or "."`
  - `matrix has no non-empty rows.`
  - `matrix is <cols>x<rows> = <n> cells, which is far past anything useful. Draw the shape at a lower resolution and raise pixel_size.`（> 20000 格）
  - `Unknown plane "<plane>". Use 'xy' (front), 'xz' (top) or 'yz' (side).`
  - `The matrix produced no cubes — every cell was blank. Blank characters are "<blank>"; anything else becomes a cube.`
- 返回：`generatedReport` + `plane_mapping`（上面那句 note 原文）、`grid:{columns,rows}`、`pixel_size`、`cells_filled`、`symbols`（字符→次数）、`parent`、`merged`、可能的 `unmapped_chars`/`unmapped_note`/`skipped`、`next: 'pack_uv after the last geometry call, then detail_cubes / paint_faces.'`
- 示例：
```json
{"action":"voxelize_matrix","params":{
  "matrix":["..##..","####.#","..##.."],
  "plane":"xy","pixel_size":1,"default_depth":1,"origin":[0,20,0],
  "palette":{"#":{"name":"blade","depth":1.5,"offset_z":-0.5}},
  "merge_adjacent":true,"name":"emblem","parent":"chest"
},"id":12}
```

#### `add_hollow_volume`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `bounds` | `{from,to}` | 条件必填 | — | 外壳外框；也可用顶层 `from`/`to` 代替（`bounds.from ?? p.from`） |
| `wall_thickness` | number | 否 | `1` | 必须 > 0；某轴放不下时会夹紧并在 `warnings` 里说明 |
| `open_faces` | array\|string | 否 | 无 | 打开的面向；字符串按 `[,\s]+` 拆分。名称接受 `north/south/east/west/up/down` 以及模型相对词 `front/back/left/right/top/bottom` 和 `+x/-x/+y/-y/+z/-z`（`normalizeFaceName`） |
| `name` | string | 否 | `'shell'` | 每个墙名 `<name>_<方向>` |
| `inflate` | number | 否 | `0` | |
| `parent` | string | 否 | root | |
| `side` | `"left"`\|`"right"` | 否 | 无 | 按 X 范围中点校验 |
| `max_cubes` | number | 否 | — | 传给 `assertBudget` |

- 校验报错：`bounds {from:[x,y,z], to:[x,y,z]} is required (the OUTER box of the shell).`；`bounds must have a positive size on every axis (got <sx> x <sy> x <sz>).`；`wall_thickness must be greater than 0.`；`Every face is in open_faces — that leaves nothing to build. Leave at least one closed.`；`The requested walls all came out empty — the bounds are smaller than wall_thickness.`；`Unknown face "<name>". Use north/south/east/west/up/down, or the model-relative words front/back/left/right/top/bottom.`
- 返回：`generatedReport` + `walls`（方向数组）、`open_faces`、`wall_thickness:{x,y,z}`、`cavity`、`cavity_size`、`warnings?`、`note`。
- 注意（源码 note）：六个墙互不重叠，所以彼此不会 z-fight；但放进空腔里的东西要与墙保持 ≥0.1 间隙。

#### `generate_array`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | `"linear"`\|`"radial"`\|`"grid"` | 否 | `'linear'` | 其它值报 `Unknown mode "<mode>". Use 'linear', 'radial' or 'grid'.` |
| `element_size` | [w,h,d] | **是** | — | 必须 ≥3 个元素且每轴 > 0 |
| `count` | number | 条件 | `0` | linear/radial 必填且 > 0；grid 在没给 `counts` 时必填且 > 0 |
| `start` / `end` | [x,y,z] | 条件 | — | linear 必需（行两端）；grid 必需（区域对角） |
| `center` | [x,y,z] | 条件 | — | radial 必需 |
| `radii` | [rx,rz] | 否 | `[4,4]` | radial 的两个半径 |
| `arc_degrees` | number | 否 | `360` | ≥359.999 视为整圈（步长 = arc/count，否则 arc/(count-1)） |
| `start_degrees` | number | 否 | `0` | 起始角 |
| `counts` | [nx,ny,nz] | 否 | 无 | grid 用；无则按 `count` 摊到跨度最大的两个轴 |
| `distribution` | `"span"`\|`"cells"` | 否 | `'span'` | `span`=首末落在 start/end；`cells`=均匀铺满不超出；其它值报错 |
| `anchor` | `"center"`\|`"top"`\|`"bottom"`\|`"min"` | 否 | `'center'` | 也接受 `centre`/`base`/`corner`；其它值报 `Unknown anchor "<anchor>". Use 'center', 'top', 'bottom' or 'min'.` |
| `jitter` | [x,y,z] | 否 | `[0,0,0]` | 每轴随机抖动幅度（±jitter） |
| `size_decay` | [x,y,z] | 否 | `[0,0,0]` | 逐元素尺寸增量（锥化）；每轴下限 0.05 |
| `depth_stagger` | number | 否 | `0` | **隔一个**元素沿 `depth_axis`（或径向外）偏移，防止共面 |
| `depth_axis` | `"auto"`\|`"x"`\|`"y"`\|`"z"`\|`"radial"`\|`"none"` | 否 | `'auto'` | 其它值报 `Unknown depth_axis "<v>". Use 'auto', 'x', 'y', 'z', 'radial' or 'none'.` |
| `rotation` | [x,y,z] | 否 | `[0,0,0]` | 基准旋转 |
| `rotation_range` | `{min,max}` | 否 | 无 | 每元素在 `min + rand*(max-min)` 上加旋转；只给 `min` 则固定加 `min` |
| `align_to_center` | boolean | 否 | radial 时 `true`，否则 `false` | radial 下让元件正面朝外 |
| `seed` | number\|string | 否 | 无 | 传了就变成可复现随机 |
| `name_prefix` | string | 否 | `'element'` | 实际名 `<prefix>_<序号>`（尾部 `_`/空格会被去掉） |
| `inflate` | number | 否 | `0` | |
| `parent`, `side`, `max_cubes` | 同上 | 否 | — | |

- 常见报错：`element_size [width, height, depth] is required.`；`element_size must be positive on every axis (got a, b, c).`；`count (>0) is required for linear mode.`；`linear mode needs start:[x,y,z] and end:[x,y,z] (the two ends of the row).`；`count (>0) is required for radial mode.`；`radial mode needs center:[x,y,z].`；`grid mode needs start:[x,y,z] and end:[x,y,z] (opposite corners of the area).`；`grid mode needs counts:[nx,ny,nz] or count.`
- 返回：`generatedReport` + `mode`、`distribution`、`anchor`、`depth_stagger`、`depth_axis`、`seeded`、`parent`；如果 `depth_stagger` 为 0 且相邻元件真的重叠，会附加
  `hint: 'depth_stagger was 0 and neighbouring elements overlap, so they sit at the same depth and will z-fight. Pass depth_stagger 0.05-0.2 for overlapping rows (scales, shingles, plates).'`
  以及 `z_fight_hint`（提示只隔一个不够：i 与 i+2 仍同深度，同高度元素共享上下平面；修法：`jitter` >0.05、按一个 element_size 间距排布、或加小 `rotation_range`）。
- 示例（一圈 8 片鳞）：
```json
{"action":"generate_array","params":{
  "mode":"radial","center":[0,20,0],"radii":[5,5],"count":8,"arc_degrees":360,
  "element_size":[1.2,2,0.4],"anchor":"center","depth_stagger":0.12,
  "rotation_range":{"min":[-6,0,0],"max":[6,0,0]},"seed":7,
  "name_prefix":"scale","parent":"chest"
},"id":13}
```

#### `extrude_chain`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `segments` | number | 否 | `4` | 必须 ≥1 且 ≤64（超了报 `<n> is over the 64 cap — a chain that long is almost never what you want.`） |
| `base_origin` | [x,y,z] | 否 | `[0,0,0]` | 起点（建议让它插进根基 ≥0.1） |
| `segment_length` | number | 否 | `4` | 每段长度，必须 > 0 |
| `initial_size` | [w,d] | 否 | `[4,4]` | 截面宽/深，必须 > 0 |
| `taper` | number | 否 | `0.35` | 夹在 0–0.98 的锥化系数 |
| `length_taper` | number | 否 | `0` | 夹在 0–0.9 的段长锥化 |
| `curvature` | [x,y,z] | 否 | `[0,0,0]` | **每段累加**的弯曲（第 i 段在 base_rotation 上叠加 i 次） |
| `base_rotation` | [x,y,z] | 否 | `[0,0,0]` | 第 1 段的旋转 |
| `direction` | `"up"`\|`"down"`\|`"forward"`\|`"back"`\|`"left"`\|`"right"` | 否 | `'up'` | 其它值报 `Unknown direction "<v>". Use up, down, forward, back, left or right.` |
| `create_bones` | boolean | 否 | `true` | 每段一个嵌套骨骼（可动画）；`false` 时旋转烘进方块 |
| `name` | string | 否 | `'chain'` | 骨骼名 `<name>1..n`，方块名 `<name>N_seg` |
| `inflate` | number | 否 | `0` | |
| `parent`, `side`, `max_cubes` | 同上 | 否 | — | |

- 返回：`generatedReport` + `segments`、`direction`、`create_bones`、`bones:[{name,origin,rotation}]`、`tip`（末端坐标）、`total_length`、`end_thickness`、`parent`、`note`；无骨骼且当前是动画格式时附加 `warning: 'This is an animated format and the chain has no bones. Pass create_bones:true unless the chain is meant to be rigid.'`
- 注意（源码 note）：`java_block` 只允许一个旋转轴，这种格式请用 `create_bones:true`。

#### `add_wing`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `side` | `"left"`\|`"right"` | **是** | — | 报 `side is required: "left" or "right" — the model's own side the wing grows from.` |
| `base_origin` | [x,y,z] | **是** | — | 报 `base_origin [x,y,z] is required — the shoulder joint the wing grows from.` |
| `plane` | `"horizontal"`\|`"vertical"` | 否 | `'horizontal'` | 其它值报错；`vertical` 时膜下垂、默认角度不同 |
| `fingers` | number | 否 | `3` | 1–6，否则 `fingers must be between 1 and 6.` |
| `arm_length` | number | 否 | `8` | > 0 |
| `forearm_length` | number | 否 | `10` | > 0（两者非正报 `arm_length and forearm_length must be greater than 0.`） |
| `arm_angle` | number | 否 | horizontal `20` / vertical `35` | 度 |
| `forearm_angle` | number | 否 | horizontal `-15` / vertical `70` | 度 |
| `finger_length` | number \| number[] | 否 | `16`（逐个递减 30%） | 也可以给每指一个值；任一 ≤0 报 `finger_length for finger <i> must be greater than 0.` |
| `finger_angles` | number[] | 否 | 由 `finger_spread` 线性插值 | 非数字报 `finger_angles needs a number for finger <i>.` |
| `finger_spread` | [a0,a1] | 否 | horizontal `[0,80]` / vertical `[100,10]` | 度 |
| `bone_thickness` | number | 否 | `2` | 下限 0.2 |
| `membrane` | `"auto"`\|`"cubes"`\|`"mesh"`\|`"none"` | 否 | `'auto'` | 其它值报错；`auto` → 格式支持 mesh 就用 `mesh`，否则 `cubes`；不允许 mesh 时报 `This format does not support meshes. Use membrane:"cubes" (works in every format and animates with the bones).` |
| `membrane_thickness` | number | 否 | `0.5` | 下限 0.05 |
| `membrane_step` | number | 否 | `1` | 条带宽度，下限 0.25 |
| `membrane_sag` | number | 否 | `0.25` | 夹在 0–0.6 |
| `membrane_attach` | [x,y,z] | 否 | 自动推算 | 必须能解析成点，否则 `membrane_attach must be an [x,y,z] point on the body.` |
| `attach_to_body` | boolean | 否 | `true` | 是否生成连到身体的膜 |
| `texture` | string | 否 | 默认贴图 | `membrane:"mesh"` 时用于膜面 |
| `name` | string | 否 | `'wing'` | 骨骼名如 `<name>_arm`、`<name>_forearm`、`<name>_finger1..n` |
| `parent`, `side`, `max_cubes` | 同上 | 否 | — | |

- 返回：`generatedReport` + `side`、`plane`、`membrane`、`bones:[{name,origin,rotation}]`、`shoulder`、`elbow`、`wrist`、`finger_tips`、`membrane_attach`、`membrane_panels`、`meshes`、`parent`、`note`。
- 注意（源码 note）：rest 姿势已烘进骨骼旋转；动画用 `generate_animation {type:"fly"}` 会用到 `*_arm` / `*_forearm` / `*_finger`；**另一侧要用同一调用把 side 翻转重建，不要 `mirror_element`**。

#### `audit_complexity`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `target` | `"auto"`\|`"prop"`\|`"character"`\|`"creature"`\|`"hero"` | 否 | `'auto'` | 其它值报 `Unknown target "<v>". Use 'auto', 'prop', 'character', 'creature' or 'hero'.`；`auto` 按骨架识别结果推断 |
| `min_cubes` | number | 否 | 按 target 的 `minimum` | 覆盖最低方块数 |
| `monolith_share` | number | 否 | `0.3` | 夹在 0.05–0.9：单块体积占比阈值 |
| `min_overlays` | number | 否 | `4` | 大块周围至少要有多少相邻细节件，否则算 `monolithic_box` |
| `flat_face_area` | number | 否 | `48` | 裸面面积阈值，超过且四周无物算 `undetailed_slab` |

- 预算表（源码 `BUDGETS`）：`prop {minimum:30, acceptable_from:30, high_detail_from:80}`；`character {80,100,180}`；`creature {80,100,180}`；`hero {120,180,300}`。
- 返回：
```json
{"verdict":"too_primitive|acceptable|high_detail",
 "ready_for_texturing":false,"target":"character",
 "budget":{"target":"character","minimum":80,"acceptable_from":100,"high_detail_from":180,"label":"standard mob / NPC"},
 "cubes":42,"groups":9,"rig_kind":"humanoid",
 "metrics":{"micro_cubes":0,"micro_pct":0,"small_cubes":3,"overlapping_cubes":0,"overlapping_pct":0,
   "overlapping_pairs":0,"rotated_elements":0,"inflated_cubes":0,"bone_depth":3,
   "cubes_per_bone":4.667,"largest_cube_share_pct":41,"total_cube_volume":123.5,"pairwise_analysis":true},
 "monoliths":[{"cube":"body","volume_share_pct":41,"size":[8,6,4],"overlays":0}],
 "issue_count":3,"issues":[{"issue":"below_cube_budget","cubes":42,"minimum":80,"hint":"..."}],
 "recommendations":["..."],
 "note":"Density is necessary, not sufficient: ..."}
```
- 可能的 `issues[].issue` 值：`empty_model`、`monolithic_box`、`below_cube_budget`、`no_layering`、`low_micro_detail`、`undetailed_slab`、`shallow_hierarchy`、`no_rotated_elements`。
- 阻塞项（决定 `ready_for_texturing`）：`below_cube_budget`、`monolithic_box`、`empty_model`。
- 判定阈值：`layer_ratio < 0.25` 且 ≥8 方块 → `no_layering`；`micro/cubes < 0.15` 且 ≥20 方块 → `low_micro_detail`；骨骼深度 <3 且组数 >2 → `shallow_hierarchy`；无任何旋转且 ≥20 方块 → `no_rotated_elements`。方块数 ≥2200 时跳过 O(n²) 邻接分析（`pairwise_analysis:false`）。

#### `pack_uv`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `cubes` | array \| `"all"` | 否 | 全部方块 | 省略或 `'all'` = 所有 `Cube.all`；也可传名字/uuid 列表 |
| `padding` | number | 否 | `1` | 货架打包间距（`| 0` 取整） |
| `auto_resize` | boolean | 否 | `true`（`!== false`） | true 时若排版超出高度就按 2 倍逐级加高贴图（保留已画内容），然后重新打包 |

- 报错：`No cubes to pack.`
- 返回：`{"packed":<数量>,"used":[宽度占用,高度占用],"texture_size":[w,h]}`
- 每方块 UV 足迹 = `2*(w+d)` 宽 × `(h+d)` 高（`boxUVFootprint`）。**box UV 模型必须先跑这个**再贴图（源码注释：所有新 box UV 方块都在 `uv_offset [0,0]`，会共用同一片像素；加/改方块后要重跑）。

#### `add_plane`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 否 | `'plane'` | `crossed` 时第二片叫 `<name>_x` |
| `parent` | string | 否 | root | |
| `from` | [x,y,z] | 否 | `[0,0,0]` | 基准角 |
| `facing` | `"x"`\|`"y"`\|`"z"` | 否 | `'z'` | 决定哪两个面是大面；**非法值不报错**，会落回 `'z'` 的 `north/south` |
| `width` | number | 否 | `16` | |
| `height` | number | 否 | `16` | |
| `origin` | [x,y,z] | 否 | 几何中心 | |
| `rotation` | [x,y,z] | 否 | `[0,0,0]` | |
| `texture` | string | 否 | 默认贴图 | 只在两个大面上铺满整张贴图，其它面 `texture:null, uv:[0,0,0,0]` |
| `crossed` | boolean | 否 | `false` | 再生成一片与之垂直、共中心的平面（体积感粒子） |

- 实现：零厚度方块（两个大面共用贴图）。要双面可见需把贴图 `render_sides` 设为 `double`（见 `set_texture_render_mode`）。
- 返回：`{"created":<1|2>,"planes":[serializeElement...]}`。

#### `add_mesh`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `shape` | string | 否 | `'crystal'` | `plane`、`pyramid`、`wedge`/`prism`、`octahedron`/`crystal`/`gem`/`shard`/`diamond`、`cone`、`cylinder`（其它值走 `default`，源码未说明具体回退形状） |
| `size` | [w,h,d] | 否 | `[8,8,8]` | |
| `from` | [x,y,z] | 否 | `[-w/2, 0, -d/2]` | |
| `segments` | number | 否 | 8（内部 `Math.max(3, segments \|\| 8)`） | cone/cylinder 的环段数 |
| `origin` | [x,y,z] | 否 | 几何中心 | |
| `rotation` | [x,y,z] | 否 | `[0,0,0]` | |
| `name` | string | 否 | 等于 `shape` | |
| `texture` | string | 否 | 默认贴图 | |
| `uv` | [u1,v1,u2,v2] | 否 | 整张贴图 | |
| `parent` | string | 否 | root | |

- 报错：`Meshes are not available in this Blockbench build.`；`Current format does not support meshes. Use a free/generic project, or build the shape from rotated cubes.`；`Parent group not found: <ref>`
- 返回：`{"uuid":..,"name":..,"type":"mesh","shape":..,"vertices":..,"faces":..}`
- 注意：**GeckoLib/Java 只导出方块，mesh 不会导出**（源码注释）；这些格式用旋转 45° 的方块代替。

#### `mirror_element`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `element` | string | 二选一 | — | 单个元素名/uuid |
| `elements` | array | 二选一 | — | 多个元素 |
| `axis` | `"x"`\|`"y"`\|`"z"` | 否 | `'x'` | 其它值 → `axis` 为 undefined，源码未做校验（会静默出错，勿传非法值） |
| `pivot` | number | 否 | `0` | 镜像平面位置；`r[axis] = 2*pivot - r[axis]` |

- 报错：`No element(s) found to mirror.`
- 行为：方块名里 `left`→`right`、`_l$`→`_r`；名字不含左右时加 `_m` 后缀；镜像轴之外的两个旋转分量取反。组：名字 `left`→`right`，轴外两个旋转取反，子方块逐个镜像（只克隆直接子方块）。
- 返回：`{"created":<数量>,"elements":[serializeGroup|serializeElement...]}`。
- 注意：**翅膀类上下不对称的部件不要镜像**，源码在 `add_wing` 里明确要求「用同样参数、side 翻转重建」。

#### `edit_element`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `element` \| `uuid` \| `name` | string | 三者取一 | — | 找不到报 `Element not found: <ref>` |
| `new_name` | string | 否 | 不变 | |
| `origin` | [x,y,z] | 否 | 不变 | 有值才写 |
| `rotation` | [x,y,z] | 否 | 不变 | 有值才写 |
| `from` / `to` | [x,y,z] | 否 | 不变 | **仅方块**（组忽略） |
| `inflate` | number | 否 | 不变 | 仅方块 |
| `visibility` | boolean | 否 | 不变 | `!== undefined` 才写 |
| `parent` | string | 否 | 不变 | `'root'` 表示移到根；找不到报 `Parent group not found: <ref>` |

- 返回：组返回 `serializeGroup(el)`（不深展开），方块返回 `serializeElement(el)`。

#### `delete_element`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `element` \| `uuid` \| `name` | string | 三者取一 | — 找不到报 `Element not found: <ref>` |

- 返回：`{"deleted":true}`。

#### `list_outliner`
- 参数：无。
- 返回：`Outliner.root` 的树，组用 `serializeGroup(n, true)` 深展开（含 `children`），方块用 `serializeElement`。

#### `get_element`
| 参数 | 类型 | 必填 | 默认 |
| --- | --- | --- | --- |
| `element` \| `uuid` \| `name` | string | 三者取一 | — |

- 返回：组 → `serializeGroup(el, true)`（含子级）；方块 → `serializeElement(el)`。

#### `check_model`
- 参数：无。
- 检查项（`issues[].issue`）：`no_texture`（面没贴图）、`zero_uv`（UV 宽或高为 0）、`uv_out_of_bounds`（UV 超出 `texture_width/height`）、`degenerate_size`（某轴尺寸 ≤0）、`no_bone_parent`（动画格式下方块没挂在骨骼下）、`coplanar_overlap`（未旋转方块两两共面且重叠 → z-fighting，最多报 80 组），另外会把 `check_sides()` 的左右问题一并并入。
- 返回：
```json
{"cubes":132,"groups":21,"textures":1,"texture_size":[128,128],"animation_format":true,
 "orientation":"The model FACES -z. Its own RIGHT is +x, its own LEFT is -x.",
 "issue_count":2,"by_type":{"coplanar_overlap":2},
 "issues":[{"issue":"coplanar_overlap","cubes":["a","b"],"axis":"z","plane":2,
            "hint":"faces coplanar -> z-fight; offset one cube by >=0.1 on this axis"}]}
```
- 共面判定：两方块在同轴上的 `from` 或 `to` 相差 <0.02，且另两轴重叠均 >0.1，且处于同一旋转骨骼框架（`rotatedBoneKey` 相同）。

#### `set_cube_uv`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `cube` \| `uuid` \| `name` | string | 三者取一 | — 找不到报 `Cube not found: <ref>` |
| `faces` | object | 否 | 无 | 键为面名（`north/south/east/west/up/down`），值 `{uv:[x1,y1,x2,y2], rotation:number, texture:"<name\|uuid>"}`；`texture` 找不到时设为 `false`（无贴图） |

- 返回：`serializeElement(cube)`。
- 示例：`{"action":"set_cube_uv","params":{"cube":"head_box","faces":{"north":{"uv":[0,0,8,8],"rotation":0,"texture":"zombie"}}},"id":20}`

#### `apply_texture`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `texture` | string | **是** | — | 名字/uuid/下标；找不到报 `Texture not found: <ref>` |
| `element` | string | 否 | 无（=全部方块） | 给定时只作用于该元素；找不到报 `Element not found: <ref>` |

- 返回：`{"applied_to":<数量>}`。

#### `create_texture`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 否 | `'texture'` | |
| `width` | number | 否 | `Project.texture_width \|\| 16` | |
| `height` | number | 否 | `Project.texture_height \|\| 16` | |
| `data_url` | string | 否 | 生成空白 PNG | 也接受 data URL 直接作为贴图源 |
| `fill` | string | 否 | 透明 | CSS 颜色，铺满整张 |
| `particle` | boolean | 否 | `false` | 真值时 `tex.enableParticle()` |

- 返回：Promise，等图片 load 完成后 resolve `serializeTexture(tex)`（内部 400 ms 兜底）。
- `serializeTexture` 结构：`{uuid, name, width, height, uv_width, uv_height, particle, render_mode, render_sides, frame_count, frame_time, frame_interpolate, path}`。

#### `create_vfx_texture`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `style` | string | 否 | `'energy'` | 可识别：`flame`/`fire`、`orb`/`glow`、`energy`/`plasma`、`spark`/`star`、`smoke`/`cloud`、`trail`/`streak`、`beam`/`beam_v`、`beam_h`、`bolt`/`lightning`、`rune`/`ring`、`crystal`/`gem`、`shockwave`（其它值走 `default` 圆形渐变） |
| `width` | number | 否 | `16` | |
| `height` | number | 否 | flame/fire/beam/beam_v → `24`，其它 `16` | |
| `frames` | number | 否 | `1` | ≥1；>1 会烘焙**竖排 flipbook**，贴图高 = `height * frames`，并启动 `TextureAnimator` |
| `palette` | string[] | 否 | 按 `preset` | 颜色梯度（索引 0 = 最亮核心） |
| `preset` | string | 否 | 无 | 调色板名：`fire`、`ember`、`ice`、`frost`、`energy`、`arcane`、`poison`、`shadow`、`holy`、`smoke`、`blood`、`nature`（源码 `VFX_PALETTES`） |
| `seed` | number | 否 | 随机 | |
| `soft_edge` | boolean | 否 | orb/glow/smoke 时 `true` | 最冷的一档 alpha 降为 150 |
| `render_mode` | string | 否 | `crystal`/`gem` → `'emissive'`，其它 → `'additive'` | |
| `render_sides` | string | 否 | `'double'` | |
| `frame_time` | number | 否 | `2` | 仅 `frames>1` |
| `frame_interpolate` | boolean | 否 | `false` | 仅 `frames>1` |
| `frame_order_type` | string | 否 | `'loop'` | 仅 `frames>1` |
| `particle` | boolean | 否 | `false` | |
| `name` | string | 否 | `<style>_vfx` | |

- 返回：`serializeTexture(tex)` + `{style, frames, palette}`。

#### `set_texture_render_mode`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `texture` | string | **是** | — | 找不到报 `Texture not found: <ref>` |
| `render_mode` | string | 否 | 不变 | 源码注释列出：`default`、`emissive`、`additive`、`layered`、`normal`、`height`、`mer`（无枚举校验） |
| `render_sides` | string | 否 | 不变 | 例如 `'double'`（平面必须双面） |
| `frame_time` | number | 否 | 不变 | `!= null` 才写 |
| `frame_interpolate` | boolean | 否 | 不变 | |
| `frame_order_type` | string | 否 | 不变 | |
| `particle` | boolean | 否 | 不变 | 仅 `=== true` 时 `enableParticle()` |
| `animate` | boolean | 否 | `false` | 真值启动 `TextureAnimator`（flipbook 播放） |

- 返回：`serializeTexture(tex)`。

#### `import_texture`（桌面版）
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `path` | string | **是** | — | 报 `path is required` |
| `name` | string | 否 | 无 | |

- 返回：`serializeTexture(tex)`。

#### `list_textures`
- 参数：无。返回 `Texture.all.map(serializeTexture)`。

#### `get_texture`
| 参数 | 类型 | 必填 | 默认 |
| --- | --- | --- | --- |
| `texture` | string | **是** | —（找不到报 `Texture not found: <ref>`） |

- 返回：`{"texture":{...},"data_url":"data:image/png;base64,..."}`。

#### `paint_texture`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `texture` | string | **是** | — | 找不到报 `Texture not found: <ref>` |
| `ops` | array | **是** | — | 报 `ops (array) is required` |
| `edit_name` | string | 否 | `'MCP: paint texture'` | 撤销条目名 |

- 绘制 op（`applyPaintOps`，坐标为贴图绝对像素）：

| `type` | 字段 | 说明 |
| --- | --- | --- |
| `pixel` | `x, y, color` | 单个像素 |
| `rect` | `x, y, width, height, color, fill?` | `fill:false` + `line_width` 时描边 |
| `line` | `x1, y1, x2, y2, color, line_width` | 线段 |
| `circle` | `x, y, radius, color, fill?, line_width?` | 圆 |
| `fill_all` | `color` | 铺满整张（在 `paint_faces` 的 op 里会被自动转成该面的 rect） |
| `clear` | `x, y, width?, height?, color` | 清除（宽高缺省=整张） |
| `gradient` | `x, y, width?, height?, x1, y1, x2, y2, stops:[[pos,color],...]` | 线性渐变 |
| `ellipse` | `x, y, width, height`（或 `radius`）, `color, fill?, line_width?` | 椭圆 |
| `polygon` | `points:[[x,y],...], color, fill?, line_width?` | 多边形（至少 2 点） |
| `dither` | `x, y, width?, height?, color, color2?, density?` | 棋盘抖动，`density` 默认 1 |
| `noise` | `x, y, width?, height?, amount?`(默认 0.12), `color?`(作为种子色), `mono?`(默认 true) | 噪点 |

- 未知类型报 `Unknown paint op: <type>`。
- 返回：`{"painted":true,"ops":<条数>,"texture":{...}}`。

#### `detail_cubes`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `texture` | string | 否 | 默认贴图，再退到第一张 | 都没有报 `No texture to paint on. Create one first with create_texture.` |
| `cubes` | array \| `"all"` | 否 | 全部方块 | 无匹配报 `No matching cubes.` |
| `base` | string | 否 | `'#9c9c9c'` | 基础色 |
| `colors` | array \| object | 否 | 无 | 区域配色：数组 `[{match:"leg\|paw",color:"#5a3d22"}]`，或对象 `{"leg\|paw":"#5a3d22"}`；`match` 是不区分大小写的正则源码，首个命中生效 |
| `noise` | number | 否 | `0.06` | 低对比斑驳强度（建议 0.04–0.08） |
| `blur` | number | 否 | `0.55` | 3×3 盒式模糊混合量（平滑笔刷） |
| `top_light` | number | 否 | `0.12` | 顶面提亮系数 |
| `bottom_dark` | number | 否 | `0.22` | 底面压暗系数 |
| `edge_darken` | number | 否 | `0` | **默认关闭**（打开会在每面描暗边，看起来像脏网格） |
| `streaks` | boolean | 否 | `false` | 在 `up`/`north` 面加毛发/木纹/石纹竖条 |
| `glow_regex` | string | 否 | `/(_core$\|_glow$)/i` | 命中名字的方块填亮、不叠加阴影与模糊（自发光件） |

- 逐面亮度乘子（源码 `faceMul`）：`up: 1+top_light`、`down: 1-bottom_dark`、`north: 0.95`、`south: 1.0`、`east: 1.06`、`west: 0.88`。
- 行为：先把贴图赋给所选方块的所有面（消灭未贴图缝隙），再逐面画渐变、斑驳、可选条纹，最后按 UV 岛做 3×3 模糊。
- 返回：`{"textured":<方块数>,"faces":<面数>,"smooth":true,"texture":{...}}`。
- 调用顺序（源码规范）：`pack_uv → create_texture → detail_cubes → paint_faces`（`paint_faces` 必须**在烘焙之后**，否则会被模糊抹掉）。

#### `paint_faces`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `faces` | array | 二选一 | — | 每项 `{cube, face, base?, ops?, texture?}`（批量） |
| `cube` | string | 二选一 | — | 单个方块（与 `face`/`base`/`ops`/`texture` 顶层字段配对） |
| `face` | string \| `"all"` | 否 | `'all'`（缺省或 `'all'` = 该方块所有面） | 面名同上 |
| `ops` | array | 否 | `[]` | 绘制 op，坐标系是**该面 UV 矩形的左上角为 (0,0)**（`offsetOps` 自动平移；`noise`/`dither`/`clear` 不给宽高时自动铺满该面；`fill_all` 自动转成该面的 rect） |
| `base` | string | 否 | 无 | 先用该色铺满这个面 |
| `texture` | string | 否 | 面已有贴图 → 默认贴图 → 第一张贴图 | 都没有报 `No texture available; create one first with create_texture.` |

- 报错：`Cube not found: <ref>`。
- 返回：`{"painted":<面数>}`。
- 示例（给右眼画眼白+瞳孔）：
```json
{"action":"paint_faces","params":{
  "cube":"head_box","face":"north",
  "ops":[{"type":"rect","x":1,"y":2,"width":2,"height":2,"color":"#ffffff"},
         {"type":"pixel","x":2,"y":3,"color":"#101010"}]
},"id":21}
```

#### `resize_texture`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `texture` | string | **是** | — | 找不到报 `Texture not found: <ref>` |
| `width` | number | **是** | — | 非 0 |
| `height` | number | **是** | — | 非 0；任一为 0 报 `width and height are required` |

- 返回：`serializeTexture(tex)`。

---

### 3.3 动画 / 绑定

以下命令都要求当前格式支持动画（`typeof Animation === 'undefined'` 时报 `Animations are not supported in this format.`）。

#### `create_animation`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 否 | `'animation'` | |
| `loop` | string | 否 | `'loop'` | 源码直接用 `p.loop \|\| 'loop'`，未做枚举校验；生成器内部用的取值是 `loop` / `once` / `hold` |
| `length` | number | 否 | `0` | 真值时另调用 `anim.setLength(length)` |

- 返回：`serializeAnimation(anim)`：
```json
{"uuid":"...","name":"animation.zombie.idle","loop":"loop","length":4,"snapping":0,
 "bones":[{"name":"arm_upper_right","uuid":"...","keyframe_count":9}]}
```
- 创建后会自动 `anim.select()`。

#### `list_animations`
- 参数：无。返回 `serializeAnimation` 数组。

#### `add_keyframe`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `animation` | string | **是** | — | 找不到报 `Animation not found: <ref>` |
| `bone` | string | **是** | — | 骨骼（组）名；找不到报 `Bone (group) not found: <ref>`；该动画作用域里不可动画时报 `Cannot animate bone in this animation scope: <bone>` |
| `channel` | string | 否 | `'rotation'` | 通道名（见下） |
| `time` | number | 否 | `0` | 秒（`Number(p.time) \|\| 0`） |
| `value` | [x,y,z] | 否 | `[0,0,0]` | |
| `interpolation` | string | 否 | `'linear'` | 生成器内部使用 `catmullrom` / `linear` / `step` |

- 副作用：`time` 大于 `anim.length` 时会把动画长度扩到该时间。
- 返回：`{"uuid":<关键帧 uuid>,"channel":<通道>,"time":<实际时间>}`。

#### `add_keyframes`（批量）
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `animation` | string | **是** | — | 找不到报 `Animation not found: <ref>` |
| `keyframes` | array | 否 | `[]` | 每项 `{bone, channel, time, value, interpolation}` |
| `length` | number | 否 | 自动 | `>0` 时直接指定动画长度；否则取 `max(原长度, 最大 time)` 再与写入结果取大 |
| `close_loop` | boolean | 否 | `false` | 真值时把每个「骨骼+通道」在 `t≈0` 的姿势复制一份到 `t=length`（若该组合最后时间早于 length），防止循环跳变 |

- 报错：`Bone (group) not found: <逗号分隔的缺失骨骼>`（**先把所有骨骼查一遍**，一个拼错就整批不写）。
- 返回：
```json
{"created":18,"loop_keyframes_added":2,
 "keyframes":[{"uuid":"...","bone":"arm_upper_right","channel":"rotation","time":0}],
 "animation":{...},
 "reminder":"Now run analyze_animation — it measures where the limbs really travel and catches motion that goes the wrong way."}
```

#### `remove_animation`
| 参数 | 类型 | 必填 |
| --- | --- | --- |
| `animation` | string | **是**（找不到报 `Animation not found: <ref>`） |

- 返回：`{"removed":true}`。

#### `create_rig`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `type` | `"humanoid"`\|`"biped"`\|`"quadruped"` | 否 | `'humanoid'` | 其它值报 `Unknown rig type: <type> (humanoid \| quadruped)` |
| `height` | number | 否 | 模板高度（humanoid 32 / quadruped 20） | 整体缩放 = `height / 模板高度 * scale` |
| `scale` | number | 否 | `1` | 额外缩放 |
| `offset` | [x,y,z] | 否 | `[0,0,0]` | 整体平移 |
| `name_prefix` | string | 否 | `''` | 所有骨骼/方块名前缀 |
| `parent` | string | 否 | root | 找不到报 `Parent group not found: <ref>` |
| `placeholder_cubes` | boolean | 否 | `true`（`!== false`） | 是否同时生成占位方块 |
| `arm_segments` | number | 否 | `3` | 夹在 2–3（**humanoid**） |
| `leg_segments` | number | 否 | `3` | 夹在 2–3（两种类型都用） |
| `spine_segments` | number | 否 | `2` | 夹在 1–3（**humanoid**） |
| `tail_segments` | number | 否 | humanoid `0` / quadruped `3` | 夹在 0–6 |
| `jaw` | boolean | 否 | `false` | 为真时额外建 `jaw` 骨骼 |

- 生成的骨骼名（humanoid）：`root`、`hips`、`spine`、`spine2`、`chest`、`neck`、`head`、`jaw`（可选）、`shoulder_left/right`、`arm_upper_left/right`、`arm_lower_left/right`、`hand_left/right`、`leg_upper_left/right`、`leg_lower_left/right`、`foot_left/right`、`tail1..n`。
- 生成的骨骼名（quadruped）：`root`、`hips`、`spine`、`chest`、`neck`、`head`、`jaw`（可选）、`leg_upper_front_right`、`leg_lower_front_right`、`paw_front_right`（front/back × left/right 共 12 个）、`tail1..n`。
- 关节原点示例（canonical，最后经 `rigFrame()` 映射到真实轴线）：humanoid `hips [0,12,0]`、`chest [0,18.5,0]`、`neck [0,23,0]`、`head [0,24,0]`、`shoulder_right [4,22,0]`、`arm_upper_right [5,22,0]`、`arm_lower_right [5,17,0]`、`hand_right [5,13,0]`、`leg_upper_right [2,12,0]`、`leg_lower_right [2,6.5,0]`、`foot_right [2,1.5,0]`。
- 返回：
```json
{"type":"humanoid","bones_created":21,"cubes_created":13,
 "orientation":"The model FACES -z. Its own RIGHT is +x, its own LEFT is -x.",
 "bones":[{"name":"hips","origin":[0,12,0],"parent":"root"}],
 "cubes":["body_lower","body_chest","head_box","..."],
 "rig":{...summarizeRig...},
 "next_steps":["The skeleton is built with the model's RIGHT on +x — keep it that way.",
   "The cubes are a blocked-out placeholder: reshape them with edit_element, then add detail cubes into the same bones.",
   "Run check_rig before animating, then generate_animation {type:\"idle\"|...} for a correct base cycle and refine it."]}
```

#### `check_rig`
- 参数：无。
- 检查项（`issues[].issue`）：`missing_limb`、`limb_too_few_segments`（<3 段 → 没有肘/膝）、`origin_not_at_joint`（骨骼原点落在该段方块的 Y 中段 30% 内 → 原地打转）、`no_rig_detected`、`no_root_bone`、`no_head_bone`、`no_spine`、`cubes_without_bone`（动画格式下有方块不在骨骼下）、左右相关（来自 `check_sides`：`wrong_side`、`pair_on_same_side` 等）、`low_bone_count`（<8 根）。
- 阻断项（决定 `ready_to_animate`）：`limb_too_few_segments`、`no_rig_detected`、`wrong_side`、`pair_on_same_side`、`cubes_without_bone`。
- 返回：
```json
{"rig":{...},"orientation":"...","bone_count":21,"issue_count":2,
 "by_type":{"origin_not_at_joint":2},"issues":[...],
 "ready_to_animate":true,
 "verdict":"Rig looks good. | Animatable, but the notes above will improve the result. | NOT ready to animate — fix the blocking issues above first (especially limb segmentation and left/right).",
 "right_axis":"+x"}
```

#### `get_rig`
- 参数：无。
- 返回：`{"rig":summarizeRig(detectRig()),"orientation":"...","unmatched_bones":[<无法归类成 root/hips/spine/chest/neck/head/jaw/tail/ear/arm/leg/wing 的骨骼名>]}`。
- 命名识别关键词（源码）：root/armature/rig/model、jaw/mandible、head/skull/cranium、neck、tail、wing、ear/horn/antler、hip/hips/pelvis/waist、chest/thorax/ribcage/shoulders、spine/torso/abdomen/body/belly、腿词（leg/thigh/femur/shin/calf/tibia/knee/haunch）、臂词（arm/humerus/bicep/forearm/elbow）、末端词（hand/fist/foot/feet/paw/hoof/claw/talon/toe/finger/ankle/wrist）。四足前后排识别词：front/fore/forward/anterior、back/hind/rear/posterior。

#### `generate_animation`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `type` | string | 否 | `'idle'` | 可用值：`idle`、`walk`、`run`、`attack`、`cast`、`jump`、`hurt`、`death`、`fly`；其它值报 `Unknown animation type: <type>. Available: <全部键>` |
| `length` | number | 否 | 各类型的默认长度 | `idle 4`、`walk 1`、`run 0.62`、`attack 0.85`、`cast 2.2`、`jump 1.1`、`hurt 0.45`、`death 1.8`、`fly 0.8`（秒） |
| `loop` | string | 否 | 各类型默认（见上；`attack/cast/jump/hurt` 为 `once`，`death` 为 `hold`，其余 `loop`） | |
| `intensity` | number | 否 | `1` | 夹在 0.2–2.5，缩放所有振幅 |
| `hand` | `"left"` \| `"right"` | 否 | `'right'`（非 `'left'` 一律当 `'right'`） | 仅 `attack` 用（返回里 `hand` 字段也只在该类型出现） |
| `direction` | string | 否 | `'backward'` | 源码不做枚举校验（`opts.direction`） |
| `name` | string | 否 | `animation.<工程名小写化>.<type>` | 工程名清洗规则：非 `a-z0-9` → `_`，去首尾 `_`，空则 `model` |
| `replace` | boolean | 否 | `true`（`!== false`） | 同名动画先删再建 |

- 前置校验：先 `detectRig()`，`kind === 'unknown'` 时抛 `No rig detected — cannot generate. Run check_rig (or create_rig) first: bones need names like arm_upper_right / leg_lower_left.`；没有任何骨骼可驱动时抛 `The rig has no bones this animation can drive. Run check_rig.`
- 返回：
```json
{"animation":{...},"type":"walk","length":1,"loop":"loop","keyframes_created":53,
 "bones_animated":["leg_upper_right","leg_lower_right","hips","chest","head"],
 "rig_kind":"humanoid","warnings":["No tail bones — nothing to carry follow-through. ..."],
 "next_steps":["Run analyze_animation to MEASURE where the limbs actually travel ...",
   "Then preview_animation to see the poses, and request_review so the user confirms it before you call it done.",
   "Refine with add_keyframes — this is a solid base, not a finished animation."]}
```
- `warnings` 里可能出现：`No <label> bone found — that part of the motion is missing.`、`<label> only has <n> segment(s): no <elbow|knee> bend, so it will read as stiff. Split the limb and re-generate.`、`No tail bones — nothing to carry follow-through. Optional, but tails/cloaks sell motion.`、`Bones not found in the animation scope: <列表>`。

#### `preview_animation`（异步）
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `animation` | string | **是** | — | 找不到报 `Animation not found: <ref>` |
| `times` | number[] | 否 | `[0, L*0.25, L*0.5, L*0.75]` | 秒，会被夹在 `[0, length]` |
| `views` | array | 否 | `['front_right']` | 视角名或 `{position,target}` |
| `width` / `height` | number | 否 | `420` | 单张渲染尺寸 |
| `annotate` | boolean | 否 | `true` | 是否加标注条（每张图上会印 `t=<时间>s`） |

- 返回：`{"animation":"<名字>","length":L,"count":<张数>,"shots":[{view, looking_at, model_right_on, note, data_url, base64, time}, ...]}`。

#### `analyze_animation`（异步）
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `animation` | string | **是** | — | 找不到报 `Animation not found: <ref>` |
| `samples` | number | 否 | `16` | 夹在 4–48；采样点 = samples+1 个，从 0 到 length 均分 |
| `expect` | string | 否 | 无 | 与动画名一起做「是否打击类」判断，正则 `/attack\|punch\|swing\|strike\|slash\|bite\|stab\|kick\|thrust/` |

- 返回：
```json
{"animation":"animation.golem.walk","length":1,"loop":"loop","orientation":"...","samples":17,
 "bones_with_keyframes":9,"total_keyframes":53,
 "per_bone":[{"bone":"arm_upper_right","keyframes":9,"channels":["rotation"]}],
 "motion":{"hand_right":{"travel":8.4,"max_forward":6.1,"at_forward_time":0.75,
   "max_backward":2.3,"at_backward_time":0.25,"rise":1.2,"drop":-0.8,"loop_gap":0.02}},
 "motion_legend":"Distances are in model units along the model's own axes. \"forward\" = -z (the way it faces).",
 "direction_check":"OK — \"hand_right\" reaches 6.1 units forward at t=0.75s (wind-up 2.3 back at t=0.25s). | null",
 "issue_count":1,"by_type":{"all_linear":1},"issues":[...],
 "verdict":"Fix the issues above, then re-run analyze_animation — do not show this to the user yet. | The motion measures clean. ..."}
```
- 跟踪的槽位：`head`、`hips`、`hand_left`/`hand_right`、`foot_left`/`foot_right`（四足为 `foot_front_right` 等四个）。
- 可能的 `issues[].issue`：`empty_animation`、`no_visible_motion`（最大位移 <0.5）、`all_linear`（>4 帧且全是 linear）、`too_few_keyframes`（循环动画里某骨骼 <3 帧）、`stiff_limbs`（上段动、下段无帧）、`only_part_of_the_body_moves`（≤2 根骨骼动而可用 ≥6 根）、`loop_not_closed`（某骨骼 `loop_gap > 0.4`）、`strike_goes_backwards`、`weak_reach`。

#### 动画相关辅助数据结构

- `serializeAnimation`：`{uuid, name, loop, length, snapping, bones:[{name, uuid, keyframe_count}]}`。
- 动画器/关键帧字段：`channel`、`time`（秒）、`interpolation`、`data_points:[{x,y,z}]`。

### 3.4 相机 / 截图 / 视角校验

#### `set_camera_angle`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `angle` | string | 否 | 无 | 仅当值为 `'ortho'` 且预览支持 `setProjectionMode` 时切正交投影 |
| `position` | [x,y,z] | 否 | 不变 | 直接设相机位置 |
| `target` | [x,y,z] | 否 | 不变 | 直接设 `controls.target` |
| `preset` | string | 否 | 无 | 在 `DefaultCameraPresets` 里按 `id` 找预设并加载 |

- 注意：`preset` 不是模型相对视角（`front`/`left` 这类名字请用 `screenshot` 的 `view`）。
- 返回：`{"camera":[x,y,z]}`。

#### `screenshot`（异步）
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `view` | string \| object | 否 | 无 = 当前相机 | 视角名（`front`/`back`/`left`/`right`/`top`/`bottom`/`front_right`/`front_left`/`back_right`/`back_left`/`iso`/`+x`/`-z`/`north`/`east`…）或 Blockbench 相机预设 id，或 `{position,target}` |
| `width` / `height` | number | 否 | Screencam 默认 | 截图尺寸 |
| `annotate` | boolean | 否 | `true`（`!== false`） | 是否给图加标注条（视图名、看的是正面还是背面、模型右侧在图像哪一边，并画 R/L 标记） |
| `stamp` | string | 否 | 无 | 追加到标注条上的自定义文字 |

- 返回：`{"mime":"image/png","view":..,"looking_at":..,"model_right_on":"image_right\|image_left\|edge_on","note":..,"data_url":"data:image/png;base64,...","base64":"..."}`。
- 传 `view` 时走 `captureViews([view])`，返回同上字段。

#### `screenshot_views`（异步）
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `views` | array | 否 | `['front_right','front','left','back']`（`DEFAULT_VIEWS`） | 每项为视角名、预设 id 或 `{position,target}`；未知视角名会退化成 `front_right`，且 `view` 字段标记 `<名字> (unknown view -> front_right)` |
| `width`/`height`/`annotate`/`stamp` | 同上 | 否 | — | |

- 返回：`{"count":<张数>,"orientation":"...","shots":[{view, looking_at, model_right_on, note, data_url, base64}, ...]}`。

#### `get_orientation`
- 参数：无。
- 返回：`orientationReport()` + `side_index`、`side_sign`、`examples`、`views`：
```json
{"facing":"-z",
 "summary":"The model FACES -z. Its own RIGHT is +x, its own LEFT is -x.",
 "front_axis":"-z","back_axis":"+z","right_axis":"+x","left_axis":"-x",
 "rules":"ANATOMY (...)\n  the model's RIGHT side is at +x (X > 0), its LEFT side at -x.\n  ...",
 "side_index":0,"side_sign":1,
 "examples":{"right_hand_bone":"name it \"*_right\" and place it at +x","left_hand_bone":"...","sword_in_right_hand":"...","shield_in_left_hand":"..."},
 "views":[{"view":"front","looking_at":"the model's FRONT (its face)","model_right_on":"image_left"}, ...]}
```
- `rules` 原文见第 5 节。

#### `check_sides`
- 参数：无。
- 检查项：`side_name_on_centred_part`（名字带左右但贴在中线上）、`wrong_side`（名字主张的一侧与几何不符）、`pair_on_same_side`（一对左右都在同侧）、`unpaired_side`（成对部位缺一半，仅对名字匹配 `arm|leg|hand|foot|feet|paw|hoof|claw|toe|finger|wing|ear|horn|antler|shoulder|thigh|shin|knee|elbow|eye|tusk|fin|antenna` 的部位报）。
- 判定细节：中线带宽 ±0.35（`sideOfCoord` 的 `eps` 默认 0.35）。
- 返回：
```json
{"orientation":"...","right_axis":"+x","left_axis":"-x","checked":153,"issue_count":1,
 "by_type":{"wrong_side":1},
 "issues":[{"issue":"wrong_side","element":"hand_left","claimed_side":"left","actual_side":"right","side_coord":5.1,"hint":"..."}],
 "unmarked_off_centre_bones":[{"name":"sword","side":"right","hint":"Consider renaming to \"sword_right\" ..."}],
 "verdict":"Left/right naming matches the geometry. | FIX THESE — left/right is wrong somewhere in the model."}
```
- `unmarked_off_centre_bones` 只列**离中线 >1.5** 且名字没写左右**的骨骼**（最多 24 条）。

#### `which_side`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `element` \| `bone` \| `name` | string | 三者取一 | — 找不到报 `Element not found: <ref>` |

- 返回：`{"element":"hand_left","side":"left","side_coord":-5.1,"name_claims":"left","matches_name":true,"explanation":"\"hand_left\" sits on the model's LEFT (+x is the model's right).","right_axis":"+x"}`。
- `side_coord` 是**带符号**的侧向坐标（正 = 模型右侧），方块取 from/to 中点，组取所有子方块中点均值（无方块则取 origin）。

### 3.5 参考图

#### `load_reference`（异步）
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `path` | string | 二选一 | — | 桌面版读文件，按扩展名推 mime：`jpg`/`jpeg` → `image/jpeg`，`webp` → `image/webp`，其它 → `image/png` |
| `data_url` | string | 二选一 | — | 两者都没有报 `Provide a reference \`path\` (desktop) or \`data_url\`.` |
| `name` | string | 否 | 用文件名；再无则 `reference_<seq>` | |
| `overlay` | boolean | 否 | `true`（`!== false`） | 是否在视口里放参考图叠层 |
| `opacity` | number | 否 | `0.45` | 叠层透明度 |
| `layer` | string | 否 | `'background'` | `ReferenceImage.layer` |

- 返回：`{"id":"ref_1","name":"...","width":..,"height":..,"overlay_added":true,"total_references":1}`。
- 参考图 id 形如 `ref_<自增序号>`。

#### `list_references`
- 参数：无。
- 返回：`{"count":1,"references":[{"id":"ref_1","name":"zombie.png","width":512,"height":512,"source":"path","overlay":true}]}`（`source` 为 `'path'` / `'data'`）。

#### `get_reference`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `id` 或 `name` | string\|number | 否 | **最后一张**（`pickReference` 空参取 `G.references` 末项） | 也接受下标 |

- 返回：`{"count":1,"references":[{"id","name","width","height","source","data_url"}]}`；没有任何参考图时返回 `{"count":0,"note":"No reference loaded. Drop an image into the BlockbenchMCP panel, or call load_reference."}`。

#### `clear_references`
- 参数：无。返回 `{"cleared":<清掉的数量>}`，并移除视口叠层。

#### `measure_model`
- 参数：无。
- 返回：
```json
{"cubes":132,"groups":21,
 "total":{"width":16,"height":32,"depth":12,"min":[-8,0,-6],"max":[8,32,6]},
 "ratios":{"width_to_height":0.5,"depth_to_height":0.375,"head_height_fraction":0.25},
 "bones":[{"name":"hips","origin":[0,12,0],"bounds":{"w":8,"h":6.6,"d":4,"cubes":1,"top":18.6,"bottom":12}}],
 "note":"Compare these proportions to the reference. Bounds are axis-aligned (ignore rotation); good enough for proportion checks."}
```
- 无方块时返回 `{"cubes":0,"note":"Model has no cubes yet."}`。
- `head_height_fraction` 用名字匹配 `head|skull|cranium` 的骨骼计算。

#### `compare_reference`（异步）
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `reference` \| `name` \| `id` | string\|number | 否 | 最后一张 | 找不到报 `No reference loaded. Drop one into the BlockbenchMCP panel or call load_reference first.` |
| `view` | string | 否 | 当前视角 | 视角名或 Blockbench 预设 id/name；会临时移动相机，比完复原 |
| `position` / `target` | [x,y,z] | 否 | 无 | 手动指定相机 |
| `threshold` | number | 否 | `0.45` | 模型剪影的 alpha 阈值 |

- 前置：模型没有方块时报 `The model has no cubes yet — build the silhouette before comparing.`；抓到的剪影为空时报 `Captured model silhouette was empty. Make sure the model is on-screen in the preview before comparing.`
- 返回：
```json
{"reference":"zombie.png","view":"front_right","match_percent":87,"iou":0.872,
 "model_only_pct":9,"ref_only_pct":7,"model_aspect":0.51,"reference_aspect":0.48,"aspect_delta_pct":6,
 "verdict":"GOOD — minor shape refinements left.",
 "advice":["7% of the reference shape (RED in the overlay) has NO model under it — you are MISSING mass there. ..."],
 "composite_data_url":"data:image/png;base64,...","composite_base64":"..."}
```
- `verdict` 分档：≥93 `EXCELLENT`；≥85 `GOOD`；≥70 `CLOSE`；≥50 `ROUGH`；否则 `POOR`。
- 三联图：`[参考 | 你的模型 | 叠加]`；叠加里 **红 = 只有参考（要补体积）**、**蓝 = 只有模型（要削/移）**、**白 = 命中**（源码/指引原文见第 4 节 reference topic）。
- 同时会更新界面上的 `G.lastCompare`（`{match_percent, view, reference, time}`）。

### 3.6 交互（会阻塞等用户）

三者共用一套机制：请求挂在 Blockbench 的 MCP Copilot 面板上，HTTP 连接保持打开；单次等待窗口很短（MCP 客户端一般 30–60 s 就超时），所以用轮询继续等。

- `timeout_seconds`（卡片存活时间）：夹在 `5–3600`，默认 `900` 秒。
- `wait_seconds`（本次调用等待时长）：夹在 `1–120`，默认 `25` 秒。
- 未答时的返回：`{"answered":false,"pending":true,"verdict":"waiting","review_id":"ask-1","waited_seconds":25,"seconds_left":875,"note":"Still waiting for the user — the card is open in the MCP Copilot panel. Call wait_review {review_id:\"ask-1\"} again to keep waiting. This is NOT approval; do not continue as if it were."}`
- 已答时的返回：`{"answered":true,"pending":false,"approved":true|false,"verdict":"approved|changes_requested|answered|no_answer","choice":null,"comment":"","answer":"...","review_id":"ask-1","waited_seconds":12,"timed_out":false,"note":"..."}`。
- 请求 id 形如 `ask-<自增序号>`。

#### `request_review`（异步 + 长连接）
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `animation` | string | 否 | 无 | 给了就渲染该动画的多时间点姿势图 |
| `times` | number[] | 否 | `[0, L*0.25, L*0.5, L*0.75]` | 仅动画模式 |
| `views` | array \| `"none"` | 否 | `DEFAULT_VIEWS`（非动画）；动画默认 `['front_right']` | `views:'none'` 且无 `animation` 时不渲染任何图 |
| `title` | string | 否 | `'Please check this'` | |
| `question` | string | 否 | `'Does this look right?'` | |
| `details` \| `context` | string | 否 | `''` | 说明文字（`details` 优先） |
| `options` | string[] | 否 | `null` | 按钮选项；不传则面板显示 通过/不通过 类按钮（源码未说明具体按钮文案） |
| `timeout_seconds` | number | 否 | `900` | 卡片存活 |
| `wait_seconds` | number | 否 | `25` | 本次等待 |
| `width`/`height` | number | 否 | 非动画时 `480` | 渲染尺寸 |

- 返回：`formatAnswer(...)` + `{"shots":[...]}`。

#### `wait_review`（异步 + 长连接）
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `review_id` \| `id` | string | 否 | 最近一个待答请求 | 都没有时返回 `{"answered":false,"note":"There is no open review to wait for."}` |
| `wait_seconds` | number | 否 | `25` | 夹在 1–120 |

- 报错：`No such review: <id>. Open ones: <逗号列表 或 none>`。

#### `ask_user`（异步 + 长连接）
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `question` | string | **是** | — | 报 `question is required` |
| `title` | string | 否 | `'Question from the AI'` | |
| `details` | string | 否 | `''` | |
| `options` | string[] | 否 | `null` | 选项按钮 |
| `views` | array \| `"none"` | 否 | 无（不渲染图） | 给定时渲染对应视角 |
| `timeout_seconds` | number | 否 | `900` | |
| `wait_seconds` | number | 否 | `25` | |
| `width`/`height` | number | 否 | `420` | |

- 返回：`formatAnswer(...)` + `{"shots":[...]}`。

#### `list_pending_reviews`
- 参数：无。
- 返回：`{"pending":[{"id","kind","question","waiting_seconds","seconds_left"}],"recent_answers":[<最近 5 条 {id,kind,question,answer,t}>]}`。

### 3.7 其他

#### `get_guide`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `topic` | string | 否 | `'modeling'` | 不区分大小写；非法 topic **不报错**，返回 `modeling` 的正文 |

- 返回：`{"topic":"<实际 topic>","guide":"<正文全文>","available_topics":["modeling","detailing","texturing","vfx","animation","rigging","orientation","review","reference"]}`。
- 注意：非法 topic 时返回的 `topic` 是 `'modeling'`（源码写死），不是请求值。

#### `list_plugins`
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `installed_only` | boolean | 否 | `false` | 只列已安装 |
| `query` | string | 否 | 无 | 在 `id`/`title`/`description` 里不区分大小写搜索（`installed_only` 优先，二者同时给时只按 installed 过滤） |

- 返回：`[{id,title,author,version,installed,disabled,tags,description}]`。

#### `install_plugin`（异步）
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `url` | string | 三选一 | — | `loadFromURL(url, true)` |
| `path` | string | 三选一 | — | 桌面版，`loadFromFile(...)` |
| `id` | string | 三选一 | — | 从商店安装；都没有报 `Provide a plugin id, url, or path.` |

- 按 `id` 时：找不到先尝试 `loadInstalledPlugins()` 再找一次，仍找不到报 `Plugin "<id>" not found in the store. Use list_plugins query to search.`；已安装返回 `{"installed":true,"already":true,"id":..}`；否则 `{"installed":<bool>,"id":..,"title":..}`。
- 按 `url` 返回 `{"installed":true,"source":"url","url":..}`；按 `path` 返回 `{"installed":true,"source":"file","path":..}`。

#### `uninstall_plugin`（异步）
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | **是** | — | 报 `id is required`；未安装报 `Plugin not installed: <id>` |

- 返回：`{"uninstalled":true,"id":<id>}`。

#### `execute_script`（逃生舱）
| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | string | **是** | — | 报 `code is required`；会被包成 `new Function('params','Blockbench', '"use strict";\n' + code)` |
| `params` | object | 否 | `{}` | 作为第一个参数传入 |

- 开关：设置项 `blockbench_mcp_allow_scripts`（UI 名「Allow execute_script」），关掉后调用报
  `execute_script is disabled in Blockbench settings ("Allow execute_script"). Use the dedicated tools, or ask the user to enable it.`
- 返回：函数返回值；返回值不能 `JSON.stringify` 时包装成 `{"value":String(r)}`；返回 Promise 会被 await。

---

## 4. `get_guide` 全部 topic 与正文原文

`available_topics`（源码 `GUIDES` 的键，顺序固定）：
`modeling`、`detailing`、`texturing`、`vfx`、`animation`、`rigging`、`orientation`、`review`、`reference`

> 以下每段为源码字符串常量 `join('\n')` 后的**完整原文**，未翻译、未摘要、未改动。

### 4.1 `modeling` → `MODELING_GUIDE`

```
BLOCKBENCH MODELING PLAYBOOK — read before building any model. Other topics:
get_guide {topic:"detailing"|"orientation"|"rigging"|"texturing"|"vfx"|"animation"|
"review"|"reference"}. Read "detailing" for the cube budget and the 4-layer doctrine
before anything with a costume, armour, cloth or a weapon. If the model will be animated, read "rigging" BEFORE placing cubes,
and "orientation" before anything that has a left and a right.

GOLDEN WORKFLOW (loop it, do not one-shot):
  get_reference (look at what you must match) -> get_status -> plan bones &
  proportions -> add_groups -> add_cubes -> compare_reference (SCORE the silhouette)
  -> fix the biggest delta -> compare_reference again ... THEN pack_uv -> create_texture
  -> detail_cubes -> paint_faces -> screenshot_views -> check_model -> FIX -> repeat.
Do at least 2-3 passes. The first pass is NEVER good enough — plan to redo it.

0. GROUND YOURSELF IN THE REFERENCE. If a reference image was provided (dropped in
   the MCP Copilot panel, or via load_reference), call get_reference and LOOK at it.
   Then build, and use compare_reference EVERY pass — it renders your model from the
   reference angle and returns a hard match_percent (silhouette IoU) plus a side-by-
   side overlay. Do not trust your own "looks close" — trust the number. See
   get_guide {topic:"reference"}.

1. SILHOUETTE FIRST. Build the grey shape and compare_reference it BEFORE texturing.
   A great texture cannot rescue wrong proportions. Match the reference silhouette:
   overall stance, head size/position, limb length. Aim for match_percent >= 85.

2. PART COUNT & DETAIL. BUDGET: simple prop 30-60 cubes, standard mob/NPC 100-180,
   hero/boss 180-300+. A humanoid under ~70 cubes is a draft, not a model, and does
   NOT go to texturing — audit_complexity is the gate and it says so. Break every
   limb into 3 segments, give the head a separate snout/brow/jaw, and build in
   LAYERS: primary mass, then secondary volumes standing 0.3-0.8 proud of it, then
   fringes and silhouette breakers, then 1x1 micro-detail. Do not hand-compute
   hundreds of boxes: add_hollow_volume (shells: hoods, helmets, armour),
   generate_array (rows: hems, scales, plates, teeth, rivets), extrude_chain (horns,
   tails, tentacles), voxelize_matrix (blades, emblems, flat detail from a character
   grid). Full doctrine: get_guide {topic:"detailing"}.

3. ROTATION & TAPER make shapes organic. Cubes AND bones take rotation:[x,y,z].
   - A single cube rotates cleanly on ONE axis; for a compound angle put it in a
     GROUP and rotate the group, or nest groups. Build each limb as a bone at the
     JOINT origin and rotate the bone to pose it.
   - inflate (small +/-) rounds/shrinks a cube in place. Taper limbs by shrinking
     each segment.
   - A cube rotated 45° reads as a crystal/diamond/blade — use this for non-boxy
     shapes in cube formats. For true non-cuboid shapes use add_mesh.

3b. AVOID Z-FIGHTING / CLIPPING (the flickering "two squares inside one another").
   It happens when two faces sit on the SAME plane at the same depth. Rules:
   - When two cubes overlap, make one clearly PENETRATE the other (by >=0.1, ideally
     ~0.5) so no faces are coplanar — never align two faces to the exact same coord.
   - Decorative pieces (leaves, scales, plates, fur, trim) must NOT sit flush on a
     surface: push each out by a small UNIQUE amount and stagger neighbours' depths
     so no two share a plane. Vary by 0.05-0.2 between adjacent pieces.
   - Two billboard PLANES must never share the exact same position — offset by >=0.1.
   - check_model reports `coplanar_overlap` pairs; fix every one by nudging a cube.

4. SYMMETRY. Build one side, then mirror_element {axis:"x"} (or emit the mirror in
   the same add_cubes call: negate X of from/to, swap so from<to, negate Y/Z
   rotation signs). Keep paired bones named *_left / *_right.

5. TEXTURE SMOOTH, not flat. pack_uv FIRST (box UV does not auto-pack), then
   detail_cubes for a smooth shaded base on every face (no gaps), then paint_faces
   for crisp features. See get_guide {topic:"texturing"}.

6. REVIEW HONESTLY. screenshot_views every pass; check_model for untextured faces /
   bad UVs / unparented cubes / left-right mistakes. If a screenshot looks wrong,
   FIX it — never call a visible flaw "acceptable" or "close enough".

7. THEN ASK THE USER. Your own opinion of your own screenshot is not verification.
   At the end of a blockout, a texture pass or an animation, call request_review —
   it shows the user labelled renders inside Blockbench and waits for their verdict
   before you continue. See get_guide {topic:"review"}.

8. LEFT AND RIGHT are the model's own, not the viewer's: the model faces -Z, so its
   RIGHT is +X and a front-view render shows it MIRRORED. Pass side:"left"/"right"
   to add_cube(s)/add_group and let the tool police it; verify with check_sides.
   See get_guide {topic:"orientation"}.

Animation formats (GeckoLib/Bedrock): every cube must live under a bone; bone
origins must sit at the real joint; limbs need 3 segments so elbows and knees can
bend (create_rig does all of this). GeckoLib store id "geckolib", format
"geckolib_model". Meshes do NOT export to GeckoLib/Java — use rotated cubes there.
```

### 4.2 `detailing` → `DETAILING_GUIDE`

```
DETAILING DOCTRINE — how a model stops being 15 boxes. Read this BEFORE placing
geometry for anything with a costume, armour, cloth, fur, plating or a weapon.

WHY THIS EXISTS: asked for a hooded figure you emit one box for the torso, one for
the cloak and one for the head, because computing 200 sets of [from,to] in your head
is impossible. do the arithmetic; your job is the SHAPE and the LAYERS.

1. CUBE BUDGET (audit_complexity enforces it):
     simple prop / small item .......  30-60 cubes
     standard mob / NPC ............. 100-180 cubes
     hero model / boss / detailed ... 180-300+ cubes
   A humanoid built from under ~70 cubes is a DRAFT, not a model, and must not go to
   texturing. Cube count alone is not quality — but under budget is always a fail.

2. THE 4-LAYER DOCTRINE. Build outward, one layer at a time.
   Layer 0 — CORE FRAME: the skeleton and joint volumes (create_rig), plus the dark
     cavities other layers sit over: the void under a hood, the gap between armour
     plates, an open mouth. Cavities are what give depth; add_hollow_volume makes them.
   Layer 1 — PRIMARY MASS: torso segmented into 2-3 blocks, every limb in at least 3
     segments (upper / lower / hand-or-foot), neck, head. Never one cube per limb.
   Layer 2 — SECONDARY VOLUMES: the outer shell — chest plate, pauldrons, bracers,
     belt, hood, boots, collar. These are SEPARATE cubes standing 0.3-0.8 units proud
     of Layer 1, not a recoloured part of it. add_hollow_volume for anything that
     wraps (hood, helmet, cuff); plain cubes for slabs.
   Layer 3 — FRINGES AND SILHOUETTE BREAKERS: torn hems, shingles, scales, feathers,
     spikes, teeth, plate rows, and cubes rotated 15-45 degrees that break the square
     outline. generate_array produces a whole row in one call. A silhouette with no
     interruptions reads as a box no matter how good the texture is.
   Layer 4 — MICRO-VOXELS AND PROPS: 1x1 and 1x2 details — studs, buckles, rivets,
     stitches, gem settings, eyes — plus the held weapon or tool. voxelize_matrix
     draws blades, emblems and flat detail from a character grid; extrude_chain
     builds horns, tails, tentacles and braids.

3. BANNED SHAPES. Each of these is an automatic rebuild:
   - one cube for a cloak, cape or skirt. Segment it vertically, then close the bottom
     with a generate_array fringe row (anchor "top", depth_stagger 0.05-0.2).
   - one solid cube for a head that wears a hood, helmet or mask. The head is Layer 1;
     the covering is add_hollow_volume with the face (north) and neck (down) open.
   - one cube per limb. Three segments minimum, or every animation looks like cardboard.
   - a large flat face with nothing on it. Overlay trim, a bevel cube at 45 degrees,
     or a fringe row. audit_complexity reports these as undetailed_slab.

4. THE GENERATORS (all universal — none of them knows what a hood or a scale is):
   voxelize_matrix    draw the silhouette as rows of characters, get cubes. Blades,
                      axe heads, bows, horn profiles, shield emblems, fins, feathered
                      wing profiles, chevrons, gears, plate patterns. Set `palette` per character for
                      depth / offset_z / name, and merge_adjacent for anything big.
   add_hollow_volume  a shell with a cavity instead of a solid box. Hoods, helmets,
                      masks, eye sockets, breastplates, pauldrons, cages, pipes,
                      wheels, crates. `open_faces` decides what stays open.
   generate_array     repeat an element along a line, around a ring or over a grid,
                      with jitter, taper, per-element rotation and depth_stagger.
                      Hems, scales, feathers, plates, teeth, spikes, rivets, links.
   extrude_chain      a tapering, curving chain, one bone per segment by default.
                      Horns, tails, tentacles, claws, branches, braids, cables.
   add_wing           a whole bat / dragon wing: arm, forearm, a fan of finger bones and
                      a CONTINUOUS membrane to the body, parented so it flaps as one.
                      Never hand-place rotated membrane slabs — they gap and z-fight.
   Use them for the repetitive mass and add_cubes for the shapes only you can judge.

5. DEPTH DISCIPLINE (this is what makes layers read as layers):
   - Layer 2 stands 0.3-0.8 proud of Layer 1. Less and it looks like a texture; more
     and it detaches.
   - Overlapping decorative pieces must never share a plane: stagger neighbours by
     0.05-0.2 (generate_array depth_stagger does it for you). Two coplanar faces
     z-fight, which is the flickering "two squares inside each other" artefact.
   - When two cubes overlap, let one clearly PENETRATE the other by >=0.1.
   - check_model reports coplanar_overlap; fix every one. The generators also
     report `z_fight_pairs` on their own output when they could not avoid it —
     a row where each element overlaps two neighbours still lines up, and elements
     at the same height share top/bottom planes. Fix it with jitter, spacing or
     a small rotation_range, do not ship it.

6. THE PIPELINE:
   1  read the reference, split the silhouette into the four layers
   2  create_rig                      (anatomy, joints, segmented limbs)
   3  add_cubes                       (Layer 1 primary mass)
   4  add_hollow_volume               (Layer 0 cavities + Layer 2 shells)
   5  generate_array                  (Layer 3 fringes, plates, scales)
   6  voxelize_matrix / extrude_chain (Layer 4 props, weapons, horns, micro-detail)
   7  audit_complexity + compare_reference + check_model  -> FIX, then repeat
   8  pack_uv -> create_texture -> detail_cubes -> paint_faces
   9  request_review — the user, not you, decides it is done

7. THE GATE: audit_complexity returns too_primitive / acceptable / high_detail plus
   monolithic boxes, layering, micro-detail density and bare slabs. Verdict
   too_primitive means keep building; it is not a suggestion. Texturing a blockout
   wastes the whole texturing pass.
```

### 4.3 `texturing` → `TEXTURING_GUIDE`

```
BLOCKBENCH TEXTURING PLAYBOOK — the smooth, Hytale/@volmur look (not dirty/noisy).

ORDER: pack_uv -> create_texture -> detail_cubes (smooth base) -> paint_faces
(crisp features) -> get_texture to inspect -> fix.

1. PACK UV FIRST. New box-UV cubes all sit at uv_offset [0,0] and share the same
   pixels. Call pack_uv before painting and again after adding/resizing cubes, or
   every face paints onto the same spot. It auto-grows the texture if needed.

2. SIZE. 64px for simple, 128px typical, 256px for very detailed. Square.

3. SMOOTH BASE COAT — detail_cubes. It bakes, per face: a soft vertical gradient in
   the base colour + gentle directional shading (top lighter, underside darker) +
   a SUBTLE low-contrast mottle, then a 3x3 box blur per UV island (the "smooth
   brush"). This is the difference between good and bad textures. Tips:
   - Use the `colors` map to colour regions by cube name, e.g.
     colors:[{match:"leg|paw",color:"#5a3d22"},{match:"belly",color:"#3a2a18"}].
     Bodies/limbs are often the SAME tone as the head with darker extremities —
     do not default everything to one brown.
   - Keep noise LOW (0.04-0.08). Do NOT raise edge_darken (a dark outline on every
     face reads as a dirty grid — the look to avoid). streaks:true adds fur/wood/
     stone grain on top/back faces.
   - Glow parts (eyes cores, gems, lanterns, runes): name them *_core or *_glow —
     detail_cubes fills them bright with no shading/blur. Mark the texture emissive
     with set_texture_render_mode for real in-engine glow.

4. CRISP FEATURES — paint_faces, AFTER the bake (so blur does not soften them).
   Coords are RELATIVE to each face ([0,0] = its top-left). Eyes are the #1 thing
   that makes a creature read as alive: dark socket rect, bright iris, 1px hotspot.
   Also nose, mouth, claws, stripes, scars, armour trim, rune lines. Ops: rect,
   ellipse, polygon, line, gradient, dither (patterns), noise.

5. INSPECT. get_texture shows the sheet; screenshot_views shows it on the model.
   Compare to the reference palette. Recolour with detail_cubes `colors` and repeat.
```

### 4.4 `vfx` → `VFX_GUIDE`

```
BLOCKBENCH PIXEL-VFX PLAYBOOK — flames, energy, projectiles, slashes, trails, auras.
The look: layered emissive PIXEL shapes, a bright hot core fading to cool edges,
jagged stepped silhouettes, animated. Built from PLANES + emissive textures, posed
and animated with bones. (Think the homegaddiel magma fire / a glowing ice shard.)

CORE IDEA: a VFX is a few flat 2-sided PLANES carrying transparent emissive pixel
textures, layered and crossed for volume, then animated (scale/position/rotation/
flipbook). Bright additive layers stack into a glow.

1. BUILD THE PLANES — add_plane {from,width,height,facing,crossed}. Make a flame/
   energy sheet as 2-3 stacked planes at slightly different depths, or crossed:true
   for a volumetric particle. Parent them to a bone so you can animate them.
   For a solid glowing core (orb, gem, shard) use a small cube or add_mesh
   {shape:"crystal"|"shard"} (or, in GeckoLib, a cube rotated 45°).

2. MAKE THE TEXTURE — create_vfx_texture {style,preset,frames}. Styles: flame,
   energy, orb/glow, spark/star, smoke, trail/streak, beam, bolt/lightning, ring,
   shockwave, crystal. Presets (palettes): fire, ember, ice, frost, energy, arcane,
   poison, shadow, holy, smoke, blood, nature. It defaults to ADDITIVE (flames/
   energy) or EMISSIVE (crystals) render mode + 2-sided, so it glows. For a looping
   animated effect set frames:4-8 — it bakes a vertical flipbook and starts the
   animation player. Tune speed with frame_time (lower=faster).

3. LAYER FOR DEPTH. Stack a wide dim outer glow + a brighter narrower mid + a small
   white-hot core (3 planes, additive). Cooler/darker = bigger & behind; hotter =
   smaller & in front. This is what makes pixel fire/energy look rich, not flat.

4. EMISSIVE/ADDITIVE — set_texture_render_mode {render_mode:"additive"|"emissive",
   render_sides:"double"}. additive = bright pixels add light & dark vanishes (best
   for fire/energy on planes); emissive = full-bright, ignores scene light (solid
   gems/runes). Always render_sides:"double" for planes.

5. ANIMATE (the life of a VFX). Use create_animation + add_keyframes on the planes/
   bones:
   - FLICKER: small fast scale Y (1.0->1.15->0.95) + tiny position jitter, looped.
   - PROJECTILE (ice shard / fireball): a solid core + a TRAIL. Trail = a row of
     planes/cubes behind the core, each scaling down and fading (scale->0) on a
     staggered delay so it streaks; or one "trail" plane stretched on the travel
     axis. The whole group flies via position; spin the core (rotation) for energy.
   - SLASH: an arc plane that sweeps (rotation) and quickly scales up then fades.
   - BURST/IMPACT: a shockwave ring (style:"shockwave", or a ring plane scaling out
     while fading) + outward spark planes.
   Fade by scaling to 0 (GeckoLib has no opacity channel); flipbook frames also
   carry motion. Use linear for snappy pops, catmullrom for smooth pulses.

6. REVIEW with screenshot_views from a few angles and against the reference. Check
   the core reads hottest, edges are jagged pixels (not smooth), and it glows.
```

### 4.5 `animation` → `ANIMATION_GUIDE`

```
BLOCKBENCH ANIMATION PLAYBOOK (GeckoLib/Bedrock). Read get_guide {topic:"rigging"}
and {topic:"orientation"} FIRST — a bad rig or a flipped axis cannot be animated out.

THE LOOP (never skip a step):
  check_rig -> generate_animation (correct base cycle) -> analyze_animation (MEASURE
  it) -> fix -> add_keyframes to refine -> preview_animation -> request_review (the
  USER confirms) -> only then move on.
Budget real time per animation. One pass is never enough; 3-4 passes is normal.

1. AXIS SIGNS — the reason attacks end up swinging into the model's back.
   +X rotation turns a bone so its FRONT face goes UP. Consequences:
     - a bone pointing DOWN (arm, leg) swings its tip FORWARD with +X;
     - a bone pointing UP (torso, neck, head) tips BACKWARD with +X;
     - ELBOWS bend +X (hand comes forward), KNEES bend -X (heel goes back);
   +Y turns the model toward its own LEFT. +Z tips a bone's top toward its LEFT.
   Never guess a sign: generate_animation already knows them, and
   analyze_animation measures where the hand actually ended up.

2. NEVER TRUST YOUR OWN EYE ON A RENDER. analyze_animation evaluates the rig and
   reports, per hand/foot/head, how far it travels FORWARD/BACK/LEFT/RIGHT/UP in the
   model's own axes, whether the loop closes, and whether the lower limb segments
   move at all. A strike that measures "backward 6.2, forward 0" is wrong no matter
   how good the screenshot looks.

3. BONES: limbs need THREE segments (upper / lower / hand-or-foot). With two there
   is no elbow or knee and every cycle looks like cardboard. check_rig reports this;
   create_rig builds it correctly. Animate the LOWER segments too — that is the
   single biggest difference between amateur and good animation.

4. KEYFRAME DENSITY: a cycle wants 6-9 keyframes per moving bone (not 2), and the
   whole body moving, not just the limb that "does" the action: hips bob and twist,
   chest counter-rotates, neck/head stabilise, tail/cloak lag behind by 0.1-0.2s.
   Use add_keyframes {close_loop:true} so the first and last poses match exactly.

5. TIMING & EASING: catmullrom for swings and settles, linear for the snap of an
   impact, step for instant changes. Anticipation before a strike (wind back ~25% of
   the length), contact HOLD of 2-3 frames at the hit, then a slower recovery.
   Typical lengths: idle 3-5s, walk 0.9-1.1s, run 0.55-0.7s, attack 0.7-0.9s.

6. CYCLES: walk = arms and legs opposite (right arm with LEFT leg), two body bobs
   per cycle, hips and chest counter-rotating. Run = bigger swing, forward lean, air
   time. Quadruped = diagonal gait (front-right with back-left), NOT a front-pair /
   back-pair bound, which reads as a march.

7. SHOW YOUR WORK: preview_animation renders labelled poses; request_review puts them
   in front of the user and waits for their verdict. Do not describe an animation as
   good, finished or working until the user has said so.

VFX animation: see get_guide {topic:"vfx"} — scale/position pulses, trails that
scale to 0, spinning cores, sweeping slashes, expanding shockwaves.
```

### 4.6 `rigging` → `RIGGING_GUIDE`

```
RIGGING PLAYBOOK — the skeleton decides how good the animation can ever be.

THE FAILURE TO AVOID: a limb made of 2 bones ("arm" + "hand"). There is no elbow, so
nothing can bend and every animation looks like cardboard cut-outs swinging. Minimum
for anything that moves:
  arm  = shoulder? -> arm_upper -> arm_lower -> hand      (3 movable segments)
  leg  = leg_upper -> leg_lower -> foot
  body = hips -> spine -> chest -> neck -> head (+ jaw)
  plus tail / ears / cloak chains of 2-4 bones for follow-through.
A creature rig is normally 15-30 bones. Under 8 is a red flag.

FASTEST PATH: create_rig {type:"humanoid"|"quadruped", height, arm_segments:3,
leg_segments:3, tail_segments:3} builds the whole hierarchy with joints on the real
pivots, correct left/right naming, and a blocked-out placeholder body you then
reshape with edit_element and add detail cubes into. Then check_rig.

JOINT ORIGINS: a bone rotates around its origin, so the origin must sit ON the joint
— the shoulder for arm_upper, the elbow for arm_lower, the wrist for the hand, the
hip/knee/ankle for legs. An origin in the middle of a limb makes it spin in place;
check_rig reports that as origin_not_at_joint.

NAMING drives every automatic tool. Use lower_snake with a side suffix:
  arm_upper_right, arm_lower_right, hand_right, leg_upper_left, foot_left, tail1..3.
The side must match the geometry: the model's right is +X (see
get_guide {topic:"orientation"}). check_sides verifies it; create_rig gets it right
by construction.

PARENTING: in animated formats every cube must live under a bone. Cubes stay in the
segment they belong to (forearm cubes under arm_lower, not under arm_upper), or the
elbow bend will tear the mesh apart.

BEFORE ANIMATING: check_rig must say ready_to_animate. Then generate_animation.
```

### 4.7 `orientation` → `ORIENTATION_GUIDE`

```
ORIENTATION — WHICH SIDE IS LEFT? (read before rigging, posing or attaching items)

THE RULE: a Minecraft-style model FACES -Z. Its own RIGHT is +X, its own LEFT is -X.
Call get_orientation for the live values (formats can declare a different facing).

WHY IT GOES WRONG: a render taken from the front shows the model MIRRORED, exactly
like standing in front of a person — their right hand is on your left. An AI that
looks at that image and says "the sword is on the right" is wrong 100% of the time.
Every screenshot from this plugin is now stamped with which image edge is the
model's right, and there is a tool for the question:
  - get_orientation  -> the axis rules for this project
  - which_side {element} -> "hand_left sits on the model's LEFT"
  - check_sides -> audits every left/right NAME against the geometry

WHEN THE USER SAYS "shield in the left hand, sword in the right":
  1. which_side on the two hand bones, or check_sides, to learn which is which.
  2. Parent the shield to the bone on -X (named *_left) and the sword to +X (*_right).
  3. check_sides again, then request_review with a FRONT and a BACK view so the user
     confirms. Never conclude it is correct from your own look at the render.

BUILDING: pass side:"left"/"right" to add_cube/add_cubes/add_group — the tool
refuses the call if the coordinate contradicts the side, so a mirrored limb is
impossible to create by accident. Keep paired bones named *_left / *_right.

EXPORT: Blockbench mirrors X when it writes Bedrock/GeckoLib/Java files, so a bone
you place at +X here is written as x = -5 in the .json. That is correct — vanilla
"rightArm" has pivot x = -5. Do not "fix" it.

CAMERA VIEWS are named from the MODEL's point of view: "front" looks at its face,
"left" looks at the side its left arm is on, "front_right" is a three-quarter from
its front-right. World-axis names (+x, -z, north, east) still work if you want them.
```

### 4.8 `review` → `REVIEW_GUIDE`

```
REVIEW PROTOCOL — how to stop shipping work that is not actually right.

The problem this fixes: taking a screenshot, judging it yourself, and telling the
user "everything looks good" when it does not. You are a poor judge of your own
render — you know what you INTENDED, so you see it. The user does not.

RULE: after every user-visible milestone, call request_review and WAIT. The tool
renders labelled views, puts them in the MCP Copilot panel inside Blockbench, and
blocks until the user presses a button — the answer comes back to you in the same
tool call, so nothing about the conversation is interrupted.

MILESTONES THAT NEED A REVIEW:
  - the silhouette / blockout is finished (before texturing)
  - the texture pass is finished
  - EACH animation, previewed at several times (pass `animation` to request_review)
  - anything the user asked for specifically ("shield in the left hand")
  - before you say a task is done

HOW TO ASK WELL: one concrete question, and say what to look at.
  request_review {question:"Walk cycle: is the stride length right and do the knees
  bend enough?", animation:"animation.golem.walk", times:[0,0.25,0.5,0.75],
  views:["front_right","left"]}
Use ask_user for a decision you cannot make yourself (which hand, which colour,
which of two silhouettes) instead of guessing and building the wrong thing.

WHEN THE ANSWER COMES BACK:
  approved -> continue.  changes requested -> fix exactly what they said, then ask
  again.  no answer (timeout) -> say so in chat; NEVER treat silence as approval.

AND BEFORE YOU ASK: run the objective checks first (check_model, check_sides,
check_rig, analyze_animation, compare_reference). Do not spend the user's attention
on something a tool would have caught.
```

### 4.9 `reference` → `REFERENCE_GUIDE`

```
MATCHING A REFERENCE — the grounded loop. Hit it, do not "almost" it.

Why models miss the reference: the AI builds from a fuzzy memory of the image, then
RATIONALISES the result ("close enough") because nothing measures the gap. This
toolset removes both excuses — the reference is in the workspace and the match is a
NUMBER. Use the number, not your opinion.

THE TOOLS:
- get_reference — returns the reference image(s) the user dropped in the MCP Copilot
  panel (or that you loaded). LOOK at it before and during the build.
- load_reference {path|data_url} — add a reference from disk / a data URL yourself.
- compare_reference {view?} — THE key tool. Renders your model from the chosen angle
  on a transparent background, extracts both silhouettes, and returns:
    match_percent (silhouette IoU 0-100), aspect_delta_pct (too wide/narrow),
    ref_only_pct (reference area with NO model under it = MISSING mass),
    model_only_pct (model sticking out beyond the reference = EXTRA mass),
    a verdict + concrete advice, AND a composite image: [reference | your model |
    overlay]. In the overlay: RED = reference only (fill it), BLUE = model only
    (trim it), WHITE = match. Drive RED and BLUE toward zero.
- measure_model — bounding box + per-bone sizes + key ratios, to match proportions
  numerically (e.g. head_height_fraction).

THE LOOP:
1. get_reference and describe it concretely in words: stance; head size & position;
   limbs/appendages (count + shape); key features; ~5 palette colours; what is
   BIGGEST. Turn that into a bone + part list before building.
2. Build the grey silhouette (no texture yet). Aim the camera to the reference angle
   (set_camera_angle / screenshot_views; models usually face -Z so "back" shows the
   FACE) — or pass `view` to compare_reference.
3. compare_reference. Read match_percent and the advice. Study the overlay: where is
   it RED (add/enlarge parts there)? where BLUE (shrink/move)? Is aspect_delta_pct
   telling you too wide/narrow? Fix the SINGLE biggest delta.
4. compare_reference again. Repeat until match_percent >= 85 (90+ for a hero asset).
   Only THEN texture — match the palette with detail_cubes `colors` + paint_faces.
5. NEVER declare success on opinion when a compare score exists. If match_percent is
   72 and you "think it looks great", it does not — keep going. Stop when the number
   is high AND the side-by-side would convince the user, not just you.
```

---

## 5. 坐标 / 朝向约定

### 5.1 模型朝向与左右（源码 `orientation()` / `orientationReport()`）

- 模型朝向取自 `Format.forward_direction`；工程可用 `Project.mcp_facing` 覆盖；**默认 `-z`**（Minecraft 风格：脸贴在 `north` 面上）。
- `right = forward × up`（右手系）。`forward = (0,0,-1)`、`up = (0,1,0)` ⇒ `right = (1,0,0)`。因此在 Blockbench 坐标里：
  - **模型自己的 RIGHT = `+X`**，**LEFT = `-X`**，`front_axis = -z`，`back_axis = +z`，`up_axis = +y`。
  - `side_index = 0`（区分左右的坐标分量下标），`side_sign = 1`（>0 表示模型右侧）。
- 左右判定带宽：`sideOfCoord(coord, eps)`，`eps` 默认 **0.35**；`> +0.35` 为 right，`< -0.35` 为 left，中间为 `center`。
- 名字识别左右（`SIDE_WORDS`）：right = `right/rght/rgt/rt/r`；left = `left/lft/lt/l`。名字能拆成 token（`armUpper_L2` → `arm`,`upper`,`l`,`2`）后再比对；一个名字同时命中左右时视为模糊（返回 `null`）。
- `orientationReport().rules` 原文：
```
ANATOMY (character's own left/right, which is what "put the sword in his right hand" means):
  the model's RIGHT side is at +x (X > 0), its LEFT side at -x.
  So a right hand/arm/leg/horn belongs at X > 0 and must be named *_right.
SCREENSHOTS LIE ABOUT SIDES: in a FRONT view (looking at the face) you see the model
  mirrored, like facing a person — its RIGHT hand appears on the LEFT of the image.
  In a BACK view its right hand appears on the right of the image. Never decide a side
  from a render: use these axes, check_sides, or the label printed on every screenshot.
ROTATION SIGNS: +X rotation turns a bone so its FRONT face goes UP. Therefore a bone
  that points DOWN (arm, leg) swings its tip FORWARD (-z) with +X, and a bone that
  points UP (torso, neck, head) tips BACKWARD with +X. +Y rotation turns the model
  toward its own LEFT. +Z rotation tips the top of a bone toward the model's LEFT.
EXPORT: Blockbench mirrors X when writing Bedrock/GeckoLib/Java files, so a bone you
  place at +x here is written out at -x in the .json — that is correct and
  matches vanilla (Bedrock "rightArm" pivot is x = -5).
```
  （上面是把运行时插值填好后的形态；源码模板里轴值来自 `o.right_axis` / `o.left_axis` / `o.front_axis`，非默认朝向下文本会不同。）

- 源码注释给出的验证依据：Minecraft 模型朝 `north = -Z`；Blockbench 读写 Bedrock/Java 时镜像 X（bedrock codec `origin[0] *= -1`、`from[0] = -(from[0]+size[0])`；modded-entity export `c[0] *= -1`），所以原生 `rightArm` 在 Bedrock 里存为 `x = -5`，在 Blockbench 里位于 `+5`。
- `side` 参数与坐标冲突时**硬失败**（`assertSide`），名字与几何不符时返回 `warning`（不失败）。**所以左右不可能被"不小心"建反。**
- `unmarked_off_centre_bones`：离中线 >1.5 且名字没写左右的骨骼会被列出来提示改名。

### 5.2 pivot / origin 语义

- `Group.origin` 是**骨骼的旋转中心**，必须落在真实关节上：`arm_upper` 放肩膀、`arm_lower` 放肘、`hand` 放腕、腿的髋/膝/踝同理。原点落在肢体中段会让它原地打转 —— `check_rig` 报 `origin_not_at_joint`（判定：该段子方块 Y 跨度 >2 且原点落在跨度中间 30% 内）。
- `Cube.origin` 默认等于 `from`；`add_cube` / `add_cubes` 支持显式 `origin`。
- 生成器（`generate_array` / `voxelize_matrix` / `extrude_chain` 等）里 `origin` 决定旋转参考点；`anchor`（`center`/`top`/`bottom`/`min`）决定 `point` 对应方块的哪个角。
- 参考骨架的 canonical 空间：**+x = 模型 RIGHT，+y = UP，-z = FRONT**，最后经 `rigFrame()` 映射到当前工程实际轴线（`point()` 做轴映射，`rot()` 把 canonical `[rx,ry,rz]` 映射到世界轴）。

### 5.3 rotation 单位与轴序

- 单位是**角度（degrees）**，不是弧度（`eulerToMat` 内部 `/180*Math.PI`；关键帧值也是度）。
- Blockbench（three.js）用 **XYZ 顺序**合成欧拉角：`R = Rx·Ry·Rz`（源码注释原文：「Blockbench (three.js) composes Euler angles in XYZ order: R = Rx·Ry·Rz」）。
- 一次只在**一个轴**上旋转方块才干净；复合角度要放进组里旋转组或嵌套组（`MODELING_GUIDE` 第 3 条原文：`A single cube rotates cleanly on ONE axis; for a compound angle put it in a GROUP and rotate the group, or nest groups.`）。
- 镜像时的旋转处理（`mirror_element`）：镜像轴**之外**的两个旋转分量取反。

### 5.4 面名映射（源码 `AXIS_TO_FACE` / `normalizeFaceName`）

Blockbench 的面方向是**世界相对**的：`north = -Z`、`south = +Z`、`east = +X`、`west = -X`、`up = +Y`、`down = -Y`。
`add_hollow_volume.open_faces` 等参数接受模型相对词，映射为：

| 你写的 | 等价面 |
| --- | --- |
| `front` | `AXIS_TO_FACE[front_axis]`（默认 `-z` → `north`） |
| `back` | 默认 `+z` → `south` |
| `right` | 默认 `+x` → `east` |
| `left` | 默认 `-x` → `west` |
| `top` | `up` |
| `bottom` | `down` |
| `+x`/`-x`/`+y`/`-y`/`+z`/`-z` | `east`/`west`/`up`/`down`/`south`/`north` |
| `north/south/east/west/up/down` | 原样 |

其它值报 `Unknown face "<name>". Use north/south/east/west/up/down, or the model-relative words front/back/left/right/top/bottom.`

### 5.5 voxelize_matrix 的平面映射（源码 `VOXEL_PLANES`）

| `plane` | u（列方向） | v（行方向，第一行在最高 v） | d（厚度/挤出轴） | 源码 note |
| --- | --- | --- | --- | --- |
| `xy` | `+X` | 向下 `-Y` | `+Z` | `columns -> +X, rows descend -Y, depth along +Z (front view)` |
| `xz` | `+X` | 向下 `-Z`（第一行在最后面） | `+Y` | `columns -> +X, rows descend -Z (first row at the back), depth along +Y (top view)` |
| `yz` | `+Z`（第 0 列在模型正面） | 向下 `-Y` | `+X` | `columns -> +Z (column 0 at the model's front), rows descend -Y, depth along +X (side view)` |

### 5.6 相机视角命名（模型视角）

视角名以**模型自身**为参照（源码注释：Blockbench 自带预设是世界轴名，旧回退会让 "front" 拍到模型的背面）：

| 类别 | 可用名 |
| --- | --- |
| 模型相对 | `front`、`face`、`head_on`、`front_view`、`back`、`behind`、`rear`、`tail`、`left`、`left_side`、`model_left`、`right`、`right_side`、`model_right`、`top`、`up`、`bottom`、`down` |
| 四分之三 | `iso`、`isometric`、`front_right`、`isometric_front_right`、`isometric_right_front`、`front_left`、`isometric_front_left`、`isometric_left_front`、`back_right`、`isometric_back_right`、`back_left`、`isometric_back_left` |
| 世界轴 | `+x`、`-x`、`+y`、`-y`、`+z`、`-z`、`east`、`west`、`south`、`north` |

- `front` 是「看着它的脸」，`left` 是「看着它左臂所在的那一侧」。
- 每张截图/每个 shot 都会带 `looking_at` 与 `model_right_on`（`image_right` / `image_left` / `edge_on`），前端视图下模型自己的右侧出现在**图像左侧**（镜像）。
- 相机距离：`dist = size * 2.2 + 12`（`applyAngleName`，`size` 为模型最大跨度）。

### 5.7 GeckoLib / Bedrock 对方块与骨骼的要求（源码原话）

- `MODELING_GUIDE` 结尾：
  `Animation formats (GeckoLib/Bedrock): every cube must live under a bone; bone origins must sit at the real joint; limbs need 3 segments so elbows and knees can bend (create_rig does all of this). GeckoLib store id "geckolib", format "geckolib_model". Meshes do NOT export to GeckoLib/Java — use rotated cubes there.`
- `RIGGING_GUIDE`：`PARENTING: in animated formats every cube must live under a bone.` 前臂方块要放在 `arm_lower` 下而不是 `arm_upper`，否则弯肘会把网格撕开。
- `add_mesh` 注释：`Requires a mesh-capable format (free/generic/bedrock); GeckoLib/Java export cubes only, so for those build crystals from rotated cubes instead.`
- `add_mesh` 运行时报错：`Meshes are not available in this Blockbench build.` / `Current format does not support meshes. Use a free/generic project, or build the shape from rotated cubes.`
- `extrude_chain` 无骨骼时 warn：`This is an animated format and the chain has no bones. Pass create_bones:true unless the chain is meant to be rigid.`；note 里补：`Some formats (java_block) only allow one rotation axis per cube — use create_bones:true there.`
- `create_rig` 返回的 `next_steps[0]`：`The skeleton is built with the model's RIGHT on <right_axis> — keep it that way.`
- 导出镜像：这里放在 `+X` 的骨骼在 Bedrock/GeckoLib/Java 文件里会写成 `x = -5` 这类负值，**这是正确的，不要去"修"**。

---

## 6. 动画关键帧数据格式

### 6.1 通道与字段

写入路径：`add_keyframe` / `add_keyframes` / `generate_animation` 最终都走 `putKeyframes()` → `animator.addKeyframe({channel, time, interpolation, data_points:[{x,y,z}]})`。

| 字段 | 类型 | 必填 | 默认 | 含义 |
| --- | --- | --- | --- | --- |
| `bone` | string | 是 | — | 骨骼（组）名，按 name 或 uuid 查（`findGroup`） |
| `channel` | string | 否 | `'rotation'` | 通道名。生成器只产出三种：`rotation`、`position`、`scale` |
| `time` | number | 否 | `0` | **秒**（不是帧）；`Number(k.time) \|\| 0` |
| `value` | [x,y,z] | 否 | `[0,0,0]` | 三分量；写入时变成 `data_points:[{x,y,z}]` |
| `interpolation` | string | 否 | `'linear'` | 生成器内部用 `catmullrom`（旋转/位移/缩放默认）、`linear`（急促撞击）、`step`（瞬时切换） |

- 动画长度：`length`（秒）。`add_keyframe` 会把长度扩到该帧时间；`add_keyframes` 取 `max(原长度, 各帧 time, 指定 length)`。
- 循环：`loop` 取值 `loop` / `once` / `hold`（生成器默认：`idle/walk/run/fly` → `loop`，`attack/cast/jump/hurt` → `once`，`death` → `hold`）。
- 平滑/闭合：`add_keyframes {close_loop:true}` 会把每个「骨骼+通道」在 `t≈0` 的姿势复制到 `t=length`（返回 `loop_keyframes_added` 告知补了几条）。
- 姿势是否闭合还会被 `analyze_animation` 量化：`motion[slot].loop_gap > 0.4` 时报 `loop_not_closed`，提示「The pose at the end does not match the pose at t=0, so the loop will pop. Duplicate the t=0 keyframes at t=length.」
- 全线性会被判为机械感：`>4` 帧且全部 `linear` 时报 `all_linear`（`Use catmullrom for swings and settles; keep linear only for snappy impacts.`）。
- 循环动画里某个骨骼 <3 帧时报 `too_few_keyframes`（`A cycle needs at least 4-8 keyframes per moving bone; 2 gives a linear back-and-forth.`）。
- **位置与旋转的量纲**：`position` 的单位与模型坐标一致（`frame.point()` 会把 canonical 偏移映射到世界轴），`rotation` 单位是度，`scale` 是倍率（`[1,1,1]` = 原大小）。VFX 里用「缩到 0」代替透明度（源码：`GeckoLib has no opacity channel`）。
- 通道是否被某个格式支持由 Blockbench 的 bone animator 决定：`Cannot animate bone in this animation scope: <bone>` 表示该骨架/动画作用域不接受这个骨骼（源码未展开说明具体限制）。

### 6.2 完整示例（3 根骨骼、多个时间点）

```json
{
  "action": "add_keyframes",
  "params": {
    "animation": "animation.zombie.walk",
    "length": 1.0,
    "close_loop": true,
    "keyframes": [
      {"bone":"leg_upper_right","channel":"rotation","time":0,    "value":[26,0,0],   "interpolation":"catmullrom"},
      {"bone":"leg_upper_right","channel":"rotation","time":0.25, "value":[0,0,0],    "interpolation":"catmullrom"},
      {"bone":"leg_upper_right","channel":"rotation","time":0.5,  "value":[-26,0,0],  "interpolation":"catmullrom"},
      {"bone":"leg_upper_right","channel":"rotation","time":0.75, "value":[0,0,0],    "interpolation":"catmullrom"},

      {"bone":"leg_lower_right","channel":"rotation","time":0,    "value":[-5,0,0],   "interpolation":"catmullrom"},
      {"bone":"leg_lower_right","channel":"rotation","time":0.25, "value":[-7,0,0],   "interpolation":"catmullrom"},
      {"bone":"leg_lower_right","channel":"rotation","time":0.5,  "value":[-32,0,0],  "interpolation":"catmullrom"},
      {"bone":"leg_lower_right","channel":"rotation","time":0.75, "value":[-52,0,0],  "interpolation":"catmullrom"},

      {"bone":"arm_upper_left","channel":"rotation","time":0,     "value":[22,0,0],   "interpolation":"catmullrom"},
      {"bone":"arm_upper_left","channel":"rotation","time":0.5,   "value":[-22,0,0],  "interpolation":"catmullrom"},

      {"bone":"hips","channel":"position","time":0,              "value":[0,0,0],    "interpolation":"catmullrom"},
      {"bone":"hips","channel":"position","time":0.25,           "value":[0,0.45,0], "interpolation":"catmullrom"},
      {"bone":"hips","channel":"position","time":0.5,            "value":[0,0,0],    "interpolation":"catmullrom"},
      {"bone":"hips","channel":"position","time":0.75,           "value":[0,0.45,0], "interpolation":"catmullrom"},

      {"bone":"chest","channel":"rotation","time":0,             "value":[0,4,0],    "interpolation":"catmullrom"},
      {"bone":"chest","channel":"rotation","time":0.5,           "value":[0,-4,0],   "interpolation":"catmullrom"},

      {"bone":"hand_right","channel":"scale","time":0,           "value":[1,1,1],    "interpolation":"catmullrom"},
      {"bone":"hand_right","channel":"scale","time":0.5,         "value":[1.1,1.1,1.1],"interpolation":"catmullrom"}
    ]
  },
  "id": 30
}
```

（`close_loop:true` 会自动把上面每个骨骼+通道在 `t=0` 的值复制到 `t=1.0`。）

返回形态：

```json
{"ok":true,"id":30,"result":{
  "created":18,"loop_keyframes_added":6,
  "keyframes":[{"uuid":"...","bone":"leg_upper_right","channel":"rotation","time":0}],
  "animation":{"uuid":"...","name":"animation.zombie.walk","loop":"loop","length":1,
              "snapping":0,"bones":[{"name":"leg_upper_right","uuid":"...","keyframe_count":5}]},
  "reminder":"Now run analyze_animation — it measures where the limbs really travel and catches motion that goes the wrong way."
}}
```

生成器产出（`generate_animation`）的写法与上面一致：旋转走 `channel:'rotation'`（`K.rot`）、位移走 `channel:'position'`（`K.pos`）、缩放走 `channel:'scale'`（`K.scale`），canonical 角度再经 `frame.rot()` 映射到实际轴；默认插值为 `catmullrom`。

---

## 7. 常见坑与注意事项（源码明确写到的）

**协议 / 运行环境**

1. 服务只绑 `127.0.0.1`，端口默认 `8787`（设置项 `blockbench_mcp_port`）。
2. `Host` 头必须是 `127.0.0.1` / `localhost` / `[::1]`（忽略端口），否则 `403 Host must be 127.0.0.1 or localhost`。
3. 带 `Origin` 头一律拒绝（`403 Browser requests are not accepted by the BlockbenchMCP bridge`）；POST 必须 `Content-Type: application/json`，否则 `415`。
4. body 累计超过 **96 MB** 会直接断连（截图/贴图 base64 很大，注意别一次要太多张）。
5. 默认 socket 空闲超时 120 s；长任务动作延长到 300 s；`request_review`/`ask_user`/`wait_review` 用 `max(120s, (wait_seconds+45)s)`。
6. `request_review` / `ask_user` / `wait_review` 单次等待上限 120 s（默认 25 s），卡片存活 5–3600 s（默认 900 s）。**超时/未答 ≠ 通过**：未答返回 `verdict:"waiting"`，源码 note 明确 "This is NOT approval; do not continue as if it were."
7. 命令抛错仍返回 HTTP 200 + `ok:false`，客户端必须检查 `ok` 而不是只看状态码。
8. 未开工程时绝大多数命令报 `No project is open. Create one first with new_project.`（`ping`、`get_status`、`list_formats`、`get_guide`、参考图相关命令不需要工程）。
9. `execute_script` 受设置项 `blockbench_mcp_allow_scripts`（UI「Allow execute_script」）控制，关掉后报 `execute_script is disabled in Blockbench settings ("Allow execute_script"). Use the dedicated tools, or ask the user to enable it.`；开启后等于允许任意 JS 在 Blockbench 里跑（源码描述里提到 prompt injection 风险）。
10. 桌面版专用（`isApp`）才会成功的路径：`export_model`、`load_project`、`import_texture`、`save_project{p:path}`、`install_plugin{p:path}`、`load_reference{p:path}`；否则 `This action is only available in the Blockbench desktop app.`

**几何 / z-fighting（源码多处强调）**

11. z-fighting 来自两个面**共面**：重叠方块要让其中一个明确**穿透**另一个 ≥0.1（理想 ~0.5）；装饰件彼此错开 0.05–0.2；两片 billboard 平面不许同位置（≥0.1 偏移）。
12. `check_model` 会给 `coplanar_overlap`，必须逐条修掉；生成器会自己报 `z_fight_pairs` / `z_fight_hint`（`depth_stagger` 只能隔一个元素错开，i 与 i+2 仍同深度；同高度元素共享上下平面）。
13. `generate_array` 的 `depth_stagger:0` 且相邻重叠会附 `hint` 提醒；`add_hollow_volume` 的六面墙彼此不重叠所以不会互相 z-fight，但空腔内的东西要与墙保持 ≥0.1 间隙；`add_wing` 每片膜/骨都有独立厚度避免共面；`extrude_chain` 首段要插进基座 ≥0.1。
14. 生成器统一上限 `MAX_GENERATED = 1500` 个方块（可用 `max_cubes` 覆盖）；`voxelize_matrix` 矩阵上限 20000 格；`extrude_chain` 段数上限 64；`add_wing` 指骨 1–6；`tail_segments` 0–6；`arm_segments`/`leg_segments` 夹在 2–3；`spine_segments` 1–3。
15. 动画格式下每个方块都必须挂在骨骼下（`check_model` 报 `no_bone_parent`，`check_rig` 报 `cubes_without_bone`）。
16. 肢体必须至少 3 段（上/下/末端），否则没有肘/膝，`check_rig` 直接阻断（`limb_too_few_segments`）。
17. 骨骼原点必须在关节上，否则原地打转（`origin_not_at_joint`）。
18. `add_mesh` 需要支持 mesh 的格式；**mesh 不会导出到 GeckoLib/Java**，这些格式用旋转 45° 的方块代替。`add_wing` 的 mesh 膜同理，非 mesh 格式要用 `membrane:"cubes"`。
19. `add_plane` / VFX 平面要在贴图上开 `render_sides:"double"`，否则另一面看不见；自发光/叠加用 `render_mode:"emissive"|"additive"`。
20. 镜像：`mirror_element` 会把轴外两个旋转分量取反、名字里 `left`→`right`/`_l`→`_r`，名字没有左右时加 `_m`；**翅膀等要"重建另一侧"而不是镜像**（`add_wing` 明确要求）。
21. `add_groups` / `add_cubes` 会**先整批校验再创建**（说明：半个骨架比没有更糟），所以一个参数写错就整批失败。
22. 一个方块一次只在一个轴上旋转才干净；复合角度用组（`MODELING_GUIDE` 3）。
23. `java_block` 每个方块只允许一个旋转轴，链条要用 `create_bones:true`。

**纹理 / UV**

24. box UV 模型**必须先 `pack_uv`**（新建 box UV 方块默认都在 `uv_offset [0,0]`，共用同一片像素），加/改方块后要重跑；`pack_uv` 会在排版超出时自动按 2 倍加高贴图并保留已画内容。
25. 顺序必须是 `pack_uv → create_texture → detail_cubes → paint_faces`：`paint_faces` 在模糊之后再画，否则会被抹掉。
26. `detail_cubes` 默认 `edge_darken:0`（描边会像脏网格），`noise` 保持 0.04–0.08；自发光件名字用 `*_core` / `*_glow`（或自定义 `glow_regex`）。
27. `create_texture` 是异步等图片 load 完成才返回（内部 400 ms 兜底），所以别在它返回前就 `paint_texture`（源码注释：否则画布还是默认 16x16，绘制会被裁剪/损坏）。
28. `paint_faces` 的坐标是**面内相对坐标**（`[0,0]` = 该面 UV 矩形左上角）；`paint_texture` 的坐标是**贴图绝对像素**，两者别混。
29. `check_model` 会报 `no_texture`、`zero_uv`、`uv_out_of_bounds`（UV 超出贴图尺寸），出图前先跑一遍。

**建模规范（来自 playbook 原文）**

30. 剪影优先，`compare_reference` 的 `match_percent` 要到 **85+**（hero 资产 90+）才进贴图流程；目标是把叠加图里的红/蓝压到 0。
31. `audit_complexity` 的 `too_primitive` 是硬门槛：humanoid 低于 ~70 方块是草稿，**不许进贴图**；`ready_for_texturing:false` 时不要继续贴图。
32. 分层：Layer 2 要高出 Layer 1 **0.3–0.8** 单位；Layer 3/4 用 `generate_array` / `voxelize_matrix` / `extrude_chain` 批量产出，别手算几百个 `[from,to]`。
33. 每个用户可见里程碑都要 `request_review` 并等回答；没回答要在对话里说明，**绝不能把沉默当通过**；自己看自己的渲染不是验证。

---

## 8. 附：参数通用的强制校验一览（照抄报错）

| 触发条件 | 报错文本 |
| --- | --- |
| `side` 不是 left/right | `side must be "left" or "right", got "<v>"` |
| `side` 与坐标矛盾 | `<what> "<name>" is declared side:"<s>" but sits at <轴>=<坐标>, which is the model's <RIGHT\|LEFT\|CENTRE>. The model faces <front>, so its <s> side is <轴>. Move it to <轴> (flip the sign of that coordinate) or change side/name.` |
| 父级找不到（`resolveParent`） | `Parent group not found: "<ref>". Use list_outliner to see the bones, or omit \`parent\` to build at the model root.` |
| 父级找不到（`add_group`/`add_cube`/`add_plane`/`add_mesh`） | `Parent group not found: <ref>` |
| 生成数量超上限 | `<what> would create <n> cubes, over the <cap> safety cap. Split it into several calls, raise pixel_size / element size, or lower the count.` |
| 生成数量 ≤0 | `<what> would create no geometry — check the parameters.` |
| 元素找不到 | `Element not found: <ref>` / `Cube not found: <ref>` |
| 骨骼找不到 | `Bone (group) not found: <ref>`（或批量时逗号分隔的列表） |
| 纹理找不到 | `Texture not found: <ref>` |
| 动画找不到 | `Animation not found: <ref>` |
| 无工程 | `No project is open. Create one first with new_project.` |
| 非桌面版 | `This action is only available in the Blockbench desktop app.` |
| 未知命令 | `Unknown command: <action>` |
| 未知面名 | `Unknown face "<name>". Use north/south/east/west/up/down, or the model-relative words front/back/left/right/top/bottom.` |
| 未知锚点 | `Unknown anchor "<anchor>". Use 'center', 'top', 'bottom' or 'min'.` |
| 未知 paint op | `Unknown paint op: <type>` |
| 格式无动画 | `Animations are not supported in this format.` |
| 格式无导出 codec | `Current format has no export codec.` |

字段名与上述一致的其它校验请见第 3 节各命令条目。


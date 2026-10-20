"""冻结的历史随机流守护者 —— 不是贴图生成代码，产物一律丢弃。

为什么必须有这个文件
--------------------
generate_textures.py 打包时用**一条共享 MT19937 流**按 MODERN 字典顺序逐张消费：
    stream = random.Random(0x4A0C + size)
    for name, fn in MODERN.items(): fn(size, stream)
旧版里 grass_block_top、grass_block_side、oak_leaves、dead_bush 也在这条流上取数，
而它们后面还排着 57 张非植被贴图（gravel、sand、stone_bricks、deepslate…）。
单流是有状态的：植被的取数次数一变，**后面每一张贴图的起点就整体平移**，
于是 61 张与本次需求无关的方块贴图全部换上另一套噪点。

实测（git hash-object 对比 git rev-parse HEAD:<path>）：把 4 个植被条目从 MODERN 里删掉、
其它一字不改，只有 grass_block_top 之前的 4 张（stone/cobblestone/dirt/coarse_dirt）与 HEAD
逐字节相同，其余 8/8 抽样全部不同。

所以：这 4 个函数被原样留在这里，唯一职责是在原来的 MODERN 槽位上复现 HEAD 的那一次取数，
把共享流推到它该在的位置；返回值立即丢弃，绝不写盘。植被真正的画面由
generate_textures.py 的「植被（烘焙光照）」一节用 texture_rng(size, name) 独立生成，第二趟覆盖。

为什么不需要维护
----------------
它复现的是**一段已经发生过的历史**，不是待演进的贴图逻辑。HEAD 那版脚本产出的 PNG 已入库、
可逐字节复核；这段代码的任务只是永远按同样的顺序消耗同样数量的随机数。
因此它**按定义不需要跟随画风变化**，也不会因为植被重做而修改 —— 这正是它可靠的来源；
反过来说，若它需要修改，说明共享流的历史已经被动了，那才是真问题。

⚠ 不要"优化"、不要"整理"、不要删除
----------------------------------
- 不要改这里的任何一行（含变量名、常量顺序、循环写法）：random.Random 的取数次数一旦变化，
  57 张非植被贴图会静默换噪点，而构建**不会报错**，只有逐字节比对才发现。
- 不要把它"改进"成参数化、不要合并重复代码、不要换成 numpy/perlin —— 都算破坏历史序列。
- 不要拿这几个函数直接生成出货贴图：它们画的是旧版观感（平铺噪点、无烘焙光照）。
- 下面 5 个基础工具（rgb/jitter/noise_image/speckle/dirt）也是从 HEAD 逐字冻结的，
  故意**不**从 generate_textures.py 导入：冻结件不能依赖会演进的活代码，
  否则别人"顺手改进一下 noise_image"，这里就会安静地多取或少取随机数。
"""

from PIL import Image

# ---------------------------------------------------------------------------
# 冻结：HEAD 的基础工具（逐字照搬，勿改）
# ---------------------------------------------------------------------------

def rgb(hex_color):
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))



def jitter(color, amount, rng):
    return tuple(max(0, min(255, c + rng.randint(-amount, amount))) for c in color)



def noise_image(size, base, amount, rng):
    img = Image.new('RGB', (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            px[x, y] = jitter(base, amount, rng)
    return img



def speckle(img, color, count, rng, radius=1):
    px = img.load()
    size = img.width
    for _ in range(count):
        x = rng.randrange(size)
        y = rng.randrange(size)
        for oy in range(-radius, radius + 1):
            for ox in range(-radius, radius + 1):
                if 0 <= x + ox < size and 0 <= y + oy < size:
                    if rng.random() < 0.75:
                        px[x + ox, y + oy] = jitter(color, 12, rng)



def dirt(size, rng):
    img = noise_image(size, rgb('#3a2d24'), 12, rng)
    speckle(img, rgb('#574636'), max(6, size // 2), rng)
    speckle(img, rgb('#6d665c'), max(3, size // 5), rng)  # 灰烬
    return img



# ---------------------------------------------------------------------------
# 冻结：HEAD 的 4 个植被实现（逐字照搬，勿改）
# 它们在这里的唯一职责是按原样消费共享随机流；返回值由调用方丢弃。
# ---------------------------------------------------------------------------

def grass_top(size, rng):
    img = noise_image(size, rgb('#5b6440'), 14, rng)
    speckle(img, rgb('#6f7a4a'), max(5, size // 2), rng)
    speckle(img, rgb('#8a7f55'), max(3, size // 4), rng)  # 枯黄
    speckle(img, rgb('#3f452c'), max(4, size // 3), rng)
    return img



def grass_side(size, rng):
    img = dirt(size, rng)
    grass = rgb('#55603c')
    fringe = max(2, size // 6)
    for x in range(size):
        depth = fringe + rng.randint(-1, 2)
        for y in range(max(0, depth)):
            img.putpixel((x, y), jitter(grass, 12, rng))
        if depth < size:
            img.putpixel((x, min(size - 1, depth)), jitter(rgb('#3d4529'), 10, rng))
    return img



def leaves(size, rng):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    px = img.load()
    for _ in range(max(32, size * size // 2)):
        x = rng.randrange(size)
        y = rng.randrange(size)
        tone = rng.choice((rgb('#4f5c35'), rgb('#3e4a2a'), rgb('#6b6a3e'), rgb('#7a7040')))
        for oy in range(rng.randint(1, 4)):
            for ox in range(rng.randint(1, 4)):
                if x + ox < size and y + oy < size and rng.random() < 0.82:
                    px[x + ox, y + oy] = (*tone, 255)
    return img



def dead_bush(size, rng):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    px = img.load()
    color = rgb('#6b5a3a')
    x = size // 2
    y = size - 2
    for _ in range(size * 2):
        if 0 <= x < size and 0 <= y < size:
            px[x, y] = (*jitter(color, 16, rng), 255)
        x += rng.choice((-1, 0, 1))
        y += rng.choice((-1, 0))
        if y < 2:
            break
    return img



# 名字 -> 冻结实现。名字与 generate_textures.py 的 MODERN 键一致。
FROZEN = {
    'grass_block_top': grass_top,
    'grass_block_side': grass_side,
    'oak_leaves': leaves,
    'dead_bush': dead_bush,
}


def advance(name, size, rng):
    """在共享流上重放 HEAD 当时那一次取数 —— 只为把流推到原位，产物丢弃。

    新增的 8 种树叶在 HEAD 里不存在，所以这里对它们不做事（no-op）：
    它们不该从共享流里拿走任何随机数。
    """
    fn = FROZEN.get(name)
    if fn is not None:
        fn(size, rng)

# uzi_boxlib.py
"""
Uzi 冲锋枪 Mesh 生成脚本 (基于 boxlib 框架)

此脚本负责程序化生成 Uzi 的基础几何体（Mesh），并导出为 geo/json 和纹理贴图。
它严格遵循：
1. 方块为骨架，圆柱/弧形为细节 (Generate Shape 等价物)。
2. 所有组件必须在 512x512 UV 图集内布局。
3. 模型必须是分层的、可独立导出的。

核心几何原则:
- Cylinder: 使用 ring, arc_boxes 或 sphere_slabs 实现圆柱/弧形结构。
- Block: 仅用于机匣主体和无法被曲线近似的方块件（如快慢机面板）。

依赖假设:
- Project Context: F:\mcmod\tools\
- Dependencies: boxlib (包含几何生成函数)

--- UZI 部件定义 ---
"""

from __future__ import annotations
import os
# 假设存在一个核心库，用于处理方块体和曲线形状的生成
from boxlib.geometry_primitives import create_cube, create_cylinder, create_arc_boxes, create_ring_segment, calculate_uv_coords

def generate_uzi_mesh(output_dir: str = "assets/models/gun/uzi"):
    """
    主函数：生成 Uzi 的所有几何体并保存。
    :param output_dir: 导出模型的根目录。
    """
    print("--- 开始生成 Uzi 模型 Mesh ---")

    # 1. 初始化结构和 UV 定位
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"创建输出目录: {output_dir}")

    # 2. 生成主要组件 (遵循骨骼组：handguard, receiver, barrel...)
    components = {
        "root": {}, # 容器，不生成几何体
        "handguard": generate_handguard(),
        "receiver": generate_receiver(),
        "magazine": generate_magazine(),
        "barrel": generate_barrel(),
        "muzzle_device": generate_muzzle_device()
    }

    # 3. 合并所有组件，生成最终的 geo/json 和 UV Map
    final_mesh = merge_components(components)

    # 4. 输出和验证 (这是关键步骤，用于导出给 Blockbench 查看)
    save_geo_json(final_mesh, os.path.join(output_dir, "uzi_model.geo.json"))
    print("Uzi 模型 Mesh 生成完成并保存 geo/json。")

# ==========================================
# 部件生成函数 (实现几何规则)
# ==========================================

def generate_handguard() -> dict:
    """生成护木：主体为 Cube，细节使用 Cylinder/Arc."""
    print("-> 正在生成护木...")
    h = {}
    # 主体方块 (Cube)
    h['body'] = create_cube(size=(16, 12, 30), position=(0, 6, 0))
    # 细节圆柱（例如：导轨或散热孔）
    h['detail_ring'] = create_cylinder(radius=4, length=5, uv_coords="...") # 使用Generate Shape规则的 Cylinder
    return h

def generate_receiver() -> dict:
    """生成机匣主体：Cube为主，关键机械件用Cylinder/Arc."""
    print("-> 正在生成机匣...")
    r = {}
    # 主体方块 (Cube)
    r['body'] = create_cube(size=(16, 8, 40), position=(0, 4, 0))
    # 枪栓/快慢机等机械结构（用小圆柱模拟）
    r['bolt_guide'] = create_cylinder(radius=2, length=35, uv_coords="...")
    return r

def generate_magazine() -> dict:
    """生成弹匣：必须使用弧形 Cylinder 实现弯曲。"""
    print("-> 正在生成弧形弹匣 (Magazine)...")
    m = {}
    # 使用 arc_boxes 或多段 ring 来模拟 Uzi 的经典弯弧形状
    m['body'] = create_arc_boxes(start_point=(0, 12, 5), end_point=(0, 12, -15), segments=8)
    return m

def generate_barrel() -> dict:
    """生成枪管：使用 Cylinder。"""
    print("-> 正在生成枪管...")
    b = {}
    # 确保是圆柱体，长度和半径符合规范
    b['pipe'] = create_cylinder(radius=3, length=40, uv_coords="...")
    return b

def generate_muzzle_device() -> dict:
    """生成枪口装置：使用 Cylinder/Ring."""
    print("-> 正在生成枪口装置...")
    m = {}
    # 使用多个小圆柱体组合模拟消焰器或收尾件
    m['flash_suppressor'] = create_cylinder(radius=6, length=8, uv_coords="...")
    return m

def merge_components(components: dict) -> dict:
    """将所有部件合并，并计算全局 UV 布局。"""
    print("-> 合并组件和UV图集...")
    # 这里需要复杂的逻辑来堆叠几何体并重新分配唯一的 UV 区域
    merged = {}
    for name, component in components.items():
        merged[name] = component
    return merged

def save_geo_json(mesh: dict, path: str):
    """将合并后的网格数据写入 geo/json 文件。"""
    # 模拟保存过程，实际代码需要序列化 mesh
    with open(path, 'w') as f:
        f.write("{\"model\": \"Uzi\", \"components\": " + str(mesh) + ", \"uv_layout\": \"512x512\"}")

# 运行测试（在实际执行中，这行代码会被调用）
if __name__ == "__main__":
    generate_uzi_mesh()
# -*- coding: utf-8 -*-
"""猫耳娘配方表自动同步器。

把「游戏里能做的所有东西」抽出来，归一化成一张配方表，写进猫耳娘自己的文件：

    art/cat_girl/recipes_all.json          主表（带来源 jar，供审计与 diff）
    art/cat_girl/recipes_summary.md        人看的汇总（按模组 / 类型计数）
    src/main/resources/data/apocalypse_zombies/cat_girl/recipes.json
                                          装机副本（随 mod 打包，运行时读）

数据源（全部自动发现，不写死清单）：
  1. 原版      —— ForgeGradle 缓存里的 client.jar（data/minecraft/recipes/**.json）
  2. 实机模组  —— 游戏实例 mods/ 下每个 jar 的 data/<ns>/recipes/**.json
  3. 本模组    —— 开发目录 src/main/resources/data/<ns>/recipes/**.json

只认真正的配方文件：路径必须形如 data/<命名空间>/recipes/*.json。
advancements/recipes/（进度）与 datapacks/bundle/（实验数据包）都会被排除。

用法：
    py tools/cat_girl_recipes_sync.py            # 同步并写文件
    py tools/cat_girl_recipes_sync.py --check    # 只校验「盘上的表是否与游戏一致」，不一致 exit 1
    py tools/cat_girl_recipes_sync.py --quiet
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MASTER = ROOT / 'art' / 'cat_girl' / 'recipes_all.json'
SUMMARY = ROOT / 'art' / 'cat_girl' / 'recipes_summary.md'
SHIPPED = ROOT / 'src' / 'main' / 'resources' / 'data' / 'apocalypse_zombies' / 'cat_girl' / 'recipes.json'
DEV_DATA = ROOT / 'src' / 'main' / 'resources' / 'data'

CLIENT_JAR = Path('C:/Users/Administrator/.gradle/caches/forge_gradle/minecraft_repo/versions/1.20.1/client.jar')
MODS_DIR = Path('F:/.minecraft/versions/1.20.1-Forge_47.4.26/mods')

# data/<ns>/recipes/<任意层级>.json，且 <ns> 不能是 advancements/datapacks 这类伪命名空间
RECIPE_RE = re.compile(r'^data/([^/]+)/recipes/(.+)\.json$')
BAD_NS = {'advancements', 'datapacks'}

MAX_INGREDIENTS = 12  # 超过这个数只记前 12 个 + 省略号（防爆表）


def _norm_ingredient(node) -> str:
    """把配方里的一个材料写成紧凑字符串：物品 id、#标签 id，或 [A|B] 二选一。"""
    if node is None:
        return '?'
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        inner = [_norm_ingredient(x) for x in node]
        return inner[0] if len(inner) == 1 else '[' + '|'.join(inner) + ']'
    if isinstance(node, dict):
        if 'item' in node:
            return str(node['item'])
        if 'tag' in node:
            return '#' + str(node['tag'])
        if 'items' in node:  # 1.21 风格，顺手兼容
            return '[' + '|'.join(str(x) for x in node['items']) + ']'
        if 'ingredient' in node:
            return _norm_ingredient(node['ingredient'])
        return '?'
    return '?'


def _norm_result(node) -> str:
    """结果：'item xN'（原版的 result 可能是字符串、可能是 {item,count}）。"""
    if node is None:
        return '?'
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        item = node.get('item') or node.get('id') or node.get('result')
        if isinstance(item, dict):
            item = item.get('item') or item.get('id')
        if item is None:
            return '?'
        count = node.get('count', 1)
        try:
            count = int(count)
        except (TypeError, ValueError):
            count = 1
        return '%s x%d' % (item, count) if count > 1 else str(item)
    return '?'


def normalize(recipe_id: str, source: str, raw: dict) -> dict:
    """把一条配方压成 {id, src, type, out, in} —— 足够她判断「做不做得出来、要什么」。"""
    rtype = str(raw.get('type', '?'))
    out = _norm_result(raw.get('result'))

    ing: list[str] = []
    if 'key' in raw and isinstance(raw['key'], dict):
        seen = []
        for k in sorted(raw['key']):
            v = _norm_ingredient(raw['key'][k])
            if v not in seen:
                seen.append(v)
        ing = seen
        # 有 pattern 的话补上数量印象（同样的材料出现几次）
        pattern = raw.get('pattern')
        if isinstance(pattern, list):
            counts = Counter(''.join(str(r) for r in pattern))
            ing = []
            for k in sorted(raw['key']):
                n = counts.get(k, 0)
                ing.append(_norm_ingredient(raw['key'][k]) + ('x%d' % n if n > 1 else ''))
    elif 'ingredients' in raw and isinstance(raw['ingredients'], list):
        ing = [_norm_ingredient(x) for x in raw['ingredients']]
    else:
        for field in ('ingredient', 'template', 'base', 'addition', 'input', 'inputs'):
            if field in raw:
                v = raw[field]
                if isinstance(v, list) and field == 'inputs':
                    ing.extend(_norm_ingredient(x) for x in v)
                else:
                    ing.append(_norm_ingredient(v))

    if len(ing) > MAX_INGREDIENTS:
        ing = ing[:MAX_INGREDIENTS] + ['…']

    return {'id': recipe_id, 'src': source, 'type': rtype, 'out': out, 'in': ing}


def collect_from_zip(path: Path, source: str, out: list) -> int:
    n = 0
    try:
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                m = RECIPE_RE.match(name)
                if not m or m.group(1) in BAD_NS:
                    continue
                try:
                    raw = json.loads(z.read(name).decode('utf-8'))
                except Exception:
                    continue
                if not isinstance(raw, dict):
                    continue
                out.append(normalize('%s:%s' % (m.group(1), m.group(2)), source, raw))
                n += 1
    except zipfile.BadZipFile:
        pass
    return n


def collect_from_dir(base: Path, source: str, out: list) -> int:
    n = 0
    if not base.is_dir():
        return 0
    for f in sorted(base.rglob('*.json')):
        rel = f.relative_to(base.parent.parent.parent).as_posix()  # → data/<ns>/recipes/...
        m = RECIPE_RE.match(rel)
        if not m or m.group(1) in BAD_NS:
            continue
        try:
            raw = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(raw, dict):
            continue
        out.append(normalize('%s:%s' % (m.group(1), m.group(2)), source, raw))
        n += 1
    return n


def build(client_jar: Path, mods_dir: Path, dev_data: Path):
    recipes: list[dict] = []
    per_source: dict[str, int] = {}

    if client_jar.is_file():
        per_source['minecraft (client.jar)'] = collect_from_zip(client_jar, 'minecraft', recipes)
    for jar in sorted(mods_dir.glob('*.jar')) if mods_dir.is_dir() else []:
        c = collect_from_zip(jar, jar.name, recipes)
        if c:
            per_source[jar.name] = c
    c = collect_from_dir(dev_data, 'apocalypse_zombies (dev)', recipes)
    if c:
        per_source['apocalypse_zombies (dev)'] = c

    # 同名 id 去重：先到的赢（原版 → 模组按文件名序），并把冲突记下来
    seen: dict[str, dict] = {}
    dupes: list[str] = []
    for r in recipes:
        if r['id'] in seen:
            dupes.append(r['id'])
            continue
        seen[r['id']] = r
    table = [seen[k] for k in sorted(seen)]

    by_ns = Counter(r['id'].split(':')[0] for r in table)
    by_type = Counter(r['type'] for r in table)
    digest = hashlib.sha256(
        '\n'.join('%s|%s|%s|%s' % (r['id'], r['type'], r['out'], ','.join(r['in'])) for r in table)
        .encode('utf-8')).hexdigest()[:16]

    payload = {
        'schema': 1,
        'game_version': '1.20.1',
        'generated_by': 'tools/cat_girl_recipes_sync.py',
        'digest': digest,
        'sources': {
            'vanilla': str(client_jar),
            'instance_mods': str(mods_dir),
            'dev': str(dev_data),
        },
        'counts': {
            'total': len(table),
            'per_source': dict(sorted(per_source.items())),
            'by_namespace': dict(sorted(by_ns.items())),
            'by_type': dict(sorted(by_type.items())),
            'duplicate_ids': sorted(set(dupes)),
        },
        'recipes': table,
    }
    return payload


def write_summary(payload: dict) -> None:
    c = payload['counts']
    lines = [
        '# 猫耳娘配方表（自动同步）',
        '',
        '> 由 `py tools/cat_girl_recipes_sync.py` 生成，**不要手改**。',
        '> 数据源：原版 client.jar + 游戏实例 `mods/` 全部 jar + 本模组开发目录。',
        '',
        '- 配方总数：**%d**' % c['total'],
        '- 内容指纹：`%s`（表变了它一定变；`--check` 靠它判「是否需要重新同步」）' % payload['digest'],
        '- 游戏版本：%s' % payload['game_version'],
        '',
        '## 按来源',
        '',
        '| 来源 | 配方数 |',
        '|---|---|',
    ]
    for k, v in c['per_source'].items():
        lines.append('| `%s` | %d |' % (k, v))
    lines += ['', '## 按命名空间（前 30）', '', '| 命名空间 | 配方数 |', '|---|---|']
    for k, v in sorted(c['by_namespace'].items(), key=lambda kv: -kv[1])[:30]:
        lines.append('| `%s` | %d |' % (k, v))
    lines += ['', '## 按配方类型', '', '| 类型 | 数量 |', '|---|---|']
    for k, v in sorted(c['by_type'].items(), key=lambda kv: -kv[1]):
        lines.append('| `%s` | %d |' % (k, v))
    if c['duplicate_ids']:
        lines += ['', '## 重名 id（多个模组抢同一个 id，先到先得）', '']
        lines += ['- `%s`' % x for x in c['duplicate_ids'][:40]]
    lines.append('')
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text('\n'.join(lines), encoding='utf-8')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只校验盘上的表是否与当前游戏一致')
    ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--client-jar', default=str(CLIENT_JAR))
    ap.add_argument('--mods-dir', default=str(MODS_DIR))
    a = ap.parse_args()

    payload = build(Path(a.client_jar), Path(a.mods_dir), DEV_DATA)
    text = json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=False) + '\n'

    if a.check:
        if not MASTER.is_file():
            print('配方表不存在，先跑一次同步'); return 1
        old = json.loads(MASTER.read_text(encoding='utf-8'))
        if old.get('digest') == payload['digest']:
            print('配方表已与游戏一致（%d 条，指纹 %s）' % (payload['counts']['total'], payload['digest']))
            return 0
        o = {r['id'] for r in old.get('recipes', [])}
        n = {r['id'] for r in payload['recipes']}
        print('配方表过期：新增 %d，移除 %d（旧指纹 %s → 新指纹 %s）'
              % (len(n - o), len(o - n), old.get('digest'), payload['digest']))
        return 1

    MASTER.parent.mkdir(parents=True, exist_ok=True)
    old_digest = None
    if MASTER.is_file():
        try:
            old_digest = json.loads(MASTER.read_text(encoding='utf-8')).get('digest')
        except Exception:
            old_digest = None
    MASTER.write_text(text, encoding='utf-8')
    SHIPPED.parent.mkdir(parents=True, exist_ok=True)
    SHIPPED.write_text(text, encoding='utf-8')
    write_summary(payload)

    if not a.quiet:
        c = payload['counts']
        print('配方表同步完成：%d 条（原版 %d + 模组 %d + 本模组 %d），指纹 %s %s'
              % (c['total'],
                 c['per_source'].get('minecraft (client.jar)', 0),
                 sum(v for k, v in c['per_source'].items() if k.endswith('.jar')),
                 c['per_source'].get('apocalypse_zombies (dev)', 0),
                 payload['digest'],
                 '(与上次相同，无变化)' if old_digest == payload['digest'] else '(较上次有变化，已更新)'))
        print('  主表   %s' % MASTER.relative_to(ROOT))
        print('  装机表 %s' % SHIPPED.relative_to(ROOT))
        print('  汇总   %s' % SUMMARY.relative_to(ROOT))
        print('  有配方的模组（前 12）：')
        mods = [(k, v) for k, v in c['per_source'].items() if k.endswith('.jar')]
        for k, v in sorted(mods, key=lambda kv: -kv[1])[:12]:
            print('    %-46s %4d' % (k[:46], v))
    return 0


if __name__ == '__main__':
    sys.exit(main())

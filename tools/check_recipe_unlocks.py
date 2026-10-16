#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配方解锁门禁：本模组每一条配方都必须有「配方解锁进度」（advancement）覆盖。

为什么需要这条门禁（1.2.3 的教训）：世界开着 `doLimitedCrafting=true` 时，原版合成台
算产物前要过 `RecipeHolder.setRecipeUsed(Level, ServerPlayer, Recipe)` 这道闸 —— 配方不在
玩家的配方书里就直接丢弃产物。症状极具误导性：服务端能匹配、能装配，产物槽却恒空、点了
也取不出来。**配方没解锁 = 合成台用不了**，所以解锁文件和配方文件一样是必需品。

口径：扫 `data/apocalypse_zombies/recipes/**.json` 得到全部配方 id，在
`data/apocalypse_zombies/advancements/**.json` 的 `rewards.recipes` 里逐一核对。
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NS = 'apocalypse_zombies'
RECIPES = os.path.join(ROOT, 'src', 'main', 'resources', 'data', NS, 'recipes')
ADVANCEMENTS = os.path.join(ROOT, 'src', 'main', 'resources', 'data', NS, 'advancements')


def recipe_ids():
    ids = set()
    for p in glob.glob(os.path.join(RECIPES, '**', '*.json'), recursive=True):
        rel = os.path.relpath(p, RECIPES).replace('\\', '/')[:-len('.json')]
        ids.add(f'{NS}:{rel}')
    return ids


def unlocked_ids():
    ids = set()
    for p in glob.glob(os.path.join(ADVANCEMENTS, '**', '*.json'), recursive=True):
        with open(p, encoding='utf-8') as f:
            data = json.load(f)
        ids.update(data.get('rewards', {}).get('recipes', []))
    return ids


def main():
    recipes = recipe_ids()
    unlocked = unlocked_ids()
    missing = sorted(recipes - unlocked)
    extra = sorted(unlocked - recipes)
    print(f'配方 {len(recipes)} 条；解锁进度覆盖 {len(recipes & unlocked)} 条')
    if extra:
        # rewards 指向不存在的配方：运行期会被安全跳过，但多半是改名/删配方后的残留，提示一下。
        print('提示：解锁文件引用了不存在的配方 id（残留或改名）：')
        for e in extra:
            print('  ·', e)
    if missing:
        print('缺解锁进度（doLimitedCrafting 世界里这些配方将无法合成）：')
        for m in missing:
            print('  ✗', m)
        return 1
    print('OK：全部配方都有解锁进度。')
    return 0


if __name__ == '__main__':
    sys.exit(main())

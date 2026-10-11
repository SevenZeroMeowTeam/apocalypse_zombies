package com.apocalypse.zombies.registry;

import net.minecraft.tags.BlockTags;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.Tier;
import net.minecraft.world.item.crafting.Ingredient;
import net.minecraftforge.common.ForgeTier;

/**
 * 模组自己的工具材质档。
 *
 * <p>原版五档之间本来没有「铜」这一层：石（耐久 131 / 攻击 +1 / 石级挖掘）上去直接是铁
 * （250 / +2 / 铁级）。铜按玩家给的定位补齐中间那一格 —— <b>耐久比石高，武器伤害与石一样</b>，
 * 挖掘等级也照石（挖得动铁矿石，挖不动钻石）。</p>
 *
 * <p>参考原版 {@code Tiers}（1.20.1 的 uses / speed / attackDamageBonus / enchantmentValue）：
 * 木 59 / 2.0 / +0 / 15，石 131 / 4.0 / +1 / 5，铁 250 / 6.0 / +2 / 14，钻石 1561 / 8.0 / +3 / 10，
 * 下界合金 2031 / 9.0 / +4 / 15。铜取 200 / 5.0 / +1 / 12 —— 除攻击加成与石**齐平**（这是玩家
 * 点名要的）之外，其余每一项都落在石与铁之间。</p>
 */
public final class ModTiers {

    /**
     * 铜：石与铁之间的一档。
     *
     * <p>攻击加成写 {@code 1.0F}（同石）而不是 1.5 —— 剑的最终伤害是
     * {@code 1（基础）+ 3（剑自身）+ 攻击加成}，所以铜剑与石剑一样是 5 点，正是「武器伤害和石制
     * 一样」这条要求。耐久 200 则比石多出 69 次挖掘。</p>
     */
    public static final Tier COPPER = new ForgeTier(
            1,                              // 挖掘等级同石：挖得动铁矿石，挖不动钻石
            200,                            // 耐久：石 131 → 高，铁 250 → 低
            5.0F,                           // 效率：石 4.0 → 高，铁 6.0 → 低
            1.0F,                           // 攻击加成同石 ⇒ 铜剑伤害 == 石剑
            12,                             // 附魔性：石 5 → 高，铁 14 → 低
            BlockTags.NEEDS_STONE_TOOL,     // 与等级 1 配套：这一档能采的方块
            () -> Ingredient.of(Items.COPPER_INGOT));

    private ModTiers() {
    }
}

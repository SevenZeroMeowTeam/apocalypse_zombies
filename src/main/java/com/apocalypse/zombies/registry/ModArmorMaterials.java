package com.apocalypse.zombies.registry;

import com.apocalypse.zombies.ApocalypseZombies;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.item.ArmorItem;
import net.minecraft.world.item.ArmorMaterial;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.crafting.Ingredient;

/**
 * 模组自己的护甲材质。
 *
 * <p>铜甲按玩家给的定位落在<b>皮革与铁之间</b>：护甲值 2 / 4 / 3 / 1（合计 10）—— 皮革是 7，
 * 铁是 15。耐久系数取 11（皮革 5 / 铁 15），韧性 0（与铁、皮革同为 0，钻石才 2）。</p>
 *
 * <p>护甲值<b>按部位写明</b>而不是塞一个数组：原版 {@code ArmorMaterials} 的数组顺序在版本之间
 * 换过（1.20.1 起是 {@code makeArmorMap(boots, leggings, chestplate, helmet)}），写错一位就是
 * 「头盔给 1、靴子给 2」这种不报错只难看的 bug。这里直接用 {@code switch} 对着
 * {@link ArmorItem.Type} 写，没有顺序可言。</p>
 *
 * <p>{@link #getName()} 返回带命名空间的 {@code apocalypse_zombies:copper} —— 原版
 * {@code ArmorItem} 拿它拼穿戴贴图路径（{@code textures/models/armor/copper_layer_1.png} 与
 * {@code _layer_2.png}），所以这两个文件的名字必须与这里一致。</p>
 */
public enum ModArmorMaterials implements ArmorMaterial {

    /**
     * 铜甲。
     *
     * @see ModArmorMaterials 类注释里那两条原版对照
     */
    COPPER("copper", 11, 12, SoundEvents.ARMOR_EQUIP_IRON, 0.0F, 0.0F);

    private final String name;
    private final int durabilityMultiplier;
    private final int enchantmentValue;
    private final SoundEvent equipSound;
    private final float toughness;
    private final float knockbackResistance;
    private final Ingredient repairIngredient;

    ModArmorMaterials(String name, int durabilityMultiplier, int enchantmentValue,
                      SoundEvent equipSound, float toughness, float knockbackResistance) {
        this.name = ApocalypseZombies.MOD_ID + ":" + name;
        this.durabilityMultiplier = durabilityMultiplier;
        this.enchantmentValue = enchantmentValue;
        this.equipSound = equipSound;
        this.toughness = toughness;
        this.knockbackResistance = knockbackResistance;
        this.repairIngredient = Ingredient.of(Items.COPPER_INGOT);
    }

    /**
     * 原版按部位给基础耐久（头 11 / 胸 16 / 腿 15 / 靴 13），再乘这一档的系数 —— 与
     * {@code ArmorMaterials.HEALTH_PER_SLOT} 是同一组数。
     *
     * <p>这里按 {@link ArmorItem.Type} 写明而不是调 {@code type.getDurability(multiplier)}：那个方法
     * 是 1.20.5 才加的，1.20.1 的 {@code Type} 上根本没有（写了就是「找不到符号」），原版自己是拿
     * 一个 private 数组按 ordinal 取的。</p>
     *
     * <p>系数 11 下的成品耐久：头 121 / 胸 176 / 腿 165 / 靴 143 —— 皮革（系数 5）是 55/80/75/65，
     * 铁（15）是 165/240/225/195，铜整档都落在两者之间。</p>
     */
    @Override
    public int getDurabilityForType(ArmorItem.Type type) {
        int base = switch (type) {
            case HELMET -> 11;
            case CHESTPLATE -> 16;
            case LEGGINGS -> 15;
            case BOOTS -> 13;
            default -> 0;
        };
        return base * this.durabilityMultiplier;
    }

    /** 护甲值：介于皮革（1/3/2/1）与铁（2/6/5/2）之间。 */
    @Override
    public int getDefenseForType(ArmorItem.Type type) {
        return switch (type) {
            case HELMET -> 2;
            case CHESTPLATE -> 4;
            case LEGGINGS -> 3;
            case BOOTS -> 1;
            default -> 0;
        };
    }

    @Override
    public int getEnchantmentValue() {
        return this.enchantmentValue;
    }

    /** 原版没有铜护甲的穿戴音（1.20.1 那会儿还没有铜甲），借铁的。 */
    @Override
    public SoundEvent getEquipSound() {
        return this.equipSound;
    }

    @Override
    public Ingredient getRepairIngredient() {
        return this.repairIngredient;
    }

    @Override
    public String getName() {
        return this.name;
    }

    @Override
    public float getToughness() {
        return this.toughness;
    }

    @Override
    public float getKnockbackResistance() {
        return this.knockbackResistance;
    }
}

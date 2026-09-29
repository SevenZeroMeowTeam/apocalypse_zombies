package com.apocalypse.zombies.item;

import com.apocalypse.zombies.registry.ModItems;
import com.apocalypse.zombies.registry.ModSounds;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.util.RandomSource;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraftforge.registries.RegistryObject;

/**
 * 一把枪在<b>怪物手里</b>的弹道表：与玩家版同源、不同款。
 *
 * <p>玩家那把是「眼睛射线 + 爆头 ×2 + 穿透 2~4」，那是给会瞄准的人准备的。怪物不会瞄准，
 * 也不该一把 AWM 隔着 200 格点死你，所以这里另立一张表：伤害取玩家版<b>近距离值的一半</b>、
 * <b>没有爆头倍率、没有穿透</b>，弹丸是看得见能躲的实体（{@link com.apocalypse.zombies.entity.BulletProjectile}），
 * 散布、冷却、换弹按枪给。两套口径分开之后，调玩家手感不会顺手改掉怪物强度，反之亦然。</p>
 *
 * <table>
 *   <caption>玩家版 → 怪物版</caption>
 *   <tr><th>枪</th><th>玩家近距离</th><th>怪物</th><th>射程</th><th>散布</th><th>冷却</th><th>换弹</th></tr>
 *   <tr><td>十字弩</td><td>12</td><td>6.0</td><td>32</td><td>3.0°</td><td>45t</td><td>55t</td></tr>
 *   <tr><td>莫辛纳甘</td><td>17</td><td>8.5</td><td>40</td><td>3.5°</td><td>40t</td><td>60t</td></tr>
 *   <tr><td>M1 加兰德</td><td>15</td><td>7.5</td><td>36</td><td>4.5°</td><td>25t</td><td>45t</td></tr>
 *   <tr><td>AWM</td><td>24</td><td>12.0</td><td>56</td><td>2.0°</td><td>70t</td><td>80t</td></tr>
 * </table>
 *
 * <p>这张表是<b>唯一来源</b>：召奬配枪、精英配枪、子弹装订都从这里取，别在别处再抄一份数字。</p>
 *
 * @param item       对应的物品，配枪时用
 * @param damage     每发伤害（玩家近距离值的一半，不含爆头与穿透）
 * @param range      有效射程（超过就不开火，但仍会靠拢）
 * @param spread     散布半角（度）
 * @param cooldownTicks 两发之间的最小间隔
 * @param reloadTicks   打空后的换弹停顿
 * @param bulletSpeed   弹速（格 / tick）
 * @param damageTypePath {@code data/apocalypse_zombies/damage_type/} 下的文件名（不含扩展名）
 */
public record GunProfile(
        Item item,
        float damage,
        double range,
        float spread,
        int cooldownTicks,
        int reloadTicks,
        float bulletSpeed,
        String damageTypePath,
        RegistryObject<SoundEvent> shotSound,
        RegistryObject<SoundEvent> reloadSound) {

    /** 怪物伤害相对玩家近距离值的比例。改这一个数就能整体调强弱。 */
    public static final float MOB_DAMAGE_SCALE = 0.5F;

    /**
     * 枪械声音只有一套（TaCZ 的 AWM 录音，四把枪共用），所以四把枪的枪声都指这里。
     * 换弹声按机构挑：栓动听拉栓、加兰德听漏夹、弩听上弦。
     */
    public static final GunProfile CROSSBOW = new GunProfile(
            ModItems.CROSSBOW.get(), 6.0F, 32.0D, 3.0F, 45, 55, 3.0F,
            "crossbow_bullet", ModSounds.AWM_SHOOT_3P, ModSounds.AWM_RECHAMBER_IN);

    public static final GunProfile MOSIN = new GunProfile(
            ModItems.MOSIN_NAGANT.get(), 8.5F, 40.0D, 3.5F, 40, 60, 3.5F,
            "mosin_nagant_bullet", ModSounds.AWM_SHOOT_3P, ModSounds.AWM_RECHAMBER_END);

    public static final GunProfile GARAND = new GunProfile(
            ModItems.M1_GARAND.get(), 7.5F, 36.0D, 4.5F, 25, 45, 3.5F,
            "m1_garand_bullet", ModSounds.AWM_SHOOT_3P, ModSounds.AMMO_CLIP_POP);

    public static final GunProfile AWM = new GunProfile(
            ModItems.AWM.get(), 12.0F, 56.0D, 2.0F, 70, 80, 4.0F,
            "awm_bullet", ModSounds.AWM_SHOOT_3P, ModSounds.AWM_RECHAMBER_END);

    /** 手里这件东西是枪的话，给出它的怪物弹道；不是枪（或空手）返回 {@code null}。 */
    public static GunProfile of(ItemStack stack) {
        if (stack.isEmpty()) {
            return null;
        }
        Item held = stack.getItem();
        if (held == CROSSBOW.item) {
            return CROSSBOW;
        }
        if (held == MOSIN.item) {
            return MOSIN;
        }
        if (held == GARAND.item) {
            return GARAND;
        }
        if (held == AWM.item) {
            return AWM;
        }
        return null;
    }

    /**
     * 配枪抽签：短枪常见、长枪稀有。
     *
     * <p>用<b>枪管长度</b>做威胁分级是刻意的 —— 玩家不需要读名字，
     * 看到那根管子长就知道该先处理谁。</p>
     */
    public static GunProfile random(RandomSource random) {
        float roll = random.nextFloat();
        if (roll < 0.45F) {
            return CROSSBOW;
        }
        if (roll < 0.80F) {
            return MOSIN;
        }
        if (roll < 0.95F) {
            return GARAND;
        }
        return AWM;
    }

    /** 弹匣容量由枪自己说了算（{@link GunItem#magazineSize()}），这里不留第二份。 */
    public int magazineSize() {
        return this.item instanceof GunItem gun ? gun.magazineSize() : 0;
    }
}

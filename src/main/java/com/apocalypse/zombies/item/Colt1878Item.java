package com.apocalypse.zombies.item;

import java.util.Map;
import java.util.function.Consumer;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.renderer.Colt1878ItemRenderer;
import com.apocalypse.zombies.registry.ModSounds;
import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.client.renderer.BlockEntityWithoutLevelRenderer;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.world.damagesource.DamageType;
import net.minecraft.world.entity.HumanoidArm;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraftforge.client.extensions.common.IClientItemExtensions;
import net.minecraftforge.registries.RegistryObject;

/**
 * 柯尔特 1878 教练枪 —— 短管双管霰弹枪（Colt Model 1878 / 20 英寸教练枪）。
 *
 * <h2>为什么要继承 {@link S686Item}</h2>
 * 两把枪是同一类武器：折开式双管、两发弹膛、外露击锤、按枪管折开做换弹动画，连骨骼树都是同一套
 * （{@code move / body / barrel / forend / shell_upper / latch / hammer_l / trigger_*}）。S686Item 里
 * "怎么开火、怎么换弹、第一人称怎么握、换弹时手往哪放"这套逻辑与枪的型号无关，全是可覆盖的方法，
 * 所以直接继承、只覆盖这把自己要变的那几项 —— 而不是复制 952 行出来，让两边以后各修各的。
 *
 * <h2>它与 S686 的差别（全部由本类覆盖）</h2>
 * <ol>
 *   <li><b>几何与动画是另一套文件</b>（并排双管而非上下双管，全长 0.93 格 vs 1.22 格）——
 *       由 {@link Colt1878ItemRenderer} + {@code Colt1878GeoModel} 指定，这里只换渲染器。</li>
 *   <li><b>动作时长是另一套</b>：两段换弹刻意做慢（{@code reload_tactical} 3.0 s = 60 tick、
 *       {@code reload_empty} 3.6 s = 72 tick，S686 分别是 39 / 50 tick），举枪也更快（0.8 s vs 1.0 s）。
 *       这些数逐条等于本枪自己的 {@code colt_1878.animation.json} 里对应片段的长度，由
 *       {@link #actionLength} 报给基类 —— 动作锁多久、什么时候结算换弹、手什么时候动，全都跟着走。
 *       {@code tools/colt_1878_install.js} 与 {@code tools/check_gun_resources.py} 两道门禁
 *       把时长钉在动画文件上。</li>
 *   <li><b>音效时刻表是另一套</b>：机械音按本枪胶片的关键帧排（见 {@link #soundCuesFor}），
 *       照抄 S686 的时刻表会让声音落在动作中间。</li>
 *   <li><b>伤害类型是自己的</b>（{@code colt_1878_bullet}）：死亡信息里说的是这把枪，而不是 S686。</li>
 *   <li><b>准线值暂时沿用 S686</b>（见 {@code ADS_X/ADS_Y} 的注）。</li>
 * </ol>
 */
public class Colt1878Item extends S686Item {

    // ------------------------------------------------------------------ 动作时长
    // 逐条等于 colt_1878.animation.json 里对应片段的长度（20 t/s）。
    // 改动画就必须同时改这里 —— tools/check_gun_resources.py 会拿动画文件的长度来核这几个数。

    /** 举枪：0.8 s。比长管猎枪利落 —— 管短、重心靠后。 */
    private static final int DRAW_TICKS = 16;
    /** 射击后坐：0.6 s，与 S686 同（这一段本来就是同一套后坐）。 */
    private static final int SHOOT_TICKS = 12;
    /** 折开退壳（不装弹）：1.4 s。 */
    private static final int BOLT_TICKS = 28;
    /** 有弹换弹：3.0 s = 60 tick。本枪"换弹慢"的主力（S686 是 39 tick）。 */
    private static final int RELOAD_TACTICAL_TICKS = 60;
    /** 空仓换弹：3.6 s = 72 tick。比有弹版多退一遍壳，再刻意多摸一下弹袋（S686 是 50 tick）。 */
    private static final int RELOAD_EMPTY_TICKS = 72;

    // ------------------------------------------------------------------ 准线
    /**
     * 举枪时把准线抬到眼前所需的位移 —— 目前<b>沿用 S686 的值</b>。
     *
     * <p>⚠️ 这两个数本该按本枪的准线高度实测（本枪肋条顶面 y ≈ 0.62 u，比 S686 的略低），
     * 实测走 {@code tools/pose_measure.py} 的同一条链。两把枪都是折开式双管、准线都压在管上方，
     * 数值同量级，所以先沿用；等实测跑过，这三个数（ADS_X / ADS_Y / adsZ）应按本枪几何重算。</p>
     */
    private static final float ADS_X = -0.4749F;
    private static final float ADS_Y = 0.3533F;
    /**
     * 物品模型第一人称 {@code display} 的旋转（度），瞄准时由 {@code GunPose} 精确抵消 ——
     * 必须等于 {@code models/item/colt_1878.json} 里 {@code firstperson_righthand.rotation} 的前两项
     * （{@code tools/check_gun_resources.py} 会核）。本枪与该 json 都取 S686 的同一套持枪角。
     */
    private static final float DISPLAY_PITCH = 2.0F;
    private static final float DISPLAY_YAW = 4.0F;

    // ------------------------------------------------------------------ 音效时刻表
    // 键 = 从动作开始算起的 tick，值 = 那一刻该响的机械音；表按本枪胶片的**关键帧**排：
    //   draw         0.8 s  枪从下方抬到位，0.6 s 稳定
    //   bolt         1.4 s  拨杆 0.20 → 管开 0.20–0.60 → 管合 1.28 → 拨杆归位 1.40
    //   reload_tac   3.0 s  拨杆 0.18 → 管开 0.30/0.90 → 退壳 1.35 → 新弹入膛 2.20/2.42 → 管合 2.86 → 归位 3.00
    //   reload_empty 3.6 s  拨杆 0.22 → 管开 0.38/1.08 → 退壳 1.62 → 新弹入膛 2.68/2.94 → 管合 3.42 → 归位 3.60
    // 末帧那一格永远不会被遍历到（elapsed >= 长度即结算），所以"归位"音统一提前一格。

    /** 举枪：枪抬起来，落到肩上时收尾。 */
    private static final Map<Integer, RegistryObject<SoundEvent>> DRAW_SOUNDS = Map.of(
            2, ModSounds.AWM_RELOAD_RAISE,
            12, ModSounds.AWM_RECHAMBER_END);

    /** 折开检查：拨杆（0.20 s）、管离开弹膛面（0.60 s）、管合上（1.28 s）、拨杆归位。 */
    private static final Map<Integer, RegistryObject<SoundEvent>> BOLT_SOUNDS = Map.of(
            4, ModSounds.AWM_RECHAMBER_OUT,
            12, ModSounds.AWM_RELOAD_MAGOUT,
            26, ModSounds.AWM_RELOAD_EMPTY_BOLTCLOSE,
            27, ModSounds.AWM_RECHAMBER_END);

    /** 有弹换弹：拨杆、折开、退掉膛里那发、两发新弹入膛、合膛、拨杆归位。 */
    private static final Map<Integer, RegistryObject<SoundEvent>> RELOAD_TACTICAL_SOUNDS = Map.of(
            4, ModSounds.AWM_RECHAMBER_OUT,
            12, ModSounds.AWM_RELOAD_MAGOUT,
            27, ModSounds.AWM_RELOAD_EJECT,
            44, ModSounds.AWM_RELOAD_MAGIN,
            57, ModSounds.AWM_RELOAD_EMPTY_BOLTCLOSE,
            59, ModSounds.AWM_RELOAD_END);

    /** 空仓换弹：比有弹版多一下"退壳更彻底"的响动，整体后移。 */
    private static final Map<Integer, RegistryObject<SoundEvent>> RELOAD_EMPTY_SOUNDS = Map.of(
            4, ModSounds.AWM_RECHAMBER_OUT,
            8, ModSounds.AWM_RELOAD_EMPTY_MAGOUT,
            32, ModSounds.AWM_RELOAD_EJECT,
            54, ModSounds.AWM_RELOAD_EMPTY_MAGIN,
            68, ModSounds.AWM_RELOAD_EMPTY_BOLTCLOSE,
            71, ModSounds.AWM_RELOAD_EMPTY_END);

    // ------------------------------------------------------------------ 伤害

    /** 本枪的伤害类型：死亡信息写成"被柯尔特 1878 喷倒"，而不是 S686。 */
    private static final ResourceKey<DamageType> DAMAGE_TYPE =
            ResourceKey.create(Registries.DAMAGE_TYPE,
                    new ResourceLocation(ApocalypseZombies.MOD_ID, "colt_1878_bullet"));

    public Colt1878Item(Item.Properties properties) {
        super(properties);
    }

    // ------------------------------------------------------------------ 覆盖：时间与音效

    /** 本枪的动作时长，逐条取自 {@code colt_1878.animation.json}。 */
    @Override
    protected int actionLength(String action) {
        return switch (action) {
            case "draw" -> DRAW_TICKS;
            case "shoot" -> SHOOT_TICKS;
            case "bolt" -> BOLT_TICKS;
            case "reload_tactical" -> RELOAD_TACTICAL_TICKS;
            case "reload_empty" -> RELOAD_EMPTY_TICKS;
            default -> 0;
        };
    }

    /** 本枪的机械音时刻表；各条表见上面常量上的注释（按本枪胶片关键帧排的）。 */
    @Override
    protected Map<Integer, RegistryObject<SoundEvent>> soundCuesFor(String action) {
        return switch (action) {
            case "shoot" -> Map.of();
            case "bolt" -> BOLT_SOUNDS;
            case "draw" -> DRAW_SOUNDS;
            case "reload_tactical" -> RELOAD_TACTICAL_SOUNDS;
            case "reload_empty" -> RELOAD_EMPTY_SOUNDS;
            default -> Map.of();
        };
    }

    // ------------------------------------------------------------------ 覆盖：伤害类型

    @Override
    protected ResourceKey<DamageType> damageType() {
        return DAMAGE_TYPE;
    }

    // ------------------------------------------------------------------ 覆盖：手感

    /** 短管端起来快：0.16 s → 0.13 s。 */
    @Override
    public float aimTime() {
        return 0.13F;
    }

    /**
     * 铁瞄，且本枪的肋条比 S686 略低，所以视场缩小得少一点 —— 举枪时看得见更多两侧，
     * 这符合短管近战的用法。
     */
    @Override
    public double aimedFov() {
        return 60.0D;
    }

    /**
     * 短枪在手里显得小，所以要补得比 S686 更多一点，否则第一人称里会显得像玩具。
     */
    @Override
    public float firstPersonScale() {
        return 1.32F;
    }

    @Override
    public float adsX() {
        return ADS_X;
    }

    @Override
    public float adsY() {
        return ADS_Y;
    }

    @Override
    public float adsPitch() {
        return DISPLAY_PITCH;
    }

    @Override
    public float adsYaw() {
        return DISPLAY_YAW;
    }

    @Override
    public void initializeClient(Consumer<IClientItemExtensions> consumer) {
        consumer.accept(new IClientItemExtensions() {
            private Colt1878ItemRenderer renderer;

            @Override
            public BlockEntityWithoutLevelRenderer getCustomRenderer() {
                if (this.renderer == null) {
                    this.renderer = new Colt1878ItemRenderer();
                }
                return this.renderer;
            }

            /** Hands the first-person transform to {@code WeaponHandGrip}, exactly as the other guns do. */
            @Override
            public boolean applyForgeHandTransform(PoseStack poseStack, LocalPlayer player, HumanoidArm arm,
                                                   ItemStack stack, float partialTick, float equipProcess,
                                                   float swingProcess) {
                return com.apocalypse.zombies.client.weapon.WeaponHandGrip
                        .apply(poseStack, player, arm, stack, equipProcess);
            }
        });
    }
}

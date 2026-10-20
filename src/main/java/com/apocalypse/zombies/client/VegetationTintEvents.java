package com.apocalypse.zombies.client;

import com.apocalypse.zombies.ApocalypseZombies;
import net.minecraft.client.renderer.BiomeColors;
import net.minecraft.core.BlockPos;
import net.minecraft.util.Mth;
import net.minecraft.world.level.BlockAndTintGetter;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.DoublePlantBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.FoliageColor;
import net.minecraft.world.level.GrassColor;
import net.minecraft.world.level.block.state.properties.DoubleBlockHalf;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RegisterColorHandlersEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * v6.2：植被色调（末日枯黄基调）+ 全帧光照分级里的「植被那一半」。
 *
 * <p><b>为什么用 {@code RegisterColorHandlersEvent.Block} 而不是 Mixin：</b>1.20.1 的 Forge
 * {@code ViewportEvent} 只有镜头角度/雾色/雾距/FOV 四个钩子，没有能给区块网格上色的
 * lightmap 钩子。方块 tint 是唯一一条「不建 Mixin 也能改植被本色」的真实入口 ——
 * 原版在 {@code BlockColors.createDefault()} 里注册完自己的颜色之后，才回调
 * {@code ForgeHooksClient.onBlockColorsInit}（即本事件），所以同名方块的后注册者直接覆盖
 * 原版 handler，颜色会被烘进区块网格（改完需要重建区块才看得到）。注意这个事件在
 * <b>MOD 总线</b>上（{@code ModLoader.postEvent}），不是 FORGE 总线。</p>
 *
 * <p><b>怎么调色：</b>先取生物群系本色（草方块/高草/蕨/大蕨走
 * {@code BiomeColors.getAverageGrassColor}，树叶走 {@code getAverageFoliageColor}，
 * 与原版同一套采样，含 4×4 邻域平均），再做三步：去饱和（向自身亮度收敛，削掉荧光绿）、
 * 暖偏移（抬红压蓝）、轻微压暗。三步都是对每个群系本色做同一条仿射变换，所以群系之间的
 * 差异被整体保留 —— 丛林仍然最深、平原偏黄、针叶林偏冷，只是统一收敛到「干枯」的基调。</p>
 *
 * <p><b>为什么要轻（这是一条边界，别再加回来）：</b>贴图侧已经烘焙了去饱和与枯黄
 * （见 {@code resourcepack/apocalypse_16x} 等植被贴图，也可能随 mod 一起内嵌下发），
 * 代码侧只做轻量校正 —— tint 在游戏里是乘法叠加在贴图上的，若这里也来一遍 40% 去饱和 + 0.90 压暗，
 * 两层叠加会把草压成脏灰，而不是更真实。量化：以 {@code grass_block_top} 16x 均值
 * (97.4, 99.2, 65.0) 计，六种群系（plains/forest/jungle/savanna/swamp/snowy）叠加后的
 * 亮度 / 原版基线落在 0.97~0.98；若用早先的 0.42 去饱和 + 0.90 压暗则会掉到 0.89~0.92
 * （jungle 只有 0.893，已经跌破 0.90）。</p>
 *
 * <p><b>只碰植被：</b>注册表里只有草方块、高草/蕨/大蕨与 1.20.1 的全部树叶方块；
 * 原版其它带 tint 的方块（水、甘蔗、睡莲、藤蔓、红石线、茎、花）一律不动，没有登记的方块
 * 不会调用到这里。</p>
 *
 * <p>性能：handler 在区块建网格时按方块调用，只有标量运算与一次群系颜色查询（与原版同价），
 * 零分配。</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, value = Dist.CLIENT,
        bus = Mod.EventBusSubscriber.Bus.MOD)
public final class VegetationTintEvents {

    /** 去饱和强度：向自身亮度收敛的比例，0 = 原色，1 = 全灰。轻量校正，主观感交给贴图。 */
    private static final float DESATURATE = 0.20F;
    /** 暖偏移：抬红、略抬绿、压蓝（末日尘土感的来源）；幅度与 {@link #DESATURATE} 同量级。 */
    private static final float WARM_RED = 1.06F;
    private static final float WARM_GREEN = 1.01F;
    private static final float WARM_BLUE = 0.90F;
    /** 压暗：几乎不压暗（0.97~1.0），贴图侧已经比原版偏枯黄，这里再压就会发脏。 */
    private static final float DARKEN = 0.98F;
    /** 云杉/白桦保留多少原版种内固有色（0 = 纯群系色，1 = 纯原版固有色）。 */
    private static final float SPECIES_BIAS = 0.45F;

    private VegetationTintEvents() {
    }

    @SubscribeEvent
    public static void onRegisterBlockColors(RegisterColorHandlersEvent.Block event) {
        // 草类：草方块 + 高草/蕨/大蕨（大蕨与高草是双格植物，上半格取样下半格，同原版）。
        event.register(VegetationTintEvents::grassColor,
                Blocks.GRASS_BLOCK, Blocks.TALL_GRASS, Blocks.FERN, Blocks.LARGE_FERN);
        // 1.20.1 全部树叶方块：群系树叶色（橡木/丛林/金合欢/深色橡木/红树/樱花/杜鹃）。
        event.register(VegetationTintEvents::foliageColor,
                Blocks.OAK_LEAVES, Blocks.JUNGLE_LEAVES, Blocks.ACACIA_LEAVES,
                Blocks.DARK_OAK_LEAVES, Blocks.MANGROVE_LEAVES, Blocks.CHERRY_LEAVES,
                Blocks.AZALEA_LEAVES, Blocks.FLOWERING_AZALEA_LEAVES);
        // 原版给云杉/白桦的是固有色（不吃群系），这里两者折中：保留种内色相 + 吃群系差异。
        event.register(VegetationTintEvents::spruceColor, Blocks.SPRUCE_LEAVES);
        event.register(VegetationTintEvents::birchColor, Blocks.BIRCH_LEAVES);
    }

    private static int grassColor(BlockState state, BlockAndTintGetter level, BlockPos pos,
                                  int tintIndex) {
        if (!enabled()) {
            return level != null && pos != null ? BiomeColors.getAverageGrassColor(level, pos)
                    : GrassColor.getDefaultColor();
        }
        if (level == null || pos == null) {
            return dry(GrassColor.getDefaultColor());
        }
        BlockPos sample = pos;
        if (state.hasProperty(DoublePlantBlock.HALF)
                && state.getValue(DoublePlantBlock.HALF) == DoubleBlockHalf.UPPER) {
            sample = pos.below();
        }
        return dry(BiomeColors.getAverageGrassColor(level, sample));
    }

    private static int foliageColor(BlockState state, BlockAndTintGetter level, BlockPos pos,
                                    int tintIndex) {
        return leaves(level, pos, FoliageColor.getDefaultColor(), 0.0F);
    }

    private static int spruceColor(BlockState state, BlockAndTintGetter level, BlockPos pos,
                                   int tintIndex) {
        return leaves(level, pos, FoliageColor.getEvergreenColor(), SPECIES_BIAS);
    }

    private static int birchColor(BlockState state, BlockAndTintGetter level, BlockPos pos,
                                  int tintIndex) {
        return leaves(level, pos, FoliageColor.getBirchColor(), SPECIES_BIAS);
    }

    /**
     * 树叶共用：生物群系树叶色（缺 level/pos 时退回原版默认色），可选按 {@code speciesBias}
     * 混入种内固有色，最后统一走 {@link #dry(int)}。
     */
    private static int leaves(BlockAndTintGetter level, BlockPos pos, int speciesColor,
                              float speciesBias) {
        int biome = level != null && pos != null
                ? BiomeColors.getAverageFoliageColor(level, pos)
                : FoliageColor.getDefaultColor();
        if (!enabled()) {
            return speciesBias <= 0.0F ? biome : blend(biome, speciesColor, speciesBias);
        }
        return dry(speciesBias > 0.0F ? blend(biome, speciesColor, speciesBias) : biome);
    }

    /** 去饱和 + 暖偏移 + 轻微压暗。纯标量运算，无分配。 */
    private static int dry(int color) {
        float red = (color >> 16 & 0xFF) / 255.0F;
        float green = (color >> 8 & 0xFF) / 255.0F;
        float blue = (color & 0xFF) / 255.0F;
        float luma = red * 0.299F + green * 0.587F + blue * 0.114F;
        red = Mth.lerp(DESATURATE, red, luma) * WARM_RED * DARKEN;
        green = Mth.lerp(DESATURATE, green, luma) * WARM_GREEN * DARKEN;
        blue = Mth.lerp(DESATURATE, blue, luma) * WARM_BLUE * DARKEN;
        return 0xFF000000 | channel(red) << 16 | channel(green) << 8 | channel(blue);
    }

    private static int blend(int a, int b, float bias) {
        int red = channel(Mth.lerp(bias, (a >> 16 & 0xFF) / 255.0F, (b >> 16 & 0xFF) / 255.0F));
        int green = channel(Mth.lerp(bias, (a >> 8 & 0xFF) / 255.0F, (b >> 8 & 0xFF) / 255.0F));
        int blue = channel(Mth.lerp(bias, (a & 0xFF) / 255.0F, (b & 0xFF) / 255.0F));
        return 0xFF000000 | red << 16 | green << 8 | blue;
    }

    private static int channel(float value) {
        return (int) (Mth.clamp(value, 0.0F, 1.0F) * 255.0F + 0.5F);
    }

    /**
     * 开关：{@code sky.realistic_sky_effects}（总）+ {@code sky.vegetation_tint}。
     * 关掉时原样返回群系本色（不叠加任何调整）。tint 会被烘进区块网格，改动需重建区块生效。
     */
    private static boolean enabled() {
        return ClientConfig.REALISTIC_SKY_EFFECTS.get() && ClientConfig.VEGETATION_TINT.get();
    }
}

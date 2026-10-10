package com.apocalypse.zombies.client;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.gui.CatGirlTradeScreen;
import com.apocalypse.zombies.client.model.CorroderModel;
import com.apocalypse.zombies.client.model.CrusherModel;
import com.apocalypse.zombies.client.model.ScreamerModel;
import com.apocalypse.zombies.client.renderer.BrideGeoRenderer;
import com.apocalypse.zombies.client.renderer.CatGirlGeoRenderer;
import com.apocalypse.zombies.registry.ModMenus;
import com.apocalypse.zombies.client.renderer.OverlordGeoRenderer;
import com.apocalypse.zombies.client.renderer.SoldierGeoRenderer;
import com.apocalypse.zombies.client.renderer.CharmedZombieRenderer;
import com.apocalypse.zombies.client.renderer.CorroderRenderer;
import com.apocalypse.zombies.client.renderer.CrusherRenderer;
import com.apocalypse.zombies.client.renderer.MarksmanGeoRenderer;
import com.apocalypse.zombies.client.renderer.ScreamerRenderer;
import com.apocalypse.zombies.entity.AcidProjectile;
import com.apocalypse.zombies.entity.BouquetProjectile;
import com.apocalypse.zombies.entity.BulletProjectile;
import com.apocalypse.zombies.registry.ModEntities;
import com.apocalypse.zombies.client.renderer.GiantArrowRenderer;
import net.minecraft.client.renderer.entity.ThrownItemRenderer;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.EntityRenderersEvent;
import net.minecraftforge.client.event.RegisterKeyMappingsEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * Mod-bus wiring that must not exist on a dedicated server.
 *
 * <p>Key mappings register on the mod bus during client setup, which is a different bus from the one
 * {@link ClientEvents} listens on, so the two live in separate classes.</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, value = Dist.CLIENT,
        bus = Mod.EventBusSubscriber.Bus.MOD)
public final class ClientModBusEvents {

    private ClientModBusEvents() {
    }

    @SubscribeEvent
    public static void onRegisterKeyMappings(RegisterKeyMappingsEvent event) {
        event.register(KeyBindings.RELOAD);
        event.register(KeyBindings.COLLECT);
    }

    /**
     * 每个精英（含美女僵尸）各挂一层独立的人形网格，魅惑召奬再占一层。
     *
     * <p>不能图省事复用 {@code ModelLayers.ZOMBIE} / {@code ModelLayers.SKELETON}：
     * 同一层的 {@code ModelPart} 是共享实例，几个模型摆姿势时会互相覆盖，
     * 表现出来就是远处的怪跟着近处的怪做同一个动作。</p>
     */
    @SubscribeEvent
    public static void onRegisterLayerDefinitions(EntityRenderersEvent.RegisterLayerDefinitions event) {
        event.registerLayerDefinition(ScreamerModel.LAYER, ScreamerModel::createBodyLayer);
        event.registerLayerDefinition(CrusherModel.LAYER, CrusherModel::createBodyLayer);
        event.registerLayerDefinition(CorroderModel.LAYER, CorroderModel::createBodyLayer);
        // 骸骨射手与美女僵尸 Phase 2 一样换成 GeckoLib 骨骼模型：不再占人形层（模型自带骨骼树）
        event.registerLayerDefinition(CharmedZombieRenderer.LAYER, CharmedZombieRenderer::createBodyLayer);
    }

    /**
     * 菜单 → 界面 的绑定。
     *
     * <p><b>Forge 1.20.1 没有 {@code RegisterMenuScreensEvent}</b> —— 那是 1.20.2+（NeoForge）才有的
     * 事件。1.20.1 的原版做法是在 {@code FMLClientSetupEvent} 里 {@code enqueueWork} 之后调
     * {@code MenuScreens.register}。单独一个 handler 而不是塞进已有的初始化，是为了「界面没绑上」
     * 这类问题能一眼定位。</p>
     */
    @SubscribeEvent
    public static void onClientSetupMenuScreens(net.minecraftforge.fml.event.lifecycle.FMLClientSetupEvent event) {
        event.enqueueWork(() -> net.minecraft.client.gui.screens.MenuScreens.register(
                ModMenus.CAT_GIRL_TRADE.get(), CatGirlTradeScreen::new));
    }

    @SubscribeEvent
    public static void onRegisterRenderers(EntityRenderersEvent.RegisterRenderers event) {
        event.registerEntityRenderer(ModEntities.SCREAMER.get(), ScreamerRenderer::new);
        event.registerEntityRenderer(ModEntities.CRUSHER.get(), CrusherRenderer::new);
        event.registerEntityRenderer(ModEntities.CORRODER.get(), CorroderRenderer::new);
        // 骸骨射手：GeckoLib 骨骼模型（32u = 2 格，命中箱不变；不要加物品层，弓在自己骨骼里）
        event.registerEntityRenderer(ModEntities.MARKSMAN.get(), MarksmanGeoRenderer::new);
        event.registerEntityRenderer(ModEntities.BRIDE.get(), BrideGeoRenderer::new);
        event.registerEntityRenderer(ModEntities.SOLDIER.get(), SoldierGeoRenderer::new);
        // 尸潮之主：三阶段 Boss。同样是 GeckoLib 骨骼模型，模型自己 3 格高，不做缩放。
        event.registerEntityRenderer(ModEntities.OVERLORD.get(), OverlordGeoRenderer::new);
        event.registerEntityRenderer(ModEntities.CHARMED.get(), CharmedZombieRenderer::new);
        // 猫耳娘：骨骼模型 + 手持物品层（她手里的东西是玩家给的真实物品，见渲染器注释）
        event.registerEntityRenderer(ModEntities.CAT_GIRL.get(), CatGirlGeoRenderer::new);
        // 酸液直接借原版投掷物的渲染：一个飞出去的小球，材质疑似物品贴图
        event.registerEntityRenderer(ModEntities.ACID_PROJECTILE.get(),
                context -> new ThrownItemRenderer<AcidProjectile>(context, 1.0F, true));
        // 子弹同理，只是画得小一圈、始终自发光 —— 曳光弹在暗处也该看得见
        event.registerEntityRenderer(ModEntities.BULLET.get(),
                context -> new ThrownItemRenderer<BulletProjectile>(context, 0.8F, true));
        // 美女僵尸的花束：同样是投掷物渲染，但它是「甩出去的一束花」，画得正常大小即可
        event.registerEntityRenderer(ModEntities.BOUQUET_PROJECTILE.get(),
                context -> new ThrownItemRenderer<BouquetProjectile>(context, 1.0F, true));
        // 骷髅的重箭：复用原版箭的模型与贴图，只做缩放 —— 放大绕的是实体原点，
        // 必须先沿视线回退 (scale−1)×0.675 格，箭尖才不会跑到命中点前面（见渲染器注释）
        event.registerEntityRenderer(ModEntities.GIANT_ARROW.get(), GiantArrowRenderer::new);
        // 骨矢：同一套缩放渲染。它飞得更快、命中即碎，伤害自己按目标血量算（见 BoneLockArrow）
        event.registerEntityRenderer(ModEntities.BONE_LOCK_ARROW.get(), GiantArrowRenderer::new);
    }
}

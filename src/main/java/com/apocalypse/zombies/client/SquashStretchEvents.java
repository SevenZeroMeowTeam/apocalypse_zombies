package com.apocalypse.zombies.client;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.client.anim.SquashStretch;
import net.minecraft.client.Minecraft;
import net.minecraft.client.model.EntityModel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ClientPlayerNetworkEvent;
import net.minecraftforge.client.event.RenderLivingEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import software.bernie.geckolib.event.GeoRenderEvent;

/**
 * Q 弹效果的事件桥。
 *
 * <p><b>为什么必须挂两条链</b>：{@code GeoEntityRenderer} 自己重写了 {@code render} 且不调
 * {@code super}，所以 GeckoLib 生物（本 mod 的骸骨射手 / 美女僵尸 / 士兵僵尸 / 尸潮之主）
 * <b>根本不会</b>发布 {@code RenderLivingEvent} —— 只挂一条会静默漏掉一半怪，而且不报错。
 * 反过来 GeckoLib 的 {@code GeoRenderEvent.Entity} 只有走 {@code GeoEntityRenderer} 的实体才发，
 * 覆盖不到原版和其它模组生物。两条链的实体集合不相交（同一个实体不会两边都触发），
 * 所以不会双重形变。</p>
 *
 * <p>玩家是唯一例外：{@code PlayerRenderer.render} 先 post {@code RenderPlayerEvent} 再调
 * {@code super.render}（内部又 post {@code RenderLivingEvent}），所以玩家会被本类触发一次；
 * 排除逻辑放在 {@link SquashStretch#apply} 里，两条链共用。</p>
 */
@Mod.EventBusSubscriber(modid = ApocalypseZombies.MOD_ID, value = Dist.CLIENT,
        bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class SquashStretchEvents {

    private SquashStretchEvents() {
    }

    // ------------------------------------------------------------ 原版模型系

    /**
     * {@code LOWEST}：让别人的缩放（进化 tier、碎颅者的 1.15）先乘进来，
     * 我们的压扁作用在最外层 —— 等价于「在世界空间里压扁已经选好体型的模型」。
     * 放最里层的话，1.5 倍体型的怪压扁幅度会被同比例放大，观感不一致。
     */
    @SubscribeEvent(priority = EventPriority.LOWEST)
    public static void onRenderLivingPre(RenderLivingEvent.Pre<LivingEntity, EntityModel<LivingEntity>> event) {
        LivingEntity entity = event.getEntity();
        // 渲染即观察：只处理屏幕上真正在画的实体，零额外遍历
        SquashStretch.observeHurt(entity);
        SquashStretch.observeMotion(entity);
        SquashStretch.apply(entity, event.getPoseStack(), event.getPartialTick());
    }

    @SubscribeEvent(priority = EventPriority.LOWEST)
    public static void onRenderLivingPost(RenderLivingEvent.Post<LivingEntity, EntityModel<LivingEntity>> event) {
        SquashStretch.popIfApplied(event.getEntity(), event.getPoseStack());
    }

    // ------------------------------------------------------------ GeckoLib 系

    @SubscribeEvent(priority = EventPriority.LOWEST)
    public static void onGeoEntityPre(GeoRenderEvent.Entity.Pre event) {
        Entity entity = event.getEntity();
        if (!(entity instanceof LivingEntity living)) {
            return;
        }
        SquashStretch.observeHurt(living);
        SquashStretch.observeMotion(living);
        SquashStretch.apply(living, event.getPoseStack(), event.getPartialTick());
    }

    @SubscribeEvent(priority = EventPriority.LOWEST)
    public static void onGeoEntityPost(GeoRenderEvent.Entity.Post event) {
        if (event.getEntity() instanceof LivingEntity living) {
            SquashStretch.popIfApplied(living, event.getPoseStack());
        }
    }

    // ------------------------------------------------------------ 驱动

    /** 推进冲击的年龄（20 Hz）—— 与渲染帧率解耦，回弹速度才是稳定的。 */
    @SubscribeEvent
    public static void onClientTick(TickEvent.ClientTickEvent event) {
        if (event.phase != TickEvent.Phase.END) {
            return;
        }
        if (Minecraft.getInstance().level == null) {
            return;
        }
        SquashStretch.tick();
    }

    /** 退出世界时清空：世界换了，实体 id 空间也换了。 */
    @SubscribeEvent
    public static void onLoggingOut(ClientPlayerNetworkEvent.LoggingOut event) {
        SquashStretch.clear();
    }
}

package com.apocalypse.zombies.registry;

import net.minecraft.world.inventory.MenuType;
import net.minecraftforge.common.extensions.IForgeMenuType;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.entity.menu.CatGirlTradeMenu;

/**
 * 容器菜单注册。
 *
 * <p>实体绑定的菜单要带额外数据（这里是实体 id），所以用
 * {@code IForgeMenuType.create(...)}：客户端从 {@code openMenu} 附带的
 * {@link net.minecraft.network.FriendlyByteBuf} 里读回实体 id，再在本地世界里
 * 找回同一个实体 —— 双方各自持有自己那份实例，槽位内容由菜单每 tick 的
 * {@code broadcastChanges} 对齐。</p>
 */
public final class ModMenus {

    public static final DeferredRegister<MenuType<?>> MENUS =
            DeferredRegister.create(ForgeRegistries.MENU_TYPES, ApocalypseZombies.MOD_ID);

    public static final RegistryObject<MenuType<CatGirlTradeMenu>> CAT_GIRL_TRADE =
            MENUS.register("cat_girl_trade", () -> IForgeMenuType.create(
                    (windowId, inventory, data) -> new CatGirlTradeMenu(windowId, inventory, data.readVarInt())));

    private ModMenus() {
    }

    public static void register(IEventBus modBus) {
        MENUS.register(modBus);
    }
}

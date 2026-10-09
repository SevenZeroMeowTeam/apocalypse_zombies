package com.apocalypse.zombies.client;

import com.mojang.blaze3d.platform.InputConstants;
import net.minecraft.client.KeyMapping;
import org.lwjgl.glfw.GLFW;

/**
 * Client key bindings. Registered on the mod bus by {@link ClientModBusEvents}; polled in
 * {@link ClientEvents#onClientTick}.
 */
public final class KeyBindings {

    /** Own controls category so the bind sits in its own group in the options screen. */
    public static final String CATEGORY = "key.categories.apocalypse_zombies";

    /** R — reload the weapon in hand. */
    public static final KeyMapping RELOAD = new KeyMapping(
            "key.apocalypse_zombies.reload", InputConstants.Type.KEYSYM, GLFW.GLFW_KEY_R, CATEGORY);

    /** G — 一键采集范围内的掉落物（范围与上限在配置的 [collect] 段）。 */
    public static final KeyMapping COLLECT = new KeyMapping(
            "key.apocalypse_zombies.collect", InputConstants.Type.KEYSYM, GLFW.GLFW_KEY_G, CATEGORY);

    private KeyBindings() {
    }
}

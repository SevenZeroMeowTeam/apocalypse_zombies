package com.apocalypse.zombies.client;

import com.apocalypse.zombies.moon.MoonEvent;

/**
 * Client-side mirror of the server's lunar state.
 *
 * <p>Intentionally free of any client-only Minecraft class so common code can read it without
 * dragging render classes onto a dedicated server.</p>
 */
public final class ClientMoonState {

    private static volatile MoonEvent moonEvent = MoonEvent.NONE;
    private static volatile int evolutionLevel = 0;

    private ClientMoonState() {
    }

    public static MoonEvent getMoonEvent() {
        return moonEvent;
    }

    public static int getEvolutionLevel() {
        return evolutionLevel;
    }

    public static void set(MoonEvent event, int level) {
        moonEvent = event;
        evolutionLevel = level;
    }

    public static void reset() {
        moonEvent = MoonEvent.NONE;
        evolutionLevel = 0;
    }
}

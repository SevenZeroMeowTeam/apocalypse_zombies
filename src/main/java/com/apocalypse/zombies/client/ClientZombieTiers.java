package com.apocalypse.zombies.client;

import com.apocalypse.zombies.zombie.EvolutionTier;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/** Client-side mirror of every tracked zombie's evolution tier, keyed by entity id. */
public final class ClientZombieTiers {

    private static final Map<Integer, Integer> TIERS = new ConcurrentHashMap<>();

    private ClientZombieTiers() {
    }

    public static void set(int entityId, int tier) {
        if (tier <= 0) {
            TIERS.remove(entityId);
        } else {
            TIERS.put(entityId, tier);
        }
    }

    public static int get(int entityId) {
        Integer tier = TIERS.get(entityId);
        return tier == null ? 0 : tier;
    }

    public static EvolutionTier getTier(int entityId) {
        return EvolutionTier.byIndex(get(entityId));
    }

    public static void clear() {
        TIERS.clear();
    }
}

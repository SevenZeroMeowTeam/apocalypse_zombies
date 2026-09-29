package com.apocalypse.zombies.moon;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;

/**
 * Persisted apocalypse state: which moon is up, which night it was rolled on, and how far the
 * zombie population has evolved.
 *
 * <p>Kept deliberately tiny and dependency-free so the storage hookup is a single line.</p>
 */
public class ApocalypseData extends net.minecraft.world.level.saveddata.SavedData {

    public static final String DATA_NAME = "apocalypse_zombies";

    private MoonEvent moonEvent = MoonEvent.NONE;
    private long lastRolledDay = Long.MIN_VALUE;
    private int evolutionLevel = 0;

    public ApocalypseData() {
    }

    public ApocalypseData(CompoundTag tag) {
        this.load(tag);
    }

    public void load(CompoundTag tag) {
        this.moonEvent = MoonEvent.byId(tag.getString("MoonEvent"));
        this.lastRolledDay = tag.contains("LastRolledDay") ? tag.getLong("LastRolledDay") : Long.MIN_VALUE;
        this.evolutionLevel = tag.getInt("EvolutionLevel");
    }

    @Override
    public CompoundTag save(CompoundTag tag) {
        tag.putString("MoonEvent", this.moonEvent.getId());
        tag.putLong("LastRolledDay", this.lastRolledDay);
        tag.putInt("EvolutionLevel", this.evolutionLevel);
        return tag;
    }

    public MoonEvent getMoonEvent() {
        return this.moonEvent;
    }

    public void setMoonEvent(MoonEvent event) {
        this.moonEvent = event;
        this.setDirty();
    }

    public long getLastRolledDay() {
        return this.lastRolledDay;
    }

    public void setLastRolledDay(long day) {
        this.lastRolledDay = day;
        this.setDirty();
    }

    public int getEvolutionLevel() {
        return this.evolutionLevel;
    }

    public void setEvolutionLevel(int level) {
        this.evolutionLevel = level;
        this.setDirty();
    }

    /** Fetches the shared instance from the overworld's data storage. */
    public static ApocalypseData get(ServerLevel level) {
        ServerLevel overworld = level.getServer().overworld();
        return overworld.getDataStorage().computeIfAbsent(ApocalypseData::new, ApocalypseData::new, DATA_NAME);
    }
}

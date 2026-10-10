package com.apocalypse.zombies.entity.ai;

import java.util.EnumSet;

import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.phys.Vec3;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.CatGirlCrafting;
import com.apocalypse.zombies.entity.CatGirlEntity;
import com.apocalypse.zombies.entity.CatGirlStation;

/**
 * 「去工作方块干活」：她有活要干时，走到就近的合成台 / 熔炉再动手；就近没有，
 * 就自己做一个放到脚边（{@code cat_girl.station_self_craft}）。
 *
 * <p>为什么要有这个目标而不是就地空手做：主人的「她应该像玩家一样操作」——
 * 玩家不会站在野外空手摆 3×3，而是走到台子前。这个目标只负责<b>到位</b>：
 * 真正的制作仍然由 {@code CatGirlCrafting.tick} 负责，它只在
 * {@link CatGirlEntity#isAtStation} 成立时才动手（见那边的站台门槛）。</p>
 *
 * <p><b>不会卡死</b>：就近没台子、又不许自己做时，制作那一侧会退回老行为（就地做），
 * 这个目标只是找不到目标而已 —— 不做任何破坏性的事。</p>
 */
public class CatGirlStationGoal extends Goal {

    /** 到位的判定距离（格）。 */
    private static final double REACH = 3.5D;

    /** 扫描冷却：canUse 每 tick 被问，靠这个字段把重活摊开。 */
    private static final int SCAN_INTERVAL = 20;

    /** 自作自用的站台，认定有效期（tick）—— 够她做几十件东西，又不至于走开了还认。 */
    private static final int SELF_MADE_STATION_TICKS = 2400;

    private final CatGirlEntity cat;
    private int scanCooldown;
    private BlockPos target;

    public CatGirlStationGoal(CatGirlEntity cat) {
        this.cat = cat;
        this.setFlags(EnumSet.of(Goal.Flag.MOVE, Goal.Flag.LOOK));
    }

    @Override
    public boolean canUse() {
        if (!Config.CAT_GIRL_STATION_USE.get() || !this.cat.isAutoJob()) {
            return false;
        }
        if (this.scanCooldown > 0) {
            this.scanCooldown--;
            return false;
        }
        this.scanCooldown = SCAN_INTERVAL;
        this.target = null;

        CatGirlStation.Kind kind = this.wantedWork();
        if (kind == CatGirlStation.Kind.NONE) {
            return false;
        }
        // 已经站在台子边上了：不用走过去（制作那一侧会自己动手）
        if (this.cat.isAtStation(kind)) {
            return false;
        }
        BlockPos near = this.cat.stationNear(kind, Config.CAT_GIRL_STATION_RADIUS.get());
        if (near != null) {
            this.target = near;
            return true;
        }
        if (!Config.CAT_GIRL_STATION_SELF_CRAFT.get()) {
            return false;
        }
        this.selfProvide(kind);
        return false;
    }

    /**
     * 就近没有工作方块 → 自己做一个放脚边。
     *
     * <p>顺序：库存里已经有就直接放；没有就按配方自己做（合成台 = 4 木板，熔炉 = 8 圆石，
     * 材料她伐木 / 挖矿自己会攒）。做不出来就什么都不做 —— 她不会为这个拆主人的东西。</p>
     */
    private void selfProvide(CatGirlStation.Kind kind) {
        if (!(this.cat.level() instanceof ServerLevel level)) {
            return;
        }
        var item = CatGirlStation.itemFor(kind);
        if (item.isEmpty()) {
            return;
        }
        if (!this.cat.hasGoodsMatching(stack -> stack.is(item.getItem()))) {
            CatGirlCrafting.selfMake(this.cat, level, item, 1);
            if (!this.cat.hasGoodsMatching(stack -> stack.is(item.getItem()))) {
                return; // 料不够：这轮算了，攒够了下轮再说
            }
        }
        BlockPos placed = CatGirlStation.placeNear(this.cat, kind);
        if (placed != null) {
            this.cat.setStation(placed, SELF_MADE_STATION_TICKS);
        }
    }

    private CatGirlStation.Kind wantedWork() {
        if (!(this.cat.level() instanceof ServerLevel level)) {
            return CatGirlStation.Kind.NONE;
        }
        return CatGirlCrafting.wantedWork(this.cat, level);
    }

    @Override
    public boolean canContinueToUse() {
        if (this.target == null || !Config.CAT_GIRL_STATION_USE.get() || !this.cat.isAutoJob()) {
            return false;
        }
        if (this.cat.blockPosition().distSqr(this.target) <= REACH * REACH) {
            // 到位：认下这个台子，交给制作那一侧动手，这个目标退场
            this.cat.setStation(this.target, SELF_MADE_STATION_TICKS);
            return false;
        }
        return this.cat.isAlive();
    }

    @Override
    public void start() {
        this.cat.getNavigation().moveTo(this.target.getX() + 0.5D, this.target.getY(), this.target.getZ() + 0.5D, 1.0D);
    }

    @Override
    public void stop() {
        this.cat.getNavigation().stop();
    }

    @Override
    public void tick() {
        if (this.target == null) {
            return;
        }
        Vec3 center = Vec3.atCenterOf(this.target);
        this.cat.getLookControl().setLookAt(center.x, center.y, center.z, 30.0F, 30.0F);
    }
}

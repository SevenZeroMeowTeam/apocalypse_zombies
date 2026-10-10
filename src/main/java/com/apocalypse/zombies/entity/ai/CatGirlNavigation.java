package com.apocalypse.zombies.entity.ai;

import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.navigation.GroundPathNavigation;
import net.minecraft.world.level.Level;

/**
 * 玩家式寻路。
 *
 * <p>原版 {@code Mob} 的默认导航不会开门、不浮水、遇到门/围栏就当作墙 —— 结果就是
 * 「走过去砍那棵树」经常变成站在门口原地抽搐。玩家那几样本事这里一次补齐：</p>
 *
 * <ul>
 *   <li>{@code canOpenDoors / canPassDoors} —— 木门/栅栏门能推开再走过（关上门后她自己也不会被关在外面）。</li>
 *   <li>{@code canFloat} —— 落水能浮着继续走，不会沉底卡死。</li>
 *   <li>{@code avoidSun = false} —— 她不是亡灵，没有躲太阳的理由；开了反而会绕远路。</li>
 * </ul>
 *
 * <p>注意：这只是「会走路」，<b>不会</b>凭空开路。挡死的方块归
 * {@link CatGirlClearWayGoal}，沟壑归 {@link CatGirlBridgeGoal}。</p>
 */
public class CatGirlNavigation extends GroundPathNavigation {

    public CatGirlNavigation(Mob mob, Level level) {
        super(mob, level);
        this.setCanOpenDoors(true);
        this.setCanPassDoors(true);
        this.setCanFloat(true);
        this.setAvoidSun(false);
    }
}

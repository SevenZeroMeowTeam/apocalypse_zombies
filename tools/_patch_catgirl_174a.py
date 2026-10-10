# -*- coding: utf-8 -*-
"""1.1.74 第一批（她的手和脚）：导航 / 开路 / 搭桥 / 找目标的半径 / 跟随速度。"""
from pathlib import Path

NL = chr(10)
fails = []


def edit(path, pairs, label):
    p = Path(path)
    s = p.read_text(encoding='utf-8')
    for old, new in pairs:
        if old not in s:
            fails.append('%s ｜ 锚点没找到: %s' % (label, old.strip().splitlines()[0][:70]))
            continue
        s = s.replace(old, new, 1)
    p.write_text(s, encoding='utf-8')
    print('  [OK] ' + label)


ENT = 'F:/mcmod/src/main/java/com/apocalypse/zombies/entity/CatGirlEntity.java'

edit(ENT, [
    # ---- imports
    ('import com.apocalypse.zombies.entity.ai.CatGirlBowGoal;',
     'import com.apocalypse.zombies.entity.ai.CatGirlBowGoal;' + NL +
     'import com.apocalypse.zombies.entity.ai.CatGirlBridgeGoal;' + NL +
     'import com.apocalypse.zombies.entity.ai.CatGirlClearWayGoal;' + NL +
     'import com.apocalypse.zombies.entity.ai.CatGirlNavigation;'),
    # ---- 跟随速度
    ('        this.goalSelector.addGoal(1, new FollowOwnerGoal(this, 1.15D, 10.0F, 2.5F, false));',
     '        // 速度走 Config.CAT_GIRL_FOLLOW_SPEED（默认 1.3）：原版跟班的 1.15 在主人冲刺时会被稳稳甩掉。' + NL +
     '        // 注册期读一次，所以改完这个值要重进世界。' + NL +
     '        this.goalSelector.addGoal(1,' + NL +
     '                new FollowOwnerGoal(this, Config.CAT_GIRL_FOLLOW_SPEED.get(), 10.0F, 2.5F, false));'),
    # ---- 开路/搭桥插进 3，劳作顺延
    ('        this.goalSelector.addGoal(3, new WorkBlockGoal(this, Job.LUMBER, CatGirlEntity::isLog, ACTION_CHOP));' + NL +
     '        this.goalSelector.addGoal(4, new WorkBlockGoal(this, Job.MINE, CatGirlEntity::isOre, ACTION_MINE));' + NL +
     '        this.goalSelector.addGoal(5, new WaterAvoidingRandomStrollGoal(this, 1.0D));' + NL +
     '        this.goalSelector.addGoal(6, new LookAtPlayerGoal(this, Player.class, 8.0F));' + NL +
     '        this.goalSelector.addGoal(7, new RandomLookAroundGoal(this));',
     '        // 开路 / 搭桥：只在「正在导航且卡住」时接管，所以排在战斗之后、劳作之前。' + NL +
     '        this.goalSelector.addGoal(3, new CatGirlClearWayGoal(this));' + NL +
     '        this.goalSelector.addGoal(3, new CatGirlBridgeGoal(this));' + NL +
     '        this.goalSelector.addGoal(4, new WorkBlockGoal(this, Job.LUMBER, CatGirlEntity::isLog, ACTION_CHOP));' + NL +
     '        this.goalSelector.addGoal(5, new WorkBlockGoal(this, Job.MINE, CatGirlEntity::isOre, ACTION_MINE));' + NL +
     '        this.goalSelector.addGoal(6, new WaterAvoidingRandomStrollGoal(this, 1.0D));' + NL +
     '        this.goalSelector.addGoal(7, new LookAtPlayerGoal(this, Player.class, 8.0F));' + NL +
     '        this.goalSelector.addGoal(8, new RandomLookAroundGoal(this));'),
    # ---- createNavigation
    ('    private static boolean isOre(BlockState state) {' + NL +
     '        return state.is(Tags.Blocks.ORES);' + NL +
     '    }',
     '    private static boolean isOre(BlockState state) {' + NL +
     '        return state.is(Tags.Blocks.ORES);' + NL +
     '    }' + NL + NL +
     '    /**' + NL +
     '     * 换成会开门 / 会浮水的导航（{@link CatGirlNavigation}）。' + NL +
     '     *' + NL +
     '     * <p>原版 {@code Mob} 的默认导航把她当僵尸用：门就是墙、水就是死路，' + NL +
     '     * 于是「走过去砍那棵树」经常变成站在门口原地抽搐。</p>' + NL +
     '     */' + NL +
     '    @Override' + NL +
     '    protected net.minecraft.world.entity.ai.navigation.PathNavigation createNavigation(' + NL +
     '            net.minecraft.world.level.Level level) {' + NL +
     '        return new CatGirlNavigation(this, level);' + NL +
     '    }'),
    # ---- harvestBlockHard（开路/搭桥共用同一套掉落规则）
    ('    /** 交易菜单用的催肥粒子（钱不够时的反馈）。 */',
     '    /**' + NL +
     '     * 「砸开挡路的」通用实现：和伐木/挖矿同一套掉落规则（含 always_drops），' + NL +
     '     * 破坏后收进她的库存 —— 开路行为不能把「她砸什么都有产物」这条绕过去。' + NL +
     '     */' + NL +
     '    public void harvestBlockHard(BlockPos pos, boolean axeLike) {' + NL +
     '        if (!(this.level() instanceof ServerLevel server)) {' + NL +
     '            return;' + NL +
     '        }' + NL +
     '        BlockState state = server.getBlockState(pos);' + NL +
     '        net.minecraft.world.level.block.entity.BlockEntity be = server.getBlockEntity(pos);' + NL +
     '        List<ItemStack> drops = net.minecraft.world.level.block.Block.getDrops(' + NL +
     '                state, server, pos, be, this, this.getMainHandItem());' + NL +
     '        if (drops.isEmpty() && state.requiresCorrectToolForDrops()' + NL +
     '                && Config.CAT_GIRL_ALWAYS_DROPS.get()) {' + NL +
     '            ItemStack cheat = new ItemStack(axeLike' + NL +
     '                    ? net.minecraft.world.item.Items.NETHERITE_AXE' + NL +
     '                    : net.minecraft.world.item.Items.NETHERITE_PICKAXE);' + NL +
     '            drops = net.minecraft.world.level.block.Block.getDrops(state, server, pos, be, this, cheat);' + NL +
     '        }' + NL +
     '        server.destroyBlock(pos, false);' + NL +
     '        this.storeOrDrop(drops, pos);' + NL +
     '        this.playSound(SoundEvents.ITEM_PICKUP, 0.5F, 1.6F);' + NL +
     '    }' + NL + NL +
     '    /** 交易菜单用的催肥粒子（钱不够时的反馈）。 */'),
], 'CatGirlEntity')

# ---------------------------------------------------------------- WorkBlockGoal：半径 + 主人牵引
WBG = 'F:/mcmod/src/main/java/com/apocalypse/zombies/entity/ai/WorkBlockGoal.java'
edit(WBG, [
    ('    private BlockPos findBlock() {' + NL +
     '        int radius = Config.CAT_GIRL_WORK_RADIUS.get();',
     '    private BlockPos findBlock() {' + NL +
     '        // 取两者较大的那个：老存档里 work_radius 还是 12，光靠它她走不出院子。' + NL +
     '        int radius = Math.max(Config.CAT_GIRL_WORK_RADIUS.get(), Config.CAT_GIRL_AUTONOMY_RADIUS.get());'),
    ('    public boolean canUse() {' + NL +
     '        if (this.cat.getJob() != this.job) {' + NL +
     '            return false;' + NL +
     '        }',
     '    public boolean canUse() {' + NL +
     '        if (this.cat.getJob() != this.job) {' + NL +
     '            return false;' + NL +
     '        }' + NL +
     '        // 主人跑远了先跟人：她是随从，不该为了砍树把主人丢在地图另一头。' + NL +
     '        net.minecraft.world.entity.LivingEntity owner = this.cat.getOwner();' + NL +
     '        if (owner != null) {' + NL +
     '            double leash = Config.CAT_GIRL_AUTONOMY_RADIUS.get();' + NL +
     '            if (this.cat.distanceToSqr(owner) > leash * leash) {' + NL +
     '                return false;' + NL +
     '            }' + NL +
     '        }'),
], 'WorkBlockGoal')

# ---------------------------------------------------------------- Config
CFG = 'F:/mcmod/src/main/java/com/apocalypse/zombies/Config.java'
edit(CFG, [
    ('    public static final ForgeConfigSpec.IntValue CAT_GIRL_WORK_RADIUS;',
     '    public static final ForgeConfigSpec.IntValue CAT_GIRL_WORK_RADIUS;' + NL +
     '    /** 她能自己走出去找目标的半径（格）：比 work_radius 大，够她绕过一栋房子。 */' + NL +
     '    public static final ForgeConfigSpec.IntValue CAT_GIRL_AUTONOMY_RADIUS;' + NL +
     '    /** 开路：导航走不通时砸掉挡路的自然方块。 */' + NL +
     '    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_CLEAR_WAY;' + NL +
     '    /** 搭桥：前方是坑时用她自己背包里的实心方块铺落脚点。 */' + NL +
     '    public static final ForgeConfigSpec.BooleanValue CAT_GIRL_BRIDGE;' + NL +
     '    /** 她的跟随速度（原版跟班 1.15；主人冲刺时会被甩掉）。 */' + NL +
     '    public static final ForgeConfigSpec.DoubleValue CAT_GIRL_FOLLOW_SPEED;'),
    ('        CAT_GIRL_WORK_RADIUS = b.comment("伐木 / 挖矿时以她为中心的搜索半径（格）。")' + NL +
     '                .defineInRange("work_radius", 12, 4, 32);',
     '        CAT_GIRL_WORK_RADIUS = b.comment("伐木 / 挖矿时以她为中心的搜索半径（格）。")' + NL +
     '                .defineInRange("work_radius", 12, 4, 32);' + NL +
     '        CAT_GIRL_AUTONOMY_RADIUS = b.comment("她能自己走出去找目标的半径（格）—— 实际取它与 work_radius 的较大值，",' + NL +
     '                        "所以老存档里的 12 不会把她关在院子里。")' + NL +
     '                .defineInRange("autonomy_radius", 32, 8, 64);' + NL +
     '        CAT_GIRL_CLEAR_WAY = b.comment("开路：导航走不通时砸掉挡路的自然方块（原木/树叶/土/沙/圆石类，绝不碰箱子·熔炉·门）。")' + NL +
     '                .define("clear_way", true);' + NL +
     '        CAT_GIRL_BRIDGE = b.comment("搭桥：正前方是坑（深谷/水/岩浆）时，用她自己背包里的实心方块铺一格落脚点。")' + NL +
     '                .define("bridge", true);' + NL +
     '        CAT_GIRL_FOLLOW_SPEED = b.comment("她的跟随速度（原版跟班是 1.15，主人冲刺时会被甩掉）。注册期读一次，改完要重进世界。")' + NL +
     '                .defineInRange("follow_speed", 1.3D, 0.5D, 2.0D);'),

], 'Config')

print(NL + ('全部命中' if not fails else '失败 %d 条：' % len(fails)))
for f in fails:
    print('  [FAIL] ' + f)
Path('F:/mcmod/build/p174_note.txt').write_text(NL.join(fails), encoding='utf-8')

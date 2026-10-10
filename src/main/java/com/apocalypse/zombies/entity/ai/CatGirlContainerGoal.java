package com.apocalypse.zombies.entity.ai;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.CatGirlEntity;
import net.minecraft.core.BlockPos;
import net.minecraft.world.Container;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.item.ArmorItem;
import net.minecraft.world.item.BowItem;
import net.minecraft.world.item.CrossbowItem;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.ShieldItem;
import net.minecraft.world.item.TieredItem;
import net.minecraftforge.common.Tags;

import java.util.EnumSet;
import java.util.HashSet;
import java.util.Set;

/**
 * 用容器：把多余的成品塞进「她的储物点」，缺矿时再从里面拿。
 *
 * <h2>储物点是她自己的，不是随便哪个箱子</h2>
 * <p>原版判断不出「这个箱子是不是玩家的」，所以这里不做「看到她旁边有箱子就翻」这种事 ——
 * 储物点必须由主人用 {@code /apocalypse catgirl chest} 明确绑定（她看着的、最近的容器）。
 * 没绑定就完全不碰任何容器。</p>
 *
 * <h2>存什么</h2>
 * <ul>
 *   <li>只存<b>成品</b>：工具 / 武器 / 盔甲 / 弓弩 / 盾。</li>
 *   <li><b>每种至少留一件</b>（除非箱子里已经有了同类）—— 免得她把自己唯一那把镐子存进去、
 *       下一趟空手出门。</li>
 *   <li>矿石反过来：背包里矿石少于 {@link #WANT_ORES} 时从箱子里取一组（接着走内部熔炉）。</li>
 * </ul>
 */
public class CatGirlContainerGoal extends Goal {

    /** 走到这么近就能动手（格）。 */
    private static final double REACH = 3.0D;

    /** 两次存取之间的间隔（tick）。 */
    private static final int INTERVAL = 60;

    /** 背包里矿石少于这个数就从箱子里补。 */
    private static final int WANT_ORES = 4;

    private final CatGirlEntity cat;
    private int cooldown;

    public CatGirlContainerGoal(CatGirlEntity cat) {
        this.cat = cat;
        this.setFlags(EnumSet.of(Goal.Flag.MOVE, Goal.Flag.LOOK));
    }

    @Override
    public boolean canUse() {
        if (!Config.CAT_GIRL_CHEST.get() || this.cooldown > 0) {
            if (this.cooldown > 0) {
                this.cooldown--;
            }
            return false;
        }
        Container chest = this.chest();
        if (chest == null) {
            return false;
        }
        return this.hasProductToStore() || this.needsOre(chest);
    }

    @Override
    public boolean canContinueToUse() {
        return Config.CAT_GIRL_CHEST.get() && this.chest() != null;
    }

    @Override
    public void start() {
        this.cat.setTarget(null);
    }

    @Override
    public void tick() {
        BlockPos target = this.cat.getStorage();
        if (target == null) {
            return;
        }
        double distance = Math.sqrt(this.cat.distanceToSqr(
                target.getX() + 0.5D, target.getY() + 0.5D, target.getZ() + 0.5D));
        if (distance > REACH) {
            this.cat.getNavigation().moveTo(target.getX() + 0.5D, target.getY() + 0.5D,
                    target.getZ() + 0.5D, 1.0D);
            return;
        }
        this.cat.getNavigation().stop();
        this.cat.getLookControl().setLookAt(target.getX() + 0.5D, target.getY() + 0.5D,
                target.getZ() + 0.5D, 30.0F, 30.0F);
        Container chest = this.chest();
        if (chest == null) {
            return;
        }
        int moved = this.deposit(chest);
        int taken = this.withdrawOre(chest);
        if (moved > 0 || taken > 0) {
            this.cat.getGoods().setChanged();
            this.cat.playSound(net.minecraft.sounds.SoundEvents.ITEM_PICKUP, 0.5F, 1.5F);
        }
        this.cooldown = INTERVAL;
    }

    @Override
    public void stop() {
        this.cat.getNavigation().stop();
    }

    private Container chest() {
        BlockPos pos = this.cat.getStorage();
        if (pos == null) {
            return null;
        }
        var level = this.cat.level();
        return level.getBlockEntity(pos) instanceof Container container ? container : null;
    }

    /** 背包里有没有「多余到可以存起来」的成品。 */
    private boolean hasProductToStore() {
        var goods = this.cat.getGoods();
        Set<Item> seen = new HashSet<>();
        for (int i = 0; i < goods.getContainerSize(); i++) {
            ItemStack stack = goods.getItem(i);
            if (stack.isEmpty() || !isProduct(stack)) {
                continue;
            }
            if (!seen.add(stack.getItem())) {
                return true;    // 同类第二件：确定是多余的
            }
        }
        return false;
    }

    private boolean needsOre(Container chest) {
        return this.oreCount() < WANT_ORES && this.countIn(chest, Tags.Items.ORES) > 0;
    }

    /** 存进箱子；返回移动了几件。 */
    private int deposit(Container chest) {
        var goods = this.cat.getGoods();
        Set<Item> seen = new HashSet<>();
        int moved = 0;
        for (int i = 0; i < goods.getContainerSize(); i++) {
            ItemStack stack = goods.getItem(i);
            if (stack.isEmpty() || !isProduct(stack)) {
                continue;
            }
            boolean first = seen.add(stack.getItem());
            if (first && this.countIn(chest, stack.getItem()) == 0) {
                continue;   // 留一件在身上
            }
            ItemStack rest = this.insert(chest, stack.copy());
            int put = stack.getCount() - rest.getCount();
            if (put > 0) {
                stack.shrink(put);
                goods.setItem(i, stack.isEmpty() ? ItemStack.EMPTY : stack);
                moved += put;
            }
        }
        return moved;
    }

    /** 从箱子里取一组矿石；返回取了几件。 */
    private int withdrawOre(Container chest) {
        int need = WANT_ORES - this.oreCount();
        if (need <= 0) {
            return 0;
        }
        int taken = 0;
        for (int i = 0; i < chest.getContainerSize() && taken < need; i++) {
            ItemStack stack = chest.getItem(i);
            if (stack.isEmpty() || !stack.is(Tags.Items.ORES)) {
                continue;
            }
            int take = Math.min(need - taken, stack.getCount());
            ItemStack slice = stack.copyWithCount(take);
            ItemStack leftover = this.cat.getGoods().addItem(slice);
            int actual = take - leftover.getCount();
            if (actual > 0) {
                stack.shrink(actual);
                chest.setItem(i, stack.isEmpty() ? ItemStack.EMPTY : stack);
                taken += actual;
            }
            if (leftover.getCount() == take) {
                break;      // 她装不下，别在箱子里空转
            }
        }
        if (taken > 0) {
            chest.setChanged();
        }
        return taken;
    }

    /** 把 stack 放进箱子，返回没放下的部分。 */
    private ItemStack insert(Container chest, ItemStack stack) {
        for (int i = 0; i < chest.getContainerSize() && !stack.isEmpty(); i++) {
            ItemStack slot = chest.getItem(i);
            if (slot.isEmpty() || !ItemStack.isSameItemSameTags(slot, stack)) {
                continue;
            }
            int room = Math.min(slot.getMaxStackSize(), chest.getMaxStackSize()) - slot.getCount();
            if (room <= 0) {
                continue;
            }
            int put = Math.min(room, stack.getCount());
            slot.grow(put);
            stack.shrink(put);
            chest.setItem(i, slot);
        }
        for (int i = 0; i < chest.getContainerSize() && !stack.isEmpty(); i++) {
            if (!chest.getItem(i).isEmpty()) {
                continue;
            }
            int put = Math.min(chest.getMaxStackSize(), stack.getCount());
            chest.setItem(i, stack.copyWithCount(put));
            stack.shrink(put);
        }
        return stack;
    }

    private int oreCount() {
        return this.countIn(this.cat.getGoods(), Tags.Items.ORES);
    }

    private int countIn(Container container, net.minecraft.tags.TagKey<Item> tag) {
        int total = 0;
        for (int i = 0; i < container.getContainerSize(); i++) {
            ItemStack stack = container.getItem(i);
            if (!stack.isEmpty() && stack.is(tag)) {
                total += stack.getCount();
            }
        }
        return total;
    }

    private int countIn(Container container, Item item) {
        int total = 0;
        for (int i = 0; i < container.getContainerSize(); i++) {
            ItemStack stack = container.getItem(i);
            if (!stack.isEmpty() && stack.is(item)) {
                total += stack.getCount();
            }
        }
        return total;
    }

    /** 成品：工具 / 武器 / 盔甲 / 弓弩 / 盾。 */
    private static boolean isProduct(ItemStack stack) {
        return stack.getItem() instanceof TieredItem
                || stack.getItem() instanceof ArmorItem
                || stack.getItem() instanceof BowItem
                || stack.getItem() instanceof CrossbowItem
                || stack.getItem() instanceof ShieldItem
                || stack.is(net.minecraft.tags.ItemTags.SWORDS)
                || stack.is(Items.TRIDENT);
    }
}

# -*- coding: utf-8 -*-
"""1.1.68：修猫耳娘交互（蹲下优先 + 每步给反馈）+ 她的界面只显示她自己的部分。"""
from pathlib import Path

J = 'src/main/java/com/apocalypse/zombies/'

# ---------- ① mobInteract：蹲下优先 + 每个分支都给反馈 ----------
p = Path(J + 'entity/CatGirlEntity.java')
s = p.read_text(encoding='utf-8')
start = s.index('    public InteractionResult mobInteract(Player player, InteractionHand hand) {')
end = s.index('    /** 工具或武器：原版四大工具')
new_method = '''    public InteractionResult mobInteract(Player player, InteractionHand hand) {
        ItemStack stack = player.getItemInHand(hand);
        if (this.level().isClientSide) {
            return InteractionResult.SUCCESS;
        }

        // ---- 潜行右键：打开她自己的界面。刻意放在所有分支最前面 ----
        // 「蹲下点击」是玩家明确下达的指令，不该被「手里正好拿着把斧子」（交工具）或
        // 「正好拿着鱼」（喂食）吃掉；而且 shift 状态是每 tick 同步的，服务端有一两 tick 滞后，
        // 分支越靠前越不容易被抢 —— 这是「蹲下点击没反应 / 反而切了工种」的根因。
        if (player.isShiftKeyDown()) {
            if (!this.isTame()) {
                player.displayClientMessage(Component.translatable("cat_girl.not_tame"), true);
                return InteractionResult.CONSUME;
            }
            if (!this.isOwnedBy(player)) {
                player.displayClientMessage(Component.translatable("cat_girl.not_owner"), true);
                return InteractionResult.CONSUME;
            }
            if (player instanceof ServerPlayer serverPlayer) {
                // 1.20.1 的 ServerPlayer 只有 openMenu(MenuProvider)，没有带额外数据的 2 参重载；
                // 要把 entityId 同步给客户端菜单，得走 Forge 的 NetworkHooks.openScreen。
                net.minecraftforge.network.NetworkHooks.openScreen(serverPlayer,
                        new SimpleMenuProvider(
                                (id, inv, p) -> new CatGirlTradeMenu(id, inv, this.getId()),
                                this.getDisplayName()),
                        buf -> buf.writeVarInt(this.getId()));
            }
            return InteractionResult.CONSUME;
        }

        // ---- 未驯服：喂鱼即认主；拿别的东西点她也给一句话，不再静默无反应 ----
        if (!this.isTame()) {
            if (stack.is(ItemTags.FISHES)) {
                if (!player.getAbilities().instabuild) {
                    stack.shrink(1);
                }
                this.tame(player);
                this.navigation.stop();
                this.setTarget(null);
                this.level().broadcastEntityEvent(this, (byte) 7); // 爱心粒子
                this.playSound(SoundEvents.CAT_EAT, 1.0F, 1.0F);
                return InteractionResult.CONSUME;
            }
            player.displayClientMessage(Component.translatable("cat_girl.not_tame"), true);
            return InteractionResult.CONSUME;
        }

        // ---- 已驯服：只认主人（别人点她也要说明白）----
        if (!this.isOwnedBy(player)) {
            player.displayClientMessage(Component.translatable("cat_girl.not_owner"), true);
            return InteractionResult.CONSUME;
        }

        // 手里拿鱼：加餐回血（顺手当个治疗手段）
        if (stack.is(ItemTags.FISHES) && this.getHealth() < this.getMaxHealth()) {
            if (!player.getAbilities().instabuild) {
                stack.shrink(1);
            }
            this.heal(6.0F);
            this.playSound(SoundEvents.CAT_EAT, 1.0F, 1.0F);
            this.level().broadcastEntityEvent(this, (byte) 7);
            return InteractionResult.CONSUME;
        }

        // 手里拿工具 / 武器：交给她
        if (isToolOrWeapon(stack)) {
            ItemStack old = this.getMainHandItem().copy();
            this.setItemSlot(EquipmentSlot.MAINHAND, stack.split(1));
            if (!old.isEmpty()) {
                // 换下来的还回玩家背包（背包满了就掉在脚边）
                if (!player.getInventory().add(old)) {
                    player.drop(old, false);
                }
            }
            this.setAction(ACTION_EQUIP, 12);
            this.playSound(SoundEvents.ARMOR_EQUIP_LEATHER, 0.8F, 1.4F);
            return InteractionResult.CONSUME;
        }

        if (stack.isEmpty()) {
            // 空手右键：循环切换任务模式
            Job next = this.getJob().next();
            this.setJob(next);
            player.displayClientMessage(Component.translatable("cat_girl.job.switched",
                    this.getDisplayName(),
                    Component.translatable(next.langKey())), true);
            this.playSound(SoundEvents.CAT_PURR, 0.8F, 1.2F);
            return InteractionResult.CONSUME;
        }

        return InteractionResult.PASS;
    }

'''
s = s[:start] + new_method + s[end:]
p.write_text(s, encoding='utf-8')
print('(1) CatGirlEntity.mobInteract 重排完成')

# ---------- ② 菜单：玩家 27 格藏到面板外，快捷栏留在底部 ----------
p = Path(J + 'entity/menu/CatGirlTradeMenu.java')
s = p.read_text(encoding='utf-8')
old = """        // ---- 玩家背包 ----
        for (int row = 0; row < 3; row++) {
            for (int col = 0; col < 9; col++) {
                this.addSlot(new Slot(playerInventory, col + row * 9 + 9, 8 + col * 18, 144 + row * 18));
            }
        }
        for (int col = 0; col < 9; col++) {
            this.addSlot(new Slot(playerInventory, col, 8 + col * 18, 202));
        }"""
new = """        // ---- 玩家背包 ----
        // 她的界面按需求「只显示她自己的东西」：玩家那 27 格整块挪到面板外面（y 远在视区之下），
        // 槽位本身仍然存在 —— 所以 shift 一件件搬进背包、关界面把给予/合成格还回玩家都照常可用；
        // 但只把**快捷栏那一行**留在面板底部：不然界面上一个玩家来源格都没有，
        // 给予格要放东西、3x3 合成要拿材料，就全都没法填了。
        for (int row = 0; row < 3; row++) {
            for (int col = 0; col < 9; col++) {
                this.addSlot(new Slot(playerInventory, col + row * 9 + 9, 8 + col * 18,
                        HIDDEN_PLAYER_Y + row * 18));
            }
        }
        for (int col = 0; col < 9; col++) {
            this.addSlot(new Slot(playerInventory, col, 8 + col * 18, HOTBAR_Y));
        }"""
assert old in s, '菜单旧槽位代码没找到'
s = s.replace(old, new, 1)
anchor = '    public static final int GOODS_COUNT'
assert anchor in s, 'GOODS_COUNT 没找到'
s = s.replace(anchor, """    /** 面板高度（只有她的部分）：界面底部落在快捷栏那一行下面。 */
    public static final int PANEL_HEIGHT = 150;

    /** 快捷栏那一行在面板里的 y。 */
    public static final int HOTBAR_Y = 132;

    /** 玩家 27 格的 y 原点：远在面板之下 = 存在但不可见（shift 搬运只走槽位索引）。 */
    public static final int HIDDEN_PLAYER_Y = 10000;

""" + anchor, 1)
p.write_text(s, encoding='utf-8')
print('(2) CatGirlTradeMenu 槽位重排完成')

# ---------- ③ 屏幕：只画她的面板 ----------
p = Path(J + 'client/gui/CatGirlTradeScreen.java')
s = p.read_text(encoding='utf-8')
a = """        this.imageWidth = 176;
        this.imageHeight = 166;
        this.inventoryLabelY = this.imageHeight - 94;"""
b = """        this.imageWidth = 176;
        // 面板只包她自己的部分（交易行 / 库存行 / 底部快捷栏），玩家的 27 格不在这块面板里。
        this.imageHeight = CatGirlTradeMenu.PANEL_HEIGHT;
        // 玩家背包标题也挪出可视区：槽位已经藏在面板外，标题不该飘在别人的界面上。
        this.inventoryLabelY = 10000;"""
assert a in s, '屏幕构造没找到'
s = s.replace(a, b, 1)
a = """        for (net.minecraft.world.inventory.Slot slot : this.menu.slots) {
            guiGraphics.fill("""
b = """        for (net.minecraft.world.inventory.Slot slot : this.menu.slots) {
            if (slot.y >= this.imageHeight) {
                continue; // 面板外的槽（玩家的 27 格）不画
            }
            guiGraphics.fill("""
assert a in s, '槽位绘制循环没找到'
s = s.replace(a, b, 1)
a = """        guiGraphics.drawString(this.font, this.playerInventoryTitle, 8, this.inventoryLabelY, LABEL_DARK, false);"""
b = """        guiGraphics.drawString(this.font, Component.translatable("cat_girl.trade.hotbar"), 8, 121, LABEL_DARK, false);"""
assert a in s, '玩家背包标题行没找到'
s = s.replace(a, b, 1)
p.write_text(s, encoding='utf-8')
print('(3) CatGirlTradeScreen 只画她的面板')

# ---------- ④ lang ----------
lang = {
    'en_us.json': [
        ("cat_girl.not_tame", "She has not bonded with you yet - feed her a fish (any fish)."),
        ("cat_girl.not_owner", "She only answers to her owner."),
        ("cat_girl.trade.hotbar", "Hotbar"),
    ],
    'zh_cn.json': [
        ("cat_girl.not_tame", "她还没认主，喂她一条鱼（任何鱼类都行）"),
        ("cat_girl.not_owner", "她只认自己的主人"),
        ("cat_girl.trade.hotbar", "快捷栏"),
    ],
}
for f, kv in lang.items():
    p = Path('src/main/resources/assets/apocalypse_zombies/lang/' + f)
    s = p.read_text(encoding='utf-8')
    anchor = '  "cat_girl.trade.title"'
    assert anchor in s, f
    ins = ''.join('  "%s": "%s",\n' % (k, v) for k, v in kv)
    s = s.replace(anchor, ins + anchor, 1)
    p.write_text(s, encoding='utf-8')
    print('(4) lang %s +%d 键' % (f, len(kv)))

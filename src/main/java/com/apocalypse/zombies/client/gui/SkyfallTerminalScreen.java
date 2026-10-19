package com.apocalypse.zombies.client.gui;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.network.NetworkHandler;
import com.apocalypse.zombies.network.TerminalActionPacket;
import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import com.apocalypse.zombies.orbital.engine.StrikeProtocol;
import com.apocalypse.zombies.orbital.engine.StrikeProtocols;
import com.apocalypse.zombies.orbital.terminal.TerminalAction;
import com.apocalypse.zombies.orbital.terminal.TerminalState;
import net.minecraft.Util;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraftforge.registries.ForgeRegistries;

import java.util.Locale;

/**
 * 天陨指挥终端界面（v4.0 P2）。
 *
 * <h2>布局</h2>
 * <ul>
 *   <li><b>左：六边形协议轮盘</b> —— 六份协议（焚城 / 断层 / 隔离 / 蜂群 / 黎明 / 黑雨）按六边形
 *       顶点围成一圈，每个节点内直接写出协议名；已装核心按协议色点亮，未装核心灰暗并带小锁。
 *       中心是当前协议：大号协议名 + 英文代号 + 简易徽记。选中节点有一圈白色外框和呼吸光晕。</li>
 *   <li><b>右：参数面板</b> —— 半径 / 威力 / 下落速度三条滑条（百分比 50~200，
 *       {@link TerminalState#MULTIPLIER_MIN}~{@link TerminalState#MULTIPLIER_MAX}），
 *       半径额外显示按当前终端参数估算的格数；下面依次是当前协议、充能进度条、倒计时、
 *       已装核心数与终端主人。</li>
 *   <li><b>底部</b> —— {@code skyfall.gui.hint}；点未解锁节点时临时替换成
 *       「需要 xx 核心」的红色提示。P3 起充能区下方多一行「快速充能」提示：未充满时显示
 *       「红石块 · 快速充能：冷却缩短 N 秒」（物品取自 {@code skyfall_terminal.quick_charge_item}），
 *       充满后显示 {@code skyfall.terminal.ready_now}。</li>
 * </ul>
 *
 * <h2>数据方向</h2>
 * <p>这个界面<b>不持有权威状态</b>：滑条 / 节点 / 过场开关只发 {@link TerminalActionPacket}，
 * 服务端校验后回 {@code TerminalSyncPacket}，再由 {@code SkyfallClientHooks.onSync}
 * 调 {@link #update(TerminalState)} 换数据。拖动滑条时会先用本地草稿顶住显示，
 * 等服务端回包值与草稿一致就丢掉草稿 —— 这样拖动手感不会被网络往返拽回去。</p>
 *
 * <p><b>充能倒计时为什么要在客户端外推：</b>服务端只在包到达时打包一次 {@code gameTime}，
 * 之后充能期间不会再发包；直接读 {@link TerminalState#secondsLeft()} 会定格。
 * 这里用「客户端 gameTime - 收包时的客户端 gameTime」作为增量，加回快照里的服务端
 * {@code gameTime}，就能在两次回包之间把进度条和倒计时继续走完。</p>
 *
 * <p>纯客户端类，专用服务器不会加载。</p>
 */
public class SkyfallTerminalScreen extends Screen {

    // ------------------------------------------------------------------ 面板几何

    private static final int PANEL_W = 400;
    private static final int PANEL_H = 232;
    private static final int PANEL_MARGIN = 6;
    /** 轮盘中心相对面板左上角的偏移与半径（小屏会按面板尺寸夹紧）。 */
    private static final int WHEEL_OFFSET_X = 104;
    private static final int WHEEL_OFFSET_Y = 112;
    private static final int WHEEL_RADIUS = 60;
    /** 单个协议节点的外接圆半径。 */
    private static final int NODE_RADIUS = 17;

    // ------------------------------------------------------------------ 配色

    private static final int ACCENT = 0xFF7FE8FF;
    private static final int TEXT_TITLE = 0xFFCFF4FF;
    private static final int TEXT_LABEL = 0xFFA8C2CE;
    private static final int TEXT_VALUE = 0xFF8FE8FF;
    private static final int TEXT_DIM = 0xFF5E7A88;
    private static final int TEXT_GOOD = 0xFF7FFFA0;
    private static final int TEXT_WARN = 0xFFFFC15A;
    private static final int TEXT_BAD = 0xFFFF8080;
    private static final int PANEL_BORDER = 0xFF1E3D49;
    private static final int PANEL_FILL_TOP = 0xF00B1720;
    private static final int PANEL_FILL_BOTTOM = 0xF0070D12;
    private static final int NODE_FILL = 0xFF0A1419;
    private static final int NODE_LOCKED_RIM = 0xFF39444C;
    private static final int NODE_LOCKED_TEXT = 0xFF76858F;
    private static final int TRACK_FILL = 0xFF07141A;
    private static final int TRACK_EDGE = 0xFF1B3640;

    // ------------------------------------------------------------------ 协议节点表

    /**
     * 六份协议的顺序。
     *
     * <p>顺序和 {@code StrikeProtocols} 的 FILES 一致，旋转一周从正上方开始顺时针排。
     * 名字/英文代号/对应模式/主色全部从引擎的 {@link StrikeProtocols} 读（即
     * {@code assets/apocalypse_zombies/strike/*.xml} 里的 color），保证终端节点与 HUD 打击演出、
     * 协议核心图标同色；这里不另外维护一份调过色的近似值。</p>
     */
    private static final String[] PROTOCOL_IDS = {
            "cinder", "fault", "quarantine", "swarm", "dawn", "black_rain"
    };

    private record ProtocolNode(String id, OrbitalStrikeMode mode, String display, String codename, int tint) {
    }

    private static final ProtocolNode[] NODES = buildNodes();

    private static ProtocolNode[] buildNodes() {
        ProtocolNode[] nodes = new ProtocolNode[PROTOCOL_IDS.length];
        for (int i = 0; i < PROTOCOL_IDS.length; i++) {
            StrikeProtocol protocol = StrikeProtocols.byId(PROTOCOL_IDS[i]);
            nodes[i] = new ProtocolNode(PROTOCOL_IDS[i], protocol.mode(),
                    protocol.display(), protocol.codename(), protocol.color());
        }
        return nodes;
    }

    // ------------------------------------------------------------------ 状态

    private TerminalState state;
    private final BlockPos pos;

    /** 收包那一刻的客户端 gameTime / 墙钟：用来在两次回包之间外推充能进度。 */
    private long anchorGameTime = -1L;
    private long anchorMillis;

    /** 滑条草稿（非 null 表示「已发包、还没收到同值回包」）。 */
    private Integer radiusDraft;
    private Integer powerDraft;
    private Integer speedDraft;
    private long draftSentAt;
    /** 过场开关的本地先行值，回包一致后清掉。 */
    private Boolean filmDraft;
    private long filmSentAt;

    /** 正在拖的滑条；null = 没在拖。 */
    private Slider dragging;

    /** 底部临时提示（点未解锁节点时）。 */
    private Component notice;
    private long noticeUntil;

    /** 当前帧的面板布局（窗口改变时由 {@link #layout()} 重算）。 */
    private int panelX;
    private int panelY;
    private int panelW;
    private int panelH;
    private int wheelX;
    private int wheelY;
    private int wheelRadius;

    /** 三条滑条：操作码 + 语言键 + 顺序（顺序决定纵向位置）。 */
    private enum Slider {
        RADIUS(TerminalAction.RADIUS, "skyfall.gui.radius"),
        POWER(TerminalAction.POWER, "skyfall.gui.power"),
        SPEED(TerminalAction.SPEED, "skyfall.gui.speed");

        private final int action;
        private final String labelKey;

        Slider(int action, String labelKey) {
            this.action = action;
            this.labelKey = labelKey;
        }
    }

    public SkyfallTerminalScreen(TerminalState state) {
        super(Component.translatable("skyfall.gui.title"));
        this.state = state;
        this.pos = state.pos();
        anchorClock();
    }

    public BlockPos pos() {
        return pos;
    }

    /** 服务端回了新状态：只换数据，不重建界面（否则正在拖的滑条会被重置）。 */
    public void update(TerminalState state) {
        this.state = state;
        anchorClock();

        long now = Util.getMillis();
        // 服务端夹紧后的值等于草稿 -> 这一笔操作已经落地，草稿可以退休了。
        if (radiusDraft != null && radiusDraft == state.radiusPercent()) {
            radiusDraft = null;
        }
        if (powerDraft != null && powerDraft == state.powerPercent()) {
            powerDraft = null;
        }
        if (speedDraft != null && speedDraft == state.speedPercent()) {
            speedDraft = null;
        }
        if (filmDraft != null && filmDraft == state.filmOn()) {
            filmDraft = null;
        }
        // 兜底：服务器一直没回（掉线 / 被权限拒绝）时别让草稿永久顶住真实值。
        if (now - draftSentAt > 3000L) {
            radiusDraft = null;
            powerDraft = null;
            speedDraft = null;
        }
        if (now - filmSentAt > 3000L) {
            filmDraft = null;
        }
    }

    public TerminalState state() {
        return state;
    }

    @Override
    public boolean isPauseScreen() {
        return false;
    }

    @Override
    protected void init() {
        super.init();
        layout();
    }

    // ------------------------------------------------------------------ 布局

    private void layout() {
        panelW = Math.min(PANEL_W, Math.max(240, this.width - 2 * PANEL_MARGIN));
        panelH = Math.min(PANEL_H, Math.max(180, this.height - 2 * PANEL_MARGIN));
        panelX = (this.width - panelW) / 2;
        panelY = (this.height - panelH) / 2;

        wheelX = panelX + Math.min(WHEEL_OFFSET_X, panelW / 4 + 4);
        wheelY = panelY + Math.min(WHEEL_OFFSET_Y, panelH - 94);
        // 同时受面板高度（上下要留出标题/底部提示）和左列宽度（不能压到右侧参数栏）约束
        wheelRadius = Math.max(26, Math.min(WHEEL_RADIUS,
                Math.min(panelH / 2 - 56, panelW / 4 - 40)));
    }

    private int sideX0() {
        return panelX + panelW / 2 - 10;
    }

    private int sideX1() {
        return panelX + panelW - 12;
    }

    private int closeX() {
        return panelX + panelW - 52;
    }

    private static int sliderTrackY(int panelTop, Slider slider) {
        return panelTop + 48 + slider.ordinal() * 26;
    }

    private int nodeX(int index) {
        return (int) Math.round(wheelX + Math.cos(nodeAngle(index)) * wheelRadius);
    }

    private int nodeY(int index) {
        return (int) Math.round(wheelY + Math.sin(nodeAngle(index)) * wheelRadius);
    }

    private static double nodeAngle(int index) {
        return -Math.PI / 2.0D + index * (Math.PI / 3.0D);
    }

    // ------------------------------------------------------------------ 绘制主入口

    @Override
    public void render(GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
        layout();
        long now = Util.getMillis();
        if (notice != null && now >= noticeUntil) {
            notice = null;
        }

        drawBackdrop(graphics);
        drawPanel(graphics);
        drawHeader(graphics, mouseX, mouseY);
        drawWheel(graphics, mouseX, mouseY, now);
        drawSidePanel(graphics, mouseX, mouseY);
        drawFooter(graphics, now);

        super.render(graphics, mouseX, mouseY, partialTick);
        drawNodeTooltip(graphics, mouseX, mouseY);
    }

    // ------------------------------------------------------------------ 背景 / 面板 / 标题

    /** 不调用 {@code renderBackground}：终端界面自己铺一层冷色深空底，避开全局末日主题。 */
    private void drawBackdrop(GuiGraphics graphics) {
        graphics.fillGradient(0, 0, this.width, this.height, 0xFF05080C, 0xFF0A151D);
        // 屏幕中心的一团冷光（几层叠加的半透明矩形近似径向渐变）
        for (int i = 0; i < 5; i++) {
            int inset = 8 + i * 26;
            graphics.fill(inset, inset, this.width - inset, this.height - inset, 0x061F5E70);
        }
        // 科技网格 + 扫描线
        for (int x = 0; x < this.width; x += 48) {
            graphics.fill(x, 0, x + 1, this.height, 0x08143A46);
        }
        for (int y = 0; y < this.height; y += 48) {
            graphics.fill(0, y, this.width, y + 1, 0x08143A46);
        }
        for (int y = 0; y < this.height; y += 4) {
            graphics.fill(0, y, this.width, y + 1, 0x0A000000);
        }
    }

    private void drawPanel(GuiGraphics graphics) {
        graphics.fill(panelX - 4, panelY - 4, panelX + panelW + 4, panelY + panelH + 4, 0x66000000);
        graphics.fill(panelX, panelY, panelX + panelW, panelY + panelH, PANEL_BORDER);
        graphics.fillGradient(panelX + 1, panelY + 1, panelX + panelW - 1, panelY + panelH - 1,
                PANEL_FILL_TOP, PANEL_FILL_BOTTOM);
        // 顶部标题分隔线：一条暗线 + 左端一段亮青
        graphics.fill(panelX + 10, panelY + 25, panelX + panelW - 10, panelY + 26, 0x331E3D49);
        graphics.fill(panelX + 10, panelY + 25, panelX + 72, panelY + 26, ACCENT);
        // 四角切角
        drawBrackets(graphics, panelX, panelY, panelX + panelW, panelY + panelH, 12, 0xCC7FE8FF);
    }

    private static void drawBrackets(GuiGraphics graphics, int x1, int y1, int x2, int y2,
                                     int length, int color) {
        graphics.fill(x1, y1, x1 + length, y1 + 1, color);
        graphics.fill(x1, y1, x1 + 1, y1 + length, color);
        graphics.fill(x2 - length, y1, x2, y1 + 1, color);
        graphics.fill(x2 - 1, y1, x2, y1 + length, color);
        graphics.fill(x1, y2 - 1, x1 + length, y2, color);
        graphics.fill(x1, y2 - length, x1 + 1, y2, color);
        graphics.fill(x2 - length, y2 - 1, x2, y2, color);
        graphics.fill(x2 - 1, y2 - length, x2, y2, color);
    }

    private void drawHeader(GuiGraphics graphics, int mouseX, int mouseY) {
        graphics.drawString(font, this.title, panelX + 12, panelY + 8, TEXT_TITLE, true);

        Component subtitle = Component.translatable("skyfall.gui.subtitle", state.unlockedCount());
        graphics.drawString(font, subtitle, closeX() - 8 - font.width(subtitle), panelY + 8,
                TEXT_DIM, false);

        // 关闭按钮
        int bw = 44;
        int bh = 14;
        int bx = closeX();
        int by = panelY + 5;
        boolean hover = mouseX >= bx - 2 && mouseX < bx + bw + 2
                && mouseY >= by - 2 && mouseY < by + bh + 2;
        graphics.fill(bx - 1, by - 1, bx + bw + 1, by + bh + 1,
                hover ? 0xCC7FE8FF : 0x441E3D49);
        graphics.fill(bx, by, bx + bw, by + bh, hover ? 0xD01E4A5A : 0xB00D1A21);
        Component close = Component.translatable("skyfall.gui.close");
        graphics.drawString(font, close, bx + (bw - font.width(close)) / 2, by + 3,
                hover ? 0xFFFFFFFF : TEXT_LABEL, false);
    }

    // ------------------------------------------------------------------ 六边形轮盘

    private void drawWheel(GuiGraphics graphics, int mouseX, int mouseY, long now) {
        drawWheelOrbit(graphics, now);
        drawWheelLines(graphics, now);
        drawWheelCenter(graphics, now);
        for (int i = 0; i < NODES.length; i++) {
            drawNode(graphics, i, mouseX, mouseY, now);
        }
    }

    /** 轮盘外圈的一圈缓慢旋转的小点：远看像一台在扫描的终端。 */
    private void drawWheelOrbit(GuiGraphics graphics, long now) {
        int orbit = wheelRadius + 22;
        for (int i = 0; i < 36; i++) {
            double angle = i * (Math.PI * 2.0D / 36.0D) + now * 0.00045D;
            int x = (int) Math.round(wheelX + Math.cos(angle) * orbit);
            int y = (int) Math.round(wheelY + Math.sin(angle) * orbit);
            int color = (i % 9 == 0) ? 0x777FE8FF : 0x222E6472;
            graphics.fill(x, y, x + 2, y + 2, color);
        }
    }

    /** 节点之间的六边形连线（虚线）+ 中心到各节点的辐条 + 指向当前协议的选择线。 */
    private void drawWheelLines(GuiGraphics graphics, long now) {
        int dim = 0x332C5A6A;
        for (int i = 0; i < NODES.length; i++) {
            int next = (i + 1) % NODES.length;
            drawDashedLine(graphics, nodeX(i), nodeY(i), nodeX(next), nodeY(next), dim, 3, 4);
            drawDashedLine(graphics, wheelX, wheelY, nodeX(i), nodeY(i), 0x1E2C5A6A, 2, 6);
        }
        // 选中节点方向的一条亮线（呼吸）
        ProtocolNode current = nodeOf(state.selectedMode());
        if (current != null) {
            int index = indexOf(current);
            float pulse = 0.5F + 0.5F * (float) Math.sin(now * 0.0045D);
            int color = withAlpha(current.tint(), 60 + (int) (70 * pulse));
            drawLine(graphics, wheelX, wheelY, nodeX(index), nodeY(index), color);
            drawLine(graphics, wheelX + 1, wheelY + 1, nodeX(index) + 1, nodeY(index) + 1, color);
        }
    }

    private void drawWheelCenter(GuiGraphics graphics, long now) {
        ProtocolNode current = nodeOf(state.selectedMode());
        int tint = current != null ? current.tint() : ACCENT;

        float pulse = 0.5F + 0.5F * (float) Math.sin(now * 0.0035D);
        drawHex(graphics, wheelX, wheelY, 37 + (int) (pulse * 2.0F), withAlpha(tint, 26));
        drawHex(graphics, wheelX, wheelY, 35, withAlpha(tint, 120));
        drawHex(graphics, wheelX, wheelY, 33, NODE_FILL);
        drawHexOutline(graphics, wheelX, wheelY, 29, withAlpha(tint, 80));

        Component label = Component.translatable("skyfall.gui.selected");
        graphics.drawString(font, label, wheelX - font.width(label) / 2, wheelY - 28,
                TEXT_DIM, false);

        if (current != null) {
            drawEmblem(graphics, current.mode(), wheelX, wheelY - 11, withAlpha(tint, 0xDD));

            Component display = Component.literal(current.display());
            int displayWidth = font.width(display);
            var pose = graphics.pose();
            pose.pushPose();
            pose.translate(wheelX - displayWidth, wheelY - 2.0F, 0.0F);
            pose.scale(2.0F, 2.0F, 1.0F);
            graphics.drawString(font, display, 0, 0, tint, true);
            pose.popPose();

            String code = current.id().replace('_', ' ').toUpperCase(Locale.ROOT);
            graphics.drawString(font, code, wheelX - font.width(code) / 2, wheelY + 18,
                    withAlpha(tint, 0xAA), false);
        }
    }

    private void drawNode(GuiGraphics graphics, int index, int mouseX, int mouseY, long now) {
        ProtocolNode node = NODES[index];
        int nx = nodeX(index);
        int ny = nodeY(index);
        boolean unlocked = state.unlocked(node.mode());
        boolean selected = state.selectedMode() == node.mode();
        boolean hovered = Math.hypot(mouseX - nx, mouseY - ny) <= NODE_RADIUS + 6;
        int tint = unlocked ? node.tint() : NODE_LOCKED_RIM;

        if (selected) {
            // 呼吸光晕：选中节点明显比其它节点亮一圈
            float pulse = 0.5F + 0.5F * (float) Math.sin(now * 0.0045D);
            drawHex(graphics, nx, ny, NODE_RADIUS + 10 + (int) (pulse * 3.0F),
                    withAlpha(tint, 26 + (int) (34 * pulse)));
            drawHex(graphics, nx, ny, NODE_RADIUS + 4, withAlpha(tint, 70));
        } else if (hovered) {
            drawHex(graphics, nx, ny, NODE_RADIUS + 4, withAlpha(ACCENT, 45));
        }

        // 外圈协议色 + 深色内盘
        drawHex(graphics, nx, ny, NODE_RADIUS, tint);
        drawHex(graphics, nx, ny, NODE_RADIUS - 3, NODE_FILL);
        drawHexOutline(graphics, nx, ny, NODE_RADIUS - 5,
                withAlpha(unlocked ? tint : NODE_LOCKED_RIM, 90));

        Component name = Component.literal(node.display());
        graphics.drawString(font, name, nx - font.width(name) / 2, ny - 4,
                unlocked ? tint : NODE_LOCKED_TEXT, false);
        if (!unlocked) {
            drawLock(graphics, nx, ny + 9, hovered);
        }

        if (selected) {
            drawHexOutline(graphics, nx, ny, NODE_RADIUS + 2, 0xFFE8FBFF);
            // 节点下方的小三角：当前协议指示
            graphics.fill(nx - 3, ny + NODE_RADIUS + 7, nx + 4, ny + NODE_RADIUS + 8, tint);
            graphics.fill(nx - 2, ny + NODE_RADIUS + 8, nx + 3, ny + NODE_RADIUS + 9, tint);
            graphics.fill(nx - 1, ny + NODE_RADIUS + 9, nx + 2, ny + NODE_RADIUS + 10, tint);
        }
    }

    /** 小锁：未装核心的节点用，锁梁 + 锁体 + 锁孔。 */
    private static void drawLock(GuiGraphics graphics, int cx, int cy, boolean hot) {
        int color = hot ? 0xFFAFC4CF : 0xFF5E6E79;
        int bx = cx - 4;
        graphics.fill(bx + 1, cy - 5, bx + 2, cy, color);
        graphics.fill(bx + 7, cy - 5, bx + 8, cy, color);
        graphics.fill(bx + 1, cy - 6, bx + 8, cy - 5, color);
        graphics.fill(bx, cy, bx + 9, cy + 7, color);
        graphics.fill(bx + 1, cy + 1, bx + 8, cy + 6, 0xFF16232B);
        graphics.fill(bx + 4, cy + 2, bx + 5, cy + 4, color);
    }

    /** 中心大徽记：用方块拼出每份协议最直观的轮廓（不依赖贴图）。 */
    private static void drawEmblem(GuiGraphics graphics, OrbitalStrikeMode mode, int cx, int cy, int color) {
        switch (mode) {
            case CANNON -> {
                // 向下贯穿的动能矛
                graphics.fill(cx - 1, cy - 7, cx + 1, cy + 3, color);
                graphics.fill(cx - 4, cy + 3, cx + 5, cy + 5, color);
                graphics.fill(cx - 2, cy + 5, cx + 3, cy + 7, color);
            }
            case LANCE -> {
                // 细长裂谷 + 尖端
                graphics.fill(cx, cy - 8, cx + 1, cy + 4, color);
                graphics.fill(cx - 2, cy + 4, cx + 3, cy + 6, color);
                graphics.fill(cx - 3, cy + 6, cx + 4, cy + 7, color);
            }
            case GRAVITY -> {
                // 引力环 + 中心奇点
                drawHexOutline(graphics, cx, cy, 6, color);
                graphics.fill(cx - 1, cy - 1, cx + 2, cy + 2, color);
            }
            case STORM -> {
                // 三个落点（蜂群）
                graphics.fill(cx - 6, cy - 4, cx - 3, cy - 1, color);
                graphics.fill(cx + 3, cy - 4, cx + 6, cy - 1, color);
                graphics.fill(cx - 2, cy + 2, cx + 2, cy + 5, color);
            }
            case LASER -> {
                // 十字光束（黎明）
                graphics.fill(cx - 1, cy - 8, cx + 1, cy + 8, color);
                graphics.fill(cx - 7, cy - 1, cx + 8, cy + 1, color);
            }
            case PLANET -> {
                // 行星 + 环（黑雨）
                drawHex(graphics, cx, cy, 5, color);
                graphics.fill(cx - 8, cy, cx + 8, cy + 1, color);
                graphics.fill(cx - 6, cy + 2, cx + 6, cy + 3, withAlpha(color, 0x88));
            }
        }
    }

    // ------------------------------------------------------------------ 右侧参数面板

    private void drawSidePanel(GuiGraphics graphics, int mouseX, int mouseY) {
        int x0 = sideX0();
        int x1 = sideX1();

        for (Slider slider : Slider.values()) {
            drawSlider(graphics, x0, x1, slider, mouseX, mouseY);
        }
        drawFilmRow(graphics, x0, x1, mouseX, mouseY);

        graphics.fill(x0, panelY + 134, x1, panelY + 135, 0x441E3D49);

        // —— 当前协议
        int statusY = panelY + 140;
        graphics.drawString(font, Component.translatable("skyfall.gui.selected"), x0, statusY,
                TEXT_DIM, false);
        ProtocolNode current = nodeOf(state.selectedMode());
        if (current != null) {
            graphics.drawString(font, Component.literal(current.display()), x0, statusY + 11,
                    current.tint(), true);
            String code = current.id().replace('_', ' ').toUpperCase(Locale.ROOT);
            graphics.drawString(font, code, x1 - font.width(code), statusY + 11, TEXT_DIM, false);
        }

        // —— 充能进度条
        float progress = chargeProgressNow();
        boolean ready = readyNow();
        int chargeY = panelY + 163;
        graphics.drawString(font, Component.translatable("skyfall.gui.charge",
                Math.round(progress * 100.0F)), x0, chargeY, TEXT_LABEL, false);

        int barY = chargeY + 10;
        int barH = 8;
        graphics.fill(x0 - 1, barY - 1, x1 + 1, barY + barH + 1, TRACK_EDGE);
        graphics.fill(x0, barY, x1, barY + barH, TRACK_FILL);
        int barWidth = Math.max(0, x1 - x0 - 2);
        int filled = Math.round(barWidth * Mth.clamp(progress, 0.0F, 1.0F));
        if (filled > 0) {
            int barColor = ready ? 0xFF7FFFA0 : (progress > 0.66F ? 0xFF7FE8FF : 0xFF3F9FB8);
            graphics.fill(x0 + 1, barY + 1, x0 + 1 + filled, barY + barH - 1, barColor);
            graphics.fill(x0 + 1 + Math.max(0, filled - 2), barY, x0 + 1 + filled,
                    barY + barH, 0xFFFFFFFF);
        }
        for (int i = 1; i < 10; i++) {
            int tickX = x0 + (x1 - x0) * i / 10;
            graphics.fill(tickX, barY + 1, tickX + 1, barY + barH - 1, 0x44000000);
        }

        // —— 倒计时 / 就绪
        int statusLine = panelY + 187;
        if (ready) {
            graphics.drawString(font, Component.translatable("skyfall.gui.ready"), x0, statusLine,
                    TEXT_GOOD, true);
        } else {
            graphics.drawString(font, Component.translatable("skyfall.gui.charging", secondsLeftNow()),
                    x0, statusLine, TEXT_WARN, false);
        }

        // —— 终端主人
        String owner = state.ownerName();
        Component ownerLine = Component.translatable("skyfall.gui.owner",
                owner == null || owner.isBlank() ? "-" : owner);
        graphics.drawString(font, ownerLine, x0, panelY + 197, TEXT_DIM, false);

        // —— 快速充能提示（v4.0 P3）：未就绪时告诉玩家还能用红石块加速，就绪时提示可以开火。
        drawQuickChargeHint(graphics, ready);
    }

    /**
     * 底部一条横跨面板的快速充能提示（v4.0 P3）。
     *
     * <p>未就绪：「红石块 · 快速充能：冷却缩短 15 秒」（物品名从
     * {@code skyfall_terminal.quick_charge_item} 解析，配置换了物品提示也跟着变）；
     * 已就绪：「终端已经充满，随时可以授权打击」。功能被配置关掉时这条不出现 ——
     * 不宣传一个按不动的交互。</p>
     */
    private void drawQuickChargeHint(GuiGraphics graphics, boolean ready) {
        Component line;
        int color;
        if (ready) {
            line = Component.translatable("skyfall.terminal.ready_now");
            color = TEXT_GOOD;
        } else {
            if (!Config.TERMINAL_QUICK_CHARGE_ENABLED.get()) {
                return;
            }
            Component quick = Component.translatable("skyfall.terminal.quick_charge",
                    Config.TERMINAL_QUICK_CHARGE_SECONDS.get());
            line = quickChargeItemName().copy().append(" · ").append(quick);
            color = TEXT_WARN;
        }
        int available = panelW - 24;
        int x = panelX + (panelW - font.width(line)) / 2;
        if (font.width(line) > available) {
            // 语言包或模组物品名特别长时截断，宁可少显示也不越过面板。
            String truncated = font.plainSubstrByWidth(line.getString(), available);
            graphics.drawString(font, truncated,
                    panelX + (panelW - font.width(truncated)) / 2, panelY + 207, color, false);
            return;
        }
        graphics.drawString(font, line, x, panelY + 207, color, false);
    }

    /** 快速充能物品的本地化名字；配置里的 id 解析不出来时退回显示原始 id。 */
    private Component quickChargeItemName() {
        String raw = Config.TERMINAL_QUICK_CHARGE_ITEM.get();
        ResourceLocation id = ResourceLocation.tryParse(raw == null ? "" : raw.trim());
        Item item = id == null ? null : ForgeRegistries.ITEMS.getValue(id);
        if (item == null) {
            return Component.literal(raw == null ? "?" : raw.trim());
        }
        return new ItemStack(item).getHoverName();
    }

    /** 一条滑条：上行是标签 + 百分比，下行是轨道、刻度和滑块头。 */
    private void drawSlider(GuiGraphics graphics, int x0, int x1, Slider slider,
                            int mouseX, int mouseY) {
        int trackY = sliderTrackY(panelY, slider);
        int labelY = trackY - 12;
        int value = displayedPercent(slider);
        boolean hot = slider == dragging || pointInTrack(slider, mouseX, mouseY);

        graphics.drawString(font, Component.translatable(slider.labelKey), x0, labelY,
                TEXT_LABEL, false);
        String text = slider == Slider.RADIUS
                ? value + "% [" + radiusBlocks() + "]"
                : value + "%";
        graphics.drawString(font, text, x1 - font.width(text), labelY,
                hot ? 0xFFFFFFFF : TEXT_VALUE, false);

        int trackH = 6;
        graphics.fill(x0, trackY, x1, trackY + trackH, TRACK_FILL);
        graphics.fill(x0, trackY, x1, trackY + 1, 0x661B3640);

        int span = TerminalState.MULTIPLIER_MAX - TerminalState.MULTIPLIER_MIN;
        int filled = Math.round((x1 - x0) * (value - TerminalState.MULTIPLIER_MIN) / (float) span);
        graphics.fill(x0, trackY, x0 + Math.max(2, filled), trackY + trackH,
                withAlpha(TEXT_VALUE, hot ? 0xCC : 0x88));

        for (int i = 0; i <= 6; i++) {
            int tickX = x0 + (x1 - x0) * i / 6;
            graphics.fill(tickX, trackY - 1, tickX + 1, trackY + trackH + 1, 0x551B3640);
        }

        int headX = x0 + filled;
        graphics.fill(headX - 2, trackY - 3, headX + 3, trackY + trackH + 3,
                hot ? 0xFFFFFFFF : 0xFFB8F0FF);
        graphics.fill(headX - 1, trackY - 2, headX + 2, trackY + trackH + 2, ACCENT);
    }

    private void drawFilmRow(GuiGraphics graphics, int x0, int x1, int mouseX, int mouseY) {
        int y = panelY + 114;
        graphics.drawString(font, Component.translatable("skyfall.gui.film"), x0, y + 3,
                TEXT_LABEL, false);

        boolean on = filmOn();
        int bw = 56;
        int bh = 16;
        int bx = x1 - bw;
        boolean hover = mouseX >= bx - 2 && mouseX < bx + bw + 2
                && mouseY >= y - 2 && mouseY < y + bh + 2;

        graphics.fill(bx - 1, y - 1, bx + bw + 1, y + bh + 1,
                hover ? 0xAA7FE8FF : TRACK_EDGE);
        graphics.fill(bx, y, bx + bw, y + bh, on ? 0xD0164552 : 0xD01A2329);
        int knobX = on ? bx + bw - 14 : bx + 2;
        graphics.fill(knobX, y + 2, knobX + 12, y + bh - 2, on ? ACCENT : 0xFF44545E);

        Component stateText = Component.translatable(on ? "skyfall.gui.on" : "skyfall.gui.off");
        int center = on ? bx + (bw - 16) / 2 : bx + 16 + (bw - 16) / 2;
        graphics.drawString(font, stateText, center - font.width(stateText) / 2, y + 4,
                on ? ACCENT : TEXT_LABEL, false);
    }

    // ------------------------------------------------------------------ 底部提示

    private void drawFooter(GuiGraphics graphics, long now) {
        Component text = Component.translatable("skyfall.gui.hint");
        int color = TEXT_DIM;
        if (notice != null && now < noticeUntil) {
            text = notice;
            color = TEXT_BAD;
        }
        graphics.drawString(font, text, panelX + (panelW - font.width(text)) / 2,
                panelY + 218, color, true);
    }

    // ------------------------------------------------------------------ 悬浮提示

    private void drawNodeTooltip(GuiGraphics graphics, int mouseX, int mouseY) {
        int index = nodeIndexAt(mouseX, mouseY);
        if (index < 0) {
            return;
        }
        ProtocolNode node = NODES[index];
        Component first = Component.literal(node.codename());
        Component second = state.unlocked(node.mode())
                ? null
                : Component.translatable("skyfall.gui.need_core", node.display());
        int w = font.width(first) + 10;
        if (second != null) {
            w = Math.max(w, font.width(second) + 10);
        }
        int h = second == null ? 17 : 29;
        int x = mouseX + 10;
        int y = mouseY + 8;
        if (x + w > this.width - 4) {
            x = mouseX - w - 10;
        }
        if (y + h > this.height - 4) {
            y = mouseY - h - 8;
        }
        graphics.fill(x - 1, y - 1, x + w + 1, y + h + 1, 0xCC2C6A7A);
        graphics.fill(x, y, x + w, y + h, 0xF00A141A);
        graphics.drawString(font, first, x + 5, y + 4, node.tint(), false);
        if (second != null) {
            graphics.drawString(font, second, x + 5, y + 16, TEXT_BAD, false);
        }
    }

    // ------------------------------------------------------------------ 输入

    @Override
    public boolean mouseClicked(double mouseX, double mouseY, int button) {
        if (button != 0) {
            return super.mouseClicked(mouseX, mouseY, button);
        }
        // 关闭按钮
        int bw = 44;
        int bh = 14;
        if (mouseX >= closeX() && mouseX < closeX() + bw
                && mouseY >= panelY + 5 && mouseY < panelY + 5 + bh) {
            onClose();
            return true;
        }
        // 协议节点
        int nodeIndex = nodeIndexAt(mouseX, mouseY);
        if (nodeIndex >= 0) {
            clickNode(nodeIndex);
            return true;
        }
        // 过场开关
        int filmX = sideX1() - 56;
        int filmY = panelY + 114;
        if (mouseX >= filmX && mouseX < filmX + 56 && mouseY >= filmY && mouseY < filmY + 16) {
            toggleFilm();
            return true;
        }
        // 滑条
        Slider slider = sliderAt(mouseX, mouseY);
        if (slider != null) {
            dragging = slider;
            updateSlider(slider, mouseX);
            return true;
        }
        return super.mouseClicked(mouseX, mouseY, button);
    }

    @Override
    public boolean mouseDragged(double mouseX, double mouseY, int button, double dragX, double dragY) {
        if (dragging != null && button == 0) {
            updateSlider(dragging, mouseX);
            return true;
        }
        return super.mouseDragged(mouseX, mouseY, button, dragX, dragY);
    }

    @Override
    public boolean mouseReleased(double mouseX, double mouseY, int button) {
        if (dragging != null) {
            Slider slider = dragging;
            dragging = null;
            updateSlider(slider, mouseX);
            return true;
        }
        return super.mouseReleased(mouseX, mouseY, button);
    }

    /** 点节点：已解锁 -> 发 SELECT；未解锁 -> 不发包，底部提示「需要 xx 核心」。 */
    private void clickNode(int index) {
        ProtocolNode node = NODES[index];
        if (!state.unlocked(node.mode())) {
            notice = Component.translatable("skyfall.gui.need_core", node.display());
            noticeUntil = Util.getMillis() + 2600L;
            return;
        }
        if (state.selectedMode() == node.mode()) {
            return;
        }
        send(TerminalAction.SELECT, node.mode().ordinal());
    }

    private void toggleFilm() {
        boolean next = !filmOn();
        filmDraft = next;
        filmSentAt = Util.getMillis();
        send(TerminalAction.FILM, next ? 1 : 0);
    }

    /** 把鼠标 x 映射成 50~200 的百分比；值真的变了才发包（拖动节流就靠这一句）。 */
    private void updateSlider(Slider slider, double mouseX) {
        int x0 = sideX0();
        int x1 = sideX1();
        float ratio = (float) ((mouseX - x0) / Math.max(1.0D, (double) (x1 - x0)));
        ratio = Mth.clamp(ratio, 0.0F, 1.0F);
        int value = TerminalState.MULTIPLIER_MIN
                + Math.round(ratio * (TerminalState.MULTIPLIER_MAX - TerminalState.MULTIPLIER_MIN));
        if (value == displayedPercent(slider)) {
            return;
        }
        storeDraft(slider, value);
        draftSentAt = Util.getMillis();
        send(slider.action, value);
    }

    private void send(int action, int value) {
        NetworkHandler.CHANNEL.sendToServer(new TerminalActionPacket(pos, action, value));
    }

    // ------------------------------------------------------------------ 命中测试

    private int nodeIndexAt(double mouseX, double mouseY) {
        for (int i = 0; i < NODES.length; i++) {
            if (Math.hypot(mouseX - nodeX(i), mouseY - nodeY(i)) <= NODE_RADIUS + 6) {
                return i;
            }
        }
        return -1;
    }

    private boolean pointInTrack(Slider slider, double mouseX, double mouseY) {
        int x0 = sideX0();
        int x1 = sideX1();
        int trackY = sliderTrackY(panelY, slider);
        return mouseX >= x0 - 4 && mouseX <= x1 + 4
                && mouseY >= trackY - 5 && mouseY <= trackY + 11;
    }

    private Slider sliderAt(double mouseX, double mouseY) {
        for (Slider slider : Slider.values()) {
            if (pointInTrack(slider, mouseX, mouseY)) {
                return slider;
            }
        }
        return null;
    }

    // ------------------------------------------------------------------ 数据草稿

    private int displayedPercent(Slider slider) {
        Integer draft = draftOf(slider);
        return draft != null ? draft : statePercent(slider);
    }

    private Integer draftOf(Slider slider) {
        return switch (slider) {
            case RADIUS -> radiusDraft;
            case POWER -> powerDraft;
            case SPEED -> speedDraft;
        };
    }

    private void storeDraft(Slider slider, int value) {
        switch (slider) {
            case RADIUS -> radiusDraft = value;
            case POWER -> powerDraft = value;
            case SPEED -> speedDraft = value;
        }
    }

    private int statePercent(Slider slider) {
        return switch (slider) {
            case RADIUS -> state.radiusPercent();
            case POWER -> state.powerPercent();
            case SPEED -> state.speedPercent();
        };
    }

    private boolean filmOn() {
        return filmDraft != null ? filmDraft : state.filmOn();
    }

    /**
     * 按服务端 {@code SkyfallTerminalBlockEntity#radius()} 同一套算法估算当前半径格数，
     * 只用于显示。真正生效的值以服务端夹紧结果为准（专用服务器上客户端本地配置可能不同）。
     */
    private int radiusBlocks() {
        int base = Mth.clamp(Config.ORBITAL_STRIKE_RADIUS.get(), 1, 96);
        int scaled = Math.round(state.selectedMode().radius(base)
                * (displayedPercent(Slider.RADIUS) / 100.0F));
        int cap = Mth.clamp(Config.TERMINAL_RADIUS_MAX.get(), 1, 96);
        return Mth.clamp(scaled, 1, Math.max(cap, 1));
    }

    // ------------------------------------------------------------------ 时间（外推充能）

    private void anchorClock() {
        Minecraft minecraft = Minecraft.getInstance();
        this.anchorGameTime = minecraft.level != null ? minecraft.level.getGameTime() : -1L;
        this.anchorMillis = Util.getMillis();
    }

    /**
     * 把「收包后经过的客户端 tick」加回快照里的服务端 gameTime。
     *
     * <p>没有客户端世界时（理论上不会，界面只在世界里打开）回落到墙钟 20 tick/s。</p>
     */
    private long effectiveGameTime() {
        Minecraft minecraft = Minecraft.getInstance();
        long elapsed;
        if (anchorGameTime >= 0L && minecraft.level != null) {
            elapsed = minecraft.level.getGameTime() - anchorGameTime;
        } else {
            elapsed = (Util.getMillis() - anchorMillis) / 50L;
        }
        return state.gameTime() + Math.max(0L, elapsed);
    }

    private boolean readyNow() {
        return effectiveGameTime() >= state.readyAt();
    }

    private int secondsLeftNow() {
        long ticks = Math.max(0L, state.readyAt() - effectiveGameTime());
        return (int) ((ticks + 19L) / 20L);
    }

    private float chargeProgressNow() {
        if (state.chargeTicks() <= 0 || readyNow()) {
            return 1.0F;
        }
        float remaining = (float) Math.max(0L, state.readyAt() - effectiveGameTime())
                / (float) state.chargeTicks();
        return Mth.clamp(1.0F - remaining, 0.0F, 1.0F);
    }

    // ------------------------------------------------------------------ 几何/颜色小工具

    /** 用逐行 fill 近似一个尖顶六边形（半径 r，越高越接近正六边形）。 */
    private static void drawHex(GuiGraphics graphics, int cx, int cy, int r, int color) {
        if (r <= 0) {
            return;
        }
        int halfWidth = Math.round(r * 0.8660254F);
        int shoulder = Math.max(1, r / 2);
        for (int dy = -r; dy < r; dy++) {
            int distance = Math.abs(dy);
            int hw = distance <= shoulder
                    ? halfWidth
                    : Math.round(halfWidth * (r - distance) / (float) Math.max(1, r - shoulder));
            if (hw <= 0) {
                continue;
            }
            graphics.fill(cx - hw, cy + dy, cx + hw, cy + dy + 1, color);
        }
    }

    private static void drawHexOutline(GuiGraphics graphics, int cx, int cy, int r, int color) {
        int halfWidth = Math.round(r * 0.8660254F);
        int[] xs = {cx, cx + halfWidth, cx + halfWidth, cx, cx - halfWidth, cx - halfWidth};
        int[] ys = {cy - r, cy - r / 2, cy + r / 2, cy + r, cy + r / 2, cy - r / 2};
        for (int i = 0; i < 6; i++) {
            int next = (i + 1) % 6;
            drawLine(graphics, xs[i], ys[i], xs[next], ys[next], color);
        }
    }

    private static void drawLine(GuiGraphics graphics, int x1, int y1, int x2, int y2, int color) {
        int dx = x2 - x1;
        int dy = y2 - y1;
        int steps = Math.max(Math.abs(dx), Math.abs(dy));
        if (steps == 0) {
            graphics.fill(x1, y1, x1 + 1, y1 + 1, color);
            return;
        }
        for (int i = 0; i <= steps; i++) {
            float t = i / (float) steps;
            int x = x1 + Math.round(dx * t);
            int y = y1 + Math.round(dy * t);
            graphics.fill(x, y, x + 1, y + 1, color);
        }
    }

    private static void drawDashedLine(GuiGraphics graphics, int x1, int y1, int x2, int y2,
                                       int color, int dash, int gap) {
        int dx = x2 - x1;
        int dy = y2 - y1;
        int steps = Math.max(Math.abs(dx), Math.abs(dy));
        if (steps == 0) {
            return;
        }
        int period = Math.max(1, dash + gap);
        for (int i = 0; i <= steps; i++) {
            if ((i % period) >= dash) {
                continue;
            }
            float t = i / (float) steps;
            int x = x1 + Math.round(dx * t);
            int y = y1 + Math.round(dy * t);
            graphics.fill(x, y, x + 1, y + 1, color);
        }
    }

    private static int withAlpha(int color, int alpha) {
        return ((Mth.clamp(alpha, 0, 255)) << 24) | (color & 0xFFFFFF);
    }

    private static ProtocolNode nodeOf(OrbitalStrikeMode mode) {
        for (ProtocolNode node : NODES) {
            if (node.mode() == mode) {
                return node;
            }
        }
        return null;
    }

    private static int indexOf(ProtocolNode node) {
        for (int i = 0; i < NODES.length; i++) {
            if (NODES[i] == node) {
                return i;
            }
        }
        return 0;
    }
}

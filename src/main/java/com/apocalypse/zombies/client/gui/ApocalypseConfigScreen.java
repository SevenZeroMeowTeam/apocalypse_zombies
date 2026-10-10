package com.apocalypse.zombies.client.gui;

import java.util.ArrayList;
import java.util.List;

import com.apocalypse.zombies.Config;

import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.components.EditBox;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;
import net.minecraftforge.common.ForgeConfigSpec;

/**
 * 模组配置界面（「模组列表 → 配置」按钮进来的那张，1.1.79）。
 *
 * <p>Forge 从 1.19 起删掉了内置的配置编辑器，所以这张界面是自己画的：直接读
 * {@link Config#values()}（声明顺序），按顶层段分组列出<b>全部 151 项</b>，
 * 改完点「完成」写回同一份 {@code config/apocalypse_zombies-common.toml}，
 * 也就是说 —— 图形界面和手改 TOML 是同一份配置，不存在两套。</p>
 *
 * <p>控件按值的类型挑：布尔 → 开/关按钮；整数/小数 → 数字输入框；
 * 列表 → 逗号分隔的输入框；其余 → 只读展示。整数会被 Forge 在读取时按配置里声明的
 * 范围夹一次（例如 {@code mine_radius} 4~64、{@code mine_max_blocks} 1~64），
 * 所以这里填超范围不会把游戏搞坏，只会被夹回去。</p>
 *
 * <p>滚轮翻页。翻页会重建控件，所以滚动前先把输入框里的字抄回行里
 * （{@link #stash()}）—— 不然一手滚轮就把刚打的数字抹了。</p>
 */
public class ApocalypseConfigScreen extends Screen {

    private static final int ROW_H = 22;
    private static final int LIST_TOP = 46;
    private static final int BOTTOM = 34;
    private static final int NUM_W = 64;
    private static final int TEXT_W = 240;

    private static final int TITLE_COLOR = 0xFFFFFFFF;
    private static final int SECTION_COLOR = 0xFF8FD3FF;
    private static final int LABEL_COLOR = 0xFFE6E6E6;
    private static final int VALUE_COLOR = 0xFFA9C7A9;
    private static final int HINT_COLOR = 0xFF8A8A8A;
    private static final int WARN_COLOR = 0xFFE8B04A;

    private final Screen parent;
    private final List<Object> items = new ArrayList<>();
    private int scroll;
    private String notice = "";

    public ApocalypseConfigScreen(Screen parent) {
        super(Component.translatable("cat_girl.config.title"));
        this.parent = parent;
        build();
    }

    // ------------------------------------------------------------------ 行模型

    private enum Kind { BOOL, NUM, TEXT, LIST, READONLY }

    /** 一行 = 一个配置项。{@code text}/{@code draft} 是「界面上的草稿」，点完成才落盘。 */
    private static final class Row {
        final ForgeConfigSpec.ConfigValue<?> value;
        final String key;
        final Kind kind;
        final Object initial;
        String text;
        Boolean draft;
        EditBox box;

        Row(ForgeConfigSpec.ConfigValue<?> value, Kind kind, Object initial) {
            this.value = value;
            this.key = String.join(".", value.getPath());
            this.kind = kind;
            this.initial = initial;
            this.text = display(initial);
            this.draft = initial instanceof Boolean b ? b : null;
        }
    }

    private static final class Section {
        final String text;

        Section(String text) {
            this.text = text;
        }
    }

    private void build() {
        String section = null;
        for (ForgeConfigSpec.ConfigValue<?> value : Config.values()) {
            String head = value.getPath().size() > 1 ? value.getPath().get(0) : "(顶层)";
            if (!head.equals(section)) {
                section = head;
                items.add(new Section(head));
            }
            Object current = value.get();
            items.add(new Row(value, kindOf(current), current));
        }
    }

    private static Kind kindOf(Object value) {
        if (value instanceof Boolean) {
            return Kind.BOOL;
        }
        if (value instanceof Integer || value instanceof Long || value instanceof Double) {
            return Kind.NUM;
        }
        if (value instanceof List) {
            return Kind.LIST;
        }
        if (value instanceof String) {
            return Kind.TEXT;
        }
        return Kind.READONLY;
    }

    private static String display(Object value) {
        if (value instanceof List<?> list) {
            StringBuilder sb = new StringBuilder();
            for (Object element : list) {
                if (sb.length() > 0) {
                    sb.append(", ");
                }
                sb.append(element);
            }
            return sb.toString();
        }
        return String.valueOf(value);
    }

    // ------------------------------------------------------------------ 布局

    private int visibleRows() {
        return Math.max(1, (this.height - LIST_TOP - BOTTOM) / ROW_H);
    }

    @Override
    protected void init() {
        clearWidgets();
        int rows = visibleRows();
        int last = Math.min(items.size(), scroll + rows);
        for (int i = scroll; i < last; i++) {
            if (!(items.get(i) instanceof Row row)) {
                continue;
            }
            int y = LIST_TOP + (i - scroll) * ROW_H;
            switch (row.kind) {
                case BOOL -> addRenderableWidget(Button.builder(onOff(row), button -> {
                            row.draft = !Boolean.TRUE.equals(row.draft);
                            button.setMessage(onOff(row));
                        })
                        .bounds(this.width - 12 - NUM_W, y, NUM_W, 18).build());
                case NUM -> row.box = box(row.text, this.width - 12 - NUM_W, y, NUM_W);
                case TEXT, LIST -> row.box = box(row.text,
                        Math.max(12 + 140, this.width - 12 - TEXT_W), y,
                        Math.min(TEXT_W, Math.max(60, this.width / 2 - 12)));
                default -> {
                    // 只读：没有控件，值画在 render 里。
                }
            }
        }

        int y = this.height - 28;
        int half = Math.min(120, (this.width - 16) / 3);
        int x = this.width / 2 - half * 3 / 2 - 8;
        addRenderableWidget(Button.builder(Component.translatable("cat_girl.config.reset"), b -> resetDefaults())
                .bounds(x, y, half, 20).build());
        addRenderableWidget(Button.builder(Component.translatable("cat_girl.config.done"), b -> commit())
                .bounds(x + half + 8, y, half, 20).build());
        addRenderableWidget(Button.builder(Component.translatable("cat_girl.config.cancel"), b -> onClose())
                .bounds(x + (half + 8) * 2, y, half, 20).build());
    }

    private EditBox box(String value, int x, int y, int width) {
        EditBox edit = new EditBox(this.font, x, y, width, 18, Component.literal(""));
        edit.setMaxLength(512);
        edit.setValue(value);
        return addRenderableWidget(edit);
    }

    private static Component onOff(Row row) {
        return Component.translatable(Boolean.TRUE.equals(row.draft)
                ? "cat_girl.config.on" : "cat_girl.config.off");
    }

    // ------------------------------------------------------------------ 渲染

    @Override
    public void render(GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
        renderBackground(graphics);
        graphics.drawCenteredString(this.font, this.title, this.width / 2, 12, TITLE_COLOR);
        graphics.drawString(this.font, Component.translatable("cat_girl.config.hint"),
                12, 30, HINT_COLOR, false);

        int rows = visibleRows();
        int last = Math.min(items.size(), scroll + rows);
        for (int i = scroll; i < last; i++) {
            int y = LIST_TOP + (i - scroll) * ROW_H;
            Object item = items.get(i);
            if (item instanceof Section section) {
                graphics.drawString(this.font,
                        Component.literal(section.text).withStyle(net.minecraft.ChatFormatting.BOLD),
                        12, y + 5, SECTION_COLOR, false);
            } else if (item instanceof Row row) {
                int widgetX = row.kind == Kind.NUM || row.kind == Kind.BOOL
                        ? this.width - 12 - NUM_W : this.width - 12 - TEXT_W;
                String label = this.font.plainSubstrByWidth(row.key, Math.max(40, widgetX - 20));
                graphics.drawString(this.font, label, 12, y + 5, LABEL_COLOR, false);
                if (row.kind == Kind.READONLY) {
                    graphics.drawString(this.font, this.font.plainSubstrByWidth(display(row.initial), 120),
                            Math.max(12, this.width - 132), y + 5, VALUE_COLOR, false);
                }
            }
        }
        super.render(graphics, mouseX, mouseY, partialTick);

        if (!notice.isEmpty()) {
            graphics.drawString(this.font, notice, 12, this.height - 44, WARN_COLOR, false);
        }
        int max = Math.max(0, items.size() - rows);
        if (max > 0) {
            graphics.drawString(this.font, (scroll + rows >= items.size() ? "" : "▼ ")
                            + (scroll + 1) + "-" + last + "/" + items.size(),
                    this.width - 12 - 60, this.height - 44, HINT_COLOR, false);
        }
    }

    // ------------------------------------------------------------------ 交互

    @Override
    public boolean mouseScrolled(double mouseX, double mouseY, double delta) {
        int max = Math.max(0, items.size() - visibleRows());
        int next = (int) Math.max(0, Math.min(max, scroll - Math.signum(delta) * 2));
        if (next != scroll) {
            stash();
            scroll = next;
            rebuildWidgets();
        }
        return true;
    }

    @Override
    public void onClose() {
        if (this.minecraft != null) {
            this.minecraft.setScreen(this.parent);
        }
    }

    /** 把输入框里的字抄回行草稿（翻页 / 提交前都要先抄，否则会丢字）。 */
    private void stash() {
        for (Object item : items) {
            if (item instanceof Row row && row.box != null) {
                row.text = row.box.getValue();
            }
        }
    }

    private void resetDefaults() {
        notice = "";
        for (Object item : items) {
            if (item instanceof Row row) {
                Object fallback = row.value.getDefault();
                apply(row.value, fallback);
                row.text = display(fallback);
                row.draft = fallback instanceof Boolean b ? b : null;
                if (row.box != null) {
                    row.box.setValue(row.text);
                }
            }
        }
        Config.SPEC.save();
        notice = Component.translatable("cat_girl.config.reset_done").getString();
    }

    /** 点「完成」：先全部解析一遍（有一项不合法就整屏不动），再落盘。 */
    private void commit() {
        stash();
        List<Row> parsed = new ArrayList<>();
        List<Object> wanted = new ArrayList<>();
        for (Object item : items) {
            if (!(item instanceof Row row)) {
                continue;
            }
            Object want;
            try {
                want = parse(row);
            } catch (NumberFormatException bad) {
                notice = Component.translatable("cat_girl.config.bad_number", row.key).getString();
                return;
            }
            parsed.add(row);
            wanted.add(want);
        }
        int changed = 0;
        for (int i = 0; i < parsed.size(); i++) {
            Row row = parsed.get(i);
            Object want = wanted.get(i);
            if (!display(row.value.get()).equals(display(want))) {
                apply(row.value, want);
                changed++;
            }
        }
        Config.SPEC.save();
        notice = Component.translatable("cat_girl.config.saved", changed).getString();
        if (changed > 0) {
            onClose();
        }
    }

    private static Object parse(Row row) {
        String text = row.text.trim();
        return switch (row.kind) {
            case BOOL -> Boolean.TRUE.equals(row.draft);
            case NUM -> {
                if (row.initial instanceof Integer) {
                    yield Integer.valueOf(text);
                }
                if (row.initial instanceof Long) {
                    yield Long.valueOf(text);
                }
                yield Double.valueOf(text);
            }
            case LIST -> {
                List<String> parts = new ArrayList<>();
                for (String part : text.split(",")) {
                    if (!part.isBlank()) {
                        parts.add(part.trim());
                    }
                }
                yield parts;
            }
            case TEXT -> text;
            case READONLY -> row.initial;
        };
    }

    @SuppressWarnings("unchecked")
    private static void apply(ForgeConfigSpec.ConfigValue<?> value, Object wanted) {
        ((ForgeConfigSpec.ConfigValue<Object>) value).set(wanted);
    }
}

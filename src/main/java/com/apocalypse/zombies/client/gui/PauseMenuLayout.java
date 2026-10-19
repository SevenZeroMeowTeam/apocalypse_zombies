package com.apocalypse.zombies.client.gui;

import com.apocalypse.zombies.ApocalypseZombies;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.Resource;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

import javax.xml.parsers.DocumentBuilderFactory;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * ESC 暂停菜单的 XML 布局读取器。
 *
 * <p><b>为什么是 XML</b>：用户希望界面参数可以被直接编辑/展示，而不是全部写死在 Java 里。
 * Minecraft 的 GUI 不原生支持 XML，这里用 JDK 自带的 {@link DocumentBuilderFactory} 解析
 * {@code assets/apocalypse_zombies/ui/pause_menu.xml}，再生成 {@link DoomButton}。
 * 资源包覆盖同路径文件即可改按钮顺序、短标签、间距，不用重新编译。</p>
 *
 * <p>XML 只描述<b>布局与文案</b>；按钮行为仍由 Java 的 action 字符串分发（resume / advancements /
 * stats / options / lan / quit），不允许 XML 注入任意代码。文件缺失或解析失败时回落到内置布局，
 * 不会因为一个坏 XML 把暂停菜单弄没。</p>
 */
final class PauseMenuLayout {

    /** 一个按钮：行为、完整文案翻译键、横向工具栏短标签、出现条件。 */
    record Spec(String action, String label, String shortLabel, String condition) {
    }

    /** 横向/网格工具栏的尺寸参数（GUI 坐标）。{@code columns} = 1 时是一行到底。 */
    record Layout(int buttonHeight, int gap, int margin, int columns) {
    }

    record Loaded(Layout layout, List<Spec> buttons) {
    }

    private static final ResourceLocation XML = new ResourceLocation(
            ApocalypseZombies.MOD_ID, "ui/pause_menu.xml");

    private PauseMenuLayout() {
    }

    static Loaded load() {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft == null || minecraft.getResourceManager() == null) {
            return fallback();
        }
        Optional<Resource> resource = minecraft.getResourceManager().getResource(XML);
        if (resource.isEmpty()) {
            return fallback();
        }
        try (InputStream in = resource.get().open()) {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            // 本地资源也按安全惯例禁掉 DTD，避免任何外部实体解析。
            try {
                factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            } catch (Exception ignored) {
                // 某些 JDK 实现不支持这个 feature；继续用默认配置解析本地文件。
            }
            Document document = factory.newDocumentBuilder().parse(in);
            Element root = document.getDocumentElement();
            int height = 24;
            int gap = 4;
            int margin = 8;
            int columns = 2;
            NodeList layouts = root.getElementsByTagName("layout");
            if (layouts.getLength() > 0) {
                Element layout = (Element) layouts.item(0);
                height = intAttr(layout, "button-height", height);
                gap = intAttr(layout, "gap", gap);
                margin = intAttr(layout, "margin", margin);
                columns = intAttr(layout, "columns", columns);
            }
            List<Spec> specs = new ArrayList<>();
            NodeList buttons = root.getElementsByTagName("button");
            for (int i = 0; i < buttons.getLength(); i++) {
                Element button = (Element) buttons.item(i);
                String action = button.getAttribute("action").trim();
                if (action.isEmpty()) {
                    continue;
                }
                specs.add(new Spec(action,
                        button.getAttribute("label").trim(),
                        button.getAttribute("short").trim(),
                        button.getAttribute("condition").trim()));
            }
            if (specs.isEmpty()) {
                return fallback();
            }
            return new Loaded(new Layout(
                    clamp(height, 16, 48),
                    clamp(gap, 0, 16),
                    clamp(margin, 0, 40),
                    clamp(columns, 1, 4)), specs);
        } catch (Exception e) {
            ApocalypseZombies.LOGGER.warn("[末日菜单] pause_menu.xml 解析失败，使用内置横向布局。", e);
            return fallback();
        }
    }

    private static int intAttr(Element element, String name, int fallback) {
        try {
            return Integer.parseInt(element.getAttribute(name).trim());
        } catch (Exception e) {
            return fallback;
        }
    }

    private static int clamp(int value, int min, int max) {
        return Math.max(min, Math.min(max, value));
    }

    /** XML 缺失/损坏时的内置布局：与 XML 默认内容一致。 */
    private static Loaded fallback() {
        List<Spec> specs = List.of(
                new Spec("resume", "menu.returnToGame", "回到游戏", ""),
                new Spec("advancements", "gui.advancements", "进度", ""),
                new Spec("stats", "gui.stats", "统计", ""),
                new Spec("options", "options", "选项", ""),
                new Spec("lan", "menu.shareToLan", "局域网", "lan"),
                new Spec("quit", "menu.returnToMenu", "退出", ""));
        return new Loaded(new Layout(24, 4, 8, 2), specs);
    }
}

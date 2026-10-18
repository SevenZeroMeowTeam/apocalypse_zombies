package com.apocalypse.zombies.orbital.engine;

import com.apocalypse.zombies.ApocalypseZombies;
import com.apocalypse.zombies.orbital.OrbitalStrikeMode;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

import javax.xml.parsers.DocumentBuilderFactory;
import java.io.InputStream;
import java.util.EnumMap;
import java.util.Map;

/**
 * 六份打击协议的定义表（v2 引擎）。
 *
 * <p>定义放在 {@code assets/apocalypse_zombies/strike/*.xml}，由 JDK 的 DocumentBuilder
 * 解析。服务端和客户端都读同一份：服务端取地形参数/相位，客户端取代号/颜色/相位做 HUD 与电影。
 * XML 缺失或解析失败时回落到内置定义，绝不让一次打击因为一个坏文件而失效。</p>
 *
 * <p>P0 只把 {@code fault}（断层）接到 v2 引擎；其余五份协议先在这里登记好名字/颜色/相位，
 * 等各自的机制迁移时再使用它们的 terrain 参数。</p>
 */
public final class StrikeProtocols {

    private static final String PATH = "/assets/apocalypse_zombies/strike/";
    /** 六份协议文件；顺序与设计文档一致。 */
    private static final String[] FILES = {
            "cinder", "fault", "quarantine", "swarm", "dawn", "black_rain"
    };

    private static final Map<OrbitalStrikeMode, StrikeProtocol> BY_MODE =
            new EnumMap<>(OrbitalStrikeMode.class);
    private static final Map<String, StrikeProtocol> BY_ID = new java.util.HashMap<>();

    private StrikeProtocols() {
    }

    static {
        for (String file : FILES) {
            StrikeProtocol protocol = load(file);
            BY_ID.put(protocol.id(), protocol);
            BY_MODE.put(protocol.mode(), protocol);
        }
    }

    public static StrikeProtocol protocolFor(OrbitalStrikeMode mode) {
        return BY_MODE.getOrDefault(mode, fallback("cinder"));
    }

    public static StrikeProtocol byId(String id) {
        StrikeProtocol protocol = BY_ID.get(id);
        return protocol != null ? protocol : protocolFor(OrbitalStrikeMode.LANCE);
    }

    // ------------------------------------------------------------------ XML

    private static StrikeProtocol load(String file) {
        try (InputStream in = StrikeProtocols.class.getResourceAsStream(PATH + file + ".xml")) {
            if (in == null) {
                return fallback(file);
            }
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            try {
                factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            } catch (Exception ignored) {
                // 某些 JDK 实现不支持；继续解析本地 jar 资源。
            }
            Document document = factory.newDocumentBuilder().parse(in);
            Element root = document.getDocumentElement();
            String id = attr(root, "id", file);
            OrbitalStrikeMode mode = OrbitalStrikeMode.byId(attr(root, "mode", "lance"));
            int color = color(attr(root, "color", "#E0C070"));

            int mark = 30;
            int ascent = 40;
            int device = 100;
            int impact = 40;
            int aftermath = 160;
            NodeList phases = root.getElementsByTagName("phase");
            for (int i = 0; i < phases.getLength(); i++) {
                Element phase = (Element) phases.item(i);
                String name = attr(phase, "name", "");
                int ticks = intAttr(phase, "ticks", -1);
                if (ticks < 0) {
                    continue;
                }
                switch (name) {
                    case "mark" -> mark = ticks;
                    case "ascent" -> ascent = ticks;
                    case "device" -> device = ticks;
                    case "impact" -> impact = ticks;
                    case "aftermath" -> aftermath = ticks;
                    default -> {
                    }
                }
            }

            StrikeProtocol.Terrain terrain = StrikeProtocol.Terrain.NONE;
            NodeList terrains = root.getElementsByTagName("terrain");
            if (terrains.getLength() > 0) {
                Element t = (Element) terrains.item(0);
                terrain = new StrikeProtocol.Terrain(
                        attr(t, "shape", ""),
                        intAttr(t, "rift-length", 96),
                        intAttr(t, "rift-width", 7),
                        intAttr(t, "rift-depth", 40));
            }
            return new StrikeProtocol(id, mode,
                    attr(root, "display", file),
                    attr(root, "codename", file.toUpperCase()),
                    color, mark, ascent, device, impact, aftermath, terrain);
        } catch (Exception e) {
            ApocalypseZombies.LOGGER.warn("[天陨] 协议 {} 读取失败，使用内置定义。", file, e);
            return fallback(file);
        }
    }

    private static String attr(Element element, String name, String fallback) {
        if (element == null || !element.hasAttribute(name)) {
            return fallback;
        }
        String value = element.getAttribute(name).trim();
        return value.isEmpty() ? fallback : value;
    }

    private static int intAttr(Element element, String name, int fallback) {
        try {
            return Integer.parseInt(attr(element, name, Integer.toString(fallback)));
        } catch (Exception e) {
            return fallback;
        }
    }

    /** #RRGGBB / #AARRGGBB → ARGB int。 */
    private static int color(String value) {
        String hex = value.startsWith("#") ? value.substring(1) : value;
        try {
            long parsed = Long.parseLong(hex, 16);
            if (hex.length() <= 6) {
                parsed |= 0xFF000000L;
            }
            return (int) parsed;
        } catch (Exception e) {
            return 0xFFE0C070;
        }
    }

    /** 内置定义：和 XML 默认内容一致，保证 jar/资源损坏时技能仍然可用。 */
    private static StrikeProtocol fallback(String file) {
        return switch (file) {
            case "fault" -> new StrikeProtocol("fault", OrbitalStrikeMode.LANCE,
                    "断层", "FAULT // 断层", 0xFFE0C070,
                    35, 45, 100, 45, 180,
                    new StrikeProtocol.Terrain("rift", 96, 7, 40));
            case "quarantine" -> new StrikeProtocol("quarantine", OrbitalStrikeMode.GRAVITY,
                    "隔离", "QUARANTINE // 隔离", 0xFFD8F4FF,
                    40, 45, 110, 35, 160,
                    new StrikeProtocol.Terrain("cordon", 0, 0, 0));
            case "swarm" -> new StrikeProtocol("swarm", OrbitalStrikeMode.STORM,
                    "蜂群", "SWARM // 蜂群", 0xFF8DFF7A,
                    30, 40, 100, 60, 160,
                    new StrikeProtocol.Terrain("brood", 0, 0, 0));
            case "dawn" -> new StrikeProtocol("dawn", OrbitalStrikeMode.LASER,
                    "黎明", "DAWN // 黎明", 0xFFFFF2C4,
                    35, 45, 100, 35, 160,
                    new StrikeProtocol.Terrain("purge", 0, 0, 0));
            case "black_rain" -> new StrikeProtocol("black_rain", OrbitalStrikeMode.PLANET,
                    "黑雨", "BLACK RAIN // 黑雨", 0xFFB08CFF,
                    35, 45, 100, 40, 180,
                    new StrikeProtocol.Terrain("rain", 0, 0, 0));
            default -> new StrikeProtocol("cinder", OrbitalStrikeMode.CANNON,
                    "焚城", "CINDER // 焚城", 0xFFFF7A2E,
                    30, 40, 110, 40, 160,
                    new StrikeProtocol.Terrain("column", 0, 0, 0));
        };
    }
}

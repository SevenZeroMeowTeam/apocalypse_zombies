package com.apocalypse.zombies.ai;

import com.apocalypse.zombies.Config;
import com.apocalypse.zombies.entity.CatGirlEntity;
import com.mojang.logging.LogUtils;

import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import org.slf4j.Logger;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 连接本机 Ollama 的桥。
 *
 * <p><b>三条纪律</b>：
 * <ol>
 *   <li><b>绝不占主线程</b>：请求在工作线程跑，结果用 {@code server.execute} 回投主线程再动游戏状态。
 *       （每条动作都要碰实体/背包，只能在主线程做。）</li>
 *   <li><b>绝不抛异常进 tick</b>：连不上、超时、回包是垃圾，一律降级成一句中文提示，游戏照常跑。</li>
 *   <li><b>熔断</b>：连续失败 3 次就歇 5 分钟，避免玩家每点一次都在等一个没起来的服务。</li>
 * </ol>
 *
 * <p>模型和端点都走配置；默认是玩家点名的 {@code qwen2 1.5B}（Ollama 里叫
 * {@code fableforge-ai/nexus-coder:q4_k_m}）。</p>
 */
public final class LocalAiClient {

    private static final Logger LOGGER = LogUtils.getLogger();

    /** 请求体的对答历史，只留最近几轮（小模型上下文小，塞多了反而乱）。 */
    private static final int MAX_HISTORY = 6;
    /** 玩家一句话最多喂进去多少字（防止有人把整本书粘进聊天框）。 */
    private static final int MAX_INPUT = 200;
    private static final int FAIL_LIMIT = 3;
    private static final long COOLDOWN_MS = 5L * 60_000L;

    private static final AtomicInteger FAILS = new AtomicInteger();
    private static volatile long cooldownUntil = 0L;

    private static final Map<UUID, Deque<String[]>> HISTORY = new ConcurrentHashMap<>();
    private static final java.util.Set<UUID> IN_FLIGHT = ConcurrentHashMap.newKeySet();

    private static HttpClient http;
    private static ExecutorService pool;

    private LocalAiClient() {
    }

    private static synchronized HttpClient http() {
        if (http == null) {
            http = HttpClient.newBuilder()
                    .connectTimeout(Duration.ofSeconds(3))
                    .followRedirects(HttpClient.Redirect.NORMAL)
                    .build();
        }
        return http;
    }

    private static synchronized ExecutorService pool() {
        if (pool == null) {
            pool = Executors.newSingleThreadExecutor(r -> {
                Thread t = new Thread(r, "apocalypse-catgirl-ai");
                t.setDaemon(true);
                return t;
            });
        }
        return pool;
    }

    // ------------------------------------------------------------------ 状态查询（给 /apocalypse ai status 用）

    public static boolean coolingDown() {
        return System.currentTimeMillis() < cooldownUntil;
    }

    public static int remainingCooldownSeconds() {
        long left = cooldownUntil - System.currentTimeMillis();
        return left <= 0 ? 0 : (int) ((left + 999) / 1000);
    }

    public static String statusLine() {
        StringBuilder sb = new StringBuilder();
        sb.append("端点 ").append(Config.CAT_GIRL_AI_ENDPOINT.get());
        sb.append(" · 模型 ").append(Config.CAT_GIRL_AI_MODEL.get());
        sb.append(Config.CAT_GIRL_AI_ENABLED.get() ? " · 已开启" : " · 已关闭");
        sb.append(Config.CAT_GIRL_AI_ACTIONS.get() ? " · 允许动手" : " · 只说话");
        sb.append(" · 连续失败 ").append(FAILS.get());
        if (coolingDown()) {
            sb.append(" · 熔断中（还剩 ").append(remainingCooldownSeconds()).append(" 秒）");
        }
        return sb.toString();
    }

    public static void clearHistory() {
        HISTORY.clear();
    }

    /** 模型换了 / 端点换了，把熔断计数也清掉，省得玩家以为坏了。 */
    public static void resetBreaker() {
        FAILS.set(0);
        cooldownUntil = 0L;
    }

    // ------------------------------------------------------------------ 主流程

    /**
     * 玩家对猫耳娘说了一句话。<b>必须在主线程调用</b>（要读实体、背包、周围生物）。
     */
    public static void ask(MinecraftServer server, ServerPlayer player, CatGirlEntity cat, String text) {
        if (!Config.CAT_GIRL_AI_ENABLED.get()) {
            player.sendSystemMessage(Component.literal("[猫耳娘] ").withStyle(ChatFormatting.LIGHT_PURPLE)
                    .append(Component.literal("我现在的脑子是关着的（配置 catgirl.ai_enabled）。")
                            .withStyle(ChatFormatting.GRAY)));
            return;
        }
        if (coolingDown()) {
            player.sendSystemMessage(Component.literal("[猫耳娘] ").withStyle(ChatFormatting.LIGHT_PURPLE)
                    .append(Component.literal("……我刚连不上脑子，歇 " + remainingCooldownSeconds()
                            + " 秒再叫我。（检查一下 ollama 起没起）").withStyle(ChatFormatting.GRAY)));
            return;
        }
        if (!IN_FLIGHT.add(player.getUUID())) {
            player.sendSystemMessage(Component.literal("[猫耳娘] ").withStyle(ChatFormatting.LIGHT_PURPLE)
                    .append(Component.literal("别急，我还在想上一句呢……").withStyle(ChatFormatting.GRAY)));
            return;
        }

        String said = text.length() > MAX_INPUT ? text.substring(0, MAX_INPUT) : text;
        List<String> candidates = CatGirlAiPrompt.candidates(said,
                cat.level() instanceof ServerLevel level ? level : null);
        String userTurn = CatGirlAiPrompt.userTurn(cat, player, said, candidates);
        List<String[]> history = new ArrayList<>(HISTORY.getOrDefault(player.getUUID(), new ArrayDeque<>()));

        String body = OllamaWire.requestBody(
                Config.CAT_GIRL_AI_MODEL.get(), CatGirlAiPrompt.SYSTEM, CatGirlAiPrompt.FEWSHOT,
                history, userTurn,
                Config.CAT_GIRL_AI_NUM_CTX.get(), 0.2D, 300, false);

        String endpoint = Config.CAT_GIRL_AI_ENDPOINT.get();
        String url = endpoint.endsWith("/") ? endpoint + "api/chat" : endpoint + "/api/chat";
        int timeoutMs = Config.CAT_GIRL_AI_TIMEOUT_MS.get();
        UUID playerId = player.getUUID();
        UUID catId = cat.getUUID();

        player.sendSystemMessage(Component.literal("[猫耳娘] ").withStyle(ChatFormatting.LIGHT_PURPLE)
                .append(Component.literal("（她在想……）").withStyle(ChatFormatting.DARK_GRAY)));

        HttpRequest request;
        try {
            request = HttpRequest.newBuilder(URI.create(url))
                    .timeout(Duration.ofMillis(timeoutMs))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(body))
                    .build();
        } catch (RuntimeException e) {
            IN_FLIGHT.remove(playerId);
            fail(server, playerId, "端点地址不对：" + endpoint);
            return;
        }

        CompletableFuture<HttpResponse<String>> future =
                http().sendAsync(request, HttpResponse.BodyHandlers.ofString());
        future.whenComplete((response, error) -> server.execute(() -> {
            IN_FLIGHT.remove(playerId);
            ServerPlayer p = server.getPlayerList().getPlayer(playerId);
            if (p == null) {
                return; // 人跑了（掉线/换维度），这轮丢掉就好
            }
            CatGirlEntity c = resolve(server, catId);
            if (error != null) {
                fail(server, playerId, describe(error));
                return;
            }
            if (response.statusCode() != 200) {
                fail(server, playerId, "模型返回 HTTP " + response.statusCode()
                        + "（模型名写错？" + Config.CAT_GIRL_AI_MODEL.get() + "）");
                return;
            }
            OllamaWire.Reply reply = OllamaWire.parse(response.body());
            if (!reply.ok()) {
                fail(server, playerId, reply.error());
                return;
            }
            FAILS.set(0);
            remember(playerId, said, replyJson(reply));
            if (c == null || c.isRemoved()) {
                p.sendSystemMessage(Component.literal("[猫耳娘] ").withStyle(ChatFormatting.LIGHT_PURPLE)
                        .append(Component.literal(reply.say().isEmpty() ? "……" : reply.say())
                                .withStyle(ChatFormatting.WHITE)));
                return;
            }
            CatGirlAiActions.apply(c, p, reply, candidates);
        }));
    }

    /** 她可能已经换了世界/被卸载；按 uuid 在当前世界找回来。 */
    private static CatGirlEntity resolve(MinecraftServer server, UUID catId) {
        for (ServerLevel level : server.getAllLevels()) {
            if (level.getEntity(catId) instanceof CatGirlEntity cat) {
                return cat;
            }
        }
        return null;
    }

    private static void fail(MinecraftServer server, UUID playerId, String why) {
        int n = FAILS.incrementAndGet();
        if (n >= FAIL_LIMIT) {
            cooldownUntil = System.currentTimeMillis() + COOLDOWN_MS;
            LOGGER.warn("cat_girl AI 连续失败 {} 次，熔断 5 分钟：{}", n, why);
        } else {
            LOGGER.warn("cat_girl AI 这一轮失败（{}）：{}", n, why);
        }
        ServerPlayer p = server.getPlayerList().getPlayer(playerId);
        if (p != null) {
            p.sendSystemMessage(Component.literal("[猫耳娘] ").withStyle(ChatFormatting.LIGHT_PURPLE)
                    .append(Component.literal("……我又想不明白了（" + why + "）。").withStyle(ChatFormatting.GRAY)));
        }
    }

    private static String describe(Throwable error) {
        Throwable cause = error.getCause() == null ? error : error.getCause();
        if (cause instanceof java.net.http.HttpTimeoutException) {
            return "等太久了（超过 " + Config.CAT_GIRL_AI_TIMEOUT_MS.get() + " 毫秒）";
        }
        if (cause instanceof java.net.ConnectException) {
            return "连不上本地模型 " + Config.CAT_GIRL_AI_ENDPOINT.get() + "（ollama 起了吗？）";
        }
        String msg = cause.getMessage();
        return msg == null || msg.isBlank() ? cause.getClass().getSimpleName() : msg;
    }

    private static String replyJson(OllamaWire.Reply reply) {
        return "{\"reply\":\"" + reply.say().replace("\\", "").replace("\"", "")
                + "\",\"action\":\"" + reply.action() + "\",\"job\":\"" + reply.job()
                + "\",\"item\":\"" + reply.item() + "\",\"count\":" + reply.count() + "}";
    }

    private static void remember(UUID playerId, String said, String answer) {
        Deque<String[]> turns = HISTORY.computeIfAbsent(playerId, k -> new ArrayDeque<>());
        turns.addLast(new String[]{said, answer});
        while (turns.size() > MAX_HISTORY) {
            turns.removeFirst();
        }
    }
}

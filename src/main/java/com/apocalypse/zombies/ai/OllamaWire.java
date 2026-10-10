package com.apocalypse.zombies.ai;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.JsonPrimitive;

import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 本地模型的「线」：负责拼请求体、剥思考标签、把回包解析成一个受约束的 {@link Reply}。
 *
 * <p><b>为什么单独一个类</b>：这里面<b>不碰任何 Minecraft 类</b>，所以可以拿一台普通 JVM
 * 加一个 gson.jar 直接对着真 Ollama 跑（见 {@code tools/ai_wire_test/OllamaWireTest.java}）——
 * 门禁里跑的是同一份字节码，不是「看起来一样」的另一份实现。</p>
 *
 * <p><b>设计底线</b>：模型说什么都只是「提议」。{@link Reply#action} 只可能是
 * {@code none/say/set_job/craft} 之一，{@link Reply#job} 只可能落在 {@link #JOBS} 里，
 * item 必须是合法的命名空间 id，count 被夹到 1..64；任何不合规的字段一律降级清空，
 * 而不是把模型的原文直接交给执行层。</p>
 */
public final class OllamaWire {

    /** 她能被指派的工种（与 {@code CatGirlEntity.Job} 同步）。 */
    public static final List<String> JOBS = List.of("LUMBER", "MINE", "FIGHT", "FOLLOW");

    /** 允许的动作白名单。 */
    public static final List<String> ACTIONS = List.of("none", "say", "set_job", "craft");

    /** 合法物品 id 形状：{@code namespace:path}。 */
    private static final Pattern ITEM_ID = Pattern.compile("^[a-z0-9_.-]+:[a-z0-9_./-]+$");

    private OllamaWire() {
    }

    /**
     * 模型的一次「提议」。{@code error} 非空表示这轮压根没拿到可用答复。
     */
    public record Reply(String say, String action, String job, String item, int count, String error) {

        /** 这轮是否拿到可用答复（不代表动作合法，动作合法性看 action/job/item）。 */
        public boolean ok() {
            return this.error.isEmpty();
        }

        public boolean wantsSetJob() {
            return "set_job".equals(this.action) && !this.job.isEmpty();
        }

        public boolean wantsCraft() {
            return "craft".equals(this.action) && !this.item.isEmpty();
        }
    }

    /** 拿不到答复时的统一降级（永远不抛异常给调用方）。 */
    public static Reply degraded(String reason) {
        return new Reply("", "none", "", "", 0, reason == null ? "unknown" : reason);
    }

    /**
     * 拼 {@code /api/chat} 的请求体。
     *
     * @param fewshot 少样本示范，每个元素是 {@code {用户串, 助手串}}；1.5B 级模型没有它就只会复读玩家的话
     * @param history 最近几轮 {@code {用户串, 助手串}}，可为空
     */
    public static String requestBody(String model, String system, List<String[]> fewshot,
                                     List<String[]> history, String user,
                                     int numCtx, double temperature, int numPredict, boolean think) {
        JsonObject root = new JsonObject();
        root.addProperty("model", model);
        root.addProperty("stream", false);
        root.addProperty("format", "json");
        root.addProperty("think", think);
        root.addProperty("keep_alive", "10m");

        JsonArray messages = new JsonArray();
        messages.add(message("system", system));
        for (String[] pair : fewshot) {
            messages.add(message("user", pair[0]));
            messages.add(message("assistant", pair[1]));
        }
        for (String[] pair : history) {
            messages.add(message("user", pair[0]));
            messages.add(message("assistant", pair[1]));
        }
        messages.add(message("user", user));
        root.add("messages", messages);

        JsonObject options = new JsonObject();
        options.addProperty("temperature", temperature);
        options.addProperty("num_ctx", numCtx);
        options.addProperty("num_predict", numPredict);
        root.add("options", options);
        return root.toString();
    }

    private static JsonObject message(String role, String content) {
        JsonObject m = new JsonObject();
        m.addProperty("role", role);
        m.addProperty("content", content);
        return m;
    }

    /**
     * 剥掉思考标签。qwen 系的量化模型即使 {@code think:false} 也会在正式答案前吐
     * {@code ...}（有时还忘了闭合），不剥掉就会污染 JSON 解析。
     */
    public static String stripThink(String raw) {
        if (raw == null) {
            return "";
        }
        String out = raw;
        for (String closer : new String[]{"</think>", "</thinking>", "</reasoning>"}) {
            while (true) {
                int i = out.indexOf(closer);
                if (i < 0) {
                    break;
                }
                out = out.substring(i + closer.length());
            }
        }
        for (String opener : new String[]{"<think", "<thinking", "<reasoning"}) {
            int i = out.indexOf(opener);
            if (i >= 0) {
                int gt = out.indexOf('>', i);
                out = out.substring(0, i) + (gt >= 0 ? out.substring(gt + 1) : "");
            }
        }
        return out.trim();
    }

    /** 从模型的回包（HTTP 响应体）里抠出 {@code message.content}。 */
    public static String contentOf(String httpBody) {
        if (httpBody == null || httpBody.isBlank()) {
            return "";
        }
        try {
            JsonElement root = JsonParser.parseString(httpBody);
            if (!root.isJsonObject()) {
                return "";
            }
            JsonElement message = root.getAsJsonObject().get("message");
            if (message == null || !message.isJsonObject()) {
                // 某些路径会把内容放在 response 字段（/api/generate 风格）
                JsonElement response = root.getAsJsonObject().get("response");
                return response == null || response.isJsonNull() ? "" : response.getAsString();
            }
            JsonElement content = message.getAsJsonObject().get("content");
            return content == null || content.isJsonNull() ? "" : content.getAsString();
        } catch (RuntimeException e) {
            return "";
        }
    }

    /** 取最外层的第一个 {@code {} 块（模型常在 JSON 前后带注释）。 */
    public static String extractJson(String text) {
        String s = stripThink(text);
        int start = s.indexOf('{');
        int end = s.lastIndexOf('}');
        if (start < 0 || end <= start) {
            return "";
        }
        return s.substring(start, end + 1);
    }

    /**
     * 把模型的回包解析成受约束的 {@link Reply}。<b>任何一步不合规都降级</b>，不抛异常。
     */
    public static Reply parse(String httpBody) {
        String content = contentOf(httpBody);
        if (content.isBlank()) {
            return degraded("空回包");
        }
        String json = extractJson(content);
        if (json.isEmpty()) {
            return degraded("没有 JSON");
        }
        JsonObject o;
        try {
            JsonElement el = JsonParser.parseString(json);
            if (!el.isJsonObject()) {
                return degraded("回包不是对象");
            }
            o = el.getAsJsonObject();
        } catch (RuntimeException e) {
            return degraded("JSON 解析失败");
        }

        String say = optString(o, "reply");
        if (say.isEmpty()) {
            say = optString(o, "say");
        }
        String action = optString(o, "action").toLowerCase(java.util.Locale.ROOT);
        if (!ACTIONS.contains(action)) {
            action = say.isEmpty() ? "none" : "say"; // 不认识的动作 → 当聊天处理
        }
        String job = optString(o, "job").toUpperCase(java.util.Locale.ROOT);
        if (!JOBS.contains(job)) {
            job = "";
        }
        String item = optString(o, "item").trim();
        if (!ITEM_ID.matcher(item).matches()) {
            item = "";
        }
        int count = optCount(o, "count");
        if (count <= 0) {
            count = 1;
        }
        if (count > 64) {
            count = 64;
        }

        if ("craft".equals(action) && item.isEmpty()) {
            action = say.isEmpty() ? "none" : "say"; // 要合成却没说清做什么 → 只当回话
        }
        if ("set_job".equals(action) && job.isEmpty()) {
            action = say.isEmpty() ? "none" : "say";
        }
        if (say.isEmpty() && "none".equals(action) && job.isEmpty() && item.isEmpty()) {
            return degraded("回包里什么都没有");
        }
        return new Reply(say, action, job, item, count, "");
    }

    private static String optString(JsonObject o, String key) {
        JsonElement e = o.get(key);
        if (e == null || e.isJsonNull()) {
            return "";
        }
        try {
            return e.getAsString().trim();
        } catch (RuntimeException ex) {
            return "";
        }
    }

    /** count 的容错：数字、字符串、浮点都要吃得下（小模型经常把 0 写成 "0"）。 */
    private static int optCount(JsonObject o, String key) {
        JsonElement e = o.get(key);
        if (e == null || e.isJsonNull()) {
            return 0;
        }
        try {
            if (e instanceof JsonPrimitive p && p.isNumber()) {
                return (int) p.getAsDouble();
            }
            String s = e.getAsString().trim();
            Matcher m = Pattern.compile("-?\\d+").matcher(s);
            return m.find() ? Integer.parseInt(m.group()) : 0;
        } catch (RuntimeException ex) {
            return 0;
        }
    }
}

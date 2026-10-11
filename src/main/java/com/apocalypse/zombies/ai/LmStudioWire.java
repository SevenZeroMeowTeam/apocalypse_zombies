package com.apocalypse.zombies.ai;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.JsonPrimitive;

import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 本地模型的「线」：LM Studio 的 OpenAI 兼容脸（{@code POST /v1/chat/completions}）。
 *
 * <p><b>和上一版（Ollama）差在哪</b>：请求体与回包形状都换了 —— LM Studio 收
 * {@code temperature / max_tokens / response_format / chat_template_kwargs}，回包走
 * {@code choices[0].message}；Ollama 那套 {@code options.num_ctx / format / think} 和
 * {@code message.content} 它一个也不认（{@code format:"json"} 会被无视，
 * {@code response_format.type:"json_object"} 直接 400，它只认 {@code json_schema} 或 {@code text}）。</p>
 *
 * <p><b>为什么单独一个类</b>：这里面<b>不碰任何 Minecraft 类</b>，所以可以拿一台普通 JVM
 * 加一个 gson.jar 直接对着真 LM Studio 跑（见 {@code tools/ai_wire_test/LmStudioWireTest.java}）——
 * 门禁里跑的是同一份字节码，不是「看起来一样」的另一份实现。</p>
 *
 * <p><b>设计底线</b>：模型说什么都只是「提议」。{@link Reply#action} 只可能是
 * {@code none/say/set_job/craft} 之一，{@link Reply#job} 只可能落在 {@link #JOBS} 里，
 * item 必须是合法的命名空间 id，count 被夹到 1..64；任何不合规的字段一律降级清空，
 * 而不是把模型的原文直接交给执行层。</p>
 */
public final class LmStudioWire {

    /** 她能被指派的工种（与 {@code CatGirlEntity.Job} 同步）。 */
    public static final List<String> JOBS = List.of("LUMBER", "MINE", "FIGHT", "FOLLOW");

    /** 允许的动作白名单。 */
    public static final List<String> ACTIONS = List.of("none", "say", "set_job", "craft");

    /** 合法物品 id 形状：{@code namespace:path}。 */
    private static final Pattern ITEM_ID = Pattern.compile("^[a-z0-9_.-]+:[a-z0-9_./-]+$");

    /** OpenAI 兼容的补全路径。 */
    public static final String CHAT_PATH = "/chat/completions";

    /** OpenAI 兼容口挂的前缀（LM Studio 默认就是这个）。 */
    public static final String V1 = "/v1";

    private LmStudioWire() {
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
     * 端点 → 真正的补全 URL。三种写法都吃，省得玩家在配置里写错一个斜杠就以为坏了：
     * <pre>
     *   http://127.0.0.1:1234            → http://127.0.0.1:1234/v1/chat/completions
     *   http://127.0.0.1:1234/v1         → http://127.0.0.1:1234/v1/chat/completions   （推荐的写法）
     *   http://127.0.0.1:1234/v1/chat/completions → 原样
     * </pre>
     */
    public static String chatUrl(String endpoint) {
        String base = endpoint == null ? "" : endpoint.trim();
        while (base.endsWith("/")) {
            base = base.substring(0, base.length() - 1);
        }
        if (base.endsWith(CHAT_PATH)) {
            return base;
        }
        return base.endsWith(V1) ? base + CHAT_PATH : base + V1 + CHAT_PATH;
    }

    /**
     * 结构化输出契约：LM Studio 的 {@code response_format} <b>只认</b> {@code json_schema} 与
     * {@code text}（照搬 Ollama 的 {@code "type":"json_object"} 会被 400 顶回来，实测过）。
     *
     * <p>把五个键连类型一起钉死，小模型就没法用「少写一个键」「count 写成文字」蒙混过关 ——
     * 不合规的字段仍然是解析层兜着，这只是把出错的概率先压下去。</p>
     */
    public static JsonObject responseFormat() {
        JsonObject props = new JsonObject();
        props.add("reply", stringProp("给玩家看的中文一句话"));
        props.add("action", enumProp(List.of("none", "say", "set_job", "craft")));
        props.add("job", enumProp(List.of("", "LUMBER", "MINE", "FIGHT", "FOLLOW")));
        props.add("item", stringProp("只能取「可做的东西列表」里的 id，没有就空串"));
        JsonObject count = new JsonObject();
        count.addProperty("type", "integer");
        count.addProperty("minimum", 0);
        count.addProperty("maximum", 64);
        count.addProperty("description", "数量，不涉及就 0");
        props.add("count", count);

        JsonArray required = new JsonArray();
        for (String key : new String[]{"reply", "action", "job", "item", "count"}) {
            required.add(key);
        }

        JsonObject schema = new JsonObject();
        schema.addProperty("type", "object");
        schema.add("properties", props);
        schema.add("required", required);
        schema.addProperty("additionalProperties", false);

        JsonObject named = new JsonObject();
        named.addProperty("name", "cat_girl_reply");
        named.addProperty("strict", true);
        named.add("schema", schema);

        JsonObject format = new JsonObject();
        format.addProperty("type", "json_schema");
        format.add("json_schema", named);
        return format;
    }

    private static JsonObject stringProp(String description) {
        JsonObject p = new JsonObject();
        p.addProperty("type", "string");
        p.addProperty("description", description);
        return p;
    }

    private static JsonObject enumProp(List<String> values) {
        JsonObject p = new JsonObject();
        p.addProperty("type", "string");
        JsonArray arr = new JsonArray();
        for (String v : values) {
            arr.add(v);
        }
        p.add("enum", arr);
        return p;
    }

    /**
     * 拼 {@code /v1/chat/completions} 的请求体。
     *
     * @param fewshot 少样本示范，每个元素是 {@code {用户串, 助手串}}；小模型没有它就只会复读玩家的话
     * @param history 最近几轮 {@code {用户串, 助手串}}，可为空
     * @param contextLength KV 缓存长度；{@code <= 0} 表示不提，交给 LM Studio 加载时的设置
     * @param think 是否允许她先想再说：默认 false（思考只会拖慢小模型并污染那行 JSON）
     * @param jsonSchema 是否用结构化输出把回包钉成五键 JSON（服务端不认时由配置关掉）
     */
    public static String requestBody(String model, String system, List<String[]> fewshot,
                                     List<String[]> history, String user,
                                     int contextLength, double temperature, int maxTokens,
                                     boolean think, boolean jsonSchema) {
        JsonObject root = new JsonObject();
        root.addProperty("model", model);
        root.addProperty("stream", false);
        root.addProperty("temperature", temperature);
        root.addProperty("max_tokens", maxTokens);
        if (contextLength > 0) {
            root.addProperty("context_length", contextLength);
        }

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

        // 关思考：Qwen 系（含 Qwen3.5 蒸馏版）默认会先吐一大段思考。模板里没有这个变量时
        // LM Studio 直接忽略（实测不报错），所以对不认它的模型也是安全的。
        JsonObject template = new JsonObject();
        template.addProperty("enable_thinking", think);
        root.add("chat_template_kwargs", template);

        if (jsonSchema) {
            root.add("response_format", responseFormat());
        }
        return root.toString();
    }

    private static JsonObject message(String role, String content) {
        JsonObject m = new JsonObject();
        m.addProperty("role", role);
        m.addProperty("content", content);
        return m;
    }

    /**
     * 剥掉思考标签。Qwen 系的量化模型即使被要求「只输出 JSON」，有时仍会在正式答案前吐
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

    /**
     * 从模型的回包（HTTP 响应体）里抠出正文。
     *
     * <p>主路是 OpenAI 形状的 {@code choices[0].message.content}；两条兜底是为了「端点被指到
     * 别处」时不至于整轮白跑：思考型模型把话说在 {@code reasoning_content} 里（content 空），
     * 以及补全式回包的 {@code choices[0].text}。</p>
     */
    public static String contentOf(String httpBody) {
        if (httpBody == null || httpBody.isBlank()) {
            return "";
        }
        try {
            JsonElement root = JsonParser.parseString(httpBody);
            if (!root.isJsonObject()) {
                return "";
            }
            JsonObject body = root.getAsJsonObject();
            JsonElement choices = body.get("choices");
            if (choices != null && choices.isJsonArray() && !choices.getAsJsonArray().isEmpty()) {
                JsonElement first = choices.getAsJsonArray().get(0);
                if (first.isJsonObject()) {
                    JsonObject choice = first.getAsJsonObject();
                    JsonElement message = choice.get("message");
                    if (message != null && message.isJsonObject()) {
                        JsonObject msg = message.getAsJsonObject();
                        String content = asText(msg.get("content"));
                        if (!content.isBlank()) {
                            return content;
                        }
                        return asText(msg.get("reasoning_content"));
                    }
                    return asText(choice.get("text"));
                }
            }
            // 兜底：老式 /api/chat 与 /api/generate 的形状
            JsonElement message = body.get("message");
            if (message != null && message.isJsonObject()) {
                return asText(message.getAsJsonObject().get("content"));
            }
            return asText(body.get("response"));
        } catch (RuntimeException e) {
            return "";
        }
    }

    private static String asText(JsonElement e) {
        if (e == null || e.isJsonNull()) {
            return "";
        }
        try {
            return e.getAsString();
        } catch (RuntimeException ex) {
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
        String action = optString(o, "action").toLowerCase(Locale.ROOT);
        if (!ACTIONS.contains(action)) {
            action = say.isEmpty() ? "none" : "say"; // 不认识的动作 → 当聊天处理
        }
        String job = optString(o, "job").toUpperCase(Locale.ROOT);
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

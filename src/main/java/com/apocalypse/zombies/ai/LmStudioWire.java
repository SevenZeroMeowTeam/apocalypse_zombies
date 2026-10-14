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
        return requestBody(model, system, fewshot, history, user, contextLength, temperature,
                maxTokens, think, jsonSchema, false);
    }

    /**
     * 同上，多一个「把答案的头一个字先写好」的开关。
     *
     * <p><b>{@code prefillJson} 为什么是这版的关键</b>：思考型模型（DeepSeek-R1 蒸馏那类）
     * 的 {@code enable_thinking} 是<b>模板里写死</b>的 —— 请求里那个参数它当没看见。实测
     * {@code DeepSeek-R1-Distill-Qwen-1.5B}：{@code max_tokens=300} 时思考能吃满 300 个 token，
     * {@code content} 交回空串、正文全在 {@code reasoning_content} 里，于是整轮白跑。
     * 在 messages 末尾追加一条内容就是一个 <code>{</code> 的 assistant 消息后，服务端把它当
     * <b>已经开好的头</b>接着往下写，模型没有"先想一段"的机会：同一句话从「299 token / 14 秒 /
     * 空答案」变成「36 token / 1.6 秒 / 合法 JSON」（2026-10-13 在 llama.cpp b11572 +
     * 该模型上实测）。</p>
     *
     * <p>代价是有的：不是所有服务端都收「以 assistant 收尾」的请求（LM Studio 与 llama.cpp
     * 收，个别实现回 400）。所以调用方必须能在 4xx 时退回去掉这一条的版本重来一次 ——
     * 见 {@code LocalAiClient}。</p>
     */
    public static String requestBody(String model, String system, List<String[]> fewshot,
                                     List<String[]> history, String user,
                                     int contextLength, double temperature, int maxTokens,
                                     boolean think, boolean jsonSchema, boolean prefillJson) {
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
        if (prefillJson) {
            // 「答案的第一个字」替她写好：思考型模型被这一段顶住，没有机会先吐思考。
            messages.add(message("assistant", "{"));
        }
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
     * 回包里那三类「正文」的原文 —— 分开拿着，因为<b>它们不是一回事</b>：
     * {@code content} 是答案，{@code reasoning_content} 是思考。另外记一下
     * {@code finish_reason} 是不是 {@code length}（被 {@code max_tokens} 截断）。
     */
    private record Body(String content, String reasoning, String text, boolean truncated) {

        boolean allBlank() {
            return this.content.isBlank() && this.reasoning.isBlank() && this.text.isBlank();
        }
    }

    /** 按 OpenAI 形状拆回包；拆不动就回一份全空的（解析层照旧降级，不抛异常）。 */
    private static Body readBody(String httpBody) {
        Body empty = new Body("", "", "", false);
        if (httpBody == null || httpBody.isBlank()) {
            return empty;
        }
        try {
            JsonElement root = JsonParser.parseString(httpBody);
            if (!root.isJsonObject()) {
                return empty;
            }
            JsonObject body = root.getAsJsonObject();
            JsonElement choices = body.get("choices");
            if (choices != null && choices.isJsonArray() && !choices.getAsJsonArray().isEmpty()) {
                JsonElement first = choices.getAsJsonArray().get(0);
                if (first.isJsonObject()) {
                    JsonObject choice = first.getAsJsonObject();
                    boolean truncated = "length".equalsIgnoreCase(asText(choice.get("finish_reason")));
                    JsonElement message = choice.get("message");
                    if (message != null && message.isJsonObject()) {
                        JsonObject msg = message.getAsJsonObject();
                        return new Body(asText(msg.get("content")), asText(msg.get("reasoning_content")),
                                asText(choice.get("text")), truncated);
                    }
                    return new Body("", "", asText(choice.get("text")), truncated);
                }
            }
            // 兜底：老式 /api/chat 与 /api/generate 的形状
            JsonElement message = body.get("message");
            if (message != null && message.isJsonObject()) {
                return new Body(asText(message.getAsJsonObject().get("content")), "", "", false);
            }
            return new Body(asText(body.get("response")), "", "", false);
        } catch (RuntimeException e) {
            return empty;
        }
    }

    /**
     * 从模型的回包（HTTP 响应体）里抠出正文 —— <b>只用来给人看/给日志看</b>，
     * 解析走 {@link #parse(String)}（那边对「思考」有专门的判定）。
     *
     * <p>主路是 OpenAI 形状的 {@code choices[0].message.content}；两条兜底是为了「端点被指到
     * 别处」时不至于整轮白跑：思考型模型把话说在 {@code reasoning_content} 里（content 空），
     * 以及补全式回包的 {@code choices[0].text}。</p>
     */
    public static String contentOf(String httpBody) {
        Body body = readBody(httpBody);
        if (!body.content().isBlank()) {
            return body.content();
        }
        return body.reasoning().isBlank() ? body.text() : body.reasoning();
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

    /**
     * 取文本里第一个 {@code {} 块。
     *
     * <p><b>为什么不是「第一个 { 到最后那个 }」</b>：模型常在 JSON 前后带注释，而思考型模型的
     * 思考里往往还草拟过一两个半截的 JSON —— 取最外层会把两段拼成一段必然解析失败的怪东西。
     * 现在按<b>括号配平</b>切（字符串里的花括号不算），再到末尾那条兜底：括号压根没配平
     * （被 {@code max_tokens} 截断），就把从 {@code {} 起剩下的原文交上去，让解析层判死。</p>
     */
    public static String extractJson(String text) {
        String s = stripThink(text);
        int start = s.indexOf('{');
        if (start < 0) {
            return "";
        }
        int end = matchBrace(s, start);
        return end < 0 ? s.substring(start) : s.substring(start, end + 1);
    }

    /** 从 {@code start}（必须是 <code>{</code>）起找配对的 <code>}</code>；找不到返回 -1。 */
    private static int matchBrace(String s, int start) {
        int depth = 0;
        boolean inString = false;
        boolean escaped = false;
        for (int i = start; i < s.length(); i++) {
            char c = s.charAt(i);
            if (inString) {
                if (escaped) {
                    escaped = false;
                } else if (c == '\\') {
                    escaped = true;
                } else if (c == '"') {
                    inString = false;
                }
                continue;
            }
            if (c == '"') {
                inString = true;
            } else if (c == '{') {
                depth++;
            } else if (c == '}') {
                depth--;
                if (depth == 0) {
                    return i;
                }
            }
        }
        return -1;
    }

    /**
     * 文本 → <b>第一个真能解析成对象的</b> JSON；挖不出来返回 {@code null}。
     *
     * <p>逐个 {@code {} 起点试：思考里的花括号、半截草稿都会被跳过，直到遇见那个整段合法的。</p>
     */
    private static JsonObject findJsonObject(String text) {
        String s = stripThink(text);
        for (int i = 0; i < s.length(); i++) {
            if (s.charAt(i) != '{') {
                continue;
            }
            int end = matchBrace(s, i);
            String chunk = end < 0 ? s.substring(i) : s.substring(i, end + 1);
            try {
                JsonElement el = JsonParser.parseString(chunk);
                if (el.isJsonObject()) {
                    return el.getAsJsonObject();
                }
            } catch (RuntimeException ignored) {
                // 这一段不是 JSON（思考里的花括号节奏），接着往下找
            }
            if (end < 0) {
                break; // 后面已经没有配平的括号了
            }
            i = end;
        }
        return null;
    }

    /**
     * 把模型的回包解析成受约束的 {@link Reply}。<b>任何一步不合规都降级</b>，不抛异常。
     *
     * <p><b>这版最要紧的一条纪律</b>：只认<b>真答案</b>。{@code content} 是答案，
     * {@code reasoning_content} 是思考 —— 思考里恰好草拟过一整段合法 JSON 时可以拿来救命
     * （有些实现把正文塞在 reasoning 里），但<b>思考本身绝不能当回话</b>。旧版是
     * 「content 空就直接把 reasoning_content 当正文」，于是思考型模型（DeepSeek-R1 蒸馏那类，
     * 它不认 {@code enable_thinking}）在 {@code max_tokens} 被思考吃满时，屏幕上就只剩一句
     * 玩家看不懂的「……我又想不明白了（没有 JSON）」。</p>
     */
    public static Reply parse(String httpBody) {
        Body body = readBody(httpBody);
        JsonObject o = findJsonObject(body.content());
        if (o == null) {
            o = findJsonObject(body.reasoning()); // 救命：思考里草拟过完整 JSON
        }
        if (o == null) {
            o = findJsonObject(body.text());
        }
        if (o == null) {
            return degraded(noJsonReason(body));
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

    /**
     * 挖不出 JSON 时，尽量说清「是哪一种没有」—— 玩家看得懂才有得改，
     * 而不是甩一句「没有 JSON」把人晾在那儿（2026-10-13 那张截图上刷屏的就是它）。
     */
    private static String noJsonReason(Body body) {
        if (body.allBlank()) {
            return "空回包（服务端一个字都没回）";
        }
        if (body.content().isBlank() && !body.reasoning().isBlank()) {
            return body.truncated()
                    ? "她的思考把 max_tokens 用光了，答案还没开始写就被截断 —— 把 ai.max_tokens 调大，"
                            + "或换一个不吐思考的模型"
                    : "她只顾着想，没给出 JSON 答案 —— 把 ai.max_tokens 调大试试";
        }
        if (body.truncated()) {
            return "回包被 max_tokens 截断了，JSON 没写完 —— 把 ai.max_tokens 调大";
        }
        return "没有 JSON";
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

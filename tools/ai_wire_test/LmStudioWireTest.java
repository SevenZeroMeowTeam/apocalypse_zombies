import com.apocalypse.zombies.ai.LmStudioWire;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;

/**
 * 门禁用：拿<b>真 LM Studio</b> 跑一遍线上那套「拼请求 → 解析 → 约束」的代码。
 *
 * <p>编译/运行（deploy 脚本里就是这么做的）：
 * <pre>
 *   javac -encoding UTF-8 -d build/aiw -cp &lt;gson.jar&gt; \
 *       src/main/java/com/apocalypse/zombies/ai/LmStudioWire.java tools/ai_wire_test/LmStudioWireTest.java
 *   java -cp "build/aiw;&lt;gson.jar&gt;" LmStudioWireTest
 * </pre>
 *
 * <p>它验四件事：①真模型的 OpenAI 形状回包能被解析成合法 {@link LmStudioWire.Reply}
 * （动作/工种/item/count 都在白名单内）；②模型胡言乱语（非 JSON、思考标签、字符串 count、
 * 越界 count、假 id）一律被降级而不是放行；③<b>回包的三种形状</b>都认得（content /
 * reasoning_content 空 content 兜底 / 补全式 text）；④端点写法宽容（主机、/v1、整条路径都能拼对），
 * 且发出去的 {@code response_format} 是 LM Studio 收的 {@code json_schema}
 * —— 照搬 Ollama 的 {@code json_object} 会被 400 顶回来（实测过，所以在这里钉死）。</p>
 */
public class LmStudioWireTest {

    private static final String ENDPOINT =
            System.getenv().getOrDefault("AI_TEST_ENDPOINT", "http://127.0.0.1:1234/v1");
    private static final String MODEL =
            System.getenv().getOrDefault("AI_TEST_MODEL", "qwen3.5-4b-claude-4.6-opus-reasoning-distilled");

    private static int passed = 0;
    private static int failed = 0;

    public static void main(String[] args) throws Exception {
        System.out.println("端点 " + ENDPOINT + " | 模型 " + MODEL);
        offlineCases();
        liveCase();
        System.out.println();
        System.out.println(("通过 " + passed + " / " + (passed + failed)));
        if (failed > 0) {
            System.exit(1);
        }
    }

    // ------------------------------------------------------------------ 不依赖网络的容错用例

    private static void offlineCases() {
        // 思考标签 + 前后杂字：必须剥干净还能解析
        String leaky = "{\"choices\":[{\"message\":{\"content\":\"<think>玩家想砍树…</think>{\\\"reply\\\":\\\"好的\\\",\\\"action\\\":\\\"set_job\\\",\\\"job\\\":\\\"lumber\\\",\\\"item\\\":\\\"\\\",\\\"count\\\":0}\"}}]}";
        LmStudioWire.Reply r1 = LmStudioWire.parse(leaky);
        check("思考标签剥除 + 小写 job 归一", r1.ok() && r1.wantsSetJob() && "LUMBER".equals(r1.job()));

        // count 写成字符串、超界 → 夹住
        LmStudioWire.Reply r2 = LmStudioWire.parse("{\"choices\":[{\"message\":{\"content\":\"{\\\"reply\\\":\\\"做\\\",\\\"action\\\":\\\"craft\\\",\\\"item\\\":\\\"minecraft:stone_pickaxe\\\",\\\"count\\\":\\\"999\\\"}\"}}]}");
        check("字符串 count + 越界夹到 64", r2.ok() && r2.count() == 64 && r2.wantsCraft());

        // 假 id（没有命名空间）→ 清掉；动作从 craft 降级为 say
        LmStudioWire.Reply r3 = LmStudioWire.parse("{\"choices\":[{\"message\":{\"content\":\"{\\\"reply\\\":\\\"给你\\\",\\\"action\\\":\\\"craft\\\",\\\"item\\\":\\\"diamond_sword\\\",\\\"count\\\":1}\"}}]}");
        check("假 id 被清空、craft 降级", r3.ok() && r3.item().isEmpty() && !r3.wantsCraft());

        // 没见过的动作 → 降级成聊天，绝不透传到执行层
        LmStudioWire.Reply r4 = LmStudioWire.parse("{\"choices\":[{\"message\":{\"content\":\"{\\\"reply\\\":\\\"我飞过去\\\",\\\"action\\\":\\\"teleport\\\",\\\"job\\\":\\\"CREATIVE\\\"}\"}}]}");
        check("未知动作/工种被降级", r4.ok() && "say".equals(r4.action()) && r4.job().isEmpty());

        // 完全不是 JSON
        LmStudioWire.Reply r5 = LmStudioWire.parse("{\"choices\":[{\"message\":{\"content\":\"我觉得你应该去砍树。\"}}]}");
        check("非 JSON 回包被降级", !r5.ok());

        // 空/坏回包
        check("空回包被降级", !LmStudioWire.parse("{}").ok() && !LmStudioWire.parse("not json at all").ok());

        // 思考型模型：content 空、话在 reasoning_content 里 → 不能白跑一轮
        LmStudioWire.Reply r6 = LmStudioWire.parse("{\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"\",\"reasoning_content\":\"{\\\"reply\\\":\\\"我在的\\\",\\\"action\\\":\\\"none\\\",\\\"job\\\":\\\"\\\",\\\"item\\\":\\\"\\\",\\\"count\\\":0}\"}}]}");
        check("content 空时回退 reasoning_content", r6.ok() && "我在的".equals(r6.say()));

        // 补全式回包（choices[0].text）也要认得
        LmStudioWire.Reply r7 = LmStudioWire.parse("{\"choices\":[{\"text\":\"{\\\"reply\\\":\\\"好\\\",\\\"action\\\":\\\"none\\\",\\\"job\\\":\\\"\\\",\\\"item\\\":\\\"\\\",\\\"count\\\":0}\"}]}");
        check("补全式 choices[0].text 兜底", r7.ok() && "好".equals(r7.say()));

        // 端点被指到别处的老形状，也只是「回话」而不是「崩掉」
        LmStudioWire.Reply r8 = LmStudioWire.parse("{\"message\":{\"content\":\"{\\\"reply\\\":\\\"老形状\\\",\\\"action\\\":\\\"none\\\"}\"}}");
        check("老式 message.content 兜底", r8.ok() && "老形状".equals(r8.say()));

        // 端点写法宽容：主机 / /v1 / 整条路径，拼出来必须是同一条
        String want = "http://127.0.0.1:1234/v1/chat/completions";
        check("端点补全：主机 + /v1 + 整条路径都拼对",
                want.equals(LmStudioWire.chatUrl("http://127.0.0.1:1234"))
                        && want.equals(LmStudioWire.chatUrl("http://127.0.0.1:1234/v1"))
                        && want.equals(LmStudioWire.chatUrl("http://127.0.0.1:1234/v1/")),
                LmStudioWire.chatUrl("http://127.0.0.1:1234"));

        // 结构化输出的形状：必须是 json_schema（json_object 会被 LM Studio 400 顶回来）
        String fmt = LmStudioWire.responseFormat().toString();
        check("response_format 用 json_schema（不是 json_object）",
                fmt.contains("\"json_schema\"") && !fmt.contains("json_object")
                        && fmt.contains("additionalProperties"));
    }

    // ------------------------------------------------------------------ 真端点用例

    private static void liveCase() throws Exception {
        java.util.List<String[]> history = new java.util.ArrayList<>();
        history.add(new String[]{"玩家说：你好", "{\"reply\":\"主人好\",\"action\":\"none\",\"job\":\"\",\"item\":\"\",\"count\":0}"});
        String body = LmStudioWire.requestBody(MODEL, SYSTEM, FEWSHOT, history,
                "可做的东西列表: [\"minecraft:stone_pickaxe\"]\n她当前：工种=FOLLOW（自主 开），血量 20/20，背包有 石头 x12、木棍 x4\n玩家说：给我做一把石镐",
                4096, 0.2D, 300, false, true);

        HttpRequest request = HttpRequest.newBuilder(URI.create(LmStudioWire.chatUrl(ENDPOINT)))
                .timeout(Duration.ofSeconds(300))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();
        HttpResponse<String> response = HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString());
        check("真模型 HTTP 200", response.statusCode() == 200,
                response.statusCode() == 200 ? null : response.body());
        if (response.statusCode() != 200) {
            return;
        }

        LmStudioWire.Reply reply = LmStudioWire.parse(response.body());
        System.out.println("    她的回话：" + reply.say());
        System.out.println("    动作：" + reply.action() + " / 工种：" + reply.job()
                + " / 物品：" + reply.item() + " / 数量：" + reply.count());
        check("真模型回包可解析", reply.ok(), reply.error());
        check("动作在白名单里", LmStudioWire.ACTIONS.contains(reply.action()));
        check("工种合法或空", reply.job().isEmpty() || LmStudioWire.JOBS.contains(reply.job()));
        check("count 在 1..64", reply.count() >= 1 && reply.count() <= 64);
        check("回话是中文", reply.say().chars().anyMatch(c -> c >= 0x4e00 && c <= 0x9fff));
    }

    private static final String SYSTEM = "你是 Minecraft 里的猫耳娘助理。必须只输出一行 JSON，键固定："
            + "reply(给玩家看的中文一句话)、action(none|say|set_job|craft)、"
            + "job(LUMBER|MINE|FIGHT|FOLLOW，不涉及就空串)、item(只能取「可做的东西列表」里的 id，没有就空串)、count(0-64，不涉及就 0)。"
            + "reply 必须是中文。";

    private static final List<String[]> FEWSHOT = List.of(
            new String[]{"可做的东西列表: [\"minecraft:stone_pickaxe\"]\n她当前：跟随主人。\n玩家说：先做一把石镐",
                    "{\"reply\":\"好的，我这就做一把石镐。\",\"action\":\"craft\",\"job\":\"\",\"item\":\"minecraft:stone_pickaxe\",\"count\":1}"},
            new String[]{"可做的东西列表: []\n她当前：跟随主人。\n玩家说：你好呀",
                    "{\"reply\":\"主人好呀！想让我干点什么？\",\"action\":\"none\",\"job\":\"\",\"item\":\"\",\"count\":0}"});

    private static void check(String what, boolean ok) {
        check(what, ok, null);
    }

    private static void check(String what, boolean ok, String detail) {
        System.out.println("  " + (ok ? "✅ " : "❌ ") + what
                + (ok || detail == null || detail.isEmpty() ? "" : "  —— " + detail));
        if (ok) {
            passed++;
        } else {
            failed++;
        }
    }
}

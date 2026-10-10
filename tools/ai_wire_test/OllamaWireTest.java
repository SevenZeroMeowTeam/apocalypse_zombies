import com.apocalypse.zombies.ai.OllamaWire;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;

/**
 * 门禁用：拿<b>真 Ollama</b> 跑一遍线上那套「拼请求 → 解析 → 约束」的代码。
 *
 * <p>编译/运行（deploy 脚本里就是这么做的）：
 * <pre>
 *   javac -encoding UTF-8 -d build/aiw -cp &lt;gson.jar&gt; \
 *       src/main/java/com/apocalypse/zombies/ai/OllamaWire.java tools/ai_wire_test/OllamaWireTest.java
 *   java -cp "build/aiw;&lt;gson.jar&gt;" OllamaWireTest
 * </pre>
 *
 * <p>它验三件事：①真模型回包能被解析成合法 {@link OllamaWire.Reply}（动作/工种/item/count 都在白名单内）；
 * ②模型胡言乱语（非 JSON、思考标签、字符串 count、越界 count、假 id）一律被降级而不是放行；③端点不通时
 * 抛的是可捕获的异常（上层会变成一句中文提示，不是崩游戏）。</p>
 */
public class OllamaWireTest {

    private static final String ENDPOINT = System.getenv().getOrDefault("AI_TEST_ENDPOINT", "http://127.0.0.1:11434");
    private static final String MODEL = System.getenv().getOrDefault("AI_TEST_MODEL", "fableforge-ai/nexus-coder:q4_k_m");

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
        String leaky = "{\"message\":{\"content\":\"<think>玩家想砍树…</think>{\\\"reply\\\":\\\"好的\\\",\\\"action\\\":\\\"set_job\\\",\\\"job\\\":\\\"lumber\\\",\\\"item\\\":\\\"\\\",\\\"count\\\":0}\"}}";
        OllamaWire.Reply r1 = OllamaWire.parse(leaky);
        check("思考标签剥除 + 小写 job 归一", r1.ok() && r1.wantsSetJob() && "LUMBER".equals(r1.job()));

        // count 写成字符串、超界 → 夹住
        OllamaWire.Reply r2 = OllamaWire.parse("{\"message\":{\"content\":\"{\\\"reply\\\":\\\"做\\\",\\\"action\\\":\\\"craft\\\",\\\"item\\\":\\\"minecraft:stone_pickaxe\\\",\\\"count\\\":\\\"999\\\"}\"}}");
        check("字符串 count + 越界夹到 64", r2.ok() && r2.count() == 64 && r2.wantsCraft());

        // 假 id（没有命名空间）→ 清掉；动作从 craft 降级为 say
        OllamaWire.Reply r3 = OllamaWire.parse("{\"message\":{\"content\":\"{\\\"reply\\\":\\\"给你\\\",\\\"action\\\":\\\"craft\\\",\\\"item\\\":\\\"diamond_sword\\\",\\\"count\\\":1}\"}}");
        check("假 id 被清空、craft 降级", r3.ok() && r3.item().isEmpty() && !r3.wantsCraft());

        // 没见过的动作 → 降级成聊天，绝不透传到执行层
        OllamaWire.Reply r4 = OllamaWire.parse("{\"message\":{\"content\":\"{\\\"reply\\\":\\\"我飞过去\\\",\\\"action\\\":\\\"teleport\\\",\\\"job\\\":\\\"CREATIVE\\\"}\"}}");
        check("未知动作/工种被降级", r4.ok() && "say".equals(r4.action()) && r4.job().isEmpty());

        // 完全不是 JSON
        OllamaWire.Reply r5 = OllamaWire.parse("{\"message\":{\"content\":\"我觉得你应该去砍树。\"}}");
        check("非 JSON 回包被降级", !r5.ok());

        // 空/坏回包
        check("空回包被降级", !OllamaWire.parse("{}").ok() && !OllamaWire.parse("not json at all").ok());
    }

    // ------------------------------------------------------------------ 真端点用例

    private static void liveCase() throws Exception {
        java.util.List<String[]> history = new java.util.ArrayList<>();
        history.add(new String[]{"玩家说：你好", "{\"reply\":\"主人好\",\"action\":\"none\",\"job\":\"\",\"item\":\"\",\"count\":0}"});
        String body = OllamaWire.requestBody(MODEL, SYSTEM, FEWSHOT, history,
                "可做的东西列表: [\"minecraft:stone_pickaxe\"]\n她当前：工种=FOLLOW（自主 开），血量 20/20，背包有 石头 x12、木棍 x4\n玩家说：给我做一把石镐",
                4096, 0.2D, 300, false);

        HttpRequest request = HttpRequest.newBuilder(URI.create(ENDPOINT + "/api/chat"))
                .timeout(Duration.ofSeconds(60))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();
        HttpResponse<String> response = HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString());
        check("真模型 HTTP 200", response.statusCode() == 200);

        OllamaWire.Reply reply = OllamaWire.parse(response.body());
        System.out.println("    她的回话：" + reply.say());
        System.out.println("    动作：" + reply.action() + " / 工种：" + reply.job()
                + " / 物品：" + reply.item() + " / 数量：" + reply.count());
        check("真模型回包可解析", reply.ok());
        check("动作在白名单里", OllamaWire.ACTIONS.contains(reply.action()));
        check("工种合法或空", reply.job().isEmpty() || OllamaWire.JOBS.contains(reply.job()));
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
        System.out.println("  " + (ok ? "✅ " : "❌ ") + what);
        if (ok) {
            passed++;
        } else {
            failed++;
        }
    }
}

package com.apocalypse.zombies.client;

import com.apocalypse.zombies.client.gui.SkyfallTerminalScreen;
import com.apocalypse.zombies.orbital.terminal.TerminalState;
import net.minecraft.client.Minecraft;

/**
 * 服务端包 → 客户端界面之间的唯一桥。只在客户端加载（服务端通过 {@code DistExecutor} 调它）。
 *
 * <p>收到状态快照时：</p>
 * <ul>
 *   <li>{@code open = true}：打开终端界面；</li>
 *   <li>{@code open = false}：如果界面正开在同一台终端上，就地把数据换掉（不重建 Screen，滑条不会跳）。</li>
 * </ul>
 */
public final class SkyfallClientHooks {

    private SkyfallClientHooks() {
    }

    public static void onSync(TerminalState state, boolean open) {
        Minecraft minecraft = Minecraft.getInstance();
        if (open) {
            // 同一台终端重复「打开」时只换数据、不重建 Screen：重建会打断正在拖的滑条，
            // 也会让播放中的过渡动画从头再来。
            if (minecraft.screen instanceof SkyfallTerminalScreen screen
                    && screen.pos().equals(state.pos())) {
                screen.update(state);
            } else {
                minecraft.setScreen(new SkyfallTerminalScreen(state));
            }
            return;
        }
        if (minecraft.screen instanceof SkyfallTerminalScreen screen && screen.pos().equals(state.pos())) {
            screen.update(state);
        }
    }
}

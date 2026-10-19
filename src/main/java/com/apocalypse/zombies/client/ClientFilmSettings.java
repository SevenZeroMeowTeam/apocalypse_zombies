package com.apocalypse.zombies.client;

/**
 * 客户端过场偏好的只读门面（v4.0 P3-c）。
 *
 * <p>渲染层（{@code OrbitalCinematic} / {@code OrbitalScreenFX}）只该关心「要不要演」这一个布尔值，
 * 不该知道配置项叫什么、存在哪份 spec 里 —— 于是留这一层。所有调用都发生在客户端世界里
 * （玩家/世界已存在），此时 CLIENT 配置一定已经加载，不需要额外的未加载保护。</p>
 */
public final class ClientFilmSettings {

    private ClientFilmSettings() {
    }

    /** 是否接受被广播的轨道打击过场；false 时镜头留在玩家自己眼里。 */
    public static boolean broadcastFilms() {
        return ClientConfig.BROADCAST_FILMS.get();
    }
}

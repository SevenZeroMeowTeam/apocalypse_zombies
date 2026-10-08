package com.apocalypse.zombies.item;

/**
 * 枪能装的弹种。
 *
 * <p><b>弹种只记在枪自己的 NBT 里</b>（{@code Ammo} 旁边那个 {@code Shell} 键），不消耗背包物品 ——
 * 与这套枪原本的弹量设计一致（{@code Ammo} 也是 NBT 计数）。玩家的选择来自按住 {@code R} 弹出的轮盘。</p>
 *
 * <p>这个枚举只描述<b>弹种的身份与通用效果</b>；具体打几颗弹丸、每颗多少伤害由各把枪自己决定 ——
 * 同样叫「独头弹」，在 S686 上是"把 8 颗换成 1 颗大弹丸"，在步枪上则没有意义。</p>
 */
public enum AmmoType {

    /** 出厂弹：S686 是 12 号鹿弹（8 颗），其余枪是各自的普通弹。没有额外效果。 */
    STANDARD("standard", 0),
    /**
     * 独头弹：只有霰弹枪有这个弹种 —— 一颗大弹丸换掉一整片小弹丸。
     *
     * <p>它<b>不</b>在这里定义伤害，因为它不是"通用效果"而是"S686 换一套弹道参数"（见 {@code S686Item}）。
     * 放在枚举里是为了让轮盘知道该不该给这把枪显示它。</p>
     */
    SLUG("slug", 0),
    /** 铝热弹：命中敌对生物会把它点着。伤害不变，价值在持续灼烧。 */
    THERMITE("thermite", 5);

    /**
     * stack NBT 里记弹种的键。五把枪共用同一个键，所以"给所有武器加铝热弹"不需要各自的实现。
     */
    public static final String TAG = "Shell";

    private final String id;
    private final int fireSeconds;

    AmmoType(String id, int fireSeconds) {
        this.id = id;
        this.fireSeconds = fireSeconds;
    }

    /** NBT 里存的短标识，也是 lang 键的后半截。 */
    public String id() {
        return id;
    }

    /** 命中后点燃目标的秒数；0 = 不点火。灼烧本身由原版的着火结算。 */
    public int fireSeconds() {
        return fireSeconds;
    }

    /** 存档 / 网络里来的标识 → 枚举；认不出来就退回普通弹（老存档没有这个键）。 */
    public static AmmoType byId(String id) {
        for (AmmoType type : values()) {
            if (type.id.equals(id)) {
                return type;
            }
        }
        return STANDARD;
    }
}

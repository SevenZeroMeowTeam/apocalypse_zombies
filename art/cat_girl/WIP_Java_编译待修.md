# 猫耳娘 v4 - Java 侧编译待修（1.1.66 出货卡点）

来自 `./gradlew compileJava`，共 10 条真错误（已修 `TamableAnimal` import 路径后）。

| 文件 | 行 | 错误 | 出错代码 |
|---|---|---|---|
| `client\ClientModBusEvents.java` | 67 | 错误: 找不到符号 | `public static void onRegisterMenuScreens(net.minecraftforge.client.event.RegisterMenuScreensEven` |
| `entity\menu\CatGirlTradeMenu.java` | 122 | 错误: 找不到符号 | `&& CatGirlTradeMenu.this.countCoins(player) >= Config.CAT_GIRL_ENCHANT_COST.get();` |
| `entity\menu\CatGirlTradeMenu.java` | 129 | 错误: 找不到符号 | `CatGirlTradeMenu.this.consumeCoins(player, Config.CAT_GIRL_ENCHANT_COST.get());` |
| `entity\menu\CatGirlTradeMenu.java` | 174 | 错误: 找不到符号 | `return Config.CAT_GIRL_ENCHANT_COST.get();` |
| `entity\CatGirlEntity.java` | 208 | 错误: 无法将类 WorkBlockGoal中的构造器 WorkBlockGoal应用到给定类型; | `this.goalSelector.addGoal(3, new WorkBlockGoal(this, Job.LUMBER, CatGirlEntity::isLog, ACTION_CH` |
| `entity\CatGirlEntity.java` | 209 | 错误: 无法将类 WorkBlockGoal中的构造器 WorkBlockGoal应用到给定类型; | `this.goalSelector.addGoal(4, new WorkBlockGoal(this, Job.MINE, CatGirlEntity::isOre, ACTION_MINE` |
| `entity\CatGirlEntity.java` | 374 | 错误: 找不到符号 | `if (!this.isOwner(player)) {` |
| `entity\CatGirlEntity.java` | 408 | 错误: 无法将类 ServerPlayer中的方法 openMenu应用到给定类型; | `serverPlayer.openMenu(new SimpleMenuProvider(` |
| `entity\CatGirlEntity.java` | 524 | 错误: 找不到符号 | `String id = net.minecraftforge.registries.ForgeRegistries.ITEM.getKey(stack.getItem()).toString(` |
| `entity\CatGirlEntity.java` | 550 | 错误: 一元运算符 '!' 的操作数类型ItemStack错误 | `if (!this.goods.addItem(stack)) {` |

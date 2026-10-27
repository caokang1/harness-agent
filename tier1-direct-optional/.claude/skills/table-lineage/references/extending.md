# 排查漏报、误报与扩展扫描器

## 扫描器怎么工作

代码在 `S/lineage/scanner.py`，纯正则加括号配对，没有用 Java 编译器。整体分五步：

1. **建模**：解析每个 .java 文件里的类、字段、方法和方法体。类的 key 是"模块|包名.类名"，所以不同模块里同名同包的类不会混在一起。
2. **方法自身的读写**：
   - SQL 来源：方法注解上的 `@Select/@Insert/@Update/@Delete`，以及同 namespace 的 Mapper XML。
   - MyBatis-Plus 内置方法（selectList、insert、save 等）按实体的 `@TableName` 判定表。
   - `${}` 动态表名：用调用方方法体里的字符串字面量去匹配已知表名。
3. **调用解析**：调用目标从这些地方找：注入字段、局部变量、参数、父类、实现类、链式调用的返回类型。
   - Feign 接口的调用会跳到别的模块里实现它的 Controller。
4. **入口和汇总**：从入口出发汇总所有可达的读写，循环调用用强连通分量统一求解。入口包括 `@KafkaListener`、Controller 方法、`@XxlJob`、`@Scheduled`、配置的调度基类。
5. **组装页面数据**：`S/lineage/build.py` 做以下几件事：
   - 把表名解析到"库.表"：同名表靠 mapper_package_db、module_db 判断；
   - 判定上游档位：binlog > 转发 > SQL > Feign 3 层内 > 更深；
   - 判定表的分类和状态；
   - 计算代码指纹。

## 排查一条漏报或误报

1. 在页面上打开这张表，到"写入与调度"标签，展开写入入口的**调用链**，看扫描是从哪个入口、经过哪些方法到达写入的。
2. **漏了写入方**，按顺序查：
   1. 写入 SQL 有没有被识别：在 `runs/<run>/scan.json` 的 `code.<表名>.mappers` 里找；
   2. 写入方法的调用方能不能解析到：常见原因有字段类型是接口但实现类在别的模块、通过 `ApplicationContext.getBean` 动态取得、lambda 或方法引用传递、反射；
   3. 入口有没有被识别：看 `scan.json` 的 `entries`。
3. **漏了上游**：
   - binlog 订阅：确认 `cdc` 配置的写法和代码一致；
   - SQL 读：确认读的方法在写入路径上。扫描只把写入路径上的读算作上游；查询方法名以 get、query、select、find、list、load、fetch、count 等开头时，也会整体算进去；
   - Feign：确认对方实现里的读在 `feign_shallow_levels` 层以内。
4. **多报上游**：最常见的原因有三个，都属于已知限制，在 accuracy_notes 里说明即可：
   - 同一个方法同时写两张表，两张表会互相算成上游；
   - 一个入口按事件类型分发给多个处理器，所有分支读到的表都会算进来；
   - SQL 里 JOIN 进来的表一律算作读取，即使取出的字段后来没有用到。

## 扩展扫描器

改代码前先想清楚：这个写法在项目里出现多少次？能不能通过配置解决？只有一两处的写法，在 accuracy_notes 里写明是盲区，往往比改扫描器更划算。

确实要改时：

1. **把识别规则做成配置项**，不要写死项目里的类名。参考 `cdc`、`scheduler` 的做法：在 scanner.py 开头读配置，在对应位置使用。
2. **加一个最小复现**：在 `assets/demo/repo` 里加一个用这种写法的类，在 `assets/demo/metadata` 里加对应的表，在 `assets/demo/workspace/knowledge/truth/1_demo.json` 里加标准答案。然后更新 `assets/demo/expected_evaluation.json`（写入新的计数）。
3. **跑两遍自测**，都必须全部通过：

   ```bash
   python S/tools/selftest.py
   python S/tools/selftest.py --workspace <workspace> --meta-csv <元数据目录>
   ```

   第一遍在示例项目上，第二遍在当前项目上，确认每组标准答案的成绩都没有下降。

4. **确定性**：输出必须逐字节可复现。run.py 已经固定了哈希种子。新代码里遍历 set 或 dict 后输出的地方，要先排序。

## 常见的扩展方向

| 写法 | 思路 |
|---|---|
| JPA `@Entity` + `@Table(name=...)` + `JpaRepository` | 仿照 MyBatis-Plus：把 `@Table` 当成 `@TableName`，把 Repository 的 save、delete、find 系列当成内置方法 |
| 注解声明订阅，如 `@Subscribe(table="db.t")` | 在 `analyze_method` 里读方法注解，直接产出 SUB 效果 |
| `JdbcTemplate` 拼 SQL | 对方法体里的字符串字面量跑 `sql_tables` |
| RocketMQ 等其他消息队列的监听 | 在 `entries()` 里加一种 kind，让它和 kafka 一样参与"实时写入"判定 |

# config/project.json 字段说明

每个字段都是对项目的一个假设。每次运行开头会做自检：库、表、模块不存在就报警告。但自检只能发现"写错了"，发现不了"漏写了"，所以第一次配置要逐项核实。

## 目录

- [基本](#基本)
- [modules：模块角色](#modules模块角色)
- [databases：库的角色与归属](#databases库的角色与归属)
- [cdc：binlog 订阅写法（可选）](#cdcbinlog-订阅写法可选)
- [scheduler：自研调度基类（可选）](#scheduler自研调度基类可选)
- [metadata：分表合并](#metadata分表合并)
- [er：ER 图](#erer-图)
- [page：页面](#page页面)

## 基本

| 字段 | 含义 |
|---|---|
| `project` | 项目名，用于页面标题 |
| `repo` | 代码仓库路径。可以写相对于工作目录的路径；运行时可以用 `--repo` 覆盖 |
| `scan.skip_dirs` | 不扫描的目录名，比如 target、test、文档目录 |
| `scan.feign_shallow_levels` | 跨服务（Feign）读取时，对方实现里几层以内的查询算作上游，默认 3（Controller → Service → Mapper）。更深的读取单独折叠，不计入上游 |

## modules：模块角色

模块指仓库的顶层目录。

### `external`：对外模块

这些模块里的 HTTP 接口会作为页面上的"外部查询接口"，表示后台页面或外部调用方读了哪些表。

- **典型例子**：运营后台、网关、开放平台。
- **怎么核实**：打开模块里几个 Controller，看是不是给页面或第三方调用的。
- **常见错误**：把业务服务也列进来。这样会让"外部接口"变得非常多，失去意义。

### `shared`、`shared_prefix`：共享模块

公共库模块，比如放 Feign 接口、DTO、工具类的那种。类名解析冲突时会优先在这里找。

- 一般列出名字即可；所有共享模块名字有统一前缀时，也可以用 `shared_prefix`。
- **怎么核实**：看这个模块是否被多个服务依赖，并且自己没有启动类。依赖关系可以看各服务的 pom 或 build 文件；构建文件里看不出来时，就看别的模块是否 import 了它的包。

## databases：库的角色与归属

### `infra`：基础设施库

配置中心、调度、binlog 管理等系统自身的库。这些库里的表一律分类为"基础设施"。

### `report`：报表库

报表库里的表分类为"报表"或"中间表"。有其他报表从它取数的是"中间表"。会为这些表计算状态、要求写口径卡片。

- **这一项必须问用户确认**，survey 只能按库名猜。

### `report_tables_outside`

放在业务库里、但其实是报表的表。写成 `库.表` 形式。

### `report_exclude`

放在报表库里、但不是报表的表，写成 `库.表`。典型例子是配置表、规则表、从业务库同步过来的维表副本。

列进来的表按普通业务表处理：
- 不计算报表状态；
- 不要求写口径卡片；
- 不再把引用它的报表表变成"中间表"。

### `verify_log_tables`

校验日志表，写成 `库.表`。配置后有两个效果：
- 它们不作为任何表的上游；
- 写它们的 Job 被视为"校验 Job"，单独列出，不算读取方。

它们**自己的分类不变**：在报表库里，依然显示为"报表"，通常状态是"写而不读"。不想让它们出现在报表统计里，再把它们加进 `report_exclude`。

### `mapper_package_db`

Mapper 所在包路径里的片段对应它连接的库。

- **作用**：同名表分属多个库时，靠这个判断表属于哪个库。比如报表库和业务库各有一张 `store` 表。
- **怎么核实**：看各服务的数据源配置，比如多数据源注解，或 `@MapperScan(basePackages=..., sqlSessionFactoryRef=...)`。
- survey 只写入了投票纯度 ≥80% 的片段。

### `module_db`

模块默认连接的库。包路径判断不出来时使用。

### `business_db_labels`

业务库的显示名，比如 `"shop_order": "订单（业务库）"`。总览里"业务底表按库"会用这个名字。

## cdc：binlog 订阅写法（可选）

适用于用 canal、Debezium 等把 binlog 推到消息队列，再由代码里的监听加工成报表的项目。扫描器要知道代码用什么写法声明"这个监听订阅哪些表"。没有这类机制的项目可以整段不写。

| 字段 | 代码里的样子 | 说明 |
|---|---|---|
| `table_ref_type` | `List<TableRef> ORDER_TABLES = Arrays.asList(new TableRef("shop_order", "orders"));` | 订阅清单里元素的类型，构造参数依次是（库, 表）。支持 `Arrays.asList`、`List.of` 和双大括号初始化 |
| `registry_class` | `CdcTables.ORDER_TABLES` | 集中存放订阅清单的**类名**（以代码里声明的 `class` 名为准，不是文件名）。监听里引用 `类名.常量` 就视为订阅。清单放在共享模块里也能找到 |
| `check_method` | `if (!event.matches(CdcTables.ORDER_TABLES)) return;` | 用清单判断是否处理的方法名。同一个文件里声明的清单也能识别 |
| `topic_marker` | `@KafkaListener(topics = "cdc.shop_order")` | 直接接 binlog 的 topic 都带的片段，用来区分"直接订阅"和"内部转发" |
| `route_rule_type` | `new Route("shop_order", "refund", Topics.REFUND)` | （可选）按表把 binlog 路由到内部 topic 的配置类。参数依次是（库, 表, 目标 topic 常量...） |

转发链会自动识别：一个监听用 `xxx.send(TOPIC_CONST, ...)` 把消息发到内部 topic，另一个监听订阅这个 topic。后一个监听会继承前一个的订阅表，上游标为"binlog 经内部 topic 转发"。

**怎么核实**：读一个报表监听，从 `@KafkaListener` 一直跟到它判断表名的地方。

配置后再跑一次。如果出现自检警告"没有任何 Kafka 监听解析出订阅表"，说明类名或方法名没对上。确认无误时，页面上报表的上游里会出现"binlog 实时订阅"。

如果项目的写法和上面都不一样，比如用注解声明订阅，或者在配置文件里声明，就需要扩展扫描器，见 [extending.md](extending.md)。扩展前，这类报表的上游会漏掉，准确率测试能把它暴露出来。

## scheduler：自研调度基类（可选）

`@XxlJob` 和 `@Scheduled` 自动识别。HTTP 接口被 xxl-job 按 URL 调用的情况，靠 `xxl_jobs.csv` 里的 `executor_param` 识别。

如果项目有自研调度框架，按约定方法名触发子类，就配置 `handler_base`：

```json
"scheduler": {"handler_base": {"method": "process", "class_prefix": "Schedule", "class_suffix": "Handler"}}
```

配置后，父类名以 `class_prefix` 开头、以 `class_suffix` 结尾的类，它的 `method` 方法算作定时入口。

## metadata：分表合并

| 字段 | 默认 | 说明 |
|---|---|---|
| `shard_suffix_regex` | `^(.*?)(_(?:\d{6,8}\|\d{1,4}))$` | 第一遍：去掉数字后缀，比如 `_0`..`_9999`、`_202501`、`_20250101`。只有一张的不合并 |
| `date_partition_regex` | `["^(.*)_\d{4}_\d{2}$", "^(.*)_\d{4}$"]` | 第二遍：按年、年月分表的再合并 |
| `backup_regex` | `_(bak\|backup\|copy\|old\|tmp\|temp\|test)\d*$\|_\d{6,8}$\|^tmp_\|^test_\|^bak_` | 匹配的单表分类为"备份/临时" |

**怎么核实**：看 report.md 里的物理表数和逻辑表数；在页面表目录里搜几个分表，看合并是否合理。

## er：ER 图

| 字段 | 说明 |
|---|---|
| `core_tables` | 只画这些表，写成 `库.表`，建议 10 到 20 张。第一次运行后，report.md 末尾的"ER 核心表候选"会列出报表最常取数的业务表，从中挑选 |
| `column_alias` | 字段名对应的目标表名，用于 `xxx_id` 命名对不上的情况，比如 `{"order_id": "orders"}` |
| `tenant_column`、`tenant_table` | （可选）几乎每张表都有的租户或机构字段，比如 `tenant_id`。它的关联线默认隐藏，页面上可以勾选显示。只有目标表里也有同名字段时才填 |
| `db_order` | ER 图里各库从左到右的顺序 |

关系线分两种：
- **实线**：代码 SQL 里真实出现过的 JOIN，可以看到出处；
- **虚线**：按字段命名推断的关联。

## page：页面

| 字段 | 说明 |
|---|---|
| `title` | 页面标题，默认是"项目名 库表血缘" |
| `example_table` | 总览页"看个例子"用的表，默认取上游最多的已核对报表 |
| `readers_cap` | 每张表最多显示多少个读取方，默认 40 |

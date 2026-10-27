# table-lineage

一个 Claude skill：从 **Java / Spring / MyBatis 微服务代码** 加 **MySQL 元数据**，生成可交互的库表血缘页面。页面回答这些问题：

- 每张表由谁写入；
- 从哪些表取数，以及取数方式：binlog 订阅、SQL、Feign；
- 谁在读；
- 属于哪个业务域。

页面还附有口径卡片、问题清单和 ER 图。

它和普通血缘工具的区别在于：**准确率是实测的**。每个项目都用独立人工核对的标准答案打分；代码或数据库变化后重跑，会自动标出哪些人工结论已经过期。

## 安装

把整个目录放到 Claude 的 skills 目录，比如 `~/.claude/skills/table-lineage/`，或者把打包好的 `.skill` 文件导入 Claude。

之后对 Claude 说这类话就会触发：
- "帮我理清这个项目的报表都是怎么来的"
- "做个库表血缘页面"

完整流程见 [SKILL.md](SKILL.md)。

## 不经过 Claude 直接试用

需要 Python 3.11 及以上，只用标准库。

```bash
# 在自带的示例项目上自测
python scripts/tools/selftest.py

# 在示例项目上生成页面，结果在 assets/demo/workspace/runs/
cd assets/demo/workspace
python ../../../scripts/run.py --meta-csv ../metadata --no-latest
```

用在自己的项目上时，先用勘察工具生成配置草稿：

```bash
python scripts/tools/survey.py --repo <代码仓库> --meta-csv <元数据目录> --workspace <工作目录>
```

元数据用 `scripts/sql/export_metadata.sql` 里的 4 条查询导出。然后按 SKILL.md 的步骤确认配置、运行、建立标准答案。

## 目录

| 路径 | 内容 |
|---|---|
| `SKILL.md` | 给 Claude 的工作流程 |
| `references/` | 配置说明、标准答案方法、口径卡片、扩展扫描器 |
| `scripts/` | 引擎：run.py、lineage/（元数据、扫描、组装、打分、自检）、web/ 页面模板、tools/（survey、rebaseline、selftest） |
| `assets/` | 知识库骨架、数据库连接模板，以及一个完全虚构的示例项目（用于自测） |

## 已知限制

不处理以下内容：
- JPA/Hibernate 实体关系；
- MongoDB、Redis、ES 的读写；
- RestTemplate 等拼 URL 的 HTTP 调用；
- 非 Java 代码。

详见 SKILL.md 和 references/extending.md。

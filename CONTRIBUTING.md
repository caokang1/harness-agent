# 参与贡献

欢迎提 Issue 和 Pull Request。这份文档说明怎么在本地改动、验证，以及几类常见改动要同步修改哪些地方。

## 提 Issue

请附上：

- 你的环境：操作系统（macOS / Linux / WSL / Git Bash）、`bash --version` 的第一行、构建工具（Gradle / Maven）。
- 你运行的命令和完整输出。如果是识别结果不对，贴上 `--auto --dry-run` 的输出。
- 你期望的结果。

请不要贴任何账号、密码、Token 或内部地址。

## 本地开发

```bash
git clone https://github.com/caokang1/harness-agent.git
cd harness-agent
```

起步包没有构建步骤，改完直接拿一个示例项目验证：

```bash
# 准备一个最小的多模块 Spring Boot 示例项目
mkdir -p /tmp/demo-svc/common /tmp/demo-svc/start/src/main/java/com/example/demo
printf "rootProject.name = 'demo-svc'\ninclude 'common', 'start'\n" > /tmp/demo-svc/settings.gradle
touch /tmp/demo-svc/build.gradle
printf 'package com.example.demo;\nimport org.springframework.boot.autoconfigure.SpringBootApplication;\n@SpringBootApplication\npublic class DemoApplication {}\n' \
  > /tmp/demo-svc/start/src/main/java/com/example/demo/DemoApplication.java

# 用本地代码安装到示例项目
cd /tmp/demo-svc && HARNESS_TARGET_DIR=/tmp/demo-svc bash /path/to/harness-agent/init.sh --auto --yes

# 验证卸载能删干净
bash /path/to/harness-agent/uninstall.sh --yes
```

## 提交前自检

| 改了什么 | 至少要做的验证 |
|---|---|
| 任何 `.sh` 文件 | `bash -n <文件>`；有 [shellcheck](https://www.shellcheck.net/) 的话跑 `shellcheck -S error <文件>` |
| `init.sh` / `uninstall.sh` / `detect-project.sh` | 按上面的「本地开发」装一次、卸一次，Gradle 和 Maven 项目各一次 |
| `scripts/build-installer.sh` | 打包后用 `dist/install.sh --auto --yes` 装一次，确认和直接运行 `init.sh` 的结果一致 |
| 带测试的 skill | 运行它自带的测试，例如 `python3 tier1-direct-optional/.claude/skills/zentao/scripts/run_tests.py` |
| 文档 | 文档里的参数、文件名、skill 数量与代码一致；README、INSTALL、CUSTOMIZE、docs/USAGE.md 之间没有互相矛盾 |

脚本需要兼容 **bash 3.2**（macOS 自带）和 GNU / BSD 两套命令行工具。不要用关联数组、`mapfile`、`${var,,}`、`sed -i`（不带后缀）、`grep -P`。

## 几类常见改动

### 新增一个可选 skill

1. 放到 `tier1-direct-optional/.claude/skills/<名字>/`。
2. `init.sh`：在帮助注释里写上新参数，加一个 `INCLUDE_<名字>` 开关和参数解析，在「1b. Tier 1 可选」一节调用 `_install_optional <名字>`，并写进安装日志。
3. `uninstall.sh`：把名字加进 `HARNESS_SKILLS`，这是没有安装清单的旧版安装用的删除范围。
4. `scripts/build-installer.sh`：在生成的 `install.sh` 头部注释里补上参数。
5. 文档：README 的可选 skill 表、INSTALL.md 的参数表、CUSTOMIZE.md §D、docs/USAGE.md 的「可选 skill」一节。
6. skill 带脚本时：只依赖标准库，附带离线测试，并在 SKILL.md 里写清楚怎么运行。
7. 来自第三方的内容：保留原许可证文件，并在 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 里登记来源和许可证。

### 改动 AGENTS.md 或方法论 skill

`tier2-template/AGENTS.md` 是 AI 在项目里遵守的总规则，skill 不能和它冲突。最容易冲突的是 git 操作：AGENTS.md 规定**未经用户确认不能 commit / push**，skill 里涉及提交、推送、合并的步骤都要以它为准。

### 对外的读写操作

需要连接外部系统（Jenkins、禅道等）的 skill，参照现有的 `jenkins-deploy` 和 `zentao`：

- 凭据只放在用户目录下的配置文件里（权限 600），不写进项目，也不写进命令行参数。
- 默认拒绝明文 HTTP，需要用户显式允许。
- 写操作先预览，再凭确认码执行。

## 提交信息

用中文写，第一行说清楚做了什么，正文说明原因和影响范围。示例：

```
新增可选 skill zentao：禅道任务 / Bug 协作与工时记录

- 安装时加 --include-zentao，默认不装
- ...
```

## 许可证

提交即表示你同意你的贡献按本仓库的 [MIT 许可证](LICENSE) 发布。

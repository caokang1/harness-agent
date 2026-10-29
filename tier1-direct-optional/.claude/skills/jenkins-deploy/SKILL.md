---
name: jenkins-deploy
description: 触发 Jenkins 参数化任务的构建：按当前 Git 仓库找到对应任务，用当前分支 / 标签推断参数，先展示给用户确认，确认后才触发，并在后台监控结果。用户明确提到 Jenkins 并要求构建、发布、打包时使用，例如"用 Jenkins 发一下""Jenkins 打个包""触发 Jenkins 构建"。只触发已有任务，不创建或修改任务。
---

# Jenkins 发布

脚本：本文件同级的 `scripts/jenkins_deploy.py`（下文写作 `jd`；项目级安装时路径是 `.claude/skills/jenkins-deploy/scripts/jenkins_deploy.py`），在业务项目的 Git 仓库根目录下执行，只依赖 Python 3.8+ 标准库。

## 一条命令发布

用户输入 `/jenkins-deploy [任务] [参数=值 ...]`，例如 `/jenkins-deploy`、`/jenkins-deploy team/svc-dev deployEnv=test`，就直接按下面的「流程」跑完：找任务 → 模拟运行 → 请用户确认 → 触发 → 后台监控。
- 中间**只停一次**，等用户确认。
- 命令里的 `参数=值` 合并成 JSON 放进 `--params`。

**每次触发都必须经过用户确认。**构建可能直接部署到环境，所以确认码机制保证触发的任务、参数、提交和用户看到的完全一致。

## 首次配置

Jenkins 地址和凭据只来自用户自己的配置，脚本里没有内置任何服务器地址。

- 推荐写配置文件 `~/.config/jenkins-deploy/config.json`，并执行 `chmod 600`。
- 也可以用环境变量 `JENKINS_URL` / `JENKINS_USER` / `JENKINS_TOKEN`，环境变量优先。

```json
{
  "url": "https://jenkins.example.com",
  "user": "<用户名>",
  "token": "<API Token>",
  "folders": ["team-a/dev", "team-a/test"]
}
```

- `folders` 可选：只扫描这些文件夹下的任务。不填就扫描整个 Jenkins，任务多时会比较慢。
- 默认拒绝 `http://` 地址，避免凭据明文传输。只能用 http 的内网环境，要用户自己加 `"allow_http": true`。
- 用户在对话里直接给了 Token：替用户写进配置文件并 `chmod 600`，回复里不要复述 Token，也不要写进项目目录。

更多说明见 [references/config.md](references/config.md)。

## 流程

1. **找任务**：按这个顺序确定任务，确定了就直接进入第 2 步。
   - 命令里指定的任务。
   - 仓库根目录 `.jenkins-deploy.json` 里的 `{"job": "<任务完整路径>"}`。这个文件团队共用，可以提交；dry-run 不带任务名时会自动读取它。
   - 都没有时，运行 `python3 jd --list` 按仓库地址匹配：只有一个就用它；有多个就问用户选哪个，不要猜；一个都没有就用 `--list --all` 列出来让用户指定。
   - 用户确认任务后，建议把它写进 `.jenkins-deploy.json`，以后不用再选。
2. **模拟运行**：`python3 jd <任务> --dry-run [--params '<JSON>']`。
   - 分支参数（`repoBranch` / `BRANCH` / `GIT_BRANCH` 等）自动填当前分支。
   - 标签参数自动填**当前提交上**的标签。
   - 其他参数用任务的默认值。用户指定的值放进 `--params`。
3. **确认**：把 dry-run 输出的整块内容（任务、参数、提交、⚠ 警告、确认码）原样发给用户，问"确认触发吗？"，然后**停下来等回复**。
   - 有 ✗ 错误时不能触发，先按提示解决，比如先 push、改参数。不要自己 push。
   - 用户明确同意（"确认 / 发 / 可以"）才进入下一步。用户要改参数，就回到第 2 步重新 dry-run。
   - 上一次的确认不能用于下一次触发。
4. **触发**：`python3 jd <任务> --trigger <确认码> [与第 2 步相同的 --params]`，输出 JSON：`queue_id`、`full_name`。
   - 提示"确认码不一致"说明任务、参数或远端提交变了，必须回到第 2 步，让用户重新确认。
5. **监控**：用后台任务运行（Claude Code 的 Bash 设 `run_in_background=true`）：
   `python3 jd --monitor-only --full-name <full_name> --queue-id <queue_id>`。
   - 结束后告诉用户结果和构建地址；失败时说明在哪一步失败，不要自动重试。
   - 结束监控只会停止观察，不会停止 Jenkins 上的构建。

## 停止构建

用户明确要求停止时，先复述"将停止 <任务> #<构建号>"并得到确认，再执行：
`python3 jd --stop <构建号> --full-name <任务完整路径>`

## 不要做

- 不经用户确认就 `--trigger`，或者自己 dry-run 拿到确认码后直接触发。
- 为了让构建包含本地改动，自己 commit、push 或打标签。
- 构建失败后自动重试，或者主动停止构建。
- 把 Token 写进项目文件、命令行参数或回复里。

---
改编自 [ABCFed/claude-marketplace](https://github.com/ABCFed/claude-marketplace) 的 jenkins-deploy（MIT License），已去除其内部配置并重写了安全相关逻辑。

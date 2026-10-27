# tasks.md（实施任务模板）

> 这是 OpenSpec 变更四件套的第三份。**目的：把 design.md 拆成可勾选的最小动作清单**。
>
> 写完后等用户最后 review 一次再开始 apply（写代码）。
>
> Apply 过程中，每完成一个 task 立即在这里勾选 `[x]`；遇到与计划不一致时**不能直接做**，回到 design.md 加"决策 N+1"记录偏差，再继续。

---

## 任务粒度规则

- **每条 task 1 个动作 + 1 个对象**：例如"在 X 类中新增 Y 字段"，不要塞 3 件事
- **每条 task 5-30 分钟可完成**：太大要拆，太小可以合并
- **失败的 task 用 `[~]` 放弃态标记**：写明放弃理由（例如"已被决策 N 替代方案覆盖"），保留诚实记录
- **跨 session 必须保证勾选状态与代码一致**：否则就是 `tasks-traceability` 类 learning

---

## 1. <模块/主题 1>

- [ ] 1.1 在 `<file>` 中新增 ...
- [ ] 1.2 在 `<file>` 中修改 ...
- [ ] 1.3 编写 DDL migration：`ALTER TABLE xxx ...`
- [ ] 1.4 ...
- [ ] 1.5 ...

## 2. <模块/主题 2>

- [ ] 2.1 在 `<file>` 中实现 ... 的运行时逻辑
- [ ] 2.2 ...（注意：本步**必须**使用 `<API>` 而不是 `<其他 API>`，原因见 design.md §决策 N）
- [ ] 2.3 ...

## 3. <后端 API>

- [ ] 3.1 在 `<Controller>` 中新增 `<METHOD> <path>`
- [ ] 3.2 在 `<Service>` 中实现业务逻辑
- [ ] 3.3 在 `<DTO>` 中新增 ... 字段
- [ ] 3.4 编写单测覆盖 ...

## 4. <前端>

- [ ] 4.1 在 `src/views/<domain>/<File>.vue` 新增 ...
- [ ] 4.2 在 `src/api/<resource>.ts` 新增 API 调用
- [ ] 4.3 在 `src/store/<resource>.ts` 新增 store action
- [ ] 4.4 ...

## 5. 文档与规则

- [ ] 5.1 更新 `BACKEND_RULES.md` 中 ... 段（如新增了规则）
- [ ] 5.2 更新 `AGENTS.md` 中规则变更日志（仅当本次变更涉及 AGENTS.md 硬条款时）

## 6. 测试与 Verify

- [ ] 6.1 跑 `bash dev.sh check --arch` 通过
- [ ] 6.2 跑相关单测
- [ ] 6.3 跑 `bash dev.sh verify-snapshot before` 留基线
- [ ] 6.4 **暂停**——告知用户进入手测阶段

## 7. 用户 Verify（人工节点）

> ⚠️ **本节由用户操作，AI 不能勾选**。AI 在 6.4 暂停后等用户手测，用户操作完后告知"通过"。

- [ ] 7.1 用户进入页面 / 跑 case，确认 ... 行为符合预期
- [ ] 7.2 用户跑 `bash dev.sh verify-snapshot after && bash dev.sh verify-snapshot diff`，确认 delta 合理
- [ ] 7.3 **用户明确说"通过"**

## 8. Commit & Archive

> ⚠️ **必须等用户在 7.3 明确说通过后才能执行**。

- [ ] 8.1 `git commit`（commit message 引用本变更名）
- [ ] 8.2 在同一个 push 周期内回填本 tasks.md 的勾选状态
- [ ] 8.3 跑 `openspec archive <change-name>`（生成 TRACE.md 记录偏差）

---

> Apply 完成后这份文件应该满屏 `[x]`（少量 `[~]` 也可，附理由即可）。任何 `[ ]` 残留 = 没完成。

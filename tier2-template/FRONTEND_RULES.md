# FRONTEND_RULES.md — 前端编码规则

> 本文件是**人话版规则**，对应 `dev.sh check --arch` 里的前端 grep 检测。
> 改一条规则要在两个地方留痕：本文件加段、`dev.sh` 加/改 `_check`。

---

## 强制触发规则（每次改前端代码前先过一遍）

打开你即将修改的文件，回答下列 4 个问题：

1. 这个改动会让 `views/<A>/` 里的文件 import `views/<B>/` 里的内部文件吗？→ §文件职责边界
2. 这个改动会让组件直接操作 store 字段，而不是通过 action 吗？→ §状态管理
3. 这个改动会用到 `storeToRefs` 之外的方式解构 Pinia store 吗？→ §响应式陷阱
4. 这个改动会在 `scoped` 样式里用 `@apply` 写 `border-style` 类的语法吗？→ §样式约定

4 个问题 OK 才能开始改代码。

---

## §文件职责边界

### 目录约定

```
src/
├── views/                       # 路由级页面
│   ├── {{DOMAIN_1}}/            # 例：market
│   ├── {{DOMAIN_2}}/            # 例：skills
│   ├── {{DOMAIN_3}}/            # 例：admin
│   └── {{DOMAIN_4}}/            # 例：common（共享路由页）
├── components/                  # 跨域复用的展示组件
├── composables/                 # 跨域复用的逻辑（useXxx）
├── store/                       # Pinia store
├── api/                         # 后端 API 调用
└── utils/                       # 纯函数工具
```

### 硬规则

| # | 规则 | dev.sh 检测 |
|---|------|-----------|
| R1 | **`views/<A>/` 里的文件禁止 import `views/<B>/` 里的内部文件**（A ≠ B）| `frontend-cross-domain` |
| R2 | 跨域共享内容必须抽到 `src/components/` 或 `src/composables/` | （review 检测）|
| R3 | `views/<A>/` 内部可以自由 import 自身子目录 | （正向，无检测）|

### 修复模板

```ts
// ❌ 反模式：market 页面 import skills 页面的内部组件
import { ToolList } from '@/views/skills/components/ToolList.vue'

// ✅ 正确做法：抽到 components/
import { ToolList } from '@/components/ToolList.vue'
// 或抽成 composable
import { useToolList } from '@/composables/useToolList.ts'
```

### 为什么这条这么严格？

跨域 import 是"上帝模块"反模式的最常见入口——一个 view 引用另一个 view 的内部，等于把两个域的实现细节耦合死。重构其中一个域时不可避免地要碰另一个域。

---

## §状态管理（Pinia）

### 硬规则

| # | 规则 | 检测 |
|---|------|-----|
| R1 | 组件读 store 用 getter / `storeToRefs`；写 store 用 action（**禁止组件直接赋值 state 字段**）| review |
| R2 | store 里禁止 import 任何 `views/` 文件（防循环）| review |
| R3 | API 调用集中在 store action 里，组件只调 action 不直接 import api 模块 | review（推荐）|

### 修复模板

```ts
// ❌ 反模式
const store = useToolStore()
store.toolList.push(newTool)  // 组件直接改 state

// ✅ 正确做法
const store = useToolStore()
store.addTool(newTool)  // 通过 action
```

---

## §响应式陷阱

### 硬规则

| # | 规则 | 检测 |
|---|------|-----|
| R1 | **Pinia store 解构必须用 `storeToRefs`**，否则 ref 字段失去响应性 | review |
| R2 | `reactive()` 对象不能整体替换（破坏响应性），用 `Object.assign` 或重建 ref | review |
| R3 | `ref<T>()` 内部用 `.value`，模板里直接写不带 `.value` | （Vue 编译器处理，无需检测）|

### 修复模板

```ts
// ❌ 反模式
const { toolList, currentTool } = useToolStore()  // toolList 不再响应式

// ✅ 正确做法
import { storeToRefs } from 'pinia'
const store = useToolStore()
const { toolList, currentTool } = storeToRefs(store)
const { addTool } = store  // action 直接解构 OK
```

---

## §样式约定

### 硬规则

| # | 规则 | 检测 |
|---|------|-----|
| R1 | **`<style scoped>` 里禁止用 `@apply` 写 `border-style` 系列**（Tailwind 在 scoped 下不会注入 border-style）| review |
| R2 | 全局样式用 `<style>` (无 scoped)，并加 `[data-scope]` 类前缀避免污染 | review |
| R3 | 样式优先级：CSS 变量 > 组件内 `style` > Tailwind class > 全局样式 | （指南）|

### 修复模板

```vue
<!-- ❌ 反模式 -->
<style scoped>
.box {
  @apply border;  /* 边框消失！scoped 下 border-style 没注入 */
}
</style>

<!-- ✅ 正确做法 -->
<style scoped>
.box {
  @apply border border-solid;  /* 显式补上 border-style */
  /* 或者 */
  border: 1px solid theme('colors.gray.300');
}
</style>
```

---

## §路由约定

### 硬规则

| # | 规则 | 检测 |
|---|------|-----|
| R1 | **`router.push(name, params)` 第二参数不是路由选项**——传参用 `query` / `params` 字段 | review |
| R2 | 跨域跳转必须经 `router.push({ name: '...' })`，禁止 `router.push('/path')` 硬编码路径 | review |
| R3 | 大页面用 `defineAsyncComponent` 或路由懒加载，避免首屏 bundle 膨胀 | review（推荐）|

---

## §HTTP & API 调用

| 项 | 约定 |
|---|------|
| 统一封装 | `src/api/client.ts` 封装 axios 实例，集中处理鉴权、错误码、loading |
| 错误处理 | 业务错误（4xx）由 store action 决定如何处理；网络错误（5xx）统一弹 toast |
| 文件下载 | 优先 `window.open(url, '_blank')`，仅在需带 token 时用 `axios + blob`（用户手势上下文丢失风险）|
| 时间字段 | 后端返回字符串 `yyyy-MM-dd HH:mm:ss`，前端用 dayjs 处理（统一团队约定）|

---

## §Learning 晋升示范

> _（暂无晋升条目。从你项目的第一次 promotion 开始填。）_

---

## §作废规则（archived）

> _（暂无作废规则。）_

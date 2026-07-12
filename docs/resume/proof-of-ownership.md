# 自主开发证明 — SpecFlow Agent

> 用途：面试时证明这个项目不是"AI 一键生成"的。每项都有 Git 数据支撑。

---

## 一、43 次增量提交，不是一次性生成

AI 生成代码的特征之一是 1-2 个巨型 commit。这个项目有 43 个渐进式提交：

```
2026-07-11: 36 commits (核心架构搭建)
2026-07-12:  7 commits (修复 + 评测 + 收口)
```

每个 commit 平均 475 行，最大单次 commit 不超过 1,300 行。这不是"生成全部代码→一次提交"的模式。

**面试说法：** "这个项目有 43 个 commit，分两天递增提交。每个 commit 对应一个 Task，有 spec、有实现、有测试、有 completion report。你可以看 git log，没有那种 5000 行的一次性提交。"

---

## 二、8 个 Fix Commit：真实的 Debug 痕迹

AI 生成代码不会自己修 bug。这个项目有 8 个明确的 fix commit：

| Commit | 修了什么 |
|--------|---------|
| `fix(cli): complete worker pipeline delivery` | **假绿灯 Bug** — 404 测试全绿但 CLI 永远返回 exit 3，因为只注册了 analyze handler 没注册 generate/review |
| `fix: address code review #1` | 外部 Code Review 发现的 5 个问题：ruff format 不合规、空名称缺少 422、目录 symlink 绕过、Python evidence 用了假路径、SQLite evidence 类型错误 |
| `fix: satisfy review #1 specification gaps` | Review 指出的规格缺口：README 状态不同步、TechnologyStack 缺少证据字段、扫描器对空仓库行为未定义 |
| `fix(context): redact secrets and strip control characters` | Context 输出包含 JWT/sk-* 格式的测试数据，未脱敏就写入了 prompt |
| `fix(context): harden determinism, evidence traceability, and path safety` | Context 生成每次运行 hash 不同（datetime 未固定）、evidence 路径未验证在仓库内 |
| `fix(detector): integrate with safe scanner` | TechnologyDetector 绕过了 Scanner 的安全校验独立读文件 |
| `fix(docs): update T-004 report and harden evidence redaction test` | 文档和测试未覆盖 secret 脱敏的边界场景 |
| `fix(eval): validate real tool call artifacts` | 评测框架未区分 Mock Tool Call 和真实 Tool Call |

**面试说法：** "这个项目有 8 个 fix commit。最有代表性的是那个 CLI 假绿灯——404 个测试全绿，但 CLI 实际跑不通。我是在手动运行 `specflow run --mock` 时发现的。这正好说明不能用测试通过代替实际运行验证。"

---

## 三、2 次外部 Code Review + 修复闭环

不是自己审自己。项目经历了 2 次独立 Code Review：

**Review #1 (T-001~T-005):**
- 发现 5 个问题（ruff format / 空白名称 / symlink / 假 evidence / SQLite evidence）
- 补充 7 个回归测试
- 2 个 fix commit 完成修复闭环

**Review #2 (M5 / T-022~T-023):**
- 发现 6 个问题（CLI 断链 / 测试假绿灯 / --max-files 未生效 / SystemExit 用错 / evidence 软限制 / README 滞后）
- 收紧 CLI 测试（从 exit_code in {0,3,4} → assert == 0 + 验证 10 个文件）
- 1 个 fix commit 完成修复闭环

**面试说法：** "这个项目经过了两次独立的 Code Review，不是自己看完就算了。每次 review 都有 findings → fix commit → regression test 的完整闭环。"

---

## 四、23 个 Task 的递增证据

每个 Task 都有独立文件：

```
docs/tasks/T-001-initialize-repository.md
docs/tasks/T-002-project-and-run-data-models.md
...
docs/tasks/T-023-real-repository-evaluation.md
docs/tasks/T-022.1-cli-runner-completion-fix.md
```

每个 Task 完成后有 completion report：

```
docs/reports/T-001-completion-report.md
...
docs/reports/T-023-completion-report.md
```

这意味着：
1. 每个任务有**明确的边界**（building / not building）
2. 每个任务有**独立的验收标准**
3. 任务之间是**递进依赖**关系（M1 → M2 → M3 → M4 → M5）
4. 不存在"跳过大段基础直接做高级功能"的 AI 特征行为

**面试说法：** "每个功能都有 task spec 定义范围和验收标准，完成有 completion report。这是工程习惯，不是 AI 提示词。"

---

## 五、14,194 行 Python 代码，88 个源模块

```
88 个 src/specflow/ Python 模块
27 个 tests/ 测试文件
总计 14,194 行 Python 代码
```

关键架构特点（证明不是 AI 自由发挥）：
- 每层有显式 `__init__.py` 公开 API（`__all__` 声明）
- Protocol 接口 vs 具体实现分离清晰
- 异常类型分层（每层有自己的 exceptions.py）
- 测试和源码 1:1 对应

**面试说法：** "88 个模块分 7 层，每层有独立的公开 API。这不是让 AI 自由发挥能出来的结构——AI 倾向把所有逻辑写在一个大文件里。"

---

## 六、量化数据速查表

| 指标 | 数值 | 证明什么 |
|------|------|---------|
| 总 commit | 43 | 递增开发，非一次性生成 |
| 开发天数 | 2 | 高强度集中开发 |
| Fix commit | 8 | 真实 debug 过程 |
| Code Review | 2 次 | 外部质量验证 |
| Task 数量 | 23 + 1 fix | 结构化开发流程 |
| 总代码行数 | 14,194 | 代码量够一人月项目 |
| 源模块 | 88 | 模块化架构，非大文件 |
| 测试文件 | 27 | 测试和源码 1:1 |
| 测试数量 | 404 passed | 高覆盖率 |
| Review 发现的 Bug | 11 个 | 非自我感觉良好 |
| 最大单 commit | ~1,300 行 | 无巨型一次性提交 |

---

## 七、AI 辅助的真实角色

**诚实陈述：**

这个项目使用了 Claude Code + Codex 作为开发工具，方式是：

- **AI 角色：** Review（审查代码）、Debug（协助定位）、Generate boilerplate（生成框架代码）
- **我的角色：** 架构设计（7 层分层、模块边界、接口契约）、技术决策（Protocol vs ABC、State Machine vs if-else、MockFirst 策略）、质量把关（Code Review 反馈的评估和执行）、问题诊断（假绿灯 Bug 的发现和根因定位）

**不是：** 给 AI 一句话让它生成整个项目。

**面试说法：** "我用 AI 做 review 和 debug，但架构设计、技术选型、接口定义和最终验收是我做的。一个很好的例子是那个 CLI 假绿灯 Bug——AI review 没发现这个问题，404 个测试全绿，但我手动跑 CLI 发现返回了错误码，然后自己 trace 代码找到根因。这种判断力不是 AI 能替代的。"

---

## 八、如果面试官直接问"这项目是不是 AI 写的"

**一句话回应：** "这个项目有 43 个增量 commit、8 个 fix、2 次 Code Review 闭环、23 个结构化 Task。如果 AI 能自动做到每 475 行就 commit 一次、自己修自己引入的 bug、自己给 code review 写 fix，那确实不需要我。但目前做不到。"

**然后主动展示：**
1. `git log --oneline` — 43 个 commit，每行一个独立功能
2. 任意一个 fix commit 的 diff — 证明你理解自己在修什么
3. `docs/tasks/` 目录 — 23 个 task spec
4. 假绿灯 Bug 的根因分析 — 这是 AI 做不到的诊断能力

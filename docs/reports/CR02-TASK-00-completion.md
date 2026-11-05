# CR02 TASK-00 核查结果

日期：2026-10-30（Asia/Shanghai）。范围已选 A/A/B/A/A，包含可观测性。
完成的是实施接点核定，不是新工作流或产品验收完成。

## 实际基线与旧接口

checkout 为 `C:/Users/50469/specflow-h04-f03-20261023`，起点
`afcc2d7048c967d6486d0d2741f6395c4e7153b6`。已读适用 AGENTS、冻结基线及
v0.2.2 定向勘误。原有新工作流目录/路由尚不存在。
复用交接中的五模块升级前结果：150 passed、1 skipped（Windows 符号链接条件）；
本任务没有重跑旧基线或旧评测。

旧八路由固定为 `/health`、项目 POST/GET、Run POST/GET/artifacts GET/
review-package GET/review-decisions POST。`runs.py:386` 创建仍同步、mock=true、
HTTP 201；业务失败不自动变 HTTP 失败。旧反馈追加不派生新运行。
`main.py:43` 中间件保留除精确 health 外全路径认证；新 API 仍使用同一边界。

## 核定接点

| 责任 | 源码事实 | 本轮选定的实现接线 |
| --- | --- | --- |
| Provider/profile | `llm/providers/openai_compatible.py:_request_payload` 从配置取实际 model；一次同步 HTTP，未发现内部重试 | 新 adapter 比较最终 payload/profile，显式次数账；不使用会丢失晚到 usage 的 attempt_executor 超时封装 |
| 有界模型读取 | 原 `_complete_once` 的 `client.post` 会先读取整个响应 | 新 adapter 必须增设流式 128 KiB 上限，不能只在完整 response.json 后检查大小；保留旧 Provider 行为 |
| 本地收尾 | 同步 `httpx.Client` 上下文退出后 complete 才返回；`execution_lanes.py:_finish` 在 operation 退出后发布 settled | 首版仅支持无脱离进程 I/O 的同步 HTTP adapter；实际 wrapper 返回和 Client 退出为当前进程收尾依据，业务接受另做 fencing |
| 跨重启收尾 | 旧 Future/settled 仅在内存；新 boot/锁均不能证明旧操作结束 | Windows 保存 PID+进程创建 FILETIME，核对同一进程对象退出或确认原身份已消失；权限/查询不明保持 unconfirmed。当前实例锁必须在 I/O 全部结束后释放 |
| 排队与超时 | 旧 Lane 内存队列在旧结果发布前自动派发下一项 | 新持久 worker 自己认领；不委托旧 lane 排业务队列。超时终结业务但保留槽，维护事务可靠收尾后才继续 queued |
| 用量 | Provider `_token_count` 拒 bool/负数；旧 LLMUsage 本身不足以保证严格入口；旧 Runner 有 missing=0 路径 | 新账本统一严格检查，known/partial/unknown 与槽状态独立；迟到 usage 只结算原 call，不接受迟到业务正文 |
| 事务与迁移 | `db.py:Database` 提供 engine/session/foreign_keys/busy_timeout；create_all 加旧五列桥接 | 新表独立迁移版本；短事务、条件 UPDATE rowcount、活动 job 部分唯一索引、幂等响应与业务同提交；不扩写旧表效力 |
| 启停 | `main.py:lifespan` 建表并仅恢复旧 WorkflowRun，最终 dispose | 新锁先于新恢复/认领；新运行关闭先停认领并收尾再释放锁，旧恢复器不碰新表 |
| 快照 | 旧 repository_tools 读取工作树 | 新 Git 对象准备器校验 worktree/git-dir/common-dir，固定完整 SHA，先大小后正文，有界准备；密封后工具只读 DB blobs |

Adapter 和新事务尚未实现。以上列的是已核定可落地边界，后续需以受控 adapter
验证超时仍活、持久化拒写、身份错误、重复收尾、queued 恢复及当前报告切换。

## 环境探针

命令：`python -B -X utf8 scripts/contract_review/probe_environment.py`。
最终退出码 0，Python 3.12.10、Git 2.53.0.windows.1，六项 PASS：

1. replacement ref 确实生效时，`--no-replace-objects` 仍取得原始 CRLF 字节。
2. promisor 仓库缺 blob，`--no-lazy-fetch` 明确失败；Trace2 无 child_start。
   同时使用 `-c protocol.allow=never`，没有尝试远端网络。
3. Git 实际目录及 common directory 返回绝对路径，可验证允许根边界。
4. SQLite BEGIN IMMEDIATE 回滚、CAS rowcount、每 review 一个活动 job 的部分唯一索引。
5. Windows msvcrt 跨进程排他锁，释放后另一进程可取得。
6. Windows OpenProcess/GetProcessTimes 绑定创建身份，WaitForSingleObject 区分活跃与退出。

探针只在临时目录建立自身 fixture，未导入 main、读取凭据或访问产品 DB。
初次探针暴露 Windows Git blob 只读属性及 sqlite context 不自动关闭连接的问题；
已限定在临时对象上 chmod 并显式 close，再运行通过。没有以异常退出当 PASS。
这些结果是环境原语证据，不能代替未来产品路径测试。

## 六例落地条件和后续检查

F01/F02 使用相同 v2 job_id 契约和正确实现，仅文档/示例字段不同；
C01/C03 分别明确 completed 错放行和 queued 错拒绝，使用可解析直接路由和同函数分支；
H01/H02 共用版本不明的 id 示例和 v1/v2 原文，唯一差异是预定人工答案。
每例先写 targets[].checks、原始材料、独立 oracle、固定 CR02/TR02/SP02 身份；
oracle 与答案脚本不进入初始模型请求。TASK-01 先冻结六例，其他公开案例按原计划登记。

静态支持矩阵仍采用 `contract-static-support.v1`：直接路由、显式字典/有限标量
BaseModel、同函数状态分支、版本明确文本。不存在可直接复用的完整静态工具；
动态注册、复杂过滤/继承、跨模块状态保护必须显示 unsupported 或缺证。

生产接线顺序：TASK-02 数据/受理/test adapter 纵向链；TASK-03 完整协议与规则；
TASK-04 五个 snapshot 工具、分析/固定复核、实际请求投影；TASK-05 答案派生输入。
TASK-08 的三类基础反例随实现进入：未收尾零派发、旧输入报告不冒充当前、重复
旧维护信号不得释放新槽。迁移只测可丢弃副本，验证旧代码可读旧资源而忽略新表。

所有新产品 AC/WAC 保持 NOT_RUN。真实模型、价值对照和语义判断均未运行。
本任务只改任务记录、报告、环境探针，无生产代码修改、依赖变更、推送或发布。

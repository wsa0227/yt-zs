# Phase 0 架构决策：Windows 腰椎康复助手 V1

> Phase 0 设计基线；Phase 1 骨架实施状态见第 10 节。不代表未实现功能。产品范围与安全约束以根目录 PRD.md 为准。

## 1. 仓库现状

检查日期：2026-10-10。

- 初始目录仅含 PRD.md、实施方案.md；Phase 1 后新增最小应用骨架及测试，详见第 10 节。
- Git 已初始化，默认分支为 main；尚无提交。
- 检查环境为 Windows PowerShell；可用 Python 为 3.13.7，未安装 PySide6、pytest 或 PyInstaller。与基线 Python 3.12 不符，目标运行时尚待建立。
- 实施方案.md 总体方向与 PRD 一致，但属于建议稿，冲突时以 PRD 为准。

结论：Phase 1 建立了应用骨架，但当前机器依赖/解释器未就绪，GUI 尚未实机启动验收。

## 2. 架构决策与目录

| 决策 | 设计与限制 |
|---|---|
| 技术栈 | Python 3.12、PySide6、SQLite 标准库；本地单进程，不增加服务器、账户、遥测或网络依赖。具体版本在 Phase 1 锁定并实机验证。 |
| 业务核心 | domain 不依赖 Qt、Win32、SQLite；时钟/存储可注入。姿势仅允许 PostureService 修改。 |
| 事实存储 | append-only 事件为事实源；快照带 last_event_seq，与事件同事务写入；启动校验并重放。 |
| 时间 | 持久化 UTC；运行期单调时钟辅助校验；记录 Windows boot id（可得时）。不假设跨休眠/重启语义。 |
| 单实例 | QLockFile 负责互斥；激活已有进程需 QLocalServer/QLocalSocket，锁文件本身不转发激活。 |
| Windows API | 独立 adapter 封装，优先 ctypes；订阅失败降级手动确认并记录。消息监听生命周期需实机验证。 |
| 提醒 | 先持久化再尝试投递；尝试状态与用户确认看到分离。 |
| 数据 | 显式 SQLite migrations，数据放 %LOCALAPPDATA%；备份使用 SQLite backup API。WAL 不等于备份。 |

建议目录：src/rehab_assistant/{app,domain,services,storage,adapters/windows,ui,resources}/、tests/{unit,integration,windows}/、installer/、docs/，项目配置 pyproject.toml。依赖及测试依赖锁定，只维护一个锁文件。引入 Win32 外部封装需记录版本、许可证和打包验证。

## 3. 模块接口契约

时间统一用带时区 UTC datetime；单调读数仅在同一运行实例内比较。存储错误显式传播。以下均为拟定接口：

| 模块 | 接口 | 契约 |
|---|---|---|
| PostureService | handle(command, observed_at) -> TransitionResult；get_current_state() -> StateView | 唯一修改姿势/周期；事件、session、快照事务提交后才报成功；非法转移拒绝。 |
| 命令 | ConfirmSitting/ConfirmUp/PauseTracking/ResumeNeedsConfirmation、ReconcileGap(answer, estimated_sit_at?)、CorrectMistake(target_event_id, command) | 更正追加事件不覆盖历史；追述标 USER_REPORTED。 |
| EnvironmentMonitor | start(callback)、close()；发布 idle、锁定/解锁、睡眠/恢复、时钟跳变 | 只改环境轴或触发询问，不能确认姿势。 |
| ReminderEngine | evaluate(state, now)、record_attempt、acknowledge_seen | 判断与投递分开；唯一键幂等；知道了不结束周期。 |
| RecoveryCoordinator | recover(context, now)、reconcile(answer) | 中断后待核实；不自动清零、认定起身或伪造精确时长。 |
| JournalService | save_day、query_trend(7|30)、export_csv | 建议每日一条可编辑；空值不补零；导出前确认。 |
| ExerciseCatalog | save_candidate/approve/suspend/list_executable/record_log | 仅 APPROVED 且未停用项可执行；初始为空；不自动推荐/排程。 |
| SafetyRules | evaluate(report) -> SafetyNotice? | 确定性规则与专业复核文案；不诊断。 |
| Repository | append_event/load_events_after/save_snapshot/create_reminder_once/transaction | 事件、快照、提醒原子更新；数据库错误上抛。 |

数据流：UI 命令 → PostureService 校验 → SQLite 单事务 → 状态视图。心跳只唤醒提醒检查并按时间重算。Windows 信号只进入环境/恢复流程，永不转成姿势命令。

## 4. 三轴状态机

姿势：UNKNOWN | SITTING | UP | PAUSED；环境：ACTIVE | IDLE | LOCKED | SLEEP_PENDING | RESUMED | UNKNOWN；区间证据：CONFIRMED_START | INFERRED_CONTINUATION | UNRESOLVED_GAP（证据标签，不是概率）。

| 当前 | 事件 | 下一姿势 | 处理 |
|---|---|---|---|
| UNKNOWN | 确认现在坐着 | SITTING | 从确认时刻开新周期，不回填未知时段。 |
| UNKNOWN | 确认已起身 | UP | 不建周期。 |
| UP | 确认重新坐下 | SITTING | 新周期从确认时刻开始。 |
| SITTING | 确认起身 | UP | 结束并持久化周期。 |
| SITTING | 达 35/40 分钟 | SITTING | 仅建提醒，不改姿势/周期。 |
| 非 PAUSED | idle、锁定/解锁 | 不变 | 仅记环境；不暂停、清零或推断起身。 |
| 任意 | 休眠、进程退出/崩溃、不可解释跳时 | 待核实 | 记录可信边界及 UNRESOLVED_GAP。 |
| 任意 | 用户暂停/恢复 | PAUSED/UNKNOWN | 暂停停止常规提醒；恢复须重新确认。 |
| 待核实 | 自述一直坐着 | SITTING（推算） | 可从原时刻推算，标 USER_REPORTED/INFERRED_CONTINUATION 并提示不确定。 |
| 待核实 | 自述曾起身/不确定 | 追述状态/UNKNOWN | 按用户提供精度记录；不确定时提示“若仍坐着，请现在起身”，不静默重开 40 分钟。 |
| 任意 | 撤销/更正 | 重算 | 追加关联事件，保留历史，提醒去重。 |

PRD 对普通 IDLE 与锁屏/休眠/崩溃需区别：进程仍运行的 IDLE 不暂停周期，返回时可询问并标推算；后者建立未知区间并待核实。两者均不代表起身。IDLE 核实为“一直坐着”后是否继续触发提醒须冻结。

## 5. 时间、提醒与恢复

1. 事件用 UTC epoch 毫秒；日志可用 ISO-8601 UTC。症状日期保存本地日期和时区标识；夏令时不改变 UTC 持续时间。
2. 运行期以注入的单调时钟测时，并与 UTC 差值交叉检查。跳变超过待定容差时记录事件、转待核实，不静默平移历史。
3. 休眠恢复不依赖某个时钟是否计入睡眠；无连续证据则该段未知。断电不保证有结束事件，启动时结合运行/boot context 保守核实。
4. 启动顺序：单实例锁 → 数据库/schema 检查 → 快照及后续事件重放 → 比较运行上下文 → 持久化待核实 → 显示询问/安全提示 → 启动提醒检查。旧 SITTING 不自动视为当前确认。
5. 唯一提醒键：35 分钟 (session_id,35,0)；40 分钟 (session_id,40,0)；重复 (session_id,40,sequence_no)。建议 40 分钟后每 5 分钟最多 3 次后续提醒（不含首次提示，待确认）。分别记录计划、投递尝试/结果/通道/错误、用户确认；未投递可重试，不把尝试当已读。
6. QTimer 仅唤醒检查器，每次按时间差重算。正常运行且事件循环不阻塞时，应用内状态更新目标为计划时刻后 5 秒内；睡眠、关机、通知抑制不保证。
7. 退出提示“退出后不会提醒”。数据库损坏恢复策略需在 Phase 5 故障注入后定稿。

## 6. SQLite 逻辑 schema

显式 SQL migrations，PRAGMA user_version；启用外键、参数化查询、短事务。以下是建议模型，尚未建表：

| 表 | 核心字段与约束 |
|---|---|
| app_events | seq PK AUTOINCREMENT、event_id UNIQUE、event_type、source、occurred_at_utc_ms、monotonic_ticks NULL、boot_id NULL、session_id NULL、payload_json、schema_version；append-only。 |
| posture_sessions | id PK、started_at_utc_ms、ended_at_utc_ms NULL、status、start/end_source、evidence、start/end_event_id；至多一个活动周期由事务保障。 |
| app_state | 单例 id=1、posture_state、environment_state、pending_reconciliation、active_session_id、last_event_seq、updated_at_utc_ms；派生快照。 |
| time_gaps | id PK、start/end_at_utc_ms、reason、resolution、reported_sit_at_utc_ms NULL、start/end_event_seq。 |
| reminders | id PK、session_id、threshold_minute、sequence_no、计划/创建/尝试/确认时间、delivery_status/channel/last_error；唯一约束 (session_id, threshold_minute, sequence_no)。 |
| settings | key PK、value_json、updated_at_utc_ms。 |
| symptom_entries | id PK、local_date UNIQUE、timezone_id、pain_score NULL CHECK 0..10、body_area NULL、leg_symptoms_json、activity_relation NULL、notes NULL、创建/更新时间；缺失评分为 NULL。 |
| exercises | id PK、name、来源、内容、注意事项、审批状态、审核者/备注、审批时间和创建/更新时间。 |
| exercise_logs | id PK、exercise_id FK、performed_at_utc_ms、completed、user_response、symptom_change、notes。 |

WAL/同步级别待实机故障测试决定；WAL 不是备份，备份使用 SQLite backup API。每日症状条数、备份保留与健康数据删除策略需确认。

## 7. 阶段及验证计划

| 阶段 | 实施 / 自动化验证 | Windows 验收 |
|---|---|---|
| 1 骨架 | 锁依赖、窗口/托盘、单实例、自启、migration、日志；测新库/重复迁移/回滚、锁、生命周期。 | Win 10/11 启动、显示隐藏、托盘退出、自启、重复启动；不宣称计时完成。 |
| 2 状态机 | 纯逻辑、事件流、周期、更正、恢复接口；Fake clock 测 35/40 边界、未确认不计、误操作、重放、跨日/跳时、存储失败。 | 检查未知状态文案；环境信号不改姿势。 |
| 3 提醒/OS | 提醒、待处理、Windows adapter；假通知测成功/失败/抑制、幂等/重试、环境隔离、订阅生命周期。 | Win 10/11 视频、idle、锁屏、睡眠、勿扰、权限关闭；记录 OS build。 |
| 4 症状/训练/安全 | CRUD、7/30 趋势、CSV、候选/审批/停用、日志、规则；测 NULL/缺失、跨日、CSV、未批准不可执行、安全规则。 | 医学文案专业复核后才进入发行。 |
| 5 恢复 | 重放、备份、时钟/数据库错误；测崩溃注入、回滚、损坏副本、快照错位、迁移、改时、并发。 | 强制结束/重启/休眠/改时/磁盘错误；区分模拟和实测。 |
| 6 安装 | PyInstaller、Inno Setup、卸载、自启清理；测干净安装、升级、卸载、无 Python 启动。 | 目标机安装/通知/休眠试用；未签名风险如实说明；未授权不部署。 |

各阶段报告变更文件、复现命令、测试类别/结果、OS 条件、风险和未覆盖项；完成后等待用户批准。

## 8. 编码前问题与风险

Phase 1 暂用默认：显示名“腰椎康复助手”、包名 lumbar-rehab-assistant、App ID Local.LumbarRehabAssistant.V1、数据存放 Qt AppLocalDataLocation、重复启动通过本地 IPC 激活既有进程。品牌图标暂缺，使用通用系统图标；最低系统按 PRD 所述 Windows 10/11，目标架构待确认。症状记录粒度尚未实现，建议每日一条可编辑。

对应阶段前确认：IDLE 自述一直坐着是否继续触发提醒；40 分钟后间隔与最多次数；时钟跳变容差和追述粒度；医学文案复核责任人；本地备份与删除策略；签名证书状态。

风险：P0 姿势误推断、恢复时静默清零/误计、提醒丢失/重复、未确认训练入计划；P1 Win32 订阅失效、跳时、快照不一致、写失败未告知、系统策略抑制；P2 Qt/打包插件、签名警告、Windows 版本差异。

## 9. Phase 0 执行记录

- 已审阅 PRD.md、实施方案.md，检查目录、AGENTS.md、项目清单和 Git 状态。
- 初始阶段仅新增本设计文档；Phase 1 变更记录见下节。
- Phase 0 未运行软件测试：当时无代码和测试框架。文档审查不等于测试通过。
- 用户随后授权初始化 Git 并继续。

## 10. Phase 1 执行记录

- Git 已初始化为 `main`，未创建提交。
- 新增 `pyproject.toml`（Python 3.12 与 PySide6 固定版本）、PyInstaller spec、包入口、最简主窗口/托盘、QLockFile 与 QLocalServer/QLocalSocket 单实例激活、HKCU 登录启动适配、SQLite `user_version` migration、日志、`.gitignore`。
- 窗口明确标注坐姿追踪未启用；本阶段未实现计时、提醒、症状或训练。
- 新增 SQLite migration、非 Windows 自启边界、Qt 窗口生命周期、单实例 IPC 和应用启动/退出测试。测试过程中发现并修复 QtNetwork 导入、无托盘退出语义、IPC 请求/确认应答和清理锁/数据库等问题。
- Python 3.12.12，`uv sync` 生成 `uv.lock` 并安装 PySide6 6.8.3；`uv lock --check` 通过。尚未安装 PyInstaller，打包配置仍为骨架。
- 最终复验：`.venv\\Scripts\\python -m unittest discover -s tests -v` 8/8 通过；`.venv\\Scripts\\python -m compileall -q src tests` 通过；`git diff --check` 通过。
- 测试运行于 Windows 主机的 Qt offscreen 平台，不是可见桌面验收。真实系统托盘显示、HKCU 自启注册/清理、用户会话重复启动行为、PyInstaller 构建及 Windows 10/11 版本兼容性未验收。品牌图标仍未提供。

## 11. Phase 2 执行记录

- 新增纯逻辑 `domain.posture` 状态模型和 `services.posture_service`：姿势只能由人工命令改变；键鼠/环境信号尚未接入；提醒评估只产生持久化待处理事件，不改变姿势。
- 状态包括 `UNKNOWN`、`SITTING`、`UP`、`PAUSED`、`NEEDS_CONFIRMATION`。首次启动未确认不创建坐姿周期；人工起身结束当前周期；重新坐下创建新 `session_id`；暂停恢复后必须重新确认。
- 坐姿事实事件追加到 SQLite，派生快照与事件在同一事务提交；启动重放事件。运行实例内用可注入单调时钟计算提醒阈值，UTC 仅记录事实时间和跨运行自述推算基准；墙上时钟跳变不会直接推进当前运行计时。
- 正常关闭也会把当前可观察状态标为待核实，因为程序退出期间没有连续姿势证据；异常退出通过未闭合 `runtime_started` 检出。恢复不会静默清零、认定起身或把未知时段确定为坐姿。
- 主窗口已接入最小人工确认、待核实和计时显示；本阶段未接 Windows 通知、键鼠监听、锁屏/休眠适配、症状/训练模块。
- 自动验证：`.venv\\Scripts\\python -m unittest discover -s tests -v`，19/19 通过；`.venv\\Scripts\\python -m compileall -q src tests` 通过；`git diff --check` 通过。测试使用 Qt offscreen；未完成可见桌面、托盘、真实休眠/恢复和通知实机验收。
- 已知后续风险：当前运行计时锚点不跨进程恢复，跨运行只能在用户明确“仍坐着”后按 UTC 记录推算并标不确定；Windows 事件适配与通知幂等投递留待 Phase 3/5；数据库损坏、断电和备份恢复留待 Phase 5。

## 12. Phase 3 执行记录

- SQLite schema 升级到 v3：新增 `environment_events` 和 `reminder_deliveries`。提醒唯一键为 `(session_id, threshold_minutes, sequence_no)`，并持久化计划时间、投递尝试、通道、错误和用户已读时间。
- `PostureService.evaluate_reminders()` 仍只负责按单调运行时间产生持久化 `reminder_due` 事实；35 分钟、40 分钟首次提醒，以及 40 分钟后的 45/50/55 分钟最多三次后续提醒均幂等。提醒生成不会改变姿势状态。
- 新增 `ReminderService`：先创建 pending 投递记录，再调用注入的通知通道；通道异常保留 pending 并支持重试；通道成功仅记录 delivered，不等同于用户已读；“知道了”只写 acknowledged，不改变姿势或坐姿周期。
- 新增 Windows 环境适配边界：键鼠 idle、会话锁定/解锁、睡眠/恢复仅发布环境事实。`session_locked`、`sleep_started`、`clock_jump` 由姿势服务转入待核实；`idle_started`/`idle_ended`、解锁和恢复不会自动确认起身或恢复坐姿。非 Windows 或 API 不可用时保留手动模式。
- 主窗口已接入提醒评估、托盘通知和“知道了”操作；环境适配器在应用退出时注销 native event filter 和会话通知。
- 自动验证：`.venv\\Scripts\\python -m unittest discover -s tests -v`，29/29 通过；`.venv\\Scripts\\python -m compileall -q src tests` 通过；`git diff --check` 通过。测试覆盖迁移幂等/失败回滚、提醒幂等/失败重试/确认分离、环境事件隔离、锁屏睡眠进入待核实和数据库写失败不改内存状态。
- 测试边界：上述 Windows API 测试为 mock/消息契约测试，不是实机验收。尚未在 Windows 10/11 目标桌面实际验证托盘通知被系统抑制、GetLastInputInfo 行为、锁屏/睡眠/恢复消息注册、不同电源策略和通知权限；尚未处理 Phase 5 的数据库损坏、备份恢复与断电故障注入。

## 13. 启动无反馈问题修复（2026-10-13）

- 用户报告命令立即返回、没有窗口。检查时，旧 `app.lock` 记录 PID 5244，但该进程已不存在，IPC 无应答；沙箱内锁检测受数据目录写入限制，在沙箱外通过 Qt 正常失效检测后成功获取并释放锁。未手动强删锁，也未终止任何 Python 进程。
- 复现确定的代码缺陷：`tryLock()` 失败后，即使已有实例没有确认激活，`main()` 仍返回 0，且没有终端反馈。先添加真实 QLockFile 占用、无 IPC 服务的回归测试，旧代码测试失败（返回 0）。
- 实际修改：只有旧实例确认激活才返回 0；激活失败输出锁路径、进程信息并返回 1；锁权限错误不会发起 IPC；数据目录创建失败和日志/数据库初始化失败也输出终端错误。未改变姿势、计时、训练或提醒业务规则。
- 自动验证：完整 unittest 37/37 通过；compileall 与 git diff --check 通过。回归覆盖真实锁占用且激活失败、激活成功、权限错误、非法数据目录、初始化失败释放锁。
- 原生 Windows 启动烟测（独立临时数据目录与 IPC 名称）：Qt 平台 windows，主窗口可见，WTS 注册成功，正常退出码 0。该烟测不等同于真实锁屏、睡眠恢复或通知展示的完整验收；offscreen 测试的 WTS 注册失败也不能称作实际注册成功。
- 本次保留安全边界：激活失败不强行移除有效锁；不创建第二个写数据库的实例。旧进程无响应、Windows 前台窗口限制和跨权限会话仍需进一步实机验证。

## 14. 主窗口视觉优化（2026-10-13）

- 使用 UI/UX Pro Max 本地检索流程，采用暖白 / 青绿的低干扰桌面设计；高对比按钮、明确焦点、语义警示，避免低对比新拟态和无功能导航。
- 将 `MainWindow` 从组合根移至 `ui/main_window.py`，通过 `app.py` 继续导出以兼容现有调用；主题和时间刻度分别位于 `ui/theme.py`、`ui/widgets.py`。启动锁、日志、托盘和恢复服务保持原样。
- 新增状态与动作层级、大数字计时、35/40 提醒刻度、可滚动的提醒列表及操作异常反馈。未修改姿势推断、计时/提醒规则、数据库 schema 或训练范围。
- 完整 unittest 49/49 通过，新增 UI 测试 Windows 原生平台 12/12 通过；compileall 与 diff 检查通过。Windows 五场景原生截图已检查，额外 DPI 倍率渲染成功；隔离启动烟测主窗口可见、WTS 注册成功、退出码 0。
- 验证不覆盖真实锁屏/睡眠恢复、被系统抑制的通知、读屏器与多显示器缩放切换。非本轮的通知阈值 `>= 2` 改动已保留并列为待确认问题。详细边界见 `docs/UI_DESIGN.md`。

## 15. 按用户设计板实施界面（2026-10-13）

- 以 `docs/腰椎康复助手界面设计板.png` 为视觉基准，替换第 14 节的暖白 / 青绿视觉。实施浅蓝导航、白色状态卡、绿色环形计时、坐姿人物及植物 SVG、蓝色操作和红色上限警示。保留原生窗口和 PySide6 技术栈。
- 倒计时、状态和开始时间绑定现有服务；未核实不显示确定时间，自述继续坐着仍标注推算。未开发的统计使用“—”，其他页面禁用并说明，未把图中的训练或示例数字作为实际数据。
- 修复退出后计时器访问已关闭数据库的生命周期问题；高 DPI 窄窗口首次检查失败后，修复环尺寸和祖先布局缓存，并增加 416 / 360 / 320 像素约束回归。
- 最终完整测试 57/57、Windows 原生 UI 测试 20/20 通过；compileall、diff 检查通过。常规及两档额外缩放各 7 场景渲染成功，实际设备像素比分别 1.25 / 1.875 / 2.5。隔离启动窗口可见、WTS 注册成功、退出码 0。详见 `docs/UI_DESIGN.md`。
- 未运行安装包构建；真实休眠恢复、通知展示、读屏器和多显示器 DPI 切换仍未验收。用户已有通知条件 `>= 2` 保留，35 分钟系统通知文案错误仍需确认修正。
- 本轮未提交、未推送、未部署。


## 16. 设计板全入口与页面骨架补齐（2026-10-13）

- 根据用户最新要求，将“业务尚未实现即禁用导航”调整为“入口可进入明确占位页”；仍严格区分界面可见与业务可用，不扩大 V1 自动训练或姿势推断范围。
- 首页补齐本地运行、开机常驻、定时提醒、记录趋势、康复训练五张能力卡；补齐症状、训练 / 我的计划、三类趋势、设置、帮助及首页快捷入口。启动询问、35 分钟通知和 40 分钟警示提供独立样式预览，预览不改变业务状态。
- 提取共享组件，新增页面与托盘菜单模块。完整托盘复用原人工姿势命令与登录启动适配器；待核实不能静默重启周期；退出须确认停止计时和提醒。
- 未完成症状保存、导出、统计查询、训练启用和提醒偏好，相关操作禁用并说明；未填写疼痛评分不是 0 分，训练示例不进入实际库，统计不绘制假数据。
- 修复隐藏标签布局缓存、首次高 DPI 窄窗滚动范围延迟、超窄窗口缺少返回入口；保留严格无横向溢出断言。
- 完整测试 76/76、Windows 原生 UI 复验 39/39 通过；三组页面 / 状态 / 弹窗预览 / 托盘截图成功，实际 DPR 1.0 / 1.875 / 2.5；隔离启动窗口可见、WTS 注册成功、退出码 0。详细记录见 `docs/UI_COVERAGE.md`。
- 后续计划按 Phase 4A 症状、4B 专业确认训练、4C 统计、4D 交互与偏好收口、5 可靠性、6 安装包逐期推进。真实系统通知、锁屏 / 休眠、读屏器、跨显示器 DPI 与安装包仍未验收。
- 用户既有通知条件 `threshold_minutes >= 2` 未改动，35 分钟系统通知错误使用 40 分钟文案仍待确认修正。未修改用户 `.idea/`，本轮未提交、未推送、未部署。

## 17. Phase 4A 症状记录与安全规则基础（2026-10-14）

- SQLite schema 升级到 v4，新增 `symptom_entries`，按本地日期每日一条；`NULL` 疼痛评分与明确选择的 `0` 分保持可区分。
- 新增 `domain.symptoms`、`services.symptom_service` 和 `safety.symptom_rules`。保存、同日更新、查询、删除和 UTF-8 BOM CSV 导出均在 SQLite 事务边界内执行；写失败不返回成功记录。
- 症状页已接入真实 service：保存成功 / 失败反馈、编辑回填、删除确认、导出确认和固定安全提示。安全规则只根据明确字段触发，不做诊断，不自动推荐训练。
- 新增领域、service、安全规则和真实 Qt UI 测试。完整自动化测试 `python -m unittest discover -s tests -p '*.py' -v` 为 90/90 通过；`compileall` 和 `git diff --check` 通过。
- 本阶段未实现 7 / 30 日趋势、训练资料 / 计划、备份恢复和安装交付；专业人员文案复核、真实系统通知、锁屏 / 休眠和目标机验收仍未完成。本记录不将自动化测试扩大解释为真实 Windows 集成验收。

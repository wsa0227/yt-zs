# 测试报告

日期：2026-10-15

## 本轮范围

本轮覆盖 Phase 6 的 EXE / Inno Setup 安装包构建、冻结程序启动烟测、编译器发现、架构校验和隔离通信修正，并在既有 Phase 5 可靠性基础和康复资料包候选导入边界之上，保留真实临时磁盘 SQLite/WAL 文件场景下的异常退出恢复测试，并保留训练日志历史、UI 回归、本地恢复幂等和损坏数据库启动保护。磁盘测试通过直接关闭底层连接模拟未执行正常收尾的进程结束，不等同于突然断电或真实进程崩溃现场验收。日志历史仅读取用户主动保存的训练日志，不生成演示记录、不改变训练计划状态，也不引入自动推荐、自动排程或训练提醒。

## 自动化测试

可复现命令：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p '*.py' -v
.\.venv\Scripts\python.exe -m compileall -q src tests tools
git diff --check
```

本轮执行结果：

- 全量 unittest：`151/151` 通过（2026-10-15）。
- 磁盘恢复专项：`1/1` 通过，覆盖 WAL 文件数据库、未调用 `PostureService.close()` 的底层连接关闭、重启重放、原始 `sitting_since` 保留和恢复期间不生成确定时长。
- 训练页面专项：`5/5` 通过，覆盖日志写入后的只读历史展示和不适上下文。
- 设置和设计页专项：`24/24` 通过。
- `compileall`：通过。
- `git diff --check`：通过；仅报告 Git 在 Windows 工作区转换 LF/CRLF 的提示，没有空白错误。

覆盖的关键故障场景：

- 无效 SQLite 恢复不会替换当前数据库。
- 应用启动会在启用 WAL 前执行 SQLite 完整性检查；损坏数据库会失败并保留原文件，不生成 `-wal` / `-shm` 旁车文件。
- 活动数据库不能作为备份或恢复目标。
- 跨表删除中途失败会回滚，内存姿势状态保持不变。
- 恢复后姿势状态重新加载并进入待确认，不静默继续计时。
- 真实临时磁盘 SQLite/WAL 数据库在底层连接未正常收尾后重新打开，姿势进入 `NEEDS_CONFIRMATION`，保留原始坐下时间，`elapsed_seconds()` 不返回恢复期间的确定时长。
- 同一运行实例重复刷新未变化的姿势存储不会重复追加 `database_restore` 中断事件；当数据管理服务确认发生外部恢复时，即使姿势事件流未变化也会强制进入恢复流程。
- 墙钟与单调时钟偏差超过 120 秒会记录 `clock_jump` 并进入待核实。
- 康复资料包必须包含有效的 `sources`、`exercises`、来源 ID 和文本字段；非法结构不会写入数据库。
- 资料包重复导入按 `catalog_id` 幂等跳过；任何后续候选写入失败都会回滚同一批次的先前写入。
- 导入资料全部保持 `CANDIDATE`，不会生成 `APPROVED`、执行计划或训练提醒。
- 重复启动锁、提醒幂等、提醒通道失败重试和 Windows 原生消息解码均有测试。

## Phase 6 构建与冻结程序验证

可复现命令：

```powershell
.\.venv\Scripts\python.exe tools\preflight_windows_package.py --skip-installer
.\tools\build_windows_package.ps1
.\.venv\Scripts\python.exe tools\smoke_frozen_exe.py
```

- Windows 本机 AMD64、64 位 Python 3.12.12、PySide6 6.8.3、PyInstaller 6.11.1、Inno Setup 6.7.3。
- EXE 和安装包构建：已通过正式 PowerShell 入口实际执行成功，生成 `dist/LumbarRehabAssistant.exe` 与 `dist/installer/YuAn-Setup-0.1.0.exe`；完整构建返回码 0，Inno 编译日志显示 `Successful compile (33.735 sec)`。
- 本轮重新构建的 EXE：210,159,009 字节；SHA-256 `8C044EC573B45AD0C5C17CFDB318A946AD1CF474A0F729894D4E1951738D83DB`。
- 最终构建后的烟测实际输出：`RESULT=PASS bootloader_pid=35088 owned_pids=[26948, 35088] main_windows=1 database_created=True cleanup=forced_test_process_only`，返回码 0。
- 冻结程序启动烟测：已在真实 Windows 桌面运行，检测标题为“宇安”的可见主窗口及独立临时目录内的 SQLite 文件；跟踪 PyInstaller one-file 启动器及应用子进程。烟测不点击姿势确认，不创建症状或训练记录。
- 退出边界：烟测结束时强制终止仅属于本次测试的进程并删除临时数据；没有据此声称冻结版托盘正常退出、正常收尾恢复或突然断电恢复通过。
- 首次烟测失败原因：原脚本只查启动器 PID，实际窗口属于应用子进程，导致误报无窗口；只终止启动器也使子进程持有临时锁。已修正子进程跟踪与定向清理，后续烟测通过，最初残留的隔离测试进程与临时数据已清理。
- 数据和通信隔离：`REHAB_ASSISTANT_DATA_DIR` 显式覆盖数据位置；仅在存在覆盖变量时由规范化目录派生独立 IPC 名称，普通启动仍保留原有应用标识。新增回归验证同目录名称稳定、不同目录隔离和默认名称兼容。
- 预检修正：`--skip-installer` 允许只构建 EXE；完整模式仍在缺少 Inno 时失败；跳过安装程序不允许跳过 PyInstaller。相关测试隔离实际工具安装状态。
- 安装包：212,281,492 字节；SHA-256 `587F1C1397453B042F036D42F7A066982CDF87D7984E4A7FC5D62EC7F4416A8C`。尚未运行安装包，没有安装、升级或卸载通过结论。
- Inno Setup 工具链：从官方 GitHub release 下载 6.7.3；下载文件 Authenticode 状态 `Valid`，签名主体 `Pyrsys B.V.`；为当前用户安装到 `%LOCALAPPDATA%\Programs\Inno Setup 6`，未修改全局 PATH。下载文件 SHA-256 `9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732`。
- 编译器发现顺序：显式 `-IsccPath`、PATH、当前用户、系统常见安装目录；无效显式路径立即失败，不静默改用其他编译器。构建入口和预检使用同一个解析函数。
- 架构保护：预检要求原生 AMD64 / x86_64 和 64 位 Python；安装器限制 `x64os`，最低系统配置为 Windows 10。32 位 Python 和 ARM64 构建机的拒绝路径有自动化测试。
- 安装配置以 UTF-8 BOM 保存，中文任务文案通过实际编译；安装向导暂用 Inno 默认语言。配置为当前用户安装，不重启此前运行的应用，卸载只清理本应用登录启动值并保留健康数据；这些运行行为尚待安装现场验证。
- 构建告警：全量收集 PySide6 出现可选 deploy 模块、`MIMAPI64.dll`、`LIBPQ.dll`、`Qt63DQuickScene3D.dll` 缺失提示；构建成功且主窗口启动通过，不代表这些可选组件已验证。当前单文件约 200 MiB，仍需目标机检查冷启动速度、逐页资源与体积。

打包专项现有 12 个测试：5 个既有预检 / 进程跟踪测试，加本轮 7 个编译器发现 / 架构拒绝测试；Qt 生命周期另有 2 个 IPC 隔离回归。全量共 151 个测试，9.452 秒，返回码 0。构建、烟测和自动测试结果互不替代。

原始日志保存在被 Git 忽略的 `artifacts/phase6-full-build.log`、`artifacts/phase6-unittest.log` 和 `artifacts/phase6-frozen-smoke.log`。

## 模拟 Windows 事件

已覆盖 Qt 原生消息对象 / 指针解码、会话锁定与解锁、电源挂起与恢复、键鼠空闲环境事实，以及 native event filter 生命周期。测试保证这些事件只能写入环境事实或触发待核实流程，不能直接把键鼠空闲解释为起身。

## 尚未完成的真实验收

以下项目不能由本地自动化测试替代：

- 真实 Windows 10/11 锁屏、休眠、唤醒和不同电源策略。
- 系统通知权限、专注助手、全屏应用和通知抑制行为。
- 真实 SQLite WAL 文件锁竞争、真实进程崩溃和突然断电后的现场恢复；本轮仅完成可控的底层连接异常关闭模拟。
- 多显示器 DPI、系统高对比度、最大文字设置和读屏器。
- 冻结版托盘正常退出、图表 / SVG / 训练 / 症状等页面逐页资源检查。
- 安装器实际安装 / 升级 / 卸载、安装后启动、登录启动清理、无 Python 环境目标机启动和安装包资源完整性。

当前没有将上述项目标记为通过，也没有执行提交或推送。

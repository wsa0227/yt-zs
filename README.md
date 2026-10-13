# yt-zs

Windows 腰椎康复助手 V1 的本地开发仓库。

当前实现按 `PRD.md` 分阶段推进，Phase 3 已完成提醒持久化/投递路由、Windows 环境事实适配接口和对应自动化测试。真实 Windows 桌面通知、锁屏、休眠/恢复仍需在目标系统上单独验收。

## 本地启动（Windows PowerShell）

本机虚拟环境已安装时：

```powershell
cd C:\workspase\python-project\yt-zs
.\.venv\Scripts\rehab-assistant.exe
```

也可运行 `.\.venv\Scripts\python.exe -m rehab_assistant`，不必激活虚拟环境。
关闭主窗口默认隐藏到托盘；真正退出请使用托盘菜单的“退出”。

### 命令立即返回但没有窗口

- 成功激活已有实例时，新进程会退出，不会另开第二个实例。
- 如果锁被占用但激活失败，程序现在会向终端输出锁路径、锁中记录的进程 ID，并返回退出码 `1`。
- 数据目录/锁访问错误和日志/数据库初始化失败也会向终端输出原因。命令返回后可运行 `$LASTEXITCODE` 查看退出码。
- 先检查系统托盘或根据提示核对对应旧进程。不要直接删除数据库、强删锁文件或批量终止所有 Python 进程。

## 主窗口视觉优化

现有桌面窗口已按 `docs/腰椎康复助手界面设计板.png` 改为浅蓝侧栏、白色状态卡、绿色环形计时和蓝色操作按钮；40 分钟上限使用红色警示。展示本次开始时间和下一提醒阈值倒计时，小窗口纵向排列并支持滚动。保留人工姿势确认和“知道了仅表示已读”的语义。首页五张能力卡及症状、训练、数据统计、设置、帮助入口已补齐。症状表单、动作卡 / 我的计划、三类趋势页目前为明确占位；未接入的保存、导出和训练启用禁用，不伪造记录或统计。设置页登录启动复用已有适配器；托盘补齐人工姿势操作和退出确认。

设计与验证记录见 `docs/UI_DESIGN.md`；完整设计板覆盖清单、占位契约与分期验收见 `docs/UI_COVERAGE.md`。可用 `tools/render_ui_preview.py` 渲染内存测试数据预览，不读写真实应用记录；生成图片保存在被 Git 忽略的 `artifacts/` 目录。正常启动命令不变。已经运行的旧实例需从托盘退出，再启动才能载入新版界面。

## 界面验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools/render_ui_preview.py --platform windows --output-dir artifacts/ui-pages-windows
```

预览使用内存 SQLite 和固定测试时钟，不读写实际健康数据，也不发送系统通知。上一轮设计还原的完整测试为 57/57、原生 UI 为 20/20；本轮最新页面覆盖测试结果见 `docs/UI_COVERAGE.md`，不能把页面占位当成业务完成。本轮未生成安装包。

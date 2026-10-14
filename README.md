# yt-zs

Windows 宇安 V1 的本地开发仓库。

产品 slogan：予慧宇，一份日常的安心。

当前实现按 `PRD.md` 分阶段推进，Phase 3 的提醒持久化/投递路由、Windows 环境事实适配接口、Phase 4A 的症状记录 / 安全规则基础、Phase 4B 的专业确认训练基础（含用户主动导入候选资料包，schema v6）、Phase 4C 的统计趋势基础、Phase 4D 的提醒偏好基础和 Phase 5 的可靠性基础已经完成。真实 Windows 桌面通知、声音控制、锁屏、休眠/恢复仍需在目标系统上单独验收。

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

现有桌面窗口已按 `docs/腰椎康复助手界面设计板.png` 改为浅蓝侧栏、白色状态卡、绿色环形计时和蓝色操作按钮；40 分钟上限使用红色警示。展示本次开始时间和下一提醒阈值倒计时，小窗口纵向排列并支持滚动。保留人工姿势确认和“知道了仅表示已读”的语义。首页五张能力卡及症状、训练、数据统计、设置、帮助入口已补齐。症状页已接入本地保存、同日更新、编辑、删除、CSV 导出和固定安全提示；训练页已接入资料候选、专业确认录入、计划状态和训练 / 不适日志，但不内置动作、不自动推荐或排程；统计页已接入最近 7 天 / 30 天的坐姿时长、症状变化和起身次数查询与原生 Qt 图表，缺失值和不确定坐姿区间不会补成零或伪造记录。设置页登录启动复用已有适配器，并已接入提醒偏好持久化；关闭重复提醒只抑制 40 分钟后的后续提醒，声音开关暂未改变系统通知声音。托盘补齐人工姿势操作和退出确认。

设计与验证记录见 `docs/UI_DESIGN.md`；完整设计板覆盖清单、占位契约与分期验收见 `docs/UI_COVERAGE.md`；未实现功能的原因、当前边界和排期见 `docs/IMPLEMENTATION_GAP_ANALYSIS.md`。可用 `tools/render_ui_preview.py` 渲染内存测试数据预览，不读写真实应用记录；生成图片保存在被 Git 忽略的 `artifacts/` 目录。正常启动命令不变。已经运行的旧实例需从托盘退出，再启动才能载入新版界面。

## 界面验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools/render_ui_preview.py --platform windows --output-dir artifacts/ui-pages-windows
```

预览使用内存 SQLite 和固定测试时钟，不读写实际健康数据，也不发送系统通知。本轮全量自动化测试 `134/134` 通过；详细覆盖、缩放结果和未验收事项见 `docs/UI_COVERAGE.md`。页面占位不等于业务完成。本轮未生成安装包。

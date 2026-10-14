# 宇安｜康复资料库与记录规范 V1

整理日期：2026-10-14。本包为候选资料与模板，不是慧宇的训练处方。

## 一、与当前系统的关系

用户提供的《Phase 0 架构决策：Windows 腰椎康复助手 V1》第3节明确：ExerciseCatalog 的接口为 save_candidate / approve / suspend / list_executable / record_log；仅 APPROVED 且未停用项可执行，初始为空，不自动推荐/排程。JournalService 记录空值不补零。第7节要求医学文案专业复核后才进入发行。
本次10项全部为候选，已批准动作0项、有效计划0份。外部资料目录不等于首次启动即导入；只能由用户主动选择后保存为候选。手工计划与详细日志字段属于新增建议，不是已实现功能。本次未修改本地代码、未建表、未迁移。
慧宇的发病阶段、影像和40分钟坐姿上限来自用户说明，未核实病历。未获得具体动作医嘱，不擅自安排次数、时长或疗程。

## 二、资料分层

健康教育用于查阅；候选动作供专业人员选择；个体化确认动作需记录针对慧宇的具体许可与处方；手工计划引用已确认内容；训练日志记录真实发生的活动与反应。
来源可靠性、中文医学文案复核、媒体动作匹配、个人动作许可、素材使用权是五个独立维度，不能共用一个“已审核”开关。运动选择应考虑个体需要、偏好与能力。[S08]

## 三、第一批10项候选动作

以下不是跟练顺序或难度排序。摘要只供检索和讨论，不是完整操作指导。所有动作默认禁用执行和训练提醒。

### YA-EX-001 · 步行与活动间歇
原词：Walking / activity breaks；类型：日常活动候选。
日常活动单独记录，不预设步数或分钟数。
来源：[S13](https://www.nhs.uk/conditions/slipped-disc/)；[S08](https://www.nice.org.uk/guidance/ng59/chapter/Recommendations)
图片：本次未配置，不用无关图片填充
需要专业确认：目前是否允许步行，一次多长、何时休息？ 站立或步行是否诱发腿部症状，是否需要辅助？
**状态：待专业确认；处方为空；不可执行。**

### YA-EX-002 · 放松呼吸
原词：Relaxed diaphragmatic breathing；类型：放松练习候选。
放松呼吸资料入口，不预设强迫深呼吸或屏气训练。
来源：[S10](https://www.mskdorset.nhs.uk/back-pain_1/back-pain-low-back-pain/)
图片：本次未配置，不用无关图片填充
需要专业确认：采用什么体位，是否需要垫枕？ 是否安排为独立练习；不适时如何处理？
**状态：待专业确认；处方为空；不可执行。**

### YA-EX-003 · 腹部收紧
原词：Abdominal bracing；类型：躯干控制候选。
腹部肌肉收紧图示，不等同于仰卧起坐。
来源：[S02](https://www.orthoinfo.org/recovery/spine-conditioning-program/)
图片：I01
需要专业确认：具体用力方式与腰部位置怎样？ 是否需要现场教学，怎样避免错误理解示意箭头？
**状态：待专业确认；处方为空；不可执行。**

### YA-EX-004 · 骨盆倾斜
原词：Pelvic tilt；类型：活动控制候选。
仰卧屈膝位骨盆活动的参考图示。
来源：[S10](https://www.mskdorset.nhs.uk/back-pain_1/back-pain-low-back-pain/)
图片：I02
需要专业确认：允许哪个方向和多大幅度？ 与腹部收紧是否分开安排，怎样避免混淆？
**状态：待专业确认；处方为空；不可执行。**

### YA-EX-005 · 仰卧屈膝左右摆动
原词：Knee rolls；类型：旋转方向候选。
屈膝仰卧时左右摆动的动作参考。
来源：[S04](https://www.guysandstthomas.nhs.uk/health-information/low-back-pain/physiotherapy-and-exercises)
图片：I03
需要专业确认：目前是否允许腰部旋转？ 单侧或双侧，终点位置和支撑方式怎样设置？
**状态：待专业确认；处方为空；不可执行。**

### YA-EX-006 · 仰卧单膝靠胸
原词：Single knee hug；类型：屈曲方向候选。
单膝靠近胸部示范，与双膝抱胸分别确认。
来源：[S04](https://www.guysandstthomas.nhs.uk/health-information/low-back-pain/physiotherapy-and-exercises)
图片：I04
需要专业确认：当前是否适合屈曲方向？ 出现腿痛、麻木或放射范围变化时如何处理？
**状态：待专业确认；处方为空；不可执行。**

### YA-EX-007 · 猫式活动
原词：Cat-style spinal mobility；类型：屈伸活动候选。
四点支撑下腰背活动的参考图示。
来源：[S01](https://www.pumch.cn/detail/38562.html)
图片：I05
需要专业确认：是否适合四点支撑及屈伸活动？ 是否只允许部分方向或缩小幅度，如何保护手腕和膝部？
**状态：待专业确认；处方为空；不可执行。**

### YA-EX-008 · 臀桥
原词：Hip bridge；类型：力量训练候选。
仰卧屈膝抬起骨盆的参考图示。
来源：[S02](https://www.orthoinfo.org/recovery/spine-conditioning-program/)
图片：I06
需要专业确认：目前是否允许桥式，抬高到什么位置？ 怎样判断动作质量，哪些反应要求停止？
**状态：待专业确认；处方为空；不可执行。**

### YA-EX-009 · 鸟狗式
原词：Bird dog；类型：对侧支撑候选。
四点支撑后伸出对侧上肢与下肢的参考图示。
来源：[S02](https://www.orthoinfo.org/recovery/spine-conditioning-program/)
图片：I07
需要专业确认：是否需要先采用简化变式？ 保持时间、次数及躯干稳定标准如何设定？
**状态：待专业确认；处方为空；不可执行。**

### YA-EX-010 · 俯卧肘支撑
原词：Prone on elbows；类型：后伸方向候选。
肘支撑的后伸方向图示，不代表完整麦肯基评估方案。
来源：[S04](https://www.guysandstthomas.nhs.uk/health-information/low-back-pain/physiotherapy-and-exercises)；[S01](https://www.pumch.cn/detail/38562.html)
图片：I08
需要专业确认：目前是否适合后伸方向，应观察哪些症状反应？ 是否只允许肘支撑，不自动升级为手撑后伸。
**状态：待专业确认；处方为空；不可执行。**

## 四、图片、视频与手册

### 8幅原站图片入口

只提供来源与原图网址，不打包原图。优先打开完整来源页面，保留文字和动作上下文。

- I01 **腹部收紧**：对应YA-EX-003；[来源页](https://www.orthoinfo.org/recovery/spine-conditioning-program/)；[原站图片](https://www.orthoinfo.org/contentassets/9a58e369fb0a47fb8ddee529dba5d829/fig-10-compressor.jpg)。原网页第10项。
- I02 **骨盆倾斜**：对应YA-EX-004；[来源页](https://www.mskdorset.nhs.uk/back-pain_1/back-pain-low-back-pain/)；[原站图片](https://www.mskdorset.nhs.uk/wp-content/uploads/2021/11/Picture-2.jpg)。网页Pelvic tilt；第三方署名Physiotools。
- I03 **仰卧屈膝左右摆动**：对应YA-EX-005；[来源页](https://www.guysandstthomas.nhs.uk/health-information/low-back-pain/physiotherapy-and-exercises)；[原站图片](https://www.guysandstthomas.nhs.uk/sites/default/files/styles/wysiwyg_default_xs/public/2024-03/6.jpg.jpg?itok=KptN5jo7)。网页Knee rolls；单侧位置图，不是完整动作。
- I04 **单膝靠胸**：对应YA-EX-006；[来源页](https://www.guysandstthomas.nhs.uk/health-information/low-back-pain/physiotherapy-and-exercises)；[原站图片](https://www.guysandstthomas.nhs.uk/sites/default/files/styles/wysiwyg_default_xs/public/2024-03/10.jpg.jpg?itok=8FhWNvo4)。网页Knee hugs；单侧示范。
- I05 **猫式活动**：对应YA-EX-007；[来源页](https://www.pumch.cn/detail/38562.html)；[原站图片](https://www.pumch.cn/Uploads/Picture/2024/11/08/u672d650cab558.png)。网页猫式伸展插图；静态查看不能代替完整动作审查。
- I06 **臀桥**：对应YA-EX-008；[来源页](https://www.orthoinfo.org/recovery/spine-conditioning-program/)；[原站图片](https://www.orthoinfo.org/contentassets/ba6ef79e071a40efb77592b7e1a54146/fig-9-compressor.jpg)。原网页第9项。
- I07 **鸟狗式**：对应YA-EX-009；[来源页](https://www.orthoinfo.org/recovery/spine-conditioning-program/)；[原站图片](https://www.orthoinfo.org/contentassets/0d29930fbfb04b26ae474629e0c16b41/fig-6-compressor.jpg)。原网页第6项。
- I08 **俯卧肘支撑**：对应YA-EX-010；[来源页](https://www.guysandstthomas.nhs.uk/health-information/low-back-pain/physiotherapy-and-exercises)；[原站图片](https://www.guysandstthomas.nhs.uk/sites/default/files/styles/wysiwyg_default_xs/public/2024-03/1.jpg.jpg?itok=f44i8BrG)。网页Back extensions；仅肘支撑变式。

### 6组视频入口

前序检索核对了官方发布页面及其链接指向，但没有完整播放、逐帧审看、核对字幕或在慧宇的Windows电脑验收。中文目录不保证普通话，英文页面也不保证特定字幕。

- V01 **坐骨神经痛：建议与动作**：[NHS](https://www.nhs.uk/live-well/exercise/exercises-sciatica-problems/)。从官方页面打开播放器。英文页面；音轨和字幕待核实。
- V02 **腰痛时如何保持活动**：[Guy’s and St Thomas’ NHS Foundation Trust](https://www.guysandstthomas.nhs.uk/health-information/low-back-pain/physiotherapy-and-exercises)。[原视频/合集](https://www.youtube.com/watch?v=Vk-kDE7UMOQ)。英文页面；音轨和字幕待核实。
- V03 **脊柱活动：屈曲方向**：[Torbay and South Devon NHS Foundation Trust](https://www.torbayandsouthdevon.nhs.uk/services/physiotherapy/support-videos/managing-mechanical-lower-back-pain/)。[原视频/合集](https://player.vimeo.com/video/906408545?dnt=1)。英文页面；音轨和字幕待核实。
- V04 **脊柱活动：后伸方向**：[Torbay and South Devon NHS Foundation Trust](https://www.torbayandsouthdevon.nhs.uk/services/physiotherapy/support-videos/managing-mechanical-lower-back-pain/)。[原视频/合集](https://player.vimeo.com/video/907499584?dnt=1)。英文页面；音轨和字幕待核实。
- V05 **脊柱力量训练**：[Torbay and South Devon NHS Foundation Trust](https://www.torbayandsouthdevon.nhs.uk/services/physiotherapy/support-videos/managing-mechanical-lower-back-pain/)。[原视频/合集](https://player.vimeo.com/video/910099963?dnt=1)。英文页面；音轨和字幕待核实。
- V06 **肩颈、背部及下肢痛症普拉提合集**：[香港医院管理局 / 屯门医院](https://www3.ha.org.hk/ntwc/msc/tc/ol/pep_bySpecialty_pt.html)。[原视频/合集](https://www.youtube.com/playlist?list=PLU44Qbt53BJvyKcVYze4D_MizRmz_AvPm)。中文目录；粤语/普通话/字幕均待核实。

主题关联不代表某条视频已核对到该动作片段。个人许可应绑定具体动作变式、视频或片段起止及版本；不得批准整张随时变化的播放列表。屈曲、后伸和力量视频不能自动拼成全套跟练。

### 两份手册

- [AAOS脊柱训练PDF](https://www.orthoinfo.org/globalassets/pdfs/spine-conditioning-program_3-20-25.pdf)：版本标识来自官网文件名；不导入整套训练量。
- [广华医院腰部护理及运动手册（2011）](https://www3.ha.org.hk/kwh/main/files/pdf/PHYS_BackCare%26Exercise.pdf)：历史资料，记录格式参考，不当作最新指南。

## 五、专业确认的记录方式

每项动作记录：使用者、动作及内容版本、具体变式、专业人员姓名/角色/机构、确认日期、允许/暂缓/不允许结论、训练量、频率、停止条件、复核安排、依据与录入人。
专业人员直接填写、依据纸质/电子医嘱代录、用户口头转述必须分开标识。泛泛的“可以运动”不等于这10项全部获准；剂量和停止条件不完整时保持待核实。
单机V1不能核验专业身份。准确的界面标识是“已记录专业确认（用户代录，软件未核验）”，不是“平台医生认证”。附件如有仅本地保存，不收集不必要的身份证等敏感资料。
字段完整性检查不能证明医学正确性或医嘱真实性。动作版本、变式或处方变化后应重新核对；不能把旧审批静默用于新内容。

## 六、训练计划

当前计划为空且保持DRAFT。已有35/40分钟提醒、人工起身确认和日常症状记录，与康复训练计划独立。40分钟是用户报告的个人医嘱，不是普遍适用的医学阈值。
得到个体化确认后，人工填写计划目标、日期范围、复核日期、整体安排依据；计划项引用动作版本、批准记录ID和处方快照，再据实际医嘱写入顺序与时段。
每个动作单独获准，不代表把它们组合后的总量也获准；组合、顺序和频率要有相应依据。次数型、保持型、计时型剂量分开；不适用字段显式标注，不能为通过校验乱填0。
不提供“每日两组”“七天疗程”“完成后自动加量”等默认值。训练提醒默认关闭；后续加入定时训练提醒需要单独确认范围，不能改变不自动排程的现有约束。

## 七、日志与趋势

保留计划/动作/审批版本、实际时间及来源、实际次数/组数/时长、完成/部分完成/中断/跳过、原因、训练前后腰痛和腿痛评分。0–10评分未填时为null，不是0。
可记录部位、左右侧、麻木/无力/放射范围变化，以及稍后补记的症状反应。缺失日期不补成真实数据；软件不自动判断病情好转、治愈或动作有效。
每日症状记录和多次训练日志分别保存，不互相覆盖。视频结束、窗口关闭、计时结束均不代表训练完成。允许记录计划外实际活动，但标“用户自述、非计划”，不能反向审批动作。
修改记录需保留更正痕迹。历史日志保留当时处方快照，未来更改计划不能改写历史。未记录不等于未训练，跳过或停止也不设置惩罚文案。

## 八、安全提示草案

若出现新发会阴或肛周麻木、排尿困难或尿潴留、大小便控制异常等，请停止训练并立即到急诊评估。症状严重或无法安全出行时联系当地急救服务，不要等待软件再次提醒。 [S09][S13]
新发或进行性腿部无力、明显加重的麻木或放射痛，应暂停相关训练并尽快联系医生；严重或快速加重时急诊评估。 [S09][S13]
训练引起疼痛明显加重、头晕或其他不适时，先停止并记录，再根据医嘱联系专业人员。 [S01]
上述中文提示发行前仍需专业复核，不是完整分诊表。任何疼痛分值再低，也不能抵消警示症状；国外网站的急救电话号码不固定照搬，按使用地区配置。

## 九、图片、视频与离线交付

本包不含医院原图、原视频或第三方PDF文件，不是离线视频包。HTML目录本身不加载外部图像、播放器、字体或遥测；只有用户主动点原站链接才联网。
海外视频可能依赖第三方播放器，本次未验收中国内地或目标电脑可播放性。不要承诺离线或无网络播放。
AAOS和NHS都有具体再使用范围限制。[S11][S12] 本包按“原站查阅、未取得再分发授权”处理媒体。需要随安装包离线分发时，先取得相应许可，或采用经当事人同意录制、经治疗师确认的个体化示范。
自绘或AI生成的动作图也需要医学复核。不能把好看的图当作动作正确的证明。local_path和sha256仅在获得合法且已确认的本地素材后填写。素材失效不能随机替换同名视频。

## 十、文件使用

双击resource_index.html查看来源目录；yu_an_review_forms.docx可打印或编辑；catalogue.json供开发适配候选内容；record_templates.json是空白数据模板；implementation_handoff.md记录增补建议与验收项。JSON尚未通过当前应用导入测试，不声称开箱即用。

## 来源目录

### S01 · 腰痛不要怕，康复医生教您居家康复
发布者：北京协和医院；语言：中文；来源版本/日期：2024-11-08。
https://www.pumch.cn/detail/38562.html
腰痛科普及猫式等动作图示。
限制：不是慧宇的处方，不整套导入训练量。

### S02 · Spine Conditioning Program
发布者：AAOS / 美国骨科医师学会；语言：英文；来源版本/日期：本次未确认。
https://www.orthoinfo.org/recovery/spine-conditioning-program/
包含腹部收紧、臀桥、鸟狗式等图示，供专业人员选取。
限制：通用脊柱训练资料，不等于对慧宇的个体化许可。

### S03 · Exercises for sciatica problems
发布者：NHS；语言：英文页面；来源版本/日期：网页/媒体复核：2026-03-02。
https://www.nhs.uk/live-well/exercise/exercises-sciatica-problems/
坐骨神经痛科普与动作视频入口。
限制：未完整播放、逐帧审看或核实字幕。

### S04 · Low back pain: Physiotherapy and exercises
发布者：Guy’s and St Thomas’ NHS Foundation Trust；语言：英文；来源版本/日期：2024-03 / 4876-VER2。
https://www.guysandstthomas.nhs.uk/health-information/low-back-pain/physiotherapy-and-exercises
屈膝摆动、抱膝、后伸图示及保持活动的科普视频。
限制：动作分别确认，不将网页全套内容视为个人方案。

### S05 · Managing mechanical lower back pain
发布者：Torbay and South Devon NHS Foundation Trust；语言：英文页面；来源版本/日期：本次未确认。
https://www.torbayandsouthdevon.nhs.uk/services/physiotherapy/support-videos/managing-mechanical-lower-back-pain/
分别提供屈曲方向、后伸方向和力量训练视频。
限制：不能自动拼成跟练疗程；实际播放未验收。

### S06 · 專為肩頸、背部及下肢痛症而設的普拉提運動
发布者：香港医院管理局 / 屯门医院；语言：繁体中文目录；来源版本/日期：目录年度：2025/26。
https://www3.ha.org.hk/ntwc/msc/tc/ol/pep_bySpecialty_pt.html
官方目录中的普拉提合集，保留为扩展候选。
限制：未核实单集动作、粤语/普通话音轨、字幕或播放。

### S07 · 腰部護理及運動手冊
发布者：香港医院管理局 / 广华医院物理治疗部；语言：繁体中文；来源版本/日期：2011-11。
https://www3.ha.org.hk/kwh/main/files/pdf/PHYS_BackCare%26Exercise.pdf
历史图文手册，印刷页26有运动日志。
限制：仅参考资料组织与记录格式，不当作最新指南。

### S08 · Low back pain and sciatica in over 16s: recommendations
发布者：NICE；语言：英文；来源版本/日期：NG59；重点参照1.2.1、1.2.2。
https://www.nice.org.uk/guidance/ng59/chapter/Recommendations
选择运动应考虑个人需要、偏好与能力。
限制：指南不能代替个人动作处方。

### S09 · Sciatica
发布者：NHS；语言：英文；来源版本/日期：本次未确认。
https://www.nhs.uk/conditions/sciatica/
用于神经相关症状和紧急就医警示核对。
限制：不构成完整分诊工具，中文发行文案需专业复核。

### S10 · Low back pain
发布者：NHS Dorset / Musculoskeletal Matters；语言：英文；来源版本/日期：本次未确认。
https://www.mskdorset.nhs.uk/back-pain_1/back-pain-low-back-pain/
骨盆倾斜图及放松呼吸资料。
限制：不导入通用训练量；图片含第三方署名，权利另核对。

### S11 · Linking (Free Use) Policy
发布者：AAOS；语言：英文；来源版本/日期：本次未确认。
https://www.orthoinfo.org/about-orthoinfo/linking-policy/
原站链接与再使用限制的核对入口。
限制：不能将公开可看等同于允许复制进安装包。

### S12 · Content not covered by our standard terms and conditions
发布者：NHS；语言：英文；来源版本/日期：本次未确认。
https://www.nhs.uk/our-policies/terms-and-conditions/content-not-licensed-for-re-use/
部分图像和视频不适用一般再使用条款。
限制：NHS主站条款不能代表所有医院或第三方素材。

### S13 · Slipped disc
发布者：NHS；语言：英文；来源版本/日期：网页复核：2024-04-24。
https://www.nhs.uk/conditions/slipped-disc/
椎间盘相关症状、活动与就医说明。
限制：一般活动说明不替代个体化许可。

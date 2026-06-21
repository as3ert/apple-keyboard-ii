# Apple Keyboard II 项目交接上下文（2026-06）

## 项目概况
自制复刻 Apple Keyboard II 的机械键盘，分两块板：
1. **键盘主板**：80 键 5×18 矩阵（ROW0-4 × COL0-17），二极管 COL2ROW，通过 28P 0.5mm FPC 排线（型号 FPC05028-43200，下接掀盖式）连到控制器板。FPC 排线方向第一版打错，已改对重打。
2. **控制器板（当前调试中）**：53×32mm，嘉立创EDA（LCEDA）设计，已打样贴片。

## 控制器板硬件（已从源文件逐引脚核对，连接全部正确）
- 主控：Seeed XIAO nRF52840（顶层，板左缘，USB 朝外）
- 2× MCP23017-E/SS（SSOP-28，0.65mm 间距）做 I/O 扩展，挂 I²C：
  - MCP23017C @ 0x20（A0-A2=GND）：GPA0-7=COL8-15，GPB7=COL16，GPB6=COL17
  - MCP23017R @ 0x24（A2=3V3, A1=A0=GND → 0x20+4=0x24）：GPB7..GPB0=COL0..COL7，GPA0-4=ROW0-4
  - 两片 RESET 都已接 3V3 ✓；INTA/INTB 悬空（已知缺陷：无法中断唤醒，省电要飞线到 XIAO 空脚 D3）
- I²C 在 XIAO 的 D4(SDA)/D5(SCL)；上拉电阻位置：R1/R3=SCK 上拉、R2/R4=SDA 上拉（两组并联冗余，**只需各焊一颗 4.7k**）
- 其他：C1/C3=100nF 0402，C2/C4=1µF 0603，R5/R6=4.7k（编码器 A/B 上拉），R7=10k（编码器 SW 上拉），BAT=PH2.0 电池座（XIAO 板载充电；**丝印朝上看：右 pad=+(1脚,带圆点,接 XIAO BAT)，左 pad=−(GND)**。注意 PH2.0 锂电插头极性无标准，接前务必万用表量电池红线=+，对准板上 + pad，接反烧 XIAO），"EC11"位号实际是 JST SH 1.0mm 5P 侧插座（编码器外接，接 XIAO D0/D1/D2），U1 是板框外的多余遗留件（不贴，下版删除）
- FPC 座引脚：1-5=GND，6-23=COL17→COL0，24-28=ROW4→ROW0

## ✅ 整机状态（2026-06：全功能调通）
- 电池、I²C+两片 MCP23017、ZMK 固件、全键位、USB、蓝牙 **全部正常工作**。
- **固件已换成 ZMK**（zmk-config/，akii shield）。CircuitPython 测试灯语**全部作废**——ZMK 没配 RGB，看到的绿灯只是 XIAO 板载充电指示，不是状态。
- 蓝牙控制键（FN 层，FN=`&mo 1` 空格右/方向键左那颗）：FN+Q~T=BT_SEL 0~4、FN+Y=BT_CLR、FN+B=OUT_BLE、FN+U=OUT_USB。配对：FN+Q→主机配 "AKII"→FN+B 切蓝牙输出。坑：插 USB 时默认走 USB 必须 FN+B；搜不到就 FN+Q 选位+FN+Y 清旧配对。
- 验机：插 USB 枚举 "AKII" 直接打字；或开 ZMK Studio 看键位高亮。
- 历史排障已结：①假 4.7k 料导致 I²C 故障 → R3 真料挪焊到 R2，已修；②电池接入时一度量到 0V，实为插头没插到位（电池本身 3.8V 正常），插到底即通；③右上角 KP*(RC(0,17)) 不出 → 那颗轴虚焊，补焊/插紧后好。

## 🔋 省电 / 两级 kscan 驱动（2026-06）
- **基线实测（2000mAh，纯空闲待机）**：stock ~1.5-1.6mA(~52天)；poll30 ~0.7-0.86mA(~3.5月,流畅)；poll50 ~0.5-0.8mA(删除发滞)；poll80 ~0.4mA(明显延迟)。慢轮询全局赢不了"省电 vs 手感"权衡。
- **ZMK 已 pin** 到 commit ff09f2d（2026-06-07，Zephyr v4.1.0+zmk-fixes；注意该 Zephyr 里 kscan 子系统已标 DEPRECATED）。
- **两级 kscan 驱动**（`twotier` 分支，自定义 out-of-tree 模块，raw I²C 接管两片 MCP23017）：ACTIVE 全扫 5ms=stock手感；IDLE 超时 750ms 后全行拉低做"摘要读"@80ms ≈ 0.4mA；按键唤醒。目标=poll80 的电 + stock 的手感。文件：`drivers/kscan/kscan_akii_twotier.c` + `dts/bindings/kscan/zmk,kscan-akii-twotier.yaml` + `zephyr/module.yml`+`CMakeLists.txt`+`Kconfig`（模块插桩）。
- **质量过程**：7 维多智能体对抗审查（抓到 LOG_WARN→LOG_WRN）→ CI 终检（抓到 `select KSCAN` 触发 Kconfig 递归，改 `depends on KSCAN`）→ **编译通过**。
- **firmware/ 里的 uf2**：**akii-twotier.uf2**=日常(Studio)；**akii-bringup.uf2**=带 USB 日志(DBG)用于 `tools/matrix_test.py` 逐键验证。（早期一级实验 uf2 akii-stock/poll30/50/80 已清理,无用;实验结论见上方"省电/两级 kscan"小节。）
- **真机验收已过（2026-06）**：matrix_test.py 全 90 键位通过；**打字 1.5mA / 静止 idle 0.57mA**（2000mAh ≈ ~5 个月待机），手感=stock、删除跟手、蓝牙常连、按键即时。两级切换实测可见(按住键 1.5mA、松手 750ms 后掉 0.57)。
- **QSPI flash 省电——全部试到底,此路不通,别再碰**：
  - `&qspi status=disabled`(overlay)= no-op(被板级 xiao_ble_zmk.dts 的 `&qspi okay` 覆盖,binary 没变,MD5 验证过)。
  - `CONFIG_NORDIC_QSPI_NOR=n`(关驱动)→ **1.15mA(更差)**:flash 靠驱动哄睡,关了驱动它一直醒着。
  - `CONFIG_PM_DEVICE_RUNTIME=y`(让驱动把 flash 打进 DPD)→ **3.31mA + 打不了字**:这是全局开关,把 **I²C 总线**也运行时挂起了,而两级驱动猛敲 I²C 却没参与 PM → 扫描崩 + suspend/resume 狂churn。(注:#55543 DPD-exit bug 其实已修(PR#64782,在 v4.1.0);理论余量只有 standby→DPD ~17µA,低于表噪声。)
  - **结论:保留 stock QSPI 驱动不动。0.57mA 里大头是 nRF/BLE idle 底 + 两片 MCP23017,flash 已在 standby。**
- **深睡(System OFF, ~2µA)**:要飞 INT 线 + 唤醒重连蓝牙(~1-3s 丢首击),不划算,**放弃**。
- **DC/DC 已开**:xiao_ble DT `&reg1 regulator-initial-mode=DCDC`,这个杠杆本来就在省了。**0.57mA 是这块硬件(蓝牙常连+不深睡)的真地板,所有杠杆探尽。**
- **✅ 已收工（2026-06）**：`twotier` 已合进 `main`,两级驱动为日常固件。日常刷 `akii-twotier.uf2`(md5 14cb95d7)。idle/active/timeout 周期在 overlay kscan0 节点可调(默认 80/5/750ms)。最终成绩:**0.57mA idle / ~5 月待机 / stock 手感 / 蓝牙常连 / 全键位**。

## 🔧 外壳/固定件阶段（进行中，电子部分已完结）
- **思路**:复用原版 AKII 外壳自带的 **3 个锥形螺柱(一排,底径 6mm)** 当定位点(那个孔本是定位钢板用的,我们只借位、不占)。打印件做"托盘":顶面平台坐控制器板,板背 PH2.0(~5.1mm)落进挖穿的凹槽,底铺平、留走线。
- **已定参数**:螺柱按 Ø6 圆柱建(跳过锥形),让位坑做 **Ø6.4**(+0.4 间隙好套);平台高 **5mm**;PH 凹槽**挖穿/≥5.5mm 深**(连接器比 5mm 高 0.1,别让板顶在连接器上)。
- **建模工具**:用 **Fusion 360**(用户已装好,主力)。OpenSCAD 也装了(`/Applications/OpenSCAD-2021.01.app`,已去 quarantine、headless `-o out.stl in.scad` 可用)备用。
- **打印/收缩经验(已确认)**:FDM 高度方向几乎不缩(层高叠出,反因象脚偏高),所以**功能高度尺寸照实建、别加放大**(纠正过"5→6 补缩水"的误区)。真正要补的是**配合孔**:孔会偏小(象脚+内壁过挤,缩 0.1–0.3),套柱孔=柱径+~0.4。导出用 **3MF**(Bambu Studio 原生、带单位,优于 STL)。可开切片里 Elephant Foot Compensation(~0.15)补象脚。

### 三个固定件进展
1. **控制器板托盘**:平台基座(已改 5.5mm 高,原 5)+ 中心**通孔 Ø6.6**(实测螺柱 Ø6.2,+0.4;通孔比盲坑稳,柱多高都能穿)。PH 让位改成"**平台压矮天然留空隙**"——不挖槽,把平台整体压矮让板背和平台间留整片空隙,PH 连接器悬空,**还顺带让 PH 座不吃力、保护座子**(板受力走螺柱/边缘)。空隙要 ≥PH 插好后高度(裸座 5.1+插头弯折,留 6.5–7mm)。填充 5%(不承重)、顶层实心 3–4 层。
2. **PCB 限位**(键盘主板浮在 钢板→泡棉→PCB 的栈上,需 XY 限位):
   - 钢板贴泡棉(Tesa 布基双面胶,擦净钢板再贴;胶太宽两条横铺满,沿长边贴上下两条)。
   - 左右靠外壳侧壁贴死、Z 靠上盖压,只需补前后+防翘。
   - **顶边两个 C 形钩**(横向滑入,夹 钢板+泡棉+PCB 整摞):**夹口 5mm 配压缩后 5.5mm 栈 = 0.5mm 过盈**,上压唇伸进 PCB 4mm(可用 4.5),前端引导斜角。**✅ 已打印,完美卡住**。
   - 底边原以为不能兜钢板底(钢板紧贴底壳),**后发现底边也塞得下同款 C 钩**→ 直接复用顶边那个件,上下各一组,两条边都咬死,2mm 薄压片方案作废。**✅ PCB 限位闭环**。
3. **电源开关座/垫高**(switch riser):矩形垫,**左右两个半圆缺口**(R2.5/Ø5.0,卡两个锥形柱,实测柱 4.6+0.4;两柱分卡左右缺口→平面 XY+旋转全锁,Z 靠上盖压,不会脱)+ **中心圆孔**给开关。厚度**暂设 5.5(占位)**,垫高量等开关到了实测"按钮顶高 vs 外壳开孔高"再改拉伸。

- **电池/电池托/走线:✅ 已全部搞定**(电池买好、托和走线槽都做完了)。
- **整个项目就差最后一步:电源开关收尾**。开关座占位件已画好(见上 #3),开关到了只需:①Fluke 蜂鸣档找"弹起断/按下通"那对脚,SPST 串电池正极线,热缩管(🦜阳台通风);②实测按钮顶高 vs 外壳开孔高 → 改开关座拉伸厚度(垫高量)+ 中心孔对开关本体 + 定固定方式;③装上验机 → **收工**。
- **等硬件**:自锁(push-push)电源开关~明天到(两端各一锥形,实测 4.6,让位缺口 R2.5/Ø5.0 已定)。

## 固件/测试现状（历史 CircuitPython 阶段，已废）
- 用 CircuitPython 测试（XIAO 刷的是拼音中文版 UF2，建议换英文版）
- 测试脚本 test_all_code.py（在 apple-keyboard-ii 文件夹）：不依赖库、直接写 MCP23017 寄存器，永不崩溃，灯语：红狂闪=I²C 无上拉；红蓝交替=缺芯片；绿心跳=两片全好+矩阵扫描中；白=检测到按键。串口看输出：`screen /dev/tty.usbmodem* 115200`
- 长期固件计划：先 KMK/CircuitPython 跑通 USB，再迁 ZMK（注意：主线 ZMK 无 MCP23017 驱动，需自写/移植；Zephyr 有 mcp230xx GPIO 驱动可参考）

## 调试时间线与当前卡点
1. 最初报错 `RuntimeError: No pull up found on SDA or SCL`（拼音版显示 "wèi zhǎo dào shàng lā"）
2. 曾误判"绿灯=测试通过"——实际那是 CircuitPython 系统状态灯（脚本崩溃后系统接管 RGB），真实状态一直是 I²C 初始化失败
3. REPL 测试（内部下拉法）确认 SDA、SCL 都无外部上拉
4. 万用表排查发现：**R1、R3 位置是真 4.7k，R2、R4 位置贴的是错料（约 1.2MΩ，整条料带都是假"4.7k"）**——SCK 线好，SDA 线瘫，导致整个 I²C 故障（红灯狂闪）
5. **当前待办：把 R3 上的真 4.7k 拆下挪焊到 R2**（SCK 留 R1 即可），任何 2.2k-10k 都能替代；之后 REPL 重跑 pull-up 测试 → 期望绿心跳 → 镊子短接 FPC 23↔28 脚应出白灯+串口打印 pressed:[(0,0)]
6. 注意事项：那批假 4.7k 料还混在元件堆里，任何电阻上板前先悬空量一遍；助焊剂残留膜会让万用表读数虚高（量之前酒精擦焊点）；电阻档测量必须断电

## 用户情况
- 在德国（斯图加特），元件买 TME/Mouser.de（FH12-28S-0.5SH(55) 是 FPC 座的 Hirose 替代，封装兼容、注意下接）或 AliExpress
- 有加热台（定温式）+钢网+锡膏，会基础贴片；养鹦鹉,焊接在阳台进行（鸟类对焊烟敏感,需隔离）
- 锂电池还没买（买带保护板的 3.7V 软包 + PH2.0 插头）

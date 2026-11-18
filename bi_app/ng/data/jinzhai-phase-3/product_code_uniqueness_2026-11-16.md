# 参数宽表 product_code 唯一性核查

工厂：jinzhai-phase-3；生成时间：2026-11-16T16:14:30.879231+08:00。

范围：35 张参数表的全历史记录，不限定日期、产线、工序编码或产品集合，不抽样。排除 NULL/空产品码后分别检查 product_code 和 (tenant_id, product_code)。

成功 35 张；同一租户内有重复 33 张；同一租户内未见重复 2 张；失败 0 张。

重复键数指同一租户内记录数大于 1 的产品数；多出行数为每个租户/产品保留一行后多出的记录数。

| 表中文描述 | 表名 | 总记录数 | 同租户重复产品数 | 多出行数 | 单产品最多记录数 | 跨租户同码数 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 分容参数宽表 | `dwd_qual_grading_param_pim` | 35,984,537 | 1,695,487 | 34,289,040 | 1,271 | 0 |
| 化成参数宽表 | `dwd_qual_formation_param_pim` | 19,946,974 | 1,776,473 | 18,169,252 | 322 | 0 |
| 切卷参数宽表 | `dwd_qual_winding_slit_param_pim` | 4,795,957 | 398,861 | 411,386 | 12,082 | 0 |
| 超声焊接生产参数宽表 | `dwd_qual_ultrasonic_weld_param_pim` | 2,169,293 | 274,346 | 371,384 | 143 | 0 |
| 包膜入壳参数宽表 | `dwd_qual_wrap_can_insert_param_pim` | 2,069,131 | 176,483 | 210,908 | 1,818 | 0 |
| 一次氦检参数宽表 | `dwd_qual_helium_leak_test1_param_pim` | 1,974,039 | 144,329 | 146,680 | 129 | 0 |
| 连接片激光焊参数宽表 | `dwd_qual_connector_laser_weld_param_pim` | 1,972,017 | 108,789 | 108,817 | 12 | 0 |
| 高温静置3参数宽表 | `dwd_qual_high_temp_rest3_param_pim` | 1,751,218 | 80,992 | 94,942 | 76 | 0 |
| 常温静置3参数宽表 | `dwd_qual_ambient_rest3_param_pim` | 1,675,211 | 86,401 | 90,830 | 7 | 0 |
| 一次注液参数宽表 | `dwd_qual_electrolyte_fill1_param_pim` | 1,868,959 | 72,061 | 80,612 | 18 | 0 |
| 顶盖激光焊参数宽表 | `dwd_qual_top_cover_laser_weld_param_pim` | 1,849,695 | 69,301 | 78,879 | 71 | 0 |
| OCV3参数宽表 | `dwd_qual_ocv3_param_pim` | 1,716,086 | 58,543 | 72,911 | 145 | 0 |
| 常温静置2参数宽表 | `dwd_qual_ambient_rest2_param_pim` | 1,708,805 | 55,347 | 68,468 | 10 | 0 |
| OCV4参数宽表 | `dwd_qual_ocv4_param_pim` | 1,639,929 | 45,813 | 54,109 | 167 | 0 |
| 二次注液参数宽表 | `dwd_qual_electrolyte_fill2_param_pim` | 1,852,367 | 44,134 | 45,537 | 11 | 0 |
| 三次注液参数宽表 | `dwd_qual_electrolyte_fill3_param_pim` | 1,650,621 | 33,939 | 35,421 | 12 | 0 |
| DCR参数宽表 | `dwd_qual_dcr_param_pim` | 1,542,153 | 27,741 | 29,758 | 20 | 0 |
| 极耳翻折检测参数宽表 | `dwd_qual_tab_fold_insp_param_pim` | 4,258,996 | 23,995 | 28,551 | 1,686 | 0 |
| 密封钉参数宽表 | `dwd_qual_seal_nail_param_pim` | 1,751,781 | 15,266 | 24,386 | 3,567 | 0 |
| 包胶参数宽表 | `dwd_qual_tape_wrap_param_pim` | 1,548,808 | 18,627 | 21,170 | 298 | 0 |
| 高温静置2参数宽表 | `dwd_qual_high_temp_rest2_param_pim` | 1,781,823 | 2,029 | 8,317 | 150 | 0 |
| AIQG智能排废内阻补偿参数表 | `dwd_qual_scrap_inter_resis_comp_param_pim` | 353,689 | 7,118 | 7,681 | 4 | 0 |
| x-ray参数宽表 | `dwd_qual_xray_param_pim` | 4,224,773 | 4,989 | 7,444 | 1,938 | 0 |
| 二次氦检参数宽表 | `dwd_qual_helium_leak_test2_param_pim` | 1,713,938 | 1,317 | 2,219 | 494 | 0 |
| 烘烤参数宽表 | `dwd_qual_bake_param_pim` | 1,742,235 | 1,352 | 1,355 | 3 | 0 |
| 高温老化参数宽表 | `dwd_qual_high_temp_aging_param_pim` | 1,712,214 | 979 | 979 | 2 | 0 |
| 负极涂布参数宽表 | `dwd_qual_neg_coating_param_pim` | 3,939 | 346 | 346 | 2 | 0 |
| 常温静置1参数宽表 | `dwd_qual_ambient_rest1_param_pim` | 1,687,103 | 340 | 340 | 2 | 0 |
| 正极涂布参数宽表 | `dwd_qual_pos_coating_param_pim` | 3,206 | 289 | 289 | 2 | 0 |
| 高温静置1参数宽表 | `dwd_qual_high_temp_rest1_param_pim` | 230,760 | 274 | 274 | 2 | 0 |
| 正极合浆瓷参数宽表 | `dwd_qual_pos_mixing_param_pim` | 2,165 | 269 | 269 | 2 | 0 |
| 负极合浆参数宽表 | `dwd_qual_neg_mixing_param_pim` | 1,616 | 140 | 140 | 2 | 0 |
| 正极合陶瓷参数宽表 | `dwd_qual_pos_ceramic_mixing_param_pim` | 365 | 16 | 16 | 2 | 0 |
| 负极辊分生产参数宽表 | `dwd_qual_neg_roll_slit_param_pim` | 3,235 | 0 | 0 | 1 | 0 |
| 正极辊分生产参数宽表 | `dwd_qual_pos_roll_slit_param_pim` | 2,706 | 0 | 0 | 1 | 0 |

## 重复记录抽查

以下样本仅解释重复记录形态，不代表所有重复均由相同原因导致。

### 常温静置1参数宽表（dwd_qual_ambient_rest1_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `03HCB0440000DWG980200217`：2 行。produce_id不同值数=2；start_time不同值数=2；end_time不同值数=2；shift_date不同值数=2；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-10-12 02:43:41 至 2026-11-01 15:19:56。
- 租户 `11300001`，产品 `03HCB0490000BWG550100015`：2 行。produce_id不同值数=2；start_time不同值数=2；end_time不同值数=2；shift_date不同值数=2；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-07 02:40:19 至 2026-06-16 19:13:32。
- 租户 `11300001`，产品 `03HCB0490000BWG550100059`：2 行。produce_id不同值数=2；start_time不同值数=2；end_time不同值数=2；shift_date不同值数=2；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-08 23:42:52 至 2026-06-27 16:49:19。

### 常温静置2参数宽表（dwd_qual_ambient_rest2_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `03HCB0490000CWG830100164`：10 行。produce_id不同值数=10；start_time不同值数=10；end_time不同值数=10；shift_date不同值数=10；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-08-18 14:32:06 至 2026-10-25 03:17:41。
- 租户 `11300001`，产品 `03HCB0490000CWG830100479`：10 行。produce_id不同值数=10；start_time不同值数=10；end_time不同值数=10；shift_date不同值数=10；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-08-17 01:41:21 至 2026-10-24 15:42:22。
- 租户 `11300001`，产品 `03HCB0490000CWG890142053`：10 行。produce_id不同值数=10；start_time不同值数=10；end_time不同值数=10；shift_date不同值数=10；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-09-11 03:54:06 至 2026-11-15 16:49:57。

### 常温静置3参数宽表（dwd_qual_ambient_rest3_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `03HCB0490000CWG840104699`：7 行。produce_id不同值数=7；start_time不同值数=7；end_time不同值数=7；shift_date不同值数=7；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-08-25 20:49:52 至 2026-10-11 16:20:48。
- 租户 `11300001`，产品 `03HCB0490000CWG840126396`：7 行。produce_id不同值数=7；start_time不同值数=7；end_time不同值数=7；shift_date不同值数=7；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-08-27 13:05:30 至 2026-10-11 06:21:43。
- 租户 `11300001`，产品 `03HCB0490000CWG880102415`：7 行。produce_id不同值数=7；start_time不同值数=7；end_time不同值数=7；shift_date不同值数=7；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-09-07 10:58:00 至 2026-10-28 12:03:24。

### 烘烤参数宽表（dwd_qual_bake_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `03HCB0440000DWG6L0200480`：3 行。produce_id不同值数=3；start_time不同值数=3；end_time不同值数=3；shift_date不同值数=3；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=3；product_quality不同值数=1；ng_type不同值数=0。时间范围：2026-07-02 03:14:06 至 2026-07-10 04:58:11。
- 租户 `11300001`，产品 `03HCB0490000BWG5A0101157`：3 行。produce_id不同值数=3；start_time不同值数=3；end_time不同值数=3；shift_date不同值数=3；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=3；product_quality不同值数=1；ng_type不同值数=0。时间范围：2026-05-23 00:30:12 至 2026-05-24 11:17:22。
- 租户 `11300001`，产品 `03HCB0490000BWG5A0101174`：3 行。produce_id不同值数=3；start_time不同值数=3；end_time不同值数=3；shift_date不同值数=3；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=3；product_quality不同值数=1；ng_type不同值数=0。时间范围：2026-05-24 00:48:15 至 2026-05-26 07:39:19。

### 连接片激光焊参数宽表（dwd_qual_connector_laser_weld_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `202605190107A07422`：12 行。produce_id不同值数=8；start_time不同值数=1；end_time不同值数=8；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-05-29 19:43:32 至 2026-05-29 19:58:33。
- 租户 `11300001`，产品 `5040129396 620433 G5J 8007386`：11 行。produce_id不同值数=6；start_time不同值数=1；end_time不同值数=6；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-05-29 18:00:12 至 2026-05-29 19:39:57。
- 租户 `11300001`，产品 `202605130307A02909`：4 行。produce_id不同值数=2；start_time不同值数=2；end_time不同值数=2；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-05-20 04:50:25 至 2026-05-20 05:45:35。

### DCR参数宽表（dwd_qual_dcr_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `GXGK009`：20 行。produce_id不同值数=20；start_time不同值数=20；end_time不同值数=20；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=2。时间范围：2026-06-17 11:42:34 至 2026-06-17 18:30:29。
- 租户 `11300001`，产品 `GXGK023`：12 行。produce_id不同值数=12；start_time不同值数=12；end_time不同值数=12；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=2。时间范围：2026-06-17 11:42:34 至 2026-06-17 18:17:32。
- 租户 `11300001`，产品 `03HCB0490000BWG5J0101255`：10 行。produce_id不同值数=10；start_time不同值数=10；end_time不同值数=10；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=2。时间范围：2026-06-17 11:42:34 至 2026-06-17 14:02:28。

### 一次注液参数宽表（dwd_qual_electrolyte_fill1_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `03HCB0440000DWG9G0203096`：18 行。produce_id不同值数=18；start_time不同值数=18；end_time不同值数=18；shift_date不同值数=11；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-09-19 07:28:45 至 2026-09-28 09:40:03。
- 租户 `11300001`，产品 `03HCB0440000DWG960200769`：11 行。produce_id不同值数=11；start_time不同值数=1；end_time不同值数=11；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=2。时间范围：2026-09-15 10:43:45 至 2026-09-15 13:43:25。
- 租户 `11300001`，产品 `03HCB0440000DWG960200797`：11 行。produce_id不同值数=11；start_time不同值数=1；end_time不同值数=11；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=2。时间范围：2026-09-15 10:43:59 至 2026-09-15 13:43:25。

### 二次注液参数宽表（dwd_qual_electrolyte_fill2_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `03HCB0440000BWG520200246`：11 行。produce_id不同值数=11；start_time不同值数=2；end_time不同值数=11；shift_date不同值数=2；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=2。时间范围：2026-06-11 16:43:21 至 2026-06-12 22:34:07。
- 租户 `11300001`，产品 `03HCB0440000DWG720200265`：10 行。produce_id不同值数=8；start_time不同值数=8；end_time不同值数=8；shift_date不同值数=5；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-07-18 06:47:54 至 2026-08-28 10:17:02。
- 租户 `11300001`，产品 `03HCB0440000DWG6L0200451`：8 行。produce_id不同值数=8；start_time不同值数=8；end_time不同值数=8；shift_date不同值数=7；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=2；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=3。时间范围：2026-07-01 09:58:25 至 2026-08-28 10:17:03。

### 三次注液参数宽表（dwd_qual_electrolyte_fill3_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `03HCB0490000BWG5S0100111`：12 行。produce_id不同值数=12；start_time不同值数=10；end_time不同值数=12；shift_date不同值数=7；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-14 02:21:23 至 2026-06-24 15:43:45。
- 租户 `11300001`，产品 `03HCB0490000CWGA60189664`：11 行。produce_id不同值数=11；start_time不同值数=11；end_time不同值数=11；shift_date不同值数=6；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=2。时间范围：2026-11-03 04:24:59 至 2026-11-10 09:20:31。
- 租户 `11300001`，产品 `03HCB0440000DWG9B0200355`：9 行。produce_id不同值数=9；start_time不同值数=9；end_time不同值数=9；shift_date不同值数=9；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=3。时间范围：2026-10-13 14:21:07 至 2026-11-14 09:18:24。

### 化成参数宽表（dwd_qual_formation_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`, `technics_step_code`)`

- 租户 `11300001`，产品 `000000000000000000000000`：322 行。produce_id不同值数=322；product_in_code不同值数=1；device_code不同值数=27；start_time不同值数=27；end_time不同值数=27；shift_date不同值数=17；technics_step_code不同值数=17；technics_step_name不同值数=4；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=27；product_quality不同值数=2；ng_type不同值数=2。时间范围：2026-05-30 15:27:51 至 2026-08-09 04:14:10。
- 租户 `11300001`，产品 `111111111111111111111111`：73 行。produce_id不同值数=73；product_in_code不同值数=1；device_code不同值数=5；start_time不同值数=5；end_time不同值数=5；shift_date不同值数=4；technics_step_code不同值数=17；technics_step_name不同值数=3；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=5；product_quality不同值数=2；ng_type不同值数=2。时间范围：2026-06-22 17:30:37 至 2026-07-08 09:19:43。
- 租户 `11300001`，产品 `03HCB0490000CWG950126723`：59 行。produce_id不同值数=59；product_in_code不同值数=1；device_code不同值数=4；start_time不同值数=5；end_time不同值数=5；shift_date不同值数=2；technics_step_code不同值数=13；technics_step_name不同值数=4；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=4；product_quality不同值数=2；ng_type不同值数=2。时间范围：2026-10-13 01:24:54 至 2026-10-13 22:53:10。

### 分容参数宽表（dwd_qual_grading_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`, `technics_step_code`)`

- 租户 `11300001`，产品 `111111111111111111111111`：1,271 行。produce_id不同值数=1271；product_in_code不同值数=1；device_code不同值数=52；start_time不同值数=67；end_time不同值数=67；shift_date不同值数=28；technics_step_code不同值数=19；technics_step_name不同值数=7；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=51；product_quality不同值数=2；ng_type不同值数=2。时间范围：2026-06-04 02:26:06 至 2026-08-17 21:41:19。
- 租户 `11300001`，产品 `03HCB0490000BWG5D0100413`：855 行。produce_id不同值数=855；product_in_code不同值数=1；device_code不同值数=35；start_time不同值数=45；end_time不同值数=45；shift_date不同值数=19；technics_step_code不同值数=19；technics_step_name不同值数=7；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=35；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-03 18:57:31 至 2026-06-29 08:11:04。
- 租户 `11300001`，产品 `03HCB0490000BWG5F0202111`：817 行。produce_id不同值数=817；product_in_code不同值数=1；device_code不同值数=34；start_time不同值数=43；end_time不同值数=43；shift_date不同值数=17；technics_step_code不同值数=19；technics_step_name不同值数=7；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=34；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-09 08:47:55 至 2026-06-29 03:48:35。

### 一次氦检参数宽表（dwd_qual_helium_leak_test1_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `5040129396 620433 G67 8004357`：129 行。produce_id不同值数=119；start_time不同值数=119；end_time不同值数=119；shift_date不同值数=94；technics_step_code不同值数=2；technics_step_name不同值数=2；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=4。时间范围：2026-07-13 20:33:56 至 2026-11-15 20:23:01。
- 租户 `11300001`，产品 `5040103700 620347 G77 2001242`：72 行。produce_id不同值数=72；start_time不同值数=72；end_time不同值数=72；shift_date不同值数=46；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=3。时间范围：2026-08-25 20:24:27 至 2026-11-16 09:53:19。
- 租户 `11300001`，产品 `5040129396 620433 G9H 8002422`：63 行。produce_id不同值数=63；start_time不同值数=63；end_time不同值数=63；shift_date不同值数=46；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=4。时间范围：2026-09-23 08:19:36 至 2026-11-16 13:19:16。

### 二次氦检参数宽表（dwd_qual_helium_leak_test2_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `ERROR`：494 行。produce_id不同值数=494；start_time不同值数=426；end_time不同值数=494；shift_date不同值数=94；technics_step_code不同值数=2；technics_step_name不同值数=2；technics_process_code不同值数=1；technics_line_name不同值数=2；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=2。时间范围：2026-06-05 14:44:34 至 2026-11-16 13:51:14。
- 租户 `11300001`，产品 `12345`：219 行。produce_id不同值数=219；start_time不同值数=209；end_time不同值数=219；shift_date不同值数=3；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-08 20:56:50 至 2026-06-21 07:54:09。
- 租户 `11300001`，产品 `03HCB0490000CWG770108251`：23 行。produce_id不同值数=23；start_time不同值数=23；end_time不同值数=23；shift_date不同值数=12；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=3。时间范围：2026-08-04 13:29:37 至 2026-08-18 20:44:47。

### 高温老化参数宽表（dwd_qual_high_temp_aging_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `03HCB0440000DWG640200189`：2 行。produce_id不同值数=2；start_time不同值数=2；end_time不同值数=2；shift_date不同值数=2；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-07-08 04:29:38 至 2026-07-08 09:18:07。
- 租户 `11300001`，产品 `03HCB0440000DWG640200194`：2 行。produce_id不同值数=2；start_time不同值数=2；end_time不同值数=2；shift_date不同值数=2；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-07-08 04:29:38 至 2026-07-08 09:18:07。
- 租户 `11300001`，产品 `03HCB0440000DWG640200204`：2 行。produce_id不同值数=2；start_time不同值数=2；end_time不同值数=2；shift_date不同值数=2；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-07-08 04:29:38 至 2026-07-08 09:18:07。

### 高温静置1参数宽表（dwd_qual_high_temp_rest1_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `03HCB0440000DWG6N0200540`：2 行。produce_id不同值数=2；start_time不同值数=2；end_time不同值数=2；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-07-04 11:07:14 至 2026-07-04 23:19:50。
- 租户 `11300001`，产品 `03HCB0440000DWG6N0200541`：2 行。produce_id不同值数=2；start_time不同值数=2；end_time不同值数=2；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-07-04 11:07:14 至 2026-07-04 23:19:50。
- 租户 `11300001`，产品 `03HCB0440000DWG6N0200542`：2 行。produce_id不同值数=2；start_time不同值数=2；end_time不同值数=2；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-07-04 11:07:14 至 2026-07-04 23:19:50。

### 高温静置2参数宽表（dwd_qual_high_temp_rest2_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `03HCB0490000CWG720119184`：150 行。produce_id不同值数=150；start_time不同值数=150；end_time不同值数=150；shift_date不同值数=2；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-07-19 03:55:49 至 2026-07-19 23:56:53。
- 租户 `11300001`，产品 `03HCB0490000CWG720119186`：150 行。produce_id不同值数=150；start_time不同值数=150；end_time不同值数=150；shift_date不同值数=2；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-07-19 03:55:49 至 2026-07-19 23:56:53。
- 租户 `11300001`，产品 `03HCB0490000CWG720119187`：150 行。produce_id不同值数=150；start_time不同值数=150；end_time不同值数=150；shift_date不同值数=2；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-07-19 03:55:49 至 2026-07-19 23:56:53。

### 高温静置3参数宽表（dwd_qual_high_temp_rest3_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `12345`：76 行。produce_id不同值数=76；start_time不同值数=56；end_time不同值数=76；shift_date不同值数=5；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=11。时间范围：2026-05-16 01:35:44 至 2026-05-19 10:38:02。
- 租户 `11300001`，产品 `03HCB0490000CWG830100164`：10 行。produce_id不同值数=10；start_time不同值数=10；end_time不同值数=10；shift_date不同值数=10；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-08-17 14:25:13 至 2026-10-23 04:15:39。
- 租户 `11300001`，产品 `03HCB0490000CWG830100479`：10 行。produce_id不同值数=10；start_time不同值数=10；end_time不同值数=10；shift_date不同值数=10；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-08-16 01:33:11 至 2026-10-23 04:05:08。

### 负极涂布参数宽表（dwd_qual_neg_coating_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `DWN2CWG6H0127`：2 行。produce_id不同值数=1；start_time不同值数=1；end_time不同值数=1；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=0；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-20 14:35:13 至 2026-06-20 14:35:13。
- 租户 `11300001`，产品 `DWN2CWG6H0128`：2 行。produce_id不同值数=1；start_time不同值数=1；end_time不同值数=1；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=0；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-20 15:38:24 至 2026-06-20 15:38:24。
- 租户 `11300001`，产品 `DWN2CWG6H0130`：2 行。produce_id不同值数=1；start_time不同值数=1；end_time不同值数=1；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=0；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-21 02:40:14 至 2026-06-21 02:40:14。

### 负极合浆参数宽表（dwd_qual_neg_mixing_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `DWN1CWG6J00105`：2 行。produce_id不同值数=1；product_in_code不同值数=2；device_code不同值数=1；start_time不同值数=1；end_time不同值数=1；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=0；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-20 03:50:46 至 2026-06-20 03:50:46。
- 租户 `11300001`，产品 `DWN1CWG6J00108`：2 行。produce_id不同值数=1；product_in_code不同值数=2；device_code不同值数=1；start_time不同值数=1；end_time不同值数=1；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=0；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-20 17:17:27 至 2026-06-20 17:17:27。
- 租户 `11300001`，产品 `DWN1CWG6K00103`：2 行。produce_id不同值数=1；product_in_code不同值数=2；device_code不同值数=1；start_time不同值数=1；end_time不同值数=1；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=0；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-21 17:27:29 至 2026-06-21 17:27:29。

### OCV3参数宽表（dwd_qual_ocv3_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `000000000000000000000000`：145 行。produce_id不同值数=145；product_in_code不同值数=1；device_code不同值数=1；start_time不同值数=145；end_time不同值数=145；shift_date不同值数=3；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=4。时间范围：2026-06-18 19:25:43 至 2026-06-20 12:47:44。
- 租户 `11300001`，产品 `03HCB0490000CWG830100164`：10 行。produce_id不同值数=10；product_in_code不同值数=1；device_code不同值数=1；start_time不同值数=10；end_time不同值数=10；shift_date不同值数=10；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=3。时间范围：2026-08-18 14:36:33 至 2026-10-25 04:33:33。
- 租户 `11300001`，产品 `03HCB0490000CWG830100479`：10 行。produce_id不同值数=10；product_in_code不同值数=1；device_code不同值数=1；start_time不同值数=10；end_time不同值数=10；shift_date不同值数=10；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=2。时间范围：2026-08-17 01:43:24 至 2026-10-24 18:20:21。

### OCV4参数宽表（dwd_qual_ocv4_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `000000000000000000000000`：167 行。produce_id不同值数=167；start_time不同值数=167；end_time不同值数=167；shift_date不同值数=5；technics_step_code不同值数=1；technics_step_name不同值数=2；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=2；product_quality不同值数=2；ng_type不同值数=2。时间范围：2026-06-04 08:50:08 至 2026-06-20 11:27:11。
- 租户 `11300001`，产品 `03HCB0490000BWG470102243`：13 行。produce_id不同值数=13；start_time不同值数=13；end_time不同值数=13；shift_date不同值数=2；technics_step_code不同值数=1；technics_step_name不同值数=2；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=2。时间范围：2026-06-04 09:05:30 至 2026-06-05 14:20:42。
- 租户 `11300001`，产品 `03HCB0490000BWG470102257`：13 行。produce_id不同值数=13；start_time不同值数=13；end_time不同值数=13；shift_date不同值数=2；technics_step_code不同值数=1；technics_step_name不同值数=2；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=2。时间范围：2026-06-04 09:05:30 至 2026-06-05 14:20:42。

### 正极合陶瓷参数宽表（dwd_qual_pos_ceramic_mixing_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `DWC1CWG6L00301`：2 行。produce_id不同值数=1；start_time不同值数=1；end_time不同值数=1；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=0；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-26 23:46:53 至 2026-06-26 23:46:53。
- 租户 `11300001`，产品 `DWC1DWG6L00301`：2 行。produce_id不同值数=1；start_time不同值数=1；end_time不同值数=1；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=0；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-23 01:57:29 至 2026-06-23 01:57:29。
- 租户 `11300001`，产品 `DWC1DWG6M00301`：2 行。produce_id不同值数=1；start_time不同值数=1；end_time不同值数=1；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=0；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-24 02:15:41 至 2026-06-24 02:15:41。

### 正极涂布参数宽表（dwd_qual_pos_coating_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `DWP2CWG6H0116`：2 行。produce_id不同值数=1；start_time不同值数=1；end_time不同值数=1；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=0；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-20 16:15:35 至 2026-06-20 16:15:35。
- 租户 `11300001`，产品 `DWP2CWG6H0117`：2 行。produce_id不同值数=1；start_time不同值数=1；end_time不同值数=1；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=0；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-20 18:46:05 至 2026-06-20 18:46:05。
- 租户 `11300001`，产品 `DWP2CWG6H0119`：2 行。produce_id不同值数=1；start_time不同值数=1；end_time不同值数=1；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=0；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-20 22:09:31 至 2026-06-20 22:09:31。

### 正极合浆瓷参数宽表（dwd_qual_pos_mixing_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `DWP1CWG6K00105`：2 行。produce_id不同值数=1；product_in_code不同值数=2；device_code不同值数=1；start_time不同值数=1；end_time不同值数=1；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=0；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-21 11:57:44 至 2026-06-21 11:57:44。
- 租户 `11300001`，产品 `DWP1CWG6K00106`：2 行。produce_id不同值数=1；product_in_code不同值数=2；device_code不同值数=1；start_time不同值数=1；end_time不同值数=1；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=0；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-21 13:33:12 至 2026-06-21 13:33:12。
- 租户 `11300001`，产品 `DWP1CWG6K00108`：2 行。produce_id不同值数=1；product_in_code不同值数=2；device_code不同值数=1；start_time不同值数=1；end_time不同值数=1；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=0；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-21 17:54:23 至 2026-06-21 17:54:23。

### AIQG智能排废内阻补偿参数表（dwd_qual_scrap_inter_resis_comp_param_pim）

DDL 键定义：`PRIMARY KEY(`product_code`, `end_time`)`

- 租户 `11300001`，产品 `03HCB0490000CWG920134800`：4 行。start_time不同值数=4；end_time不同值数=4。时间范围：2026-10-26 16:42:56 至 2026-11-15 17:22:34。
- 租户 `11300001`，产品 `03HCB0490000CWG990116458`：4 行。start_time不同值数=4；end_time不同值数=4。时间范围：2026-10-26 13:07:02 至 2026-11-15 17:22:34。
- 租户 `11300001`，产品 `03HCB0490000CWGA10100276`：4 行。start_time不同值数=4；end_time不同值数=4。时间范围：2026-11-04 14:53:11 至 2026-11-15 19:10:30。

### 密封钉参数宽表（dwd_qual_seal_nail_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `OK`：3,567 行。produce_id不同值数=3567；start_time不同值数=3429；end_time不同值数=3567；shift_date不同值数=29；technics_step_code不同值数=2；technics_step_name不同值数=2；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=3。时间范围：2026-06-12 10:03:10 至 2026-10-04 10:31:54。
- 租户 `11300001`，产品 `ERROR`：889 行。produce_id不同值数=889；start_time不同值数=885；end_time不同值数=889；shift_date不同值数=155；technics_step_code不同值数=2；technics_step_name不同值数=2；technics_process_code不同值数=1；technics_line_name不同值数=2；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=2。时间范围：2026-05-18 17:08:13 至 2026-11-16 11:53:51。
- 租户 `11300001`，产品 `D123456789`：405 行。produce_id不同值数=405；start_time不同值数=405；end_time不同值数=405；shift_date不同值数=38；technics_step_code不同值数=2；technics_step_name不同值数=2；technics_process_code不同值数=1；technics_line_name不同值数=2；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=10。时间范围：2026-05-16 09:29:44 至 2026-11-01 14:19:21。

### 极耳翻折检测参数宽表（dwd_qual_tab_fold_insp_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `ERROR`：1,686 行。produce_id不同值数=1686；start_time不同值数=1686；end_time不同值数=1686；shift_date不同值数=151；technics_step_code不同值数=2；technics_step_name不同值数=2；technics_process_code不同值数=1；technics_line_name不同值数=2；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=29。时间范围：2026-05-15 11:36:44 至 2026-11-16 00:03:33。
- 租户 `11300001`，产品 `ScannerDisable`：256 行。produce_id不同值数=256；start_time不同值数=251；end_time不同值数=256；shift_date不同值数=7；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=5。时间范围：2026-05-15 12:11:11 至 2026-06-11 16:41:14。
- 租户 `11300001`，产品 `202606100204B05109`：63 行。produce_id不同值数=63；start_time不同值数=63；end_time不同值数=63；shift_date不同值数=46；technics_step_code不同值数=2；technics_step_name不同值数=2；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=19。时间范围：2026-06-16 16:04:06 至 2026-11-16 10:11:24。

### 包胶参数宽表（dwd_qual_tape_wrap_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `03HCB0440000BWG650200038`：298 行。produce_id不同值数=298；start_time不同值数=3；end_time不同值数=298；shift_date不同值数=3；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=3。时间范围：2026-07-07 17:19:54 至 2026-07-13 16:23:11。
- 租户 `11300001`，产品 `03HCB0440000BWG650200041`：96 行。produce_id不同值数=96；start_time不同值数=60；end_time不同值数=96；shift_date不同值数=6；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=3。时间范围：2026-07-07 17:14:35 至 2026-07-13 17:09:28。
- 租户 `11300001`，产品 `03HCB0490000BWG5D0200059`：75 行。produce_id不同值数=75；start_time不同值数=1；end_time不同值数=75；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-18 09:58:46 至 2026-06-18 10:08:28。

### 顶盖激光焊参数宽表（dwd_qual_top_cover_laser_weld_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `ScanNG`：71 行。produce_id不同值数=71；start_time不同值数=71；end_time不同值数=71；shift_date不同值数=25；technics_step_code不同值数=2；technics_step_name不同值数=2；technics_process_code不同值数=1；technics_line_name不同值数=2；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=2。时间范围：2026-06-06 22:49:52 至 2026-11-15 01:51:05。
- 租户 `11300001`，产品 `ERROR`：34 行。produce_id不同值数=34；start_time不同值数=34；end_time不同值数=34；shift_date不同值数=18；technics_step_code不同值数=2；technics_step_name不同值数=2；technics_process_code不同值数=1；technics_line_name不同值数=2；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=3。时间范围：2026-06-17 03:25:39 至 2026-11-13 19:34:57。
- 租户 `11300001`，产品 `5040129396 620433 G9P 8003110`：24 行。produce_id不同值数=24；start_time不同值数=24；end_time不同值数=24；shift_date不同值数=13；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=2。时间范围：2026-09-28 17:07:01 至 2026-10-16 11:30:15。

### 超声焊接生产参数宽表（dwd_qual_ultrasonic_weld_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `OK`：143 行。produce_id不同值数=56；start_time不同值数=56；end_time不同值数=56；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-05-13 14:01:27 至 2026-05-13 14:20:04。
- 租户 `11300001`，产品 `11111`：28 行。produce_id不同值数=18；start_time不同值数=18；end_time不同值数=18；shift_date不同值数=2；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=2；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=2。时间范围：2026-06-12 16:28:04 至 2026-06-20 21:36:03。
- 租户 `11300001`，产品 `202605090303A05457`：18 行。produce_id不同值数=7；start_time不同值数=7；end_time不同值数=7；shift_date不同值数=3；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=2。时间范围：2026-05-25 08:34:05 至 2026-05-29 15:54:53。

### 切卷参数宽表（dwd_qual_winding_slit_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `Error`：12,082 行。produce_id不同值数=10441；start_time不同值数=10404；end_time不同值数=10408；shift_date不同值数=184；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=2；device_name不同值数=28；product_quality不同值数=2；ng_type不同值数=570。时间范围：2026-05-07 16:09:08 至 2026-11-16 15:15:58。
- 租户 `11300001`，产品 `202608200612B`：20 行。produce_id不同值数=20；start_time不同值数=20；end_time不同值数=20；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-08-22 07:48:09 至 2026-08-22 07:52:54。
- 租户 `11300001`，产品 `2026042906A39SO5`：9 行。produce_id不同值数=5；start_time不同值数=4；end_time不同值数=4；shift_date不同值数=3；technics_step_code不同值数=1；technics_step_name不同值数=2；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=2；product_quality不同值数=1；ng_type不同值数=0。时间范围：2026-04-14 15:19:36 至 2026-05-02 14:53:30。

### 包膜入壳参数宽表（dwd_qual_wrap_can_insert_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `ERROR`：1,818 行。produce_id不同值数=1225；start_time不同值数=902；end_time不同值数=859；shift_date不同值数=72；technics_step_code不同值数=2；technics_step_name不同值数=2；technics_process_code不同值数=1；technics_line_name不同值数=2；device_name不同值数=1；product_quality不同值数=3；ng_type不同值数=20。时间范围：2026-05-14 11:25:12 至 2026-10-30 04:29:41。
- 租户 `11300001`，产品 `strCoder_Single`：117 行。produce_id不同值数=79；start_time不同值数=79；end_time不同值数=46；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=0；device_name不同值数=1；product_quality不同值数=2；ng_type不同值数=5。时间范围：2026-05-13 12:02:48 至 2026-05-13 12:51:30。
- 租户 `11300001`，产品 `ER,LON,23`：21 行。produce_id不同值数=21；start_time不同值数=21；end_time不同值数=21；shift_date不同值数=3；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-13 12:02:04 至 2026-07-03 13:36:12。

### x-ray参数宽表（dwd_qual_xray_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`

- 租户 `11300001`，产品 `ERROR`：1,938 行。produce_id不同值数=1938；start_time不同值数=1929；end_time不同值数=1937；shift_date不同值数=150；technics_step_code不同值数=2；technics_step_name不同值数=2；technics_process_code不同值数=1；technics_line_name不同值数=2；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=11。时间范围：2026-05-14 15:18:31 至 2026-11-13 21:50:55。
- 租户 `11300001`，产品 `202605160206B13180`：32 行。produce_id不同值数=32；start_time不同值数=1；end_time不同值数=32；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-09 14:13:36 至 2026-06-09 14:14:44。
- 租户 `11300001`，产品 `202605160206B13181`：32 行。produce_id不同值数=32；start_time不同值数=1；end_time不同值数=32；shift_date不同值数=1；technics_step_code不同值数=1；technics_step_name不同值数=1；technics_process_code不同值数=1；technics_line_name不同值数=1；device_name不同值数=1；product_quality不同值数=1；ng_type不同值数=1。时间范围：2026-06-09 14:13:36 至 2026-06-09 14:14:45。

### 负极辊分生产参数宽表（dwd_qual_neg_roll_slit_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`


### 正极辊分生产参数宽表（dwd_qual_pos_roll_slit_param_pim）

DDL 键定义：`UNIQUE KEY(`tenant_id`, `product_code`, `product_in_code`, `device_code`, `end_time`)`



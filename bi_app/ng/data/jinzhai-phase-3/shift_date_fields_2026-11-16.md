# 参数宽表 shift_date 字段核查

工厂：jinzhai-phase-3；核查时间：2026-11-16T19:37:23.864005+08:00。

共35张表，34张有shift_date字段。日期筛选使用shift_date；最新记录排序继续读取字典中的end_time；默认并发8路。

| 表名 | 中文描述 | shift_date存在 | 类型 | 注释 |
| --- | --- | --- | --- | --- |
| `dwd_qual_ambient_rest1_param_pim` | 常温静置1参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_ambient_rest2_param_pim` | 常温静置2参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_ambient_rest3_param_pim` | 常温静置3参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_bake_param_pim` | 烘烤参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_connector_laser_weld_param_pim` | 连接片激光焊参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_dcr_param_pim` | DCR参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_electrolyte_fill1_param_pim` | 一次注液参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_electrolyte_fill2_param_pim` | 二次注液参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_electrolyte_fill3_param_pim` | 三次注液参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_formation_param_pim` | 化成参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_grading_param_pim` | 分容参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_helium_leak_test1_param_pim` | 一次氦检参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_helium_leak_test2_param_pim` | 二次氦检参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_high_temp_aging_param_pim` | 高温老化参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_high_temp_rest1_param_pim` | 高温静置1参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_high_temp_rest2_param_pim` | 高温静置2参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_high_temp_rest3_param_pim` | 高温静置3参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_neg_coating_param_pim` | 负极涂布参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_neg_mixing_param_pim` | 负极合浆参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_neg_roll_slit_param_pim` | 负极辊分生产参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_ocv3_param_pim` | OCV3参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_ocv4_param_pim` | OCV4参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_pos_ceramic_mixing_param_pim` | 正极合陶瓷参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_pos_coating_param_pim` | 正极涂布参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_pos_mixing_param_pim` | 正极合浆瓷参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_pos_roll_slit_param_pim` | 正极辊分生产参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_scrap_inter_resis_comp_param_pim` | AIQG智能排废内阻补偿参数表 | 无 | — | — |
| `dwd_qual_seal_nail_param_pim` | 密封钉参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_tab_fold_insp_param_pim` | 极耳翻折检测参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_tape_wrap_param_pim` | 包胶参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_top_cover_laser_weld_param_pim` | 顶盖激光焊参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_ultrasonic_weld_param_pim` | 超声焊接生产参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_winding_slit_param_pim` | 切卷参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_wrap_can_insert_param_pim` | 包膜入壳参数宽表 | 有 | date | 班次日期 |
| `dwd_qual_xray_param_pim` | x-ray参数宽表 | 有 | date | 班次日期 |

## 实际取数核对

OCV3 / 金寨三期314Ah / 2026-11-15：按shift_date读取14,527个产品，分组为{'OK': 14291, 'excluded': 101, 'NG': 135}。最新记录按end_time排序。

另以400个产品、每批100个请求的诊断设置验证线程池，实测最大同时查询数8，完成8条SQL，用时1.1866秒。实际应用批大小仍为2000，诊断设置未写入.env。

分容样本选中工步：{'999': 400}；化成样本选中工步：{'11': 390, '13': 10}。

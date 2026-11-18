# 工序生效映射核验（2026-11-18）

已核对 33 个工序、66 条路线映射；生效映射问题 0 条。实际读取 code_linkage.resolved_mapping；routes 为原始抽样证据。

| 工序码 | 工序 | 参数宽表 | 314Ah 生效字段 / 状态 | 588Ah 生效字段 / 状态 | 原抽样 no_match 路线 |
|---|---|---|---|---|---|
| C1101 | 正极合浆 | `dwd_qual_pos_mixing_param_pim` | `pos_mixing_code` / verified_on_sample | `pos_mixing_code` / limited_samples | 无 |
| C1103 | 负极合浆 | `dwd_qual_neg_mixing_param_pim` | `neg_mixing_code` / verified_on_sample | `neg_mixing_code` / limited_samples | 无 |
| C1201 | 正极涂布 | `dwd_qual_pos_coating_param_pim` | `pos_coating_code` / verified_on_sample | `pos_coating_code` / verified_on_sample | 无 |
| C1202 | 负极涂布 | `dwd_qual_neg_coating_param_pim` | `neg_coating_code` / verified_on_sample | `neg_coating_code` / verified_on_sample | 无 |
| C1301 | 正极辊压 | `dwd_qual_pos_roll_slit_param_pim` | `pos_roll_slit_code` / verified_on_sample | `pos_roll_slit_code` / verified_on_sample | 无 |
| C1302 | 负极辊压 | `dwd_qual_neg_roll_slit_param_pim` | `neg_roll_slit_code` / verified_on_sample | `neg_roll_slit_code` / verified_on_sample | 无 |
| C1400 | 切卷 | `dwd_qual_winding_slit_param_pim` | `winding_slit_code` / verified_on_sample | `winding_slit_code` / verified_on_sample | 314ah, 588ah |
| C1503 | 极耳翻折检测 | `dwd_qual_tab_fold_insp_param_pim` | `winding_slit_code` / verified_on_sample | `winding_slit_code` / verified_on_sample | 314ah, 588ah |
| C1504 | X-ray | `dwd_qual_xray_param_pim` | `winding_slit_code` / verified_on_sample | `winding_slit_code` / verified_on_sample | 314ah, 588ah |
| C1506 | 超声焊 | `dwd_qual_ultrasonic_weld_param_pim` | `butterfly_weld_code` / verified_on_sample | `butterfly_weld_code` / verified_on_sample | 314ah, 588ah |
| C1507 | 盖板连接片激光焊 | `dwd_qual_connector_laser_weld_param_pim` | `butterfly_weld_code` / verified_on_sample | `butterfly_weld_code` / verified_on_sample | 314ah, 588ah |
| C1508 | 包膜入壳 | `dwd_qual_wrap_can_insert_param_pim` | `wrap_can_insert_code` / verified_on_sample | `wrap_can_insert_code` / verified_on_sample | 314ah, 588ah |
| C1509 | 顶盖激光焊 | `dwd_qual_top_cover_laser_weld_param_pim` | `wrap_can_insert_code` / verified_on_sample | `wrap_can_insert_code` / verified_on_sample | 无 |
| C1510 | 一次氦检 | `dwd_qual_helium_leak_test1_param_pim` | `cell_code` / verified_on_sample | `cell_code` / verified_on_sample | 无 |
| C1600 | 电芯烘烤 | `dwd_qual_bake_param_pim` | `cell_code` / verified_on_sample | `cell_code` / verified_on_sample | 无 |
| C1700 | 一次注液 | `dwd_qual_electrolyte_fill1_param_pim` | `cell_code` / verified_on_sample | `cell_code` / verified_on_sample | 无 |
| C1800 | 高温静置1 | `dwd_qual_high_temp_rest1_param_pim` | `cell_code` / user_confirmed | `cell_code` / user_confirmed | 314ah |
| C1900 | 二次注液 | `dwd_qual_electrolyte_fill2_param_pim` | `cell_code` / verified_on_sample | `cell_code` / verified_on_sample | 无 |
| C2100 | 高温静置2 | `dwd_qual_high_temp_rest2_param_pim` | `cell_code` / verified_on_sample | `cell_code` / verified_on_sample | 无 |
| C2200 | 化成 | `dwd_qual_formation_param_pim` | `cell_code` / verified_on_sample | `cell_code` / verified_on_sample | 无 |
| C2300 | 高温老化 | `dwd_qual_high_temp_aging_param_pim` | `cell_code` / verified_on_sample | `cell_code` / verified_on_sample | 无 |
| C2400 | 三次注液 | `dwd_qual_electrolyte_fill3_param_pim` | `cell_code` / verified_on_sample | `cell_code` / verified_on_sample | 无 |
| C2500 | 密封钉 | `dwd_qual_seal_nail_param_pim` | `cell_code` / verified_on_sample | `cell_code` / verified_on_sample | 无 |
| C2600 | 二次氦检 | `dwd_qual_helium_leak_test2_param_pim` | `cell_code` / verified_on_sample | `cell_code` / verified_on_sample | 无 |
| C2700 | 常温静置1 | `dwd_qual_ambient_rest1_param_pim` | `cell_code` / verified_on_sample | `cell_code` / verified_on_sample | 无 |
| C2800 | 分容 | `dwd_qual_grading_param_pim` | `cell_code` / verified_on_sample | `cell_code` / verified_on_sample | 无 |
| C2900 | 高温静置3 | `dwd_qual_high_temp_rest3_param_pim` | `cell_code` / verified_on_sample | `cell_code` / verified_on_sample | 无 |
| C3000 | 常温静置2 | `dwd_qual_ambient_rest2_param_pim` | `cell_code` / verified_on_sample | `cell_code` / verified_on_sample | 无 |
| C3100 | OCV3 | `dwd_qual_ocv3_param_pim` | `cell_code` / verified_on_sample | `cell_code` / verified_on_sample | 无 |
| C3200 | 常温静置3 | `dwd_qual_ambient_rest3_param_pim` | `cell_code` / verified_on_sample | `cell_code` / verified_on_sample | 无 |
| C3300 | OCV4 | `dwd_qual_ocv4_param_pim` | `cell_code` / verified_on_sample | `cell_code` / verified_on_sample | 无 |
| C3500 | DCR | `dwd_qual_dcr_param_pim` | `cell_code` / verified_on_sample | `cell_code` / verified_on_sample | 无 |
| C3600 | 分档包胶 | `dwd_qual_tape_wrap_param_pim` | `cell_code` / verified_on_sample | `cell_code` / verified_on_sample | 无 |

## 未纳入分析的工序

- C1501 / 预热：未找到同时具备追溯、NG字段及DDL数值测量列的参数宽表
- C1502 / 热压：未找到同时具备追溯、NG字段及DDL数值测量列的参数宽表
- C1505 / 极耳预焊：未找到同时具备追溯、NG字段及DDL数值测量列的参数宽表
- C2000 / 预充：未找到同时具备追溯、NG字段及DDL数值测量列的参数宽表
- C3400 / OCV5：未找到同时具备追溯、NG字段及DDL数值测量列的参数宽表

## 实际样本较少的生效映射

- 正极合浆 / 588ah：`pos_mixing_code`；已有映射，样本支持较少。
- 负极合浆 / 588ah：`neg_mixing_code`；已有映射，样本支持较少。

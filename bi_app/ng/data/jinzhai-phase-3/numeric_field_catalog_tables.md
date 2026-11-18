# 当前NG深度分析工序表清单

直接从当前numeric_field_catalog.json生成。所有表均位于dwd数据库；314Ah、588Ah分别使用对应路线的ADS追溯表。

| 工序编码 | 工序 | 表名 | 314Ah关联字段 | 588Ah关联字段 |
|---|---|---|---|---|
| C1101 | 正极合浆 | `dwd_qual_pos_mixing_param_pim` | `pos_mixing_code` | `pos_mixing_code` |
| C1103 | 负极合浆 | `dwd_qual_neg_mixing_param_pim` | `neg_mixing_code` | `neg_mixing_code` |
| C1201 | 正极涂布 | `dwd_qual_pos_coating_param_pim` | `pos_coating_code` | `pos_coating_code` |
| C1202 | 负极涂布 | `dwd_qual_neg_coating_param_pim` | `neg_coating_code` | `neg_coating_code` |
| C1301 | 正极辊压 | `dwd_qual_pos_roll_slit_param_pim` | `pos_roll_slit_code` | `pos_roll_slit_code` |
| C1302 | 负极辊压 | `dwd_qual_neg_roll_slit_param_pim` | `neg_roll_slit_code` | `neg_roll_slit_code` |
| C1400 | 切卷 | `dwd_qual_winding_slit_param_pim` | `winding_slit_code` | `winding_slit_code` |
| C1503 | 极耳翻折检测 | `dwd_qual_tab_fold_insp_param_pim` | `winding_slit_code` | `winding_slit_code` |
| C1504 | X-ray | `dwd_qual_xray_param_pim` | `winding_slit_code` | `winding_slit_code` |
| C1506 | 超声焊 | `dwd_qual_ultrasonic_weld_param_pim` | `butterfly_weld_code` | `butterfly_weld_code` |
| C1507 | 盖板连接片激光焊 | `dwd_qual_connector_laser_weld_param_pim` | `butterfly_weld_code` | `butterfly_weld_code` |
| C1508 | 包膜入壳 | `dwd_qual_wrap_can_insert_param_pim` | `wrap_can_insert_code` | `wrap_can_insert_code` |
| C1509 | 顶盖激光焊 | `dwd_qual_top_cover_laser_weld_param_pim` | `wrap_can_insert_code` | `wrap_can_insert_code` |
| C1510 | 一次氦检 | `dwd_qual_helium_leak_test1_param_pim` | `cell_code` | `cell_code` |
| C1600 | 电芯烘烤 | `dwd_qual_bake_param_pim` | `cell_code` | `cell_code` |
| C1700 | 一次注液 | `dwd_qual_electrolyte_fill1_param_pim` | `cell_code` | `cell_code` |
| C1800 | 高温静置1 | `dwd_qual_high_temp_rest1_param_pim` | `cell_code` | `cell_code` |
| C1900 | 二次注液 | `dwd_qual_electrolyte_fill2_param_pim` | `cell_code` | `cell_code` |
| C2100 | 高温静置2 | `dwd_qual_high_temp_rest2_param_pim` | `cell_code` | `cell_code` |
| C2200 | 化成 | `dwd_qual_formation_param_pim` | `cell_code` | `cell_code` |
| C2300 | 高温老化 | `dwd_qual_high_temp_aging_param_pim` | `cell_code` | `cell_code` |
| C2400 | 三次注液 | `dwd_qual_electrolyte_fill3_param_pim` | `cell_code` | `cell_code` |
| C2500 | 密封钉 | `dwd_qual_seal_nail_param_pim` | `cell_code` | `cell_code` |
| C2600 | 二次氦检 | `dwd_qual_helium_leak_test2_param_pim` | `cell_code` | `cell_code` |
| C2700 | 常温静置1 | `dwd_qual_ambient_rest1_param_pim` | `cell_code` | `cell_code` |
| C2800 | 分容 | `dwd_qual_grading_param_pim` | `cell_code` | `cell_code` |
| C2900 | 高温静置3 | `dwd_qual_high_temp_rest3_param_pim` | `cell_code` | `cell_code` |
| C3000 | 常温静置2 | `dwd_qual_ambient_rest2_param_pim` | `cell_code` | `cell_code` |
| C3100 | OCV3 | `dwd_qual_ocv3_param_pim` | `cell_code` | `cell_code` |
| C3200 | 常温静置3 | `dwd_qual_ambient_rest3_param_pim` | `cell_code` | `cell_code` |
| C3300 | OCV4 | `dwd_qual_ocv4_param_pim` | `cell_code` | `cell_code` |
| C3500 | DCR | `dwd_qual_dcr_param_pim` | `cell_code` | `cell_code` |
| C3600 | 分档包胶 | `dwd_qual_tape_wrap_param_pim` | `cell_code` | `cell_code` |

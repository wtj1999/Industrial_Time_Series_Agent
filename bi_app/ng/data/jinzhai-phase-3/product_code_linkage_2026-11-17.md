# 工序产品编码与工艺路线核验

核验时间：2026-11-17T01:49:25.910971+00:00

每个租户、产线分别抽取最近的不同product_code；以各表自身最新时间为基准。
314Ah、588Ah分别精确匹配，不用编码长度、前缀或工序名称推断；未匹配不代表全表不存在关联。

匹配数记为“近期工序编码匹配数+已生成追溯的近期电芯反查匹配数”，两者可能重叠，不能相加为独立样本数。
共有字段先比较反查覆盖的工序编码数；覆盖数相同时比较该字段候选编码在工序表中的命中率，仍相同则保留待核验。

314Ah追溯表实际没有tab_pre_weld_code；588Ah有此字段。两张追溯表都没有tenant_id，宽表查询仍须限制目标租户。

- 314ah：反查800个电芯、1600行追溯；每电芯卷绕码数2至2。
- 588ah：反查148个电芯、592行追溯；每电芯卷绕码数4至4。

| 工序宽表 | 近期样本编码 | 314Ah字段 / 状态 / 匹配数 | 588Ah字段 / 状态 / 匹配数 | 近期未匹配 / 跨路线歧义 |
|---|---:|---|---|---:|
| 常温静置1参数宽表 `dwd_qual_ambient_rest1_param_pim` | 200 | cell_code / 样本已验证 / 100+16 | cell_code / 样本已验证 / 100+0 | 0 / 0 |
| 常温静置2参数宽表 `dwd_qual_ambient_rest2_param_pim` | 200 | cell_code / 样本已验证 / 100+0 | cell_code / 样本已验证 / 100+0 | 0 / 0 |
| 常温静置3参数宽表 `dwd_qual_ambient_rest3_param_pim` | 200 | cell_code / 样本已验证 / 100+0 | cell_code / 样本已验证 / 100+0 | 0 / 0 |
| 烘烤参数宽表 `dwd_qual_bake_param_pim` | 200 | cell_code / 样本已验证 / 100+600 | cell_code / 样本已验证 / 100+0 | 0 / 0 |
| 连接片激光焊参数宽表 `dwd_qual_connector_laser_weld_param_pim` | 200 | butterfly_weld_code / 样本已验证 / 0+800 | butterfly_weld_code / 样本已验证 / 0+148 | 200 / 0 |
| DCR参数宽表 `dwd_qual_dcr_param_pim` | 200 | cell_code / 样本已验证 / 100+0 | cell_code / 样本已验证 / 100+0 | 0 / 0 |
| 一次注液参数宽表 `dwd_qual_electrolyte_fill1_param_pim` | 200 | cell_code / 样本已验证 / 100+600 | cell_code / 样本已验证 / 100+0 | 0 / 0 |
| 二次注液参数宽表 `dwd_qual_electrolyte_fill2_param_pim` | 200 | cell_code / 样本已验证 / 100+600 | cell_code / 样本已验证 / 100+0 | 0 / 0 |
| 三次注液参数宽表 `dwd_qual_electrolyte_fill3_param_pim` | 200 | cell_code / 样本已验证 / 100+160 | cell_code / 样本已验证 / 100+0 | 0 / 0 |
| 化成参数宽表 `dwd_qual_formation_param_pim` | 200 | cell_code / 样本已验证 / 100+300 | cell_code / 样本已验证 / 100+0 | 0 / 0 |
| 分容参数宽表 `dwd_qual_grading_param_pim` | 200 | cell_code / 样本已验证 / 100+16 | cell_code / 样本已验证 / 100+0 | 0 / 0 |
| 一次氦检参数宽表 `dwd_qual_helium_leak_test1_param_pim` | 200 | cell_code / 样本已验证 / 100+800 | cell_code / 样本已验证 / 100+148 | 0 / 0 |
| 二次氦检参数宽表 `dwd_qual_helium_leak_test2_param_pim` | 200 | cell_code / 样本已验证 / 100+160 | cell_code / 样本已验证 / 100+0 | 0 / 0 |
| 高温老化参数宽表 `dwd_qual_high_temp_aging_param_pim` | 200 | cell_code / 样本已验证 / 100+160 | cell_code / 样本已验证 / 100+0 | 0 / 0 |
| 高温静置1参数宽表 `dwd_qual_high_temp_rest1_param_pim` | 100 | — / 未匹配 / 0+0 | cell_code / 样本已验证 / 100+0 | 0 / 0 |
| 高温静置2参数宽表 `dwd_qual_high_temp_rest2_param_pim` | 200 | cell_code / 样本已验证 / 100+300 | cell_code / 样本已验证 / 100+0 | 0 / 0 |
| 高温静置3参数宽表 `dwd_qual_high_temp_rest3_param_pim` | 200 | cell_code / 样本已验证 / 100+0 | cell_code / 样本已验证 / 100+0 | 0 / 0 |
| 负极涂布参数宽表 `dwd_qual_neg_coating_param_pim` | 112 | neg_coating_code / 样本已验证 / 71+55 | neg_coating_code / 样本已验证 / 6+7 | 35 / 0 |
| 负极合浆参数宽表 `dwd_qual_neg_mixing_param_pim` | 38 | neg_mixing_code / 样本已验证 / 9+19 | neg_mixing_code / 支持样本较少 / 1+2 | 28 / 0 |
| 负极辊分生产参数宽表 `dwd_qual_neg_roll_slit_param_pim` | 142 | neg_roll_slit_code / 样本已验证 / 16+117 | neg_roll_slit_code / 样本已验证 / 10+11 | 116 / 0 |
| OCV3参数宽表 `dwd_qual_ocv3_param_pim` | 200 | cell_code / 样本已验证 / 100+0 | cell_code / 样本已验证 / 100+0 | 0 / 0 |
| OCV4参数宽表 `dwd_qual_ocv4_param_pim` | 200 | cell_code / 样本已验证 / 100+0 | cell_code / 样本已验证 / 100+0 | 0 / 0 |
| 正极合陶瓷参数宽表 `dwd_qual_pos_ceramic_mixing_param_pim` | 10 | — / 未匹配 / 0+0 | — / 未匹配 / 0+0 | 10 / 0 |
| 正极涂布参数宽表 `dwd_qual_pos_coating_param_pim` | 106 | pos_coating_code / 样本已验证 / 64+49 | pos_coating_code / 样本已验证 / 3+4 | 39 / 0 |
| 正极合浆瓷参数宽表 `dwd_qual_pos_mixing_param_pim` | 56 | pos_mixing_code / 样本已验证 / 13+23 | pos_mixing_code / 支持样本较少 / 1+2 | 42 / 0 |
| 正极辊分生产参数宽表 `dwd_qual_pos_roll_slit_param_pim` | 118 | pos_roll_slit_code / 样本已验证 / 58+126 | pos_roll_slit_code / 样本已验证 / 11+13 | 49 / 0 |
| AIQG智能排废内阻补偿参数表 `dwd_qual_scrap_inter_resis_comp_param_pim` | 100 | cell_code / 样本已验证 / 100+0 | — / 未匹配 / 0+0 | 0 / 0 |
| 密封钉参数宽表 `dwd_qual_seal_nail_param_pim` | 200 | cell_code / 样本已验证 / 100+160 | cell_code / 样本已验证 / 100+0 | 0 / 0 |
| 极耳翻折检测参数宽表 `dwd_qual_tab_fold_insp_param_pim` | 200 | winding_slit_code / 样本已验证 / 0+1600 | winding_slit_code / 样本已验证 / 0+592 | 200 / 0 |
| 包胶参数宽表 `dwd_qual_tape_wrap_param_pim` | 200 | cell_code / 样本已验证 / 100+0 | cell_code / 样本已验证 / 84+0 | 0 / 16 |
| 顶盖激光焊参数宽表 `dwd_qual_top_cover_laser_weld_param_pim` | 200 | wrap_can_insert_code / 样本已验证 / 44+800 | wrap_can_insert_code / 样本已验证 / 35+148 | 121 / 0 |
| 超声焊接生产参数宽表 `dwd_qual_ultrasonic_weld_param_pim` | 200 | butterfly_weld_code / 样本已验证 / 0+800 | butterfly_weld_code / 样本已验证 / 0+148 | 200 / 0 |
| 切卷参数宽表 `dwd_qual_winding_slit_param_pim` | 200 | winding_slit_code / 样本已验证 / 0+1600 | winding_slit_code / 样本已验证 / 0+592 | 200 / 0 |
| 包膜入壳参数宽表 `dwd_qual_wrap_can_insert_param_pim` | 200 | wrap_can_insert_code / 样本已验证 / 0+800 | wrap_can_insert_code / 样本已验证 / 0+148 | 200 / 0 |
| x-ray参数宽表 `dwd_qual_xray_param_pim` | 200 | winding_slit_code / 样本已验证 / 0+1600 | winding_slit_code / 样本已验证 / 0+592 | 200 / 0 |

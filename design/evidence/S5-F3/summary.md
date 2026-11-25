# S5-F3 step 1: per-region evidence (factoria_cli.mbmap)

Python and C# readers: 64085 rays (every cell, plus the 121-ray centre grid per region), **0 disagreements**.

| Category and class | Regions |
|---|---|
| hf_below_ground:water E | 5 |
| water_above_bank:col D | 4 |
| water_above_bank:vis D | 4 |
| water_shore_step:col D | 5 |
| water_shore_step:col E | 114 |
| water_shore_step:vis D | 5 |
| water_shore_step:vis E | 114 |

## Every region

| Region | Cells | bbox (m) | Centre | Max offset (m) | Bodies | Outside owners | Ring steps | Grid top objects | Py/C# disagree | Class | Reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `water_above_bank:col#3` | 5 | (-684.5, -33.5, -682.5, -31.5) | (-683.5, -32.5) | 1.671 | water:osm:relation/2315576 | terrain:grid | (1, 2) | terrain:grid (terrain); water:osm:relation/2315576 (water) | 0 | **D** | sheet edge above the outside terrain by more than the 1.5 m carve step; bank ramp skipped (shore_ramp_blocked_m): strip meets the line mask of osm:way/34575267 |
| `water_above_bank:col#1` | 34 | (-632.5, 11.5, -631.5, 27.5) | (-632.5, 19.5) | 1.834 | water:osm:relation/2315576 | terrain:grid | (1, 2) | osm:way/34575500 (bridge) | 0 | **D** | sheet edge above the outside terrain by more than the 1.5 m carve step; bank ramp skipped (shore_ramp_blocked_m): strip meets the line mask of osm:way/33731358, osm:way/34575500 |
| `water_above_bank:col#4` | 1 | (-657.5, 43.5, -657.5, 43.5) | (-657.5, 43.5) | 1.553 | water:osm:relation/2315576 | terrain:grid | (2) | terrain:grid (terrain) | 0 | **D** | sheet edge above the outside terrain by more than the 1.5 m carve step; bank ramp skipped (shore_ramp_blocked_m): strip meets the line mask of osm:way/317417201 |
| `water_above_bank:col#2` | 20 | (-657.5, 48.5, -655.5, 57.5) | (-656.5, 52.5) | 1.729 | water:osm:relation/2315576 | terrain:grid | (1, 2) | osm:way/23615351 (bridge) | 0 | **D** | sheet edge above the outside terrain by more than the 1.5 m carve step; bank ramp skipped (shore_ramp_blocked_m): strip meets the line mask of osm:way/23615351 |
| `water_above_bank:vis#3` | 5 | (-684.5, -33.5, -682.5, -31.5) | (-683.5, -32.5) | 1.671 | water:osm:relation/2315576 | terrain:grid | (1, 2) | terrain:grid (terrain); water:osm:relation/2315576 (water) | 0 | **D** | sheet edge above the outside terrain by more than the 1.5 m carve step; bank ramp skipped (shore_ramp_blocked_m): strip meets the line mask of osm:way/34575267 |
| `water_above_bank:vis#1` | 34 | (-632.5, 11.5, -631.5, 27.5) | (-632.5, 19.5) | 1.834 | water:osm:relation/2315576 | terrain:grid | (1, 2) | osm:way/34575500 (bridge) | 0 | **D** | sheet edge above the outside terrain by more than the 1.5 m carve step; bank ramp skipped (shore_ramp_blocked_m): strip meets the line mask of osm:way/33731358, osm:way/34575500 |
| `water_above_bank:vis#4` | 1 | (-657.5, 43.5, -657.5, 43.5) | (-657.5, 43.5) | 1.553 | water:osm:relation/2315576 | terrain:grid | (2) | terrain:grid (terrain) | 0 | **D** | sheet edge above the outside terrain by more than the 1.5 m carve step; bank ramp skipped (shore_ramp_blocked_m): strip meets the line mask of osm:way/317417201 |
| `water_above_bank:vis#2` | 20 | (-657.5, 48.5, -655.5, 57.5) | (-656.5, 52.5) | 1.729 | water:osm:relation/2315576 | terrain:grid | (1, 2) | osm:way/23615351 (bridge) | 0 | **D** | sheet edge above the outside terrain by more than the 1.5 m carve step; bank ramp skipped (shore_ramp_blocked_m): strip meets the line mask of osm:way/23615351 |
| `water_shore_step:col#68` | 1 | (-799.5, -613.5, -799.5, -613.5) | (-799.5, -613.5) | 0.514 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.514 m <= 1.501 m |
| `water_shore_step:col#14` | 103 | (-798.5, -612.5, -765.5, -547.5) | (-781.5, -578.5) | 0.937 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (1, 2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.937 m <= 1.501 m |
| `water_shore_step:col#69` | 1 | (-764.5, -546.5, -764.5, -546.5) | (-764.5, -546.5) | 0.376 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.376 m <= 1.501 m |
| `water_shore_step:col#1` | 791 | (-763.5, -545.5, -510.5, -374.5) | (-661.5, -375.5) | 1.500 | water:osm:relation/2793848 | bank:osm:relation/2793848, terrain:grid | (1, 2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 1.500 m <= 1.501 m |
| `water_shore_step:col#6` | 247 | (-508.5, -418.5, -507.5, -292.5) | (-508.5, -354.5) | 1.500 | water:osm:relation/2793848 | bank:osm:relation/2793848, terrain:grid | (1, 2) | terrain:grid (terrain) | 0 | **E** | designed shore step on the audit ring, max 1.500 m <= 1.501 m |
| `water_shore_step:col#5` | 297 | (-684.5, -291.5, -509.5, -279.5) | (-597.5, -288.5) | 1.500 | water:osm:relation/2793848 | bank:osm:relation/2793848, terrain:grid | (1, 2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 1.500 m <= 1.501 m |
| `water_shore_step:col#70` | 1 | (-681.5, -278.5, -681.5, -278.5) | (-681.5, -278.5) | 0.420 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.420 m <= 1.501 m |
| `water_shore_step:col#71` | 1 | (-680.5, -277.5, -680.5, -277.5) | (-680.5, -277.5) | 0.409 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.409 m <= 1.501 m |
| `water_shore_step:col#72` | 1 | (-679.5, -276.5, -679.5, -276.5) | (-679.5, -276.5) | 0.398 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.398 m <= 1.501 m |
| `water_shore_step:col#73` | 1 | (-678.5, -275.5, -678.5, -275.5) | (-678.5, -275.5) | 0.386 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.386 m <= 1.501 m |
| `water_shore_step:col#7` | 227 | (-677.5, -274.5, -638.5, -137.5) | (-655.5, -206.5) | 0.980 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (1, 2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.980 m <= 1.501 m |
| `water_shore_step:col#74` | 1 | (-642.5, -136.5, -642.5, -136.5) | (-642.5, -136.5) | 0.420 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.420 m <= 1.501 m |
| `water_shore_step:col#75` | 1 | (-643.5, -135.5, -643.5, -135.5) | (-643.5, -135.5) | 0.433 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.433 m <= 1.501 m |
| `water_shore_step:col#76` | 1 | (-644.5, -134.5, -644.5, -134.5) | (-644.5, -134.5) | 0.445 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.445 m <= 1.501 m |
| `water_shore_step:col#77` | 1 | (-645.5, -133.5, -645.5, -133.5) | (-645.5, -133.5) | 0.458 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.458 m <= 1.501 m |
| `water_shore_step:col#78` | 1 | (-646.5, -132.5, -646.5, -132.5) | (-646.5, -132.5) | 0.470 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.470 m <= 1.501 m |
| `water_shore_step:col#79` | 1 | (-647.5, -131.5, -647.5, -131.5) | (-647.5, -131.5) | 0.470 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.470 m <= 1.501 m |
| `water_shore_step:col#80` | 1 | (-648.5, -130.5, -648.5, -130.5) | (-648.5, -130.5) | 0.455 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.455 m <= 1.501 m |
| `water_shore_step:col#81` | 1 | (-649.5, -129.5, -649.5, -129.5) | (-649.5, -129.5) | 0.451 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.451 m <= 1.501 m |
| `water_shore_step:col#82` | 1 | (-650.5, -128.5, -650.5, -128.5) | (-650.5, -128.5) | 0.509 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.509 m <= 1.501 m |
| `water_shore_step:col#83` | 1 | (-651.5, -127.5, -651.5, -127.5) | (-651.5, -127.5) | 0.533 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.533 m <= 1.501 m |
| `water_shore_step:col#25` | 30 | (-667.5, -126.5, -652.5, -112.5) | (-659.5, -119.5) | 0.723 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (1, 2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.723 m <= 1.501 m |
| `water_shore_step:col#84` | 1 | (-668.5, -111.5, -668.5, -111.5) | (-668.5, -111.5) | 0.356 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.356 m <= 1.501 m |
| `water_shore_step:col#85` | 1 | (-669.5, -110.5, -669.5, -110.5) | (-669.5, -110.5) | 0.381 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.381 m <= 1.501 m |
| `water_shore_step:col#86` | 1 | (-670.5, -109.5, -670.5, -109.5) | (-670.5, -109.5) | 0.411 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.411 m <= 1.501 m |
| `water_shore_step:col#87` | 1 | (-671.5, -108.5, -671.5, -108.5) | (-671.5, -108.5) | 0.431 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.431 m <= 1.501 m |
| `water_shore_step:col#88` | 1 | (-672.5, -107.5, -672.5, -107.5) | (-672.5, -107.5) | 0.443 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.443 m <= 1.501 m |
| `water_shore_step:col#89` | 1 | (-673.5, -106.5, -673.5, -106.5) | (-673.5, -106.5) | 0.456 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.456 m <= 1.501 m |
| `water_shore_step:col#90` | 1 | (-674.5, -105.5, -674.5, -105.5) | (-674.5, -105.5) | 0.468 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.468 m <= 1.501 m |
| `water_shore_step:col#91` | 1 | (-675.5, -104.5, -675.5, -104.5) | (-675.5, -104.5) | 0.481 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.481 m <= 1.501 m |
| `water_shore_step:col#92` | 1 | (-676.5, -103.5, -676.5, -103.5) | (-676.5, -103.5) | 0.494 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.494 m <= 1.501 m |
| `water_shore_step:col#93` | 1 | (-677.5, -102.5, -677.5, -102.5) | (-677.5, -102.5) | 0.504 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.504 m <= 1.501 m |
| `water_shore_step:col#94` | 1 | (-678.5, -101.5, -678.5, -101.5) | (-678.5, -101.5) | 0.514 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.514 m <= 1.501 m |
| `water_shore_step:col#95` | 1 | (-679.5, -100.5, -679.5, -100.5) | (-679.5, -100.5) | 0.535 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.535 m <= 1.501 m |
| `water_shore_step:col#48` | 7 | (-683.5, -99.5, -680.5, -96.5) | (-682.5, -98.5) | 0.647 | water:osm:relation/2793848 | bank:osm:relation/2315576, bank:osm:relation/2793848 | (1, 2) | bank:osm:relation/2793848 (terrain); water:osm:relation/2793848 (water) | 0 | **E** | designed shore step on the audit ring, max 0.647 m <= 1.501 m |
| `water_shore_step:col#65` | 2 | (-686.5, -92.5, -686.5, -91.5) | (-686.5, -92.5) | 0.544 | water:osm:relation/2793848 | bank:osm:relation/2315576, bank:osm:relation/2793848 | (1) | bank:osm:relation/2315576 (terrain); bank:osm:relation/2793848 (terrain); water:osm:relation/2793848 (water) | 0 | **E** | designed shore step on the audit ring, max 0.544 m <= 1.501 m |
| `water_shore_step:col#51` | 6 | (-685.5, -90.5, -683.5, -87.5) | (-684.5, -89.5) | 0.754 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.754 m <= 1.501 m |
| `water_shore_step:col#52` | 6 | (-682.5, -86.5, -680.5, -83.5) | (-681.5, -85.5) | 0.729 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.729 m <= 1.501 m |
| `water_shore_step:col#53` | 6 | (-679.5, -82.5, -677.5, -79.5) | (-678.5, -81.5) | 0.792 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.792 m <= 1.501 m |
| `water_shore_step:col#35` | 15 | (-676.5, -78.5, -669.5, -71.5) | (-673.5, -74.5) | 0.753 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain); water:osm:relation/2315576 (water) | 0 | **E** | designed shore step on the audit ring, max 0.753 m <= 1.501 m |
| `water_shore_step:col#96` | 1 | (-668.5, -70.5, -668.5, -70.5) | (-668.5, -70.5) | 0.486 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.486 m <= 1.501 m |
| `water_shore_step:col#97` | 1 | (-667.5, -69.5, -667.5, -69.5) | (-667.5, -69.5) | 0.435 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.435 m <= 1.501 m |
| `water_shore_step:col#44` | 10 | (-666.5, -68.5, -661.5, -64.5) | (-664.5, -66.5) | 0.680 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain); water:osm:relation/2315576 (water) | 0 | **E** | designed shore step on the audit ring, max 0.680 m <= 1.501 m |
| `water_shore_step:col#22` | 64 | (-736.5, -64.5, -695.5, -43.5) | (-716.5, -54.5) | 0.841 | water:osm:relation/2315576, water:osm:relation/2793848 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.841 m <= 1.501 m |
| `water_shore_step:col#16` | 100 | (-799.5, -63.5, -741.5, -53.5) | (-769.5, -60.5) | 0.986 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (1, 2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.986 m <= 1.501 m |
| `water_shore_step:col#45` | 8 | (-660.5, -63.5, -656.5, -60.5) | (-658.5, -62.5) | 0.799 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.799 m <= 1.501 m |
| `water_shore_step:col#38` | 11 | (-655.5, -59.5, -649.5, -55.5) | (-652.5, -57.5) | 0.806 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.806 m <= 1.501 m |
| `water_shore_step:col#15` | 103 | (-648.5, -54.5, -631.5, 10.5) | (-633.5, -22.5) | 1.518 | water:osm:relation/2315576 | bank:osm:relation/2315576, terrain:grid | (1, 2) | terrain:grid (terrain) | 0 | **D** | shore step 1.518 m above the 1.501 m bound; 65 cells on a bank: ramp; ramp missing at the rest (osm:way/33731358, osm:way/34575267, osm:way/34575500, osm:way/4744359, osm:way/4744407, osm:way/4752302) |
| `water_shore_step:col#98` | 1 | (-694.5, -42.5, -694.5, -42.5) | (-694.5, -42.5) | 0.455 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.455 m <= 1.501 m |
| `water_shore_step:col#99` | 1 | (-693.5, -41.5, -693.5, -41.5) | (-693.5, -41.5) | 0.433 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.433 m <= 1.501 m |
| `water_shore_step:col#100` | 1 | (-692.5, -40.5, -692.5, -40.5) | (-692.5, -40.5) | 0.444 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.444 m <= 1.501 m |
| `water_shore_step:col#101` | 1 | (-691.5, -39.5, -691.5, -39.5) | (-691.5, -39.5) | 0.410 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.410 m <= 1.501 m |
| `water_shore_step:col#102` | 1 | (-690.5, -38.5, -690.5, -38.5) | (-690.5, -38.5) | 0.413 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.413 m <= 1.501 m |
| `water_shore_step:col#103` | 1 | (-689.5, -37.5, -689.5, -37.5) | (-689.5, -37.5) | 0.415 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.415 m <= 1.501 m |
| `water_shore_step:col#104` | 1 | (-688.5, -36.5, -688.5, -36.5) | (-688.5, -36.5) | 0.379 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.379 m <= 1.501 m |
| `water_shore_step:col#105` | 1 | (-687.5, -35.5, -687.5, -35.5) | (-687.5, -35.5) | 0.395 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.395 m <= 1.501 m |
| `water_shore_step:col#106` | 1 | (-686.5, -34.5, -686.5, -34.5) | (-686.5, -34.5) | 0.377 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.377 m <= 1.501 m |
| `water_shore_step:col#107` | 1 | (-685.5, -33.5, -685.5, -33.5) | (-685.5, -33.5) | 0.393 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain); terrain:grid (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.393 m <= 1.501 m |
| `water_shore_step:col#27` | 23 | (-682.5, -30.5, -671.5, -19.5) | (-676.5, -25.5) | 1.524 | water:osm:relation/2315576 | bank:osm:relation/2315576, terrain:grid | (1, 2) | terrain:grid (terrain); water:osm:relation/2315576 (water) | 0 | **D** | shore step 1.524 m above the 1.501 m bound; 9 cells on a bank: ramp; ramp missing at the rest (osm:way/34575267, osm:way/4744359, osm:way/4744407) |
| `water_shore_step:col#108` | 1 | (-670.5, -18.5, -670.5, -18.5) | (-670.5, -18.5) | 0.513 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.513 m <= 1.501 m |
| `water_shore_step:col#109` | 1 | (-669.5, -17.5, -669.5, -17.5) | (-669.5, -17.5) | 0.465 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.465 m <= 1.501 m |
| `water_shore_step:col#13` | 120 | (-668.5, -16.5, -656.5, 47.5) | (-660.5, 15.5) | 1.533 | water:osm:relation/2315576 | bank:osm:relation/2315576, terrain:grid | (1, 2) | osm:way/33731358 (bridge); osm:way/34575500 (bridge) | 0 | **D** | shore step 1.533 m above the 1.501 m bound; 42 cells on a bank: ramp; ramp missing at the rest (osm:way/23615351, osm:way/317417201, osm:way/33731358, osm:way/34575500, osm:way/4752302) |
| `water_shore_step:col#4` | 302 | (-632.5, 28.5, -572.5, 210.5) | (-611.5, 119.5) | 1.548 | water:osm:relation/2315576 | bank:osm:relation/2315576, terrain:grid | (1, 2) | bank:osm:relation/2315576 (terrain); terrain:grid (terrain) | 0 | **D** | shore step 1.548 m above the 1.501 m bound; 202 cells on a bank: ramp; ramp missing at the rest (osm:way/214883367, osm:way/23615351, osm:way/317417201, osm:way/34575263, osm:way/34575500, osm:way/4752301, osm:way/4758298, osm:way/83926163) |
| `water_shore_step:col#10` | 160 | (-656.5, 58.5, -621.5, 151.5) | (-644.5, 103.5) | 1.544 | water:osm:relation/2315576 | bank:osm:relation/2315576, terrain:grid | (1, 2) | bank:osm:relation/2315576 (terrain); water:osm:relation/2315576 (water) | 0 | **D** | shore step 1.544 m above the 1.501 m bound; 116 cells on a bank: ramp; ramp missing at the rest (osm:way/214883367, osm:way/23615351, osm:way/34575263, osm:way/83926163) |
| `water_shore_step:col#12` | 126 | (-620.5, 152.5, -577.5, 230.5) | (-599.5, 190.5) | 1.500 | water:osm:relation/2315576 | bank:osm:relation/2315576, terrain:grid | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 1.500 m <= 1.501 m |
| `water_shore_step:col#110` | 1 | (-571.5, 211.5, -571.5, 211.5) | (-571.5, 211.5) | 0.485 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.485 m <= 1.501 m |
| `water_shore_step:col#46` | 8 | (-570.5, 212.5, -567.5, 216.5) | (-569.5, 214.5) | 0.730 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain); water:osm:relation/2315576 (water) | 0 | **E** | designed shore step on the audit ring, max 0.730 m <= 1.501 m |
| `water_shore_step:col#111` | 1 | (-566.5, 217.5, -566.5, 217.5) | (-566.5, 217.5) | 0.474 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.474 m <= 1.501 m |
| `water_shore_step:col#33` | 16 | (-565.5, 218.5, -559.5, 227.5) | (-562.5, 222.5) | 0.795 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.795 m <= 1.501 m |
| `water_shore_step:col#49` | 7 | (-558.5, 228.5, -556.5, 232.5) | (-557.5, 230.5) | 0.789 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.789 m <= 1.501 m |
| `water_shore_step:col#54` | 6 | (-576.5, 231.5, -574.5, 234.5) | (-575.5, 232.5) | 0.767 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.767 m <= 1.501 m |
| `water_shore_step:col#17` | 98 | (-555.5, 233.5, -522.5, 294.5) | (-539.5, 264.5) | 0.892 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.892 m <= 1.501 m |
| `water_shore_step:col#55` | 6 | (-573.5, 235.5, -571.5, 238.5) | (-572.5, 236.5) | 0.759 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain); water:osm:relation/2315576 (water) | 0 | **E** | designed shore step on the audit ring, max 0.759 m <= 1.501 m |
| `water_shore_step:col#56` | 6 | (-570.5, 239.5, -568.5, 242.5) | (-569.5, 240.5) | 0.751 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain); water:osm:relation/2315576 (water) | 0 | **E** | designed shore step on the audit ring, max 0.751 m <= 1.501 m |
| `water_shore_step:col#57` | 6 | (-567.5, 243.5, -565.5, 246.5) | (-566.5, 244.5) | 0.743 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain); water:osm:relation/2315576 (water) | 0 | **E** | designed shore step on the audit ring, max 0.743 m <= 1.501 m |
| `water_shore_step:col#8` | 215 | (-564.5, 247.5, -513.5, 345.5) | (-536.5, 308.5) | 1.500 | water:osm:relation/2315576 | bank:osm:relation/2315576, terrain:grid | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 1.500 m <= 1.501 m |
| `water_shore_step:col#66` | 2 | (-597.5, 278.5, -596.5, 278.5) | (-597.5, 278.5) | 0.523 | water:osm:way/818834645 | bank:osm:way/818834645 | (2) | bank:osm:way/818834645 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.523 m <= 1.501 m |
| `water_shore_step:col#18` | 89 | (-615.5, 279.5, -598.5, 335.5) | (-610.5, 306.5) | 0.914 | water:osm:way/818834645 | bank:osm:way/818834645 | (1, 2) | bank:osm:way/818834645 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.914 m <= 1.501 m |
| `water_shore_step:col#47` | 8 | (-595.5, 279.5, -592.5, 283.5) | (-594.5, 281.5) | 0.780 | water:osm:way/818834645 | bank:osm:way/818834645 | (1, 2) | bank:osm:way/818834645 (terrain); water:osm:way/818834645 (water) | 0 | **E** | designed shore step on the audit ring, max 0.780 m <= 1.501 m |
| `water_shore_step:col#9` | 186 | (-604.5, 284.5, -551.5, 342.5) | (-573.5, 319.5) | 0.995 | water:osm:way/818834645 | bank:osm:way/818834645 | (1, 2) | bank:osm:way/818834645 (terrain); water:osm:way/818834645 (water) | 0 | **E** | designed shore step on the audit ring, max 0.995 m <= 1.501 m |
| `water_shore_step:col#58` | 6 | (-521.5, 295.5, -519.5, 298.5) | (-520.5, 296.5) | 0.769 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | scatter:osm:relation/7099311#832 (vegetation) | 0 | **E** | designed shore step on the audit ring, max 0.769 m <= 1.501 m |
| `water_shore_step:col#39` | 11 | (-518.5, 299.5, -514.5, 305.5) | (-516.5, 302.5) | 0.821 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.821 m <= 1.501 m |
| `water_shore_step:col#40` | 11 | (-513.5, 306.5, -509.5, 312.5) | (-511.5, 309.5) | 0.811 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain); scatter:osm:relation/7099311#876 (vegetation) | 0 | **E** | designed shore step on the audit ring, max 0.811 m <= 1.501 m |
| `water_shore_step:col#23` | 50 | (-508.5, 313.5, -488.5, 337.5) | (-502.5, 327.5) | 0.889 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.889 m <= 1.501 m |
| `water_shore_step:col#41` | 11 | (-611.5, 336.5, -605.5, 340.5) | (-608.5, 338.5) | 0.788 | water:osm:way/818834645 | bank:osm:way/818834645 | (1, 2) | bank:osm:way/818834645 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.788 m <= 1.501 m |
| `water_shore_step:col#28` | 23 | (-487.5, 338.5, -479.5, 352.5) | (-483.5, 345.5) | 0.868 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.868 m <= 1.501 m |
| `water_shore_step:col#112` | 1 | (-512.5, 345.5, -512.5, 345.5) | (-512.5, 345.5) | 0.487 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.487 m <= 1.501 m |
| `water_shore_step:col#26` | 29 | (-511.5, 346.5, -507.5, 363.5) | (-508.5, 354.5) | 0.994 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.994 m <= 1.501 m |
| `water_shore_step:col#59` | 6 | (-478.5, 353.5, -476.5, 356.5) | (-477.5, 354.5) | 0.785 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.785 m <= 1.501 m |
| `water_shore_step:col#60` | 6 | (-475.5, 357.5, -473.5, 360.5) | (-474.5, 358.5) | 0.784 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.784 m <= 1.501 m |
| `water_shore_step:col#61` | 6 | (-472.5, 361.5, -470.5, 364.5) | (-471.5, 362.5) | 0.783 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.783 m <= 1.501 m |
| `water_shore_step:col#42` | 11 | (-506.5, 364.5, -502.5, 370.5) | (-504.5, 367.5) | 0.796 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.796 m <= 1.501 m |
| `water_shore_step:col#62` | 6 | (-469.5, 365.5, -467.5, 368.5) | (-468.5, 366.5) | 0.781 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.781 m <= 1.501 m |
| `water_shore_step:col#2` | 537 | (-466.5, 369.5, -441.5, 699.5) | (-442.5, 533.5) | 1.001 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 1.001 m <= 1.501 m |
| `water_shore_step:col#34` | 16 | (-501.5, 371.5, -495.5, 380.5) | (-498.5, 375.5) | 0.815 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.815 m <= 1.501 m |
| `water_shore_step:col#3` | 517 | (-494.5, 381.5, -462.5, 699.5) | (-464.5, 541.5) | 0.999 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.999 m <= 1.501 m |
| `water_shore_step:col#24` | 40 | (-712.5, 594.5, -688.5, 598.5) | (-700.5, 595.5) | 0.995 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (1, 2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.995 m <= 1.501 m |
| `water_shore_step:col#19` | 80 | (-668.5, 596.5, -614.5, 602.5) | (-640.5, 600.5) | 0.940 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (1, 2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.940 m <= 1.501 m |
| `water_shore_step:col#64` | 4 | (-671.5, 597.5, -669.5, 598.5) | (-670.5, 597.5) | 0.711 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (1, 2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.711 m <= 1.501 m |
| `water_shore_step:col#113` | 1 | (-687.5, 598.5, -687.5, 598.5) | (-687.5, 598.5) | 0.447 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.447 m <= 1.501 m |
| `water_shore_step:col#32` | 17 | (-683.5, 598.5, -672.5, 602.5) | (-678.5, 600.5) | 0.936 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (1, 2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.936 m <= 1.501 m |
| `water_shore_step:col#43` | 11 | (-717.5, 599.5, -713.5, 605.5) | (-715.5, 602.5) | 0.810 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (1, 2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.810 m <= 1.501 m |
| `water_shore_step:col#114` | 1 | (-686.5, 599.5, -686.5, 599.5) | (-686.5, 599.5) | 0.457 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.457 m <= 1.501 m |
| `water_shore_step:col#115` | 1 | (-685.5, 600.5, -685.5, 600.5) | (-685.5, 600.5) | 0.467 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.467 m <= 1.501 m |
| `water_shore_step:col#116` | 1 | (-684.5, 601.5, -684.5, 601.5) | (-684.5, 601.5) | 0.477 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.477 m <= 1.501 m |
| `water_shore_step:col#50` | 7 | (-614.5, 603.5, -612.5, 607.5) | (-613.5, 605.5) | 0.753 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (1, 2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.753 m <= 1.501 m |
| `water_shore_step:col#29` | 23 | (-716.5, 606.5, -710.5, 616.5) | (-711.5, 611.5) | 0.840 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (1, 2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.840 m <= 1.501 m |
| `water_shore_step:col#31` | 20 | (-627.5, 608.5, -615.5, 612.5) | (-621.5, 611.5) | 0.842 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (1, 2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.842 m <= 1.501 m |
| `water_shore_step:col#11` | 134 | (-709.5, 610.5, -628.5, 618.5) | (-668.5, 614.5) | 0.968 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (1, 2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.968 m <= 1.501 m |
| `water_shore_step:col#21` | 65 | (-682.5, 678.5, -641.5, 686.5) | (-662.5, 682.5) | 0.941 | water:osm:way/1537086924 | bank:osm:way/1537086924 | (1, 2) | bank:osm:way/1537086924 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.941 m <= 1.501 m |
| `water_shore_step:col#36` | 12 | (-685.5, 680.5, -683.5, 687.5) | (-684.5, 683.5) | 0.840 | water:osm:way/1537086924 | bank:osm:way/1537086924 | (1, 2) | bank:osm:way/1537086924 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.840 m <= 1.501 m |
| `water_shore_step:col#67` | 2 | (-640.5, 687.5, -640.5, 688.5) | (-640.5, 687.5) | 0.458 | water:osm:way/1537086924 | bank:osm:way/1537086924 | (2) | bank:osm:way/1537086924 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.458 m <= 1.501 m |
| `water_shore_step:col#20` | 72 | (-684.5, 688.5, -641.5, 696.5) | (-662.5, 692.5) | 0.940 | water:osm:way/1537086924 | bank:osm:way/1537086924 | (1, 2) | bank:osm:way/1537086924 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.940 m <= 1.501 m |
| `water_shore_step:col#30` | 22 | (-296.5, 690.5, -283.5, 693.5) | (-290.5, 691.5) | 0.971 | water:osm:way/1537086926 | bank:osm:way/1537086926 | (1, 2) | bank:osm:way/1537086926 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.971 m <= 1.501 m |
| `water_shore_step:col#37` | 12 | (-282.5, 693.5, -280.5, 699.5) | (-281.5, 696.5) | 0.865 | water:osm:way/1537086926 | bank:osm:way/1537086926 | (1, 2) | bank:osm:way/1537086926 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.865 m <= 1.501 m |
| `water_shore_step:col#117` | 1 | (-297.5, 694.5, -297.5, 694.5) | (-297.5, 694.5) | 0.498 | water:osm:way/1537086926 | bank:osm:way/1537086926 | (2) | bank:osm:way/1537086926 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.498 m <= 1.501 m |
| `water_shore_step:col#118` | 1 | (-298.5, 695.5, -298.5, 695.5) | (-298.5, 695.5) | 0.462 | water:osm:way/1537086926 | bank:osm:way/1537086926 | (2) | bank:osm:way/1537086926 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.462 m <= 1.501 m |
| `water_shore_step:col#119` | 1 | (-299.5, 696.5, -299.5, 696.5) | (-299.5, 696.5) | 0.423 | water:osm:way/1537086926 | bank:osm:way/1537086926 | (2) | bank:osm:way/1537086926 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.423 m <= 1.501 m |
| `water_shore_step:col#63` | 5 | (-300.5, 697.5, -299.5, 699.5) | (-300.5, 698.5) | 0.695 | water:osm:way/1537086926 | bank:osm:way/1537086926 | (1, 2) | bank:osm:way/1537086926 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.695 m <= 1.501 m |
| `water_shore_step:vis#68` | 1 | (-799.5, -613.5, -799.5, -613.5) | (-799.5, -613.5) | 0.514 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.514 m <= 1.501 m |
| `water_shore_step:vis#14` | 103 | (-798.5, -612.5, -765.5, -547.5) | (-781.5, -578.5) | 0.937 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (1, 2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.937 m <= 1.501 m |
| `water_shore_step:vis#69` | 1 | (-764.5, -546.5, -764.5, -546.5) | (-764.5, -546.5) | 0.376 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.376 m <= 1.501 m |
| `water_shore_step:vis#1` | 791 | (-763.5, -545.5, -510.5, -374.5) | (-661.5, -375.5) | 1.500 | water:osm:relation/2793848 | bank:osm:relation/2793848, terrain:grid | (1, 2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 1.500 m <= 1.501 m |
| `water_shore_step:vis#6` | 247 | (-508.5, -418.5, -507.5, -292.5) | (-508.5, -354.5) | 1.500 | water:osm:relation/2793848 | bank:osm:relation/2793848, terrain:grid | (1, 2) | terrain:grid (terrain) | 0 | **E** | designed shore step on the audit ring, max 1.500 m <= 1.501 m |
| `water_shore_step:vis#5` | 297 | (-684.5, -291.5, -509.5, -279.5) | (-597.5, -288.5) | 1.500 | water:osm:relation/2793848 | bank:osm:relation/2793848, terrain:grid | (1, 2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 1.500 m <= 1.501 m |
| `water_shore_step:vis#70` | 1 | (-681.5, -278.5, -681.5, -278.5) | (-681.5, -278.5) | 0.420 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.420 m <= 1.501 m |
| `water_shore_step:vis#71` | 1 | (-680.5, -277.5, -680.5, -277.5) | (-680.5, -277.5) | 0.409 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.409 m <= 1.501 m |
| `water_shore_step:vis#72` | 1 | (-679.5, -276.5, -679.5, -276.5) | (-679.5, -276.5) | 0.398 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.398 m <= 1.501 m |
| `water_shore_step:vis#73` | 1 | (-678.5, -275.5, -678.5, -275.5) | (-678.5, -275.5) | 0.386 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.386 m <= 1.501 m |
| `water_shore_step:vis#7` | 227 | (-677.5, -274.5, -638.5, -137.5) | (-655.5, -206.5) | 0.980 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (1, 2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.980 m <= 1.501 m |
| `water_shore_step:vis#74` | 1 | (-642.5, -136.5, -642.5, -136.5) | (-642.5, -136.5) | 0.420 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.420 m <= 1.501 m |
| `water_shore_step:vis#75` | 1 | (-643.5, -135.5, -643.5, -135.5) | (-643.5, -135.5) | 0.433 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.433 m <= 1.501 m |
| `water_shore_step:vis#76` | 1 | (-644.5, -134.5, -644.5, -134.5) | (-644.5, -134.5) | 0.445 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.445 m <= 1.501 m |
| `water_shore_step:vis#77` | 1 | (-645.5, -133.5, -645.5, -133.5) | (-645.5, -133.5) | 0.458 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.458 m <= 1.501 m |
| `water_shore_step:vis#78` | 1 | (-646.5, -132.5, -646.5, -132.5) | (-646.5, -132.5) | 0.470 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.470 m <= 1.501 m |
| `water_shore_step:vis#79` | 1 | (-647.5, -131.5, -647.5, -131.5) | (-647.5, -131.5) | 0.470 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.470 m <= 1.501 m |
| `water_shore_step:vis#80` | 1 | (-648.5, -130.5, -648.5, -130.5) | (-648.5, -130.5) | 0.455 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.455 m <= 1.501 m |
| `water_shore_step:vis#81` | 1 | (-649.5, -129.5, -649.5, -129.5) | (-649.5, -129.5) | 0.451 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.451 m <= 1.501 m |
| `water_shore_step:vis#82` | 1 | (-650.5, -128.5, -650.5, -128.5) | (-650.5, -128.5) | 0.509 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.509 m <= 1.501 m |
| `water_shore_step:vis#83` | 1 | (-651.5, -127.5, -651.5, -127.5) | (-651.5, -127.5) | 0.533 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.533 m <= 1.501 m |
| `water_shore_step:vis#25` | 30 | (-667.5, -126.5, -652.5, -112.5) | (-659.5, -119.5) | 0.723 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (1, 2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.723 m <= 1.501 m |
| `water_shore_step:vis#84` | 1 | (-668.5, -111.5, -668.5, -111.5) | (-668.5, -111.5) | 0.356 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.356 m <= 1.501 m |
| `water_shore_step:vis#85` | 1 | (-669.5, -110.5, -669.5, -110.5) | (-669.5, -110.5) | 0.381 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.381 m <= 1.501 m |
| `water_shore_step:vis#86` | 1 | (-670.5, -109.5, -670.5, -109.5) | (-670.5, -109.5) | 0.411 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.411 m <= 1.501 m |
| `water_shore_step:vis#87` | 1 | (-671.5, -108.5, -671.5, -108.5) | (-671.5, -108.5) | 0.431 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.431 m <= 1.501 m |
| `water_shore_step:vis#88` | 1 | (-672.5, -107.5, -672.5, -107.5) | (-672.5, -107.5) | 0.443 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.443 m <= 1.501 m |
| `water_shore_step:vis#89` | 1 | (-673.5, -106.5, -673.5, -106.5) | (-673.5, -106.5) | 0.456 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.456 m <= 1.501 m |
| `water_shore_step:vis#90` | 1 | (-674.5, -105.5, -674.5, -105.5) | (-674.5, -105.5) | 0.468 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.468 m <= 1.501 m |
| `water_shore_step:vis#91` | 1 | (-675.5, -104.5, -675.5, -104.5) | (-675.5, -104.5) | 0.481 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.481 m <= 1.501 m |
| `water_shore_step:vis#92` | 1 | (-676.5, -103.5, -676.5, -103.5) | (-676.5, -103.5) | 0.494 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.494 m <= 1.501 m |
| `water_shore_step:vis#93` | 1 | (-677.5, -102.5, -677.5, -102.5) | (-677.5, -102.5) | 0.504 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.504 m <= 1.501 m |
| `water_shore_step:vis#94` | 1 | (-678.5, -101.5, -678.5, -101.5) | (-678.5, -101.5) | 0.514 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.514 m <= 1.501 m |
| `water_shore_step:vis#95` | 1 | (-679.5, -100.5, -679.5, -100.5) | (-679.5, -100.5) | 0.535 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.535 m <= 1.501 m |
| `water_shore_step:vis#48` | 7 | (-683.5, -99.5, -680.5, -96.5) | (-682.5, -98.5) | 0.647 | water:osm:relation/2793848 | bank:osm:relation/2315576, bank:osm:relation/2793848 | (1, 2) | bank:osm:relation/2793848 (terrain); water:osm:relation/2793848 (water) | 0 | **E** | designed shore step on the audit ring, max 0.647 m <= 1.501 m |
| `water_shore_step:vis#65` | 2 | (-686.5, -92.5, -686.5, -91.5) | (-686.5, -92.5) | 0.544 | water:osm:relation/2793848 | bank:osm:relation/2315576, bank:osm:relation/2793848 | (1) | bank:osm:relation/2315576 (terrain); bank:osm:relation/2793848 (terrain); water:osm:relation/2793848 (water) | 0 | **E** | designed shore step on the audit ring, max 0.544 m <= 1.501 m |
| `water_shore_step:vis#51` | 6 | (-685.5, -90.5, -683.5, -87.5) | (-684.5, -89.5) | 0.754 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.754 m <= 1.501 m |
| `water_shore_step:vis#52` | 6 | (-682.5, -86.5, -680.5, -83.5) | (-681.5, -85.5) | 0.729 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.729 m <= 1.501 m |
| `water_shore_step:vis#53` | 6 | (-679.5, -82.5, -677.5, -79.5) | (-678.5, -81.5) | 0.792 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.792 m <= 1.501 m |
| `water_shore_step:vis#35` | 15 | (-676.5, -78.5, -669.5, -71.5) | (-673.5, -74.5) | 0.753 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain); water:osm:relation/2315576 (water) | 0 | **E** | designed shore step on the audit ring, max 0.753 m <= 1.501 m |
| `water_shore_step:vis#96` | 1 | (-668.5, -70.5, -668.5, -70.5) | (-668.5, -70.5) | 0.486 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.486 m <= 1.501 m |
| `water_shore_step:vis#97` | 1 | (-667.5, -69.5, -667.5, -69.5) | (-667.5, -69.5) | 0.435 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.435 m <= 1.501 m |
| `water_shore_step:vis#44` | 10 | (-666.5, -68.5, -661.5, -64.5) | (-664.5, -66.5) | 0.680 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain); water:osm:relation/2315576 (water) | 0 | **E** | designed shore step on the audit ring, max 0.680 m <= 1.501 m |
| `water_shore_step:vis#22` | 64 | (-736.5, -64.5, -695.5, -43.5) | (-716.5, -54.5) | 0.841 | water:osm:relation/2315576, water:osm:relation/2793848 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.841 m <= 1.501 m |
| `water_shore_step:vis#16` | 100 | (-799.5, -63.5, -741.5, -53.5) | (-769.5, -60.5) | 0.986 | water:osm:relation/2793848 | bank:osm:relation/2793848 | (1, 2) | bank:osm:relation/2793848 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.986 m <= 1.501 m |
| `water_shore_step:vis#45` | 8 | (-660.5, -63.5, -656.5, -60.5) | (-658.5, -62.5) | 0.799 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.799 m <= 1.501 m |
| `water_shore_step:vis#38` | 11 | (-655.5, -59.5, -649.5, -55.5) | (-652.5, -57.5) | 0.806 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.806 m <= 1.501 m |
| `water_shore_step:vis#15` | 103 | (-648.5, -54.5, -631.5, 10.5) | (-633.5, -22.5) | 1.518 | water:osm:relation/2315576 | bank:osm:relation/2315576, terrain:grid | (1, 2) | terrain:grid (terrain) | 0 | **D** | shore step 1.518 m above the 1.501 m bound; 65 cells on a bank: ramp; ramp missing at the rest (osm:way/33731358, osm:way/34575267, osm:way/34575500, osm:way/4744359, osm:way/4744407, osm:way/4752302) |
| `water_shore_step:vis#98` | 1 | (-694.5, -42.5, -694.5, -42.5) | (-694.5, -42.5) | 0.455 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.455 m <= 1.501 m |
| `water_shore_step:vis#99` | 1 | (-693.5, -41.5, -693.5, -41.5) | (-693.5, -41.5) | 0.433 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.433 m <= 1.501 m |
| `water_shore_step:vis#100` | 1 | (-692.5, -40.5, -692.5, -40.5) | (-692.5, -40.5) | 0.444 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.444 m <= 1.501 m |
| `water_shore_step:vis#101` | 1 | (-691.5, -39.5, -691.5, -39.5) | (-691.5, -39.5) | 0.410 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.410 m <= 1.501 m |
| `water_shore_step:vis#102` | 1 | (-690.5, -38.5, -690.5, -38.5) | (-690.5, -38.5) | 0.413 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.413 m <= 1.501 m |
| `water_shore_step:vis#103` | 1 | (-689.5, -37.5, -689.5, -37.5) | (-689.5, -37.5) | 0.415 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.415 m <= 1.501 m |
| `water_shore_step:vis#104` | 1 | (-688.5, -36.5, -688.5, -36.5) | (-688.5, -36.5) | 0.379 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.379 m <= 1.501 m |
| `water_shore_step:vis#105` | 1 | (-687.5, -35.5, -687.5, -35.5) | (-687.5, -35.5) | 0.395 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.395 m <= 1.501 m |
| `water_shore_step:vis#106` | 1 | (-686.5, -34.5, -686.5, -34.5) | (-686.5, -34.5) | 0.377 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.377 m <= 1.501 m |
| `water_shore_step:vis#107` | 1 | (-685.5, -33.5, -685.5, -33.5) | (-685.5, -33.5) | 0.393 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain); terrain:grid (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.393 m <= 1.501 m |
| `water_shore_step:vis#27` | 23 | (-682.5, -30.5, -671.5, -19.5) | (-676.5, -25.5) | 1.524 | water:osm:relation/2315576 | bank:osm:relation/2315576, terrain:grid | (1, 2) | terrain:grid (terrain); water:osm:relation/2315576 (water) | 0 | **D** | shore step 1.524 m above the 1.501 m bound; 9 cells on a bank: ramp; ramp missing at the rest (osm:way/34575267, osm:way/4744359, osm:way/4744407) |
| `water_shore_step:vis#108` | 1 | (-670.5, -18.5, -670.5, -18.5) | (-670.5, -18.5) | 0.513 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.513 m <= 1.501 m |
| `water_shore_step:vis#109` | 1 | (-669.5, -17.5, -669.5, -17.5) | (-669.5, -17.5) | 0.465 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.465 m <= 1.501 m |
| `water_shore_step:vis#13` | 120 | (-668.5, -16.5, -656.5, 47.5) | (-660.5, 15.5) | 1.533 | water:osm:relation/2315576 | bank:osm:relation/2315576, terrain:grid | (1, 2) | osm:way/33731358 (bridge); osm:way/34575500 (bridge) | 0 | **D** | shore step 1.533 m above the 1.501 m bound; 42 cells on a bank: ramp; ramp missing at the rest (osm:way/23615351, osm:way/317417201, osm:way/33731358, osm:way/34575500, osm:way/4752302) |
| `water_shore_step:vis#4` | 302 | (-632.5, 28.5, -572.5, 210.5) | (-611.5, 119.5) | 1.548 | water:osm:relation/2315576 | bank:osm:relation/2315576, terrain:grid | (1, 2) | bank:osm:relation/2315576 (terrain); terrain:grid (terrain) | 0 | **D** | shore step 1.548 m above the 1.501 m bound; 202 cells on a bank: ramp; ramp missing at the rest (osm:way/214883367, osm:way/23615351, osm:way/317417201, osm:way/34575263, osm:way/34575500, osm:way/4752301, osm:way/4758298, osm:way/83926163) |
| `water_shore_step:vis#10` | 160 | (-656.5, 58.5, -621.5, 151.5) | (-644.5, 103.5) | 1.544 | water:osm:relation/2315576 | bank:osm:relation/2315576, terrain:grid | (1, 2) | bank:osm:relation/2315576 (terrain); water:osm:relation/2315576 (water) | 0 | **D** | shore step 1.544 m above the 1.501 m bound; 116 cells on a bank: ramp; ramp missing at the rest (osm:way/214883367, osm:way/23615351, osm:way/34575263, osm:way/83926163) |
| `water_shore_step:vis#12` | 126 | (-620.5, 152.5, -577.5, 230.5) | (-599.5, 190.5) | 1.500 | water:osm:relation/2315576 | bank:osm:relation/2315576, terrain:grid | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 1.500 m <= 1.501 m |
| `water_shore_step:vis#110` | 1 | (-571.5, 211.5, -571.5, 211.5) | (-571.5, 211.5) | 0.485 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.485 m <= 1.501 m |
| `water_shore_step:vis#46` | 8 | (-570.5, 212.5, -567.5, 216.5) | (-569.5, 214.5) | 0.730 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain); water:osm:relation/2315576 (water) | 0 | **E** | designed shore step on the audit ring, max 0.730 m <= 1.501 m |
| `water_shore_step:vis#111` | 1 | (-566.5, 217.5, -566.5, 217.5) | (-566.5, 217.5) | 0.474 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.474 m <= 1.501 m |
| `water_shore_step:vis#33` | 16 | (-565.5, 218.5, -559.5, 227.5) | (-562.5, 222.5) | 0.795 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.795 m <= 1.501 m |
| `water_shore_step:vis#49` | 7 | (-558.5, 228.5, -556.5, 232.5) | (-557.5, 230.5) | 0.789 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.789 m <= 1.501 m |
| `water_shore_step:vis#54` | 6 | (-576.5, 231.5, -574.5, 234.5) | (-575.5, 232.5) | 0.767 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.767 m <= 1.501 m |
| `water_shore_step:vis#17` | 98 | (-555.5, 233.5, -522.5, 294.5) | (-539.5, 264.5) | 0.892 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.892 m <= 1.501 m |
| `water_shore_step:vis#55` | 6 | (-573.5, 235.5, -571.5, 238.5) | (-572.5, 236.5) | 0.759 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain); water:osm:relation/2315576 (water) | 0 | **E** | designed shore step on the audit ring, max 0.759 m <= 1.501 m |
| `water_shore_step:vis#56` | 6 | (-570.5, 239.5, -568.5, 242.5) | (-569.5, 240.5) | 0.751 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain); water:osm:relation/2315576 (water) | 0 | **E** | designed shore step on the audit ring, max 0.751 m <= 1.501 m |
| `water_shore_step:vis#57` | 6 | (-567.5, 243.5, -565.5, 246.5) | (-566.5, 244.5) | 0.743 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain); water:osm:relation/2315576 (water) | 0 | **E** | designed shore step on the audit ring, max 0.743 m <= 1.501 m |
| `water_shore_step:vis#8` | 215 | (-564.5, 247.5, -513.5, 345.5) | (-536.5, 308.5) | 1.500 | water:osm:relation/2315576 | bank:osm:relation/2315576, terrain:grid | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 1.500 m <= 1.501 m |
| `water_shore_step:vis#66` | 2 | (-597.5, 278.5, -596.5, 278.5) | (-597.5, 278.5) | 0.523 | water:osm:way/818834645 | bank:osm:way/818834645 | (2) | bank:osm:way/818834645 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.523 m <= 1.501 m |
| `water_shore_step:vis#18` | 89 | (-615.5, 279.5, -598.5, 335.5) | (-610.5, 306.5) | 0.914 | water:osm:way/818834645 | bank:osm:way/818834645 | (1, 2) | bank:osm:way/818834645 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.914 m <= 1.501 m |
| `water_shore_step:vis#47` | 8 | (-595.5, 279.5, -592.5, 283.5) | (-594.5, 281.5) | 0.780 | water:osm:way/818834645 | bank:osm:way/818834645 | (1, 2) | bank:osm:way/818834645 (terrain); water:osm:way/818834645 (water) | 0 | **E** | designed shore step on the audit ring, max 0.780 m <= 1.501 m |
| `water_shore_step:vis#9` | 186 | (-604.5, 284.5, -551.5, 342.5) | (-573.5, 319.5) | 0.995 | water:osm:way/818834645 | bank:osm:way/818834645 | (1, 2) | bank:osm:way/818834645 (terrain); water:osm:way/818834645 (water) | 0 | **E** | designed shore step on the audit ring, max 0.995 m <= 1.501 m |
| `water_shore_step:vis#58` | 6 | (-521.5, 295.5, -519.5, 298.5) | (-520.5, 296.5) | 0.769 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | scatter:osm:relation/7099311#832 (vegetation) | 0 | **E** | designed shore step on the audit ring, max 0.769 m <= 1.501 m |
| `water_shore_step:vis#39` | 11 | (-518.5, 299.5, -514.5, 305.5) | (-516.5, 302.5) | 0.821 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.821 m <= 1.501 m |
| `water_shore_step:vis#40` | 11 | (-513.5, 306.5, -509.5, 312.5) | (-511.5, 309.5) | 0.811 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain); scatter:osm:relation/7099311#876 (vegetation) | 0 | **E** | designed shore step on the audit ring, max 0.811 m <= 1.501 m |
| `water_shore_step:vis#23` | 50 | (-508.5, 313.5, -488.5, 337.5) | (-502.5, 327.5) | 0.889 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.889 m <= 1.501 m |
| `water_shore_step:vis#41` | 11 | (-611.5, 336.5, -605.5, 340.5) | (-608.5, 338.5) | 0.788 | water:osm:way/818834645 | bank:osm:way/818834645 | (1, 2) | bank:osm:way/818834645 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.788 m <= 1.501 m |
| `water_shore_step:vis#28` | 23 | (-487.5, 338.5, -479.5, 352.5) | (-483.5, 345.5) | 0.868 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.868 m <= 1.501 m |
| `water_shore_step:vis#112` | 1 | (-512.5, 345.5, -512.5, 345.5) | (-512.5, 345.5) | 0.487 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.487 m <= 1.501 m |
| `water_shore_step:vis#26` | 29 | (-511.5, 346.5, -507.5, 363.5) | (-508.5, 354.5) | 0.994 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.994 m <= 1.501 m |
| `water_shore_step:vis#59` | 6 | (-478.5, 353.5, -476.5, 356.5) | (-477.5, 354.5) | 0.785 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.785 m <= 1.501 m |
| `water_shore_step:vis#60` | 6 | (-475.5, 357.5, -473.5, 360.5) | (-474.5, 358.5) | 0.784 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.784 m <= 1.501 m |
| `water_shore_step:vis#61` | 6 | (-472.5, 361.5, -470.5, 364.5) | (-471.5, 362.5) | 0.783 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.783 m <= 1.501 m |
| `water_shore_step:vis#42` | 11 | (-506.5, 364.5, -502.5, 370.5) | (-504.5, 367.5) | 0.796 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.796 m <= 1.501 m |
| `water_shore_step:vis#62` | 6 | (-469.5, 365.5, -467.5, 368.5) | (-468.5, 366.5) | 0.781 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.781 m <= 1.501 m |
| `water_shore_step:vis#2` | 537 | (-466.5, 369.5, -441.5, 699.5) | (-442.5, 533.5) | 1.001 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 1.001 m <= 1.501 m |
| `water_shore_step:vis#34` | 16 | (-501.5, 371.5, -495.5, 380.5) | (-498.5, 375.5) | 0.815 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.815 m <= 1.501 m |
| `water_shore_step:vis#3` | 517 | (-494.5, 381.5, -462.5, 699.5) | (-464.5, 541.5) | 0.999 | water:osm:relation/2315576 | bank:osm:relation/2315576 | (1, 2) | bank:osm:relation/2315576 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.999 m <= 1.501 m |
| `water_shore_step:vis#24` | 40 | (-712.5, 594.5, -688.5, 598.5) | (-700.5, 595.5) | 0.995 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (1, 2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.995 m <= 1.501 m |
| `water_shore_step:vis#19` | 80 | (-668.5, 596.5, -614.5, 602.5) | (-640.5, 600.5) | 0.940 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (1, 2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.940 m <= 1.501 m |
| `water_shore_step:vis#64` | 4 | (-671.5, 597.5, -669.5, 598.5) | (-670.5, 597.5) | 0.711 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (1, 2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.711 m <= 1.501 m |
| `water_shore_step:vis#113` | 1 | (-687.5, 598.5, -687.5, 598.5) | (-687.5, 598.5) | 0.447 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.447 m <= 1.501 m |
| `water_shore_step:vis#32` | 17 | (-683.5, 598.5, -672.5, 602.5) | (-678.5, 600.5) | 0.936 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (1, 2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.936 m <= 1.501 m |
| `water_shore_step:vis#43` | 11 | (-717.5, 599.5, -713.5, 605.5) | (-715.5, 602.5) | 0.810 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (1, 2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.810 m <= 1.501 m |
| `water_shore_step:vis#114` | 1 | (-686.5, 599.5, -686.5, 599.5) | (-686.5, 599.5) | 0.457 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.457 m <= 1.501 m |
| `water_shore_step:vis#115` | 1 | (-685.5, 600.5, -685.5, 600.5) | (-685.5, 600.5) | 0.467 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.467 m <= 1.501 m |
| `water_shore_step:vis#116` | 1 | (-684.5, 601.5, -684.5, 601.5) | (-684.5, 601.5) | 0.477 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.477 m <= 1.501 m |
| `water_shore_step:vis#50` | 7 | (-614.5, 603.5, -612.5, 607.5) | (-613.5, 605.5) | 0.753 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (1, 2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.753 m <= 1.501 m |
| `water_shore_step:vis#29` | 23 | (-716.5, 606.5, -710.5, 616.5) | (-711.5, 611.5) | 0.840 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (1, 2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.840 m <= 1.501 m |
| `water_shore_step:vis#31` | 20 | (-627.5, 608.5, -615.5, 612.5) | (-621.5, 611.5) | 0.842 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (1, 2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.842 m <= 1.501 m |
| `water_shore_step:vis#11` | 134 | (-709.5, 610.5, -628.5, 618.5) | (-668.5, 614.5) | 0.968 | water:osm:way/1537086925 | bank:osm:way/1537086925 | (1, 2) | bank:osm:way/1537086925 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.968 m <= 1.501 m |
| `water_shore_step:vis#21` | 65 | (-682.5, 678.5, -641.5, 686.5) | (-662.5, 682.5) | 0.941 | water:osm:way/1537086924 | bank:osm:way/1537086924 | (1, 2) | bank:osm:way/1537086924 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.941 m <= 1.501 m |
| `water_shore_step:vis#36` | 12 | (-685.5, 680.5, -683.5, 687.5) | (-684.5, 683.5) | 0.840 | water:osm:way/1537086924 | bank:osm:way/1537086924 | (1, 2) | bank:osm:way/1537086924 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.840 m <= 1.501 m |
| `water_shore_step:vis#67` | 2 | (-640.5, 687.5, -640.5, 688.5) | (-640.5, 687.5) | 0.458 | water:osm:way/1537086924 | bank:osm:way/1537086924 | (2) | bank:osm:way/1537086924 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.458 m <= 1.501 m |
| `water_shore_step:vis#20` | 72 | (-684.5, 688.5, -641.5, 696.5) | (-662.5, 692.5) | 0.940 | water:osm:way/1537086924 | bank:osm:way/1537086924 | (1, 2) | bank:osm:way/1537086924 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.940 m <= 1.501 m |
| `water_shore_step:vis#30` | 22 | (-296.5, 690.5, -283.5, 693.5) | (-290.5, 691.5) | 0.971 | water:osm:way/1537086926 | bank:osm:way/1537086926 | (1, 2) | bank:osm:way/1537086926 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.971 m <= 1.501 m |
| `water_shore_step:vis#37` | 12 | (-282.5, 693.5, -280.5, 699.5) | (-281.5, 696.5) | 0.865 | water:osm:way/1537086926 | bank:osm:way/1537086926 | (1, 2) | bank:osm:way/1537086926 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.865 m <= 1.501 m |
| `water_shore_step:vis#117` | 1 | (-297.5, 694.5, -297.5, 694.5) | (-297.5, 694.5) | 0.498 | water:osm:way/1537086926 | bank:osm:way/1537086926 | (2) | bank:osm:way/1537086926 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.498 m <= 1.501 m |
| `water_shore_step:vis#118` | 1 | (-298.5, 695.5, -298.5, 695.5) | (-298.5, 695.5) | 0.462 | water:osm:way/1537086926 | bank:osm:way/1537086926 | (2) | bank:osm:way/1537086926 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.462 m <= 1.501 m |
| `water_shore_step:vis#119` | 1 | (-299.5, 696.5, -299.5, 696.5) | (-299.5, 696.5) | 0.423 | water:osm:way/1537086926 | bank:osm:way/1537086926 | (2) | bank:osm:way/1537086926 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.423 m <= 1.501 m |
| `water_shore_step:vis#63` | 5 | (-300.5, 697.5, -299.5, 699.5) | (-300.5, 698.5) | 0.695 | water:osm:way/1537086926 | bank:osm:way/1537086926 | (1, 2) | bank:osm:way/1537086926 (terrain) | 0 | **E** | designed shore step on the audit ring, max 0.695 m <= 1.501 m |
| `hf_below_ground:water#1` | 22252 | (-800.0, -612.0, -444.0, 700.0) | (-674.0, -178.0) | -4.271 | water:osm:relation/2315576, water:osm:relation/2793848 | - | (-) | water:osm:relation/2793848 (water) | 0 | **E** | D117: every node of .mbhf equals the collision bed under the sheet |
| `hf_below_ground:water#2` | 442 | (-614.0, 282.0, -554.0, 340.0) | (-592.0, 318.0) | -1.500 | water:osm:way/818834645 | - | (-) | water:osm:way/818834645 (water) | 0 | **E** | D117: every node of .mbhf equals the collision bed under the sheet |
| `hf_below_ground:water#3` | 308 | (-714.0, 598.0, -614.0, 616.0) | (-668.0, 606.0) | -1.500 | water:osm:way/1537086925 | - | (-) | water:osm:way/1537086925 (water) | 0 | **E** | D117: every node of .mbhf equals the collision bed under the sheet |
| `hf_below_ground:water#4` | 80 | (-684.0, 682.0, -642.0, 694.0) | (-666.0, 688.0) | -1.500 | water:osm:way/1537086924 | - | (-) | water:osm:way/1537086924 (water) | 0 | **E** | D117: every node of .mbhf equals the collision bed under the sheet |
| `hf_below_ground:water#5` | 30 | (-298.0, 694.0, -282.0, 700.0) | (-290.0, 698.0) | -1.500 | water:osm:way/1537086926 | - | (-) | water:osm:way/1537086926 (water) | 0 | **E** | D117: every node of .mbhf equals the collision bed under the sheet |

## Class D detail

#### `water_above_bank:col#3` (class D)

Blocked strips within reach (`shore_ramp_blocked_m` of the body: {'water:osm:relation/2315576': 192.5}):

* bank strip (-678.958, -28.529, 5.899) -> (-680.343, -29.818, 5.899) (1.892 m): line 2.625 osm:way/34575267
* bank strip (-680.343, -29.818, 5.899) -> (-681.727, -31.106, 5.899) (1.891 m): line 2.625 osm:way/34575267
* bank strip (-681.727, -31.106, 5.899) -> (-683.112, -32.394, 5.899) (1.891 m): line 2.625 osm:way/34575267
* bank strip (-683.112, -32.394, 5.899) -> (-684.496, -33.683, 5.899) (1.891 m): line 2.625 osm:way/34575267

| Cell XY | Collision top (z, mb_id, class) | Visual top (z, owner, category) | Sheet z (col) | Outside z (col) | Outside owner | Offset (m) |
|---|---|---|---|---|---|---|
| (-684.5, -33.5) | 6.2476, terrain:grid, terrain | 6.2476, terrain:grid, terrain | 7.9186 | 6.2476 | terrain:grid | 1.671 |
| (-684.5, -32.5) | 6.2965, terrain:grid, terrain | 6.2965, terrain:grid, terrain | 7.9186 | 6.2965 | terrain:grid | 1.6221 |
| (-683.5, -32.5) | 6.2965, terrain:grid, terrain | 6.2965, terrain:grid, terrain | 7.9186 | 6.2965 | terrain:grid | 1.6221 |
| (-683.5, -31.5) | 6.3453, terrain:grid, terrain | 6.3453, terrain:grid, terrain | 7.9186 | 6.3453 | terrain:grid | 1.5733 |
| (-682.5, -31.5) | 6.3453, terrain:grid, terrain | 6.3453, terrain:grid, terrain | 7.9186 | 6.3453 | terrain:grid | 1.5733 |

#### `water_above_bank:col#1` (class D)

Blocked strips within reach (`shore_ramp_blocked_m` of the body: {'water:osm:relation/2315576': 192.5}):

* bank strip (-632.609, 7.091, 5.899) -> (-632.617, 9.075, 5.899) (1.984 m): line 4.25 osm:way/33731358
* bank strip (-632.617, 9.075, 5.899) -> (-632.626, 11.059, 5.899) (1.984 m): line 4.25 osm:way/33731358
* bank strip (-632.626, 11.059, 5.899) -> (-632.634, 13.043, 5.899) (1.984 m): line 4.25 osm:way/33731358
* bank strip (-632.634, 13.043, 5.899) -> (-632.643, 15.028, 5.899) (1.985 m): line 7.5 osm:way/34575500; line 4.25 osm:way/33731358
* bank strip (-632.643, 15.028, 5.899) -> (-632.651, 17.012, 5.899) (1.984 m): line 7.5 osm:way/34575500; line 4.25 osm:way/33731358
* bank strip (-632.651, 17.012, 5.899) -> (-632.66, 18.996, 5.899) (1.984 m): line 7.5 osm:way/34575500
* bank strip (-632.66, 18.996, 5.899) -> (-632.668, 20.98, 5.899) (1.984 m): line 7.5 osm:way/34575500
* bank strip (-632.668, 20.98, 5.899) -> (-632.677, 22.964, 5.899) (1.984 m): line 7.5 osm:way/34575500
* bank strip (-632.677, 22.964, 5.899) -> (-632.685, 24.949, 5.899) (1.985 m): line 7.5 osm:way/34575500
* bank strip (-632.685, 24.949, 5.899) -> (-632.694, 26.933, 5.899) (1.984 m): line 7.5 osm:way/34575500
* bank strip (-632.694, 26.933, 5.899) -> (-632.702, 28.917, 5.899) (1.984 m): line 7.5 osm:way/34575500
* bank strip (-632.702, 28.917, 5.899) -> (-632.711, 30.901, 5.899) (1.984 m): line 7.5 osm:way/34575500

| Cell XY | Collision top (z, mb_id, class) | Visual top (z, owner, category) | Sheet z (col) | Outside z (col) | Outside owner | Offset (m) |
|---|---|---|---|---|---|---|
| (-632.5, 11.5) | 13.9782, osm:way/33731358, bridge | 13.9782, osm:way/33731358, bridge | 7.9186 | 6.3638 | terrain:grid | 1.5548 |
| (-632.5, 12.5) | 13.9746, osm:way/33731358, bridge | 13.9746, osm:way/33731358, bridge | 7.9186 | 6.3273 | terrain:grid | 1.5913 |
| (-631.5, 11.5) | 13.8983, osm:way/33731358, bridge | 13.8983, osm:way/33731358, bridge | 7.9186 | 6.3638 | terrain:grid | 1.5548 |
| (-632.5, 13.5) | 13.971, osm:way/33731358, bridge | 13.971, osm:way/33731358, bridge | 7.9186 | 6.2908 | terrain:grid | 1.6278 |
| (-631.5, 12.5) | 13.8947, osm:way/33731358, bridge | 13.8947, osm:way/33731358, bridge | 7.9186 | 6.3273 | terrain:grid | 1.5913 |
| (-632.5, 14.5) | 13.9674, osm:way/33731358, bridge | 13.9674, osm:way/33731358, bridge | 7.9186 | 6.2542 | terrain:grid | 1.6644 |
| (-631.5, 13.5) | 13.8911, osm:way/33731358, bridge | 13.8911, osm:way/33731358, bridge | 7.9186 | 6.2908 | terrain:grid | 1.6278 |
| (-632.5, 15.5) | 13.9638, osm:way/33731358, bridge | 13.9638, osm:way/33731358, bridge | 7.9186 | 6.2177 | terrain:grid | 1.7009 |
| (-631.5, 14.5) | 13.8875, osm:way/33731358, bridge | 13.8875, osm:way/33731358, bridge | 7.9186 | 6.2542 | terrain:grid | 1.6644 |
| (-632.5, 16.5) | 13.7308, osm:way/34575500, bridge | 13.7308, osm:way/34575500, bridge | 7.9186 | 6.1812 | terrain:grid | 1.7374 |
| (-631.5, 15.5) | 13.8839, osm:way/33731358, bridge | 13.8839, osm:way/33731358, bridge | 7.9186 | 6.2177 | terrain:grid | 1.7009 |
| (-632.5, 17.5) | 13.7207, osm:way/34575500, bridge | 13.7207, osm:way/34575500, bridge | 7.9186 | 6.1447 | terrain:grid | 1.7739 |
| (-631.5, 16.5) | 13.6514, osm:way/34575500, bridge | 13.6514, osm:way/34575500, bridge | 7.9186 | 6.1812 | terrain:grid | 1.7374 |
| (-632.5, 18.5) | 13.7107, osm:way/34575500, bridge | 13.7107, osm:way/34575500, bridge | 7.9186 | 6.1209 | terrain:grid | 1.7977 |
| (-631.5, 17.5) | 13.6414, osm:way/34575500, bridge | 13.6414, osm:way/34575500, bridge | 7.9186 | 6.1447 | terrain:grid | 1.7739 |
| (-632.5, 19.5) | 13.7007, osm:way/34575500, bridge | 13.7007, osm:way/34575500, bridge | 7.9186 | 6.0971 | terrain:grid | 1.8214 |
| (-631.5, 18.5) | 13.6313, osm:way/34575500, bridge | 13.6313, osm:way/34575500, bridge | 7.9186 | 6.1081 | terrain:grid | 1.8104 |
| (-632.5, 20.5) | 13.6906, osm:way/34575500, bridge | 13.6906, osm:way/34575500, bridge | 7.9186 | 6.1035 | terrain:grid | 1.8151 |
| (-631.5, 19.5) | 13.6213, osm:way/34575500, bridge | 13.6213, osm:way/34575500, bridge | 7.9186 | 6.0844 | terrain:grid | 1.8342 |
| (-632.5, 21.5) | 13.6806, osm:way/34575500, bridge | 13.6806, osm:way/34575500, bridge | 7.9186 | 6.14 | terrain:grid | 1.7785 |
| (-631.5, 20.5) | 13.6113, osm:way/34575500, bridge | 13.6113, osm:way/34575500, bridge | 7.9186 | 6.0908 | terrain:grid | 1.8278 |
| (-632.5, 22.5) | 13.6705, osm:way/34575500, bridge | 13.6705, osm:way/34575500, bridge | 7.9186 | 6.1766 | terrain:grid | 1.742 |
| (-631.5, 21.5) | 13.6012, osm:way/34575500, bridge | 13.6012, osm:way/34575500, bridge | 7.9186 | 6.1273 | terrain:grid | 1.7913 |
| (-632.5, 23.5) | 13.6605, osm:way/34575500, bridge | 13.6605, osm:way/34575500, bridge | 7.9186 | 6.2131 | terrain:grid | 1.7055 |
| (-631.5, 22.5) | 13.5912, osm:way/34575500, bridge | 13.5912, osm:way/34575500, bridge | 7.9186 | 6.1638 | terrain:grid | 1.7548 |
| (-632.5, 24.5) | 13.6505, osm:way/34575500, bridge | 13.6505, osm:way/34575500, bridge | 7.9186 | 6.2496 | terrain:grid | 1.669 |
| (-631.5, 23.5) | 13.5811, osm:way/34575500, bridge | 13.5811, osm:way/34575500, bridge | 7.9186 | 6.2003 | terrain:grid | 1.7183 |
| (-632.5, 25.5) | 13.6404, osm:way/34575500, bridge | 13.6404, osm:way/34575500, bridge | 7.9186 | 6.2861 | terrain:grid | 1.6324 |
| (-631.5, 24.5) | 13.5711, osm:way/34575500, bridge | 13.5711, osm:way/34575500, bridge | 7.9186 | 6.2368 | terrain:grid | 1.6817 |
| (-632.5, 26.5) | 13.6304, osm:way/34575500, bridge | 13.6304, osm:way/34575500, bridge | 7.9186 | 6.3227 | terrain:grid | 1.5959 |
| (-631.5, 25.5) | 13.561, osm:way/34575500, bridge | 13.561, osm:way/34575500, bridge | 7.9186 | 6.2734 | terrain:grid | 1.6452 |
| (-632.5, 27.5) | 13.6203, osm:way/34575500, bridge | 13.6203, osm:way/34575500, bridge | 7.9186 | 6.3592 | terrain:grid | 1.5594 |
| (-631.5, 26.5) | 13.551, osm:way/34575500, bridge | 13.551, osm:way/34575500, bridge | 7.9186 | 6.3099 | terrain:grid | 1.6087 |
| (-631.5, 27.5) | 13.541, osm:way/34575500, bridge | 13.541, osm:way/34575500, bridge | 7.9186 | 6.3464 | terrain:grid | 1.5722 |

#### `water_above_bank:col#4` (class D)

Blocked strips within reach (`shore_ramp_blocked_m` of the body: {'water:osm:relation/2315576': 192.5}):

* bank strip (-656.062, 44.317, 5.899) -> (-656.264, 42.367, 5.899) (1.96 m): line 2.625 osm:way/317417201
* bank strip (-656.264, 42.367, 5.899) -> (-656.465, 40.418, 5.899) (1.959 m): line 2.625 osm:way/317417201

| Cell XY | Collision top (z, mb_id, class) | Visual top (z, owner, category) | Sheet z (col) | Outside z (col) | Outside owner | Offset (m) |
|---|---|---|---|---|---|---|
| (-657.5, 43.5) | 6.3659, terrain:grid, terrain | 6.3659, terrain:grid, terrain | 7.9186 | 6.3659 | terrain:grid | 1.5526 |

#### `water_above_bank:col#2` (class D)

Blocked strips within reach (`shore_ramp_blocked_m` of the body: {'water:osm:relation/2315576': 192.5}):

* bank strip (-654.25, 61.865, 5.899) -> (-654.452, 59.915, 5.899) (1.96 m): line 5.875 osm:way/23615351
* bank strip (-654.452, 59.915, 5.899) -> (-654.653, 57.965, 5.899) (1.96 m): line 5.875 osm:way/23615351
* bank strip (-654.653, 57.965, 5.899) -> (-654.854, 56.016, 5.899) (1.959 m): line 5.875 osm:way/23615351
* bank strip (-654.854, 56.016, 5.899) -> (-655.056, 54.066, 5.899) (1.96 m): line 5.875 osm:way/23615351
* bank strip (-655.056, 54.066, 5.899) -> (-655.257, 52.116, 5.899) (1.96 m): line 5.875 osm:way/23615351
* bank strip (-655.257, 52.116, 5.899) -> (-655.458, 50.166, 5.899) (1.96 m): line 5.875 osm:way/23615351
* bank strip (-655.458, 50.166, 5.899) -> (-655.66, 48.217, 5.899) (1.959 m): line 5.875 osm:way/23615351

| Cell XY | Collision top (z, mb_id, class) | Visual top (z, owner, category) | Sheet z (col) | Outside z (col) | Outside owner | Offset (m) |
|---|---|---|---|---|---|---|
| (-657.5, 48.5) | 6.219, terrain:grid, terrain | 6.219, terrain:grid, terrain | 7.9186 | 6.219 | terrain:grid | 1.6996 |
| (-657.5, 49.5) | 6.1896, terrain:grid, terrain | 6.1896, terrain:grid, terrain | 7.9186 | 6.1896 | terrain:grid | 1.729 |
| (-656.5, 48.5) | 6.2391, terrain:grid, terrain | 6.2391, terrain:grid, terrain | 7.9186 | 6.2391 | terrain:grid | 1.6795 |
| (-656.5, 49.5) | 6.2097, terrain:grid, terrain | 6.2097, terrain:grid, terrain | 7.9186 | 6.2097 | terrain:grid | 1.7089 |
| (-656.5, 50.5) | 14.7537, osm:way/23615351, bridge | 14.7537, osm:way/23615351, bridge | 7.9186 | 6.1996 | terrain:grid | 1.7189 |
| (-656.5, 51.5) | 13.7634, osm:way/23615351, bridge | 13.7634, osm:way/23615351, bridge | 7.9186 | 6.2089 | terrain:grid | 1.7096 |
| (-655.5, 50.5) | 14.8331, osm:way/23615351, bridge | 14.8331, osm:way/23615351, bridge | 7.9186 | 6.2197 | terrain:grid | 1.6988 |
| (-656.5, 52.5) | 13.773, osm:way/23615351, bridge | 13.773, osm:way/23615351, bridge | 7.9186 | 6.2182 | terrain:grid | 1.7003 |
| (-655.5, 51.5) | 13.8427, osm:way/23615351, bridge | 13.8427, osm:way/23615351, bridge | 7.9186 | 6.229 | terrain:grid | 1.6895 |
| (-656.5, 53.5) | 13.7826, osm:way/23615351, bridge | 13.7826, osm:way/23615351, bridge | 7.9186 | 6.2275 | terrain:grid | 1.691 |
| (-655.5, 52.5) | 13.8523, osm:way/23615351, bridge | 13.8523, osm:way/23615351, bridge | 7.9186 | 6.2383 | terrain:grid | 1.6802 |
| (-656.5, 54.5) | 13.7922, osm:way/23615351, bridge | 13.7922, osm:way/23615351, bridge | 7.9186 | 6.2569 | terrain:grid | 1.6616 |
| (-655.5, 53.5) | 13.862, osm:way/23615351, bridge | 13.862, osm:way/23615351, bridge | 7.9186 | 6.2476 | terrain:grid | 1.6709 |
| (-656.5, 55.5) | 13.8018, osm:way/23615351, bridge | 13.8018, osm:way/23615351, bridge | 7.9186 | 6.2863 | terrain:grid | 1.6323 |
| (-655.5, 54.5) | 13.8716, osm:way/23615351, bridge | 13.8716, osm:way/23615351, bridge | 7.9186 | 6.2569 | terrain:grid | 1.6616 |
| (-656.5, 56.5) | 13.8114, osm:way/23615351, bridge | 13.8114, osm:way/23615351, bridge | 7.9186 | 6.3157 | terrain:grid | 1.6029 |
| (-655.5, 55.5) | 13.8812, osm:way/23615351, bridge | 13.8812, osm:way/23615351, bridge | 7.9186 | 6.2863 | terrain:grid | 1.6323 |
| (-656.5, 57.5) | 13.8211, osm:way/23615351, bridge | 13.8211, osm:way/23615351, bridge | 7.9186 | 6.3451 | terrain:grid | 1.5735 |
| (-655.5, 56.5) | 13.8908, osm:way/23615351, bridge | 13.8908, osm:way/23615351, bridge | 7.9186 | 6.3157 | terrain:grid | 1.6029 |
| (-655.5, 57.5) | 13.9004, osm:way/23615351, bridge | 13.9004, osm:way/23615351, bridge | 7.9186 | 6.3451 | terrain:grid | 1.5735 |

#### `water_above_bank:vis#3` (class D)

Blocked strips within reach (`shore_ramp_blocked_m` of the body: {'water:osm:relation/2315576': 192.5}):

* bank strip (-678.958, -28.529, 5.899) -> (-680.343, -29.818, 5.899) (1.892 m): line 2.625 osm:way/34575267
* bank strip (-680.343, -29.818, 5.899) -> (-681.727, -31.106, 5.899) (1.891 m): line 2.625 osm:way/34575267
* bank strip (-681.727, -31.106, 5.899) -> (-683.112, -32.394, 5.899) (1.891 m): line 2.625 osm:way/34575267
* bank strip (-683.112, -32.394, 5.899) -> (-684.496, -33.683, 5.899) (1.891 m): line 2.625 osm:way/34575267

| Cell XY | Collision top (z, mb_id, class) | Visual top (z, owner, category) | Sheet z (vis) | Outside z (vis) | Outside owner | Offset (m) |
|---|---|---|---|---|---|---|
| (-684.5, -33.5) | 6.2476, terrain:grid, terrain | 6.2476, terrain:grid, terrain | 7.9186 | 6.2476 | terrain:grid | 1.671 |
| (-684.5, -32.5) | 6.2965, terrain:grid, terrain | 6.2965, terrain:grid, terrain | 7.9186 | 6.2965 | terrain:grid | 1.6221 |
| (-683.5, -32.5) | 6.2965, terrain:grid, terrain | 6.2965, terrain:grid, terrain | 7.9186 | 6.2965 | terrain:grid | 1.6221 |
| (-683.5, -31.5) | 6.3453, terrain:grid, terrain | 6.3453, terrain:grid, terrain | 7.9186 | 6.3453 | terrain:grid | 1.5733 |
| (-682.5, -31.5) | 6.3453, terrain:grid, terrain | 6.3453, terrain:grid, terrain | 7.9186 | 6.3453 | terrain:grid | 1.5733 |

#### `water_above_bank:vis#1` (class D)

Blocked strips within reach (`shore_ramp_blocked_m` of the body: {'water:osm:relation/2315576': 192.5}):

* bank strip (-632.609, 7.091, 5.899) -> (-632.617, 9.075, 5.899) (1.984 m): line 4.25 osm:way/33731358
* bank strip (-632.617, 9.075, 5.899) -> (-632.626, 11.059, 5.899) (1.984 m): line 4.25 osm:way/33731358
* bank strip (-632.626, 11.059, 5.899) -> (-632.634, 13.043, 5.899) (1.984 m): line 4.25 osm:way/33731358
* bank strip (-632.634, 13.043, 5.899) -> (-632.643, 15.028, 5.899) (1.985 m): line 7.5 osm:way/34575500; line 4.25 osm:way/33731358
* bank strip (-632.643, 15.028, 5.899) -> (-632.651, 17.012, 5.899) (1.984 m): line 7.5 osm:way/34575500; line 4.25 osm:way/33731358
* bank strip (-632.651, 17.012, 5.899) -> (-632.66, 18.996, 5.899) (1.984 m): line 7.5 osm:way/34575500
* bank strip (-632.66, 18.996, 5.899) -> (-632.668, 20.98, 5.899) (1.984 m): line 7.5 osm:way/34575500
* bank strip (-632.668, 20.98, 5.899) -> (-632.677, 22.964, 5.899) (1.984 m): line 7.5 osm:way/34575500
* bank strip (-632.677, 22.964, 5.899) -> (-632.685, 24.949, 5.899) (1.985 m): line 7.5 osm:way/34575500
* bank strip (-632.685, 24.949, 5.899) -> (-632.694, 26.933, 5.899) (1.984 m): line 7.5 osm:way/34575500
* bank strip (-632.694, 26.933, 5.899) -> (-632.702, 28.917, 5.899) (1.984 m): line 7.5 osm:way/34575500
* bank strip (-632.702, 28.917, 5.899) -> (-632.711, 30.901, 5.899) (1.984 m): line 7.5 osm:way/34575500

| Cell XY | Collision top (z, mb_id, class) | Visual top (z, owner, category) | Sheet z (vis) | Outside z (vis) | Outside owner | Offset (m) |
|---|---|---|---|---|---|---|
| (-632.5, 11.5) | 13.9782, osm:way/33731358, bridge | 13.9782, osm:way/33731358, bridge | 7.9186 | 6.3638 | terrain:grid | 1.5548 |
| (-632.5, 12.5) | 13.9746, osm:way/33731358, bridge | 13.9746, osm:way/33731358, bridge | 7.9186 | 6.3273 | terrain:grid | 1.5913 |
| (-631.5, 11.5) | 13.8983, osm:way/33731358, bridge | 13.8983, osm:way/33731358, bridge | 7.9186 | 6.3638 | terrain:grid | 1.5548 |
| (-632.5, 13.5) | 13.971, osm:way/33731358, bridge | 13.971, osm:way/33731358, bridge | 7.9186 | 6.2908 | terrain:grid | 1.6278 |
| (-631.5, 12.5) | 13.8947, osm:way/33731358, bridge | 13.8947, osm:way/33731358, bridge | 7.9186 | 6.3273 | terrain:grid | 1.5913 |
| (-632.5, 14.5) | 13.9674, osm:way/33731358, bridge | 13.9674, osm:way/33731358, bridge | 7.9186 | 6.2542 | terrain:grid | 1.6644 |
| (-631.5, 13.5) | 13.8911, osm:way/33731358, bridge | 13.8911, osm:way/33731358, bridge | 7.9186 | 6.2908 | terrain:grid | 1.6278 |
| (-632.5, 15.5) | 13.9638, osm:way/33731358, bridge | 13.9638, osm:way/33731358, bridge | 7.9186 | 6.2177 | terrain:grid | 1.7009 |
| (-631.5, 14.5) | 13.8875, osm:way/33731358, bridge | 13.8875, osm:way/33731358, bridge | 7.9186 | 6.2542 | terrain:grid | 1.6644 |
| (-632.5, 16.5) | 13.7308, osm:way/34575500, bridge | 13.7308, osm:way/34575500, bridge | 7.9186 | 6.1812 | terrain:grid | 1.7374 |
| (-631.5, 15.5) | 13.8839, osm:way/33731358, bridge | 13.8839, osm:way/33731358, bridge | 7.9186 | 6.2177 | terrain:grid | 1.7009 |
| (-632.5, 17.5) | 13.7207, osm:way/34575500, bridge | 13.7207, osm:way/34575500, bridge | 7.9186 | 6.1447 | terrain:grid | 1.7739 |
| (-631.5, 16.5) | 13.6514, osm:way/34575500, bridge | 13.6514, osm:way/34575500, bridge | 7.9186 | 6.1812 | terrain:grid | 1.7374 |
| (-632.5, 18.5) | 13.7107, osm:way/34575500, bridge | 13.7107, osm:way/34575500, bridge | 7.9186 | 6.1209 | terrain:grid | 1.7977 |
| (-631.5, 17.5) | 13.6414, osm:way/34575500, bridge | 13.6414, osm:way/34575500, bridge | 7.9186 | 6.1447 | terrain:grid | 1.7739 |
| (-632.5, 19.5) | 13.7007, osm:way/34575500, bridge | 13.7007, osm:way/34575500, bridge | 7.9186 | 6.0971 | terrain:grid | 1.8214 |
| (-631.5, 18.5) | 13.6313, osm:way/34575500, bridge | 13.6313, osm:way/34575500, bridge | 7.9186 | 6.1081 | terrain:grid | 1.8104 |
| (-632.5, 20.5) | 13.6906, osm:way/34575500, bridge | 13.6906, osm:way/34575500, bridge | 7.9186 | 6.1035 | terrain:grid | 1.8151 |
| (-631.5, 19.5) | 13.6213, osm:way/34575500, bridge | 13.6213, osm:way/34575500, bridge | 7.9186 | 6.0844 | terrain:grid | 1.8342 |
| (-632.5, 21.5) | 13.6806, osm:way/34575500, bridge | 13.6806, osm:way/34575500, bridge | 7.9186 | 6.14 | terrain:grid | 1.7785 |
| (-631.5, 20.5) | 13.6113, osm:way/34575500, bridge | 13.6113, osm:way/34575500, bridge | 7.9186 | 6.0908 | terrain:grid | 1.8278 |
| (-632.5, 22.5) | 13.6705, osm:way/34575500, bridge | 13.6705, osm:way/34575500, bridge | 7.9186 | 6.1766 | terrain:grid | 1.742 |
| (-631.5, 21.5) | 13.6012, osm:way/34575500, bridge | 13.6012, osm:way/34575500, bridge | 7.9186 | 6.1273 | terrain:grid | 1.7913 |
| (-632.5, 23.5) | 13.6605, osm:way/34575500, bridge | 13.6605, osm:way/34575500, bridge | 7.9186 | 6.2131 | terrain:grid | 1.7055 |
| (-631.5, 22.5) | 13.5912, osm:way/34575500, bridge | 13.5912, osm:way/34575500, bridge | 7.9186 | 6.1638 | terrain:grid | 1.7548 |
| (-632.5, 24.5) | 13.6505, osm:way/34575500, bridge | 13.6505, osm:way/34575500, bridge | 7.9186 | 6.2496 | terrain:grid | 1.669 |
| (-631.5, 23.5) | 13.5811, osm:way/34575500, bridge | 13.5811, osm:way/34575500, bridge | 7.9186 | 6.2003 | terrain:grid | 1.7183 |
| (-632.5, 25.5) | 13.6404, osm:way/34575500, bridge | 13.6404, osm:way/34575500, bridge | 7.9186 | 6.2861 | terrain:grid | 1.6324 |
| (-631.5, 24.5) | 13.5711, osm:way/34575500, bridge | 13.5711, osm:way/34575500, bridge | 7.9186 | 6.2368 | terrain:grid | 1.6817 |
| (-632.5, 26.5) | 13.6304, osm:way/34575500, bridge | 13.6304, osm:way/34575500, bridge | 7.9186 | 6.3227 | terrain:grid | 1.5959 |
| (-631.5, 25.5) | 13.561, osm:way/34575500, bridge | 13.561, osm:way/34575500, bridge | 7.9186 | 6.2734 | terrain:grid | 1.6452 |
| (-632.5, 27.5) | 13.6203, osm:way/34575500, bridge | 13.6203, osm:way/34575500, bridge | 7.9186 | 6.3592 | terrain:grid | 1.5594 |
| (-631.5, 26.5) | 13.551, osm:way/34575500, bridge | 13.551, osm:way/34575500, bridge | 7.9186 | 6.3099 | terrain:grid | 1.6087 |
| (-631.5, 27.5) | 13.541, osm:way/34575500, bridge | 13.541, osm:way/34575500, bridge | 7.9186 | 6.3464 | terrain:grid | 1.5722 |

#### `water_above_bank:vis#4` (class D)

Blocked strips within reach (`shore_ramp_blocked_m` of the body: {'water:osm:relation/2315576': 192.5}):

* bank strip (-656.062, 44.317, 5.899) -> (-656.264, 42.367, 5.899) (1.96 m): line 2.625 osm:way/317417201
* bank strip (-656.264, 42.367, 5.899) -> (-656.465, 40.418, 5.899) (1.959 m): line 2.625 osm:way/317417201

| Cell XY | Collision top (z, mb_id, class) | Visual top (z, owner, category) | Sheet z (vis) | Outside z (vis) | Outside owner | Offset (m) |
|---|---|---|---|---|---|---|
| (-657.5, 43.5) | 6.3659, terrain:grid, terrain | 6.3659, terrain:grid, terrain | 7.9186 | 6.3659 | terrain:grid | 1.5526 |

#### `water_above_bank:vis#2` (class D)

Blocked strips within reach (`shore_ramp_blocked_m` of the body: {'water:osm:relation/2315576': 192.5}):

* bank strip (-654.25, 61.865, 5.899) -> (-654.452, 59.915, 5.899) (1.96 m): line 5.875 osm:way/23615351
* bank strip (-654.452, 59.915, 5.899) -> (-654.653, 57.965, 5.899) (1.96 m): line 5.875 osm:way/23615351
* bank strip (-654.653, 57.965, 5.899) -> (-654.854, 56.016, 5.899) (1.959 m): line 5.875 osm:way/23615351
* bank strip (-654.854, 56.016, 5.899) -> (-655.056, 54.066, 5.899) (1.96 m): line 5.875 osm:way/23615351
* bank strip (-655.056, 54.066, 5.899) -> (-655.257, 52.116, 5.899) (1.96 m): line 5.875 osm:way/23615351
* bank strip (-655.257, 52.116, 5.899) -> (-655.458, 50.166, 5.899) (1.96 m): line 5.875 osm:way/23615351
* bank strip (-655.458, 50.166, 5.899) -> (-655.66, 48.217, 5.899) (1.959 m): line 5.875 osm:way/23615351

| Cell XY | Collision top (z, mb_id, class) | Visual top (z, owner, category) | Sheet z (vis) | Outside z (vis) | Outside owner | Offset (m) |
|---|---|---|---|---|---|---|
| (-657.5, 48.5) | 6.219, terrain:grid, terrain | 6.219, terrain:grid, terrain | 7.9186 | 6.219 | terrain:grid | 1.6996 |
| (-657.5, 49.5) | 6.1896, terrain:grid, terrain | 6.1896, terrain:grid, terrain | 7.9186 | 6.1896 | terrain:grid | 1.729 |
| (-656.5, 48.5) | 6.2391, terrain:grid, terrain | 6.2391, terrain:grid, terrain | 7.9186 | 6.2391 | terrain:grid | 1.6795 |
| (-656.5, 49.5) | 6.2097, terrain:grid, terrain | 6.2097, terrain:grid, terrain | 7.9186 | 6.2097 | terrain:grid | 1.7089 |
| (-656.5, 50.5) | 14.7537, osm:way/23615351, bridge | 14.7537, osm:way/23615351, bridge | 7.9186 | 6.1996 | terrain:grid | 1.7189 |
| (-656.5, 51.5) | 13.7634, osm:way/23615351, bridge | 13.7634, osm:way/23615351, bridge | 7.9186 | 6.2089 | terrain:grid | 1.7096 |
| (-655.5, 50.5) | 14.8331, osm:way/23615351, bridge | 14.8331, osm:way/23615351, bridge | 7.9186 | 6.2197 | terrain:grid | 1.6988 |
| (-656.5, 52.5) | 13.773, osm:way/23615351, bridge | 13.773, osm:way/23615351, bridge | 7.9186 | 6.2182 | terrain:grid | 1.7003 |
| (-655.5, 51.5) | 13.8427, osm:way/23615351, bridge | 13.8427, osm:way/23615351, bridge | 7.9186 | 6.229 | terrain:grid | 1.6895 |
| (-656.5, 53.5) | 13.7826, osm:way/23615351, bridge | 13.7826, osm:way/23615351, bridge | 7.9186 | 6.2275 | terrain:grid | 1.691 |
| (-655.5, 52.5) | 13.8523, osm:way/23615351, bridge | 13.8523, osm:way/23615351, bridge | 7.9186 | 6.2383 | terrain:grid | 1.6802 |
| (-656.5, 54.5) | 13.7922, osm:way/23615351, bridge | 13.7922, osm:way/23615351, bridge | 7.9186 | 6.2569 | terrain:grid | 1.6616 |
| (-655.5, 53.5) | 13.862, osm:way/23615351, bridge | 13.862, osm:way/23615351, bridge | 7.9186 | 6.2476 | terrain:grid | 1.6709 |
| (-656.5, 55.5) | 13.8018, osm:way/23615351, bridge | 13.8018, osm:way/23615351, bridge | 7.9186 | 6.2863 | terrain:grid | 1.6323 |
| (-655.5, 54.5) | 13.8716, osm:way/23615351, bridge | 13.8716, osm:way/23615351, bridge | 7.9186 | 6.2569 | terrain:grid | 1.6616 |
| (-656.5, 56.5) | 13.8114, osm:way/23615351, bridge | 13.8114, osm:way/23615351, bridge | 7.9186 | 6.3157 | terrain:grid | 1.6029 |
| (-655.5, 55.5) | 13.8812, osm:way/23615351, bridge | 13.8812, osm:way/23615351, bridge | 7.9186 | 6.2863 | terrain:grid | 1.6323 |
| (-656.5, 57.5) | 13.8211, osm:way/23615351, bridge | 13.8211, osm:way/23615351, bridge | 7.9186 | 6.3451 | terrain:grid | 1.5735 |
| (-655.5, 56.5) | 13.8908, osm:way/23615351, bridge | 13.8908, osm:way/23615351, bridge | 7.9186 | 6.3157 | terrain:grid | 1.6029 |
| (-655.5, 57.5) | 13.9004, osm:way/23615351, bridge | 13.9004, osm:way/23615351, bridge | 7.9186 | 6.3451 | terrain:grid | 1.5735 |

#### `water_shore_step:col#15` (class D)

Blocked strips within reach (`shore_ramp_blocked_m` of the body: {'water:osm:relation/2315576': 192.5}):

* bank strip (-635.415, -30.307, 5.899) -> (-635.094, -28.356, 5.899) (1.977 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-635.094, -28.356, 5.899) -> (-634.773, -26.406, 5.899) (1.976 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-634.773, -26.406, 5.899) -> (-634.451, -24.455, 5.899) (1.977 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-634.451, -24.455, 5.899) -> (-634.13, -22.505, 5.899) (1.976 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-634.13, -22.505, 5.899) -> (-633.809, -20.554, 5.899) (1.977 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-632.575, -0.846, 5.899) -> (-632.583, 1.138, 5.899) (1.984 m): line 2.625 osm:way/4752302
* bank strip (-632.583, 1.138, 5.899) -> (-632.592, 3.122, 5.899) (1.984 m): line 2.625 osm:way/4752302
* bank strip (-632.592, 3.122, 5.899) -> (-632.6, 5.106, 5.899) (1.984 m): line 2.625 osm:way/4752302
* bank strip (-632.609, 7.091, 5.899) -> (-632.617, 9.075, 5.899) (1.984 m): line 4.25 osm:way/33731358, osm:way/34575500
* bank strip (-632.617, 9.075, 5.899) -> (-632.626, 11.059, 5.899) (1.984 m): line 4.25 osm:way/33731358, osm:way/34575500
* bank strip (-632.626, 11.059, 5.899) -> (-632.634, 13.043, 5.899) (1.984 m): line 4.25 osm:way/33731358, osm:way/34575500
* bank strip (-632.634, 13.043, 5.899) -> (-632.643, 15.028, 5.899) (1.985 m): line 7.5 osm:way/34575500; line 4.25 osm:way/33731358, osm:way/34575500

| Cell XY | Collision top (z, mb_id, class) | Visual top (z, owner, category) | Sheet z (col) | Outside z (col) | Outside owner | Offset (m) |
|---|---|---|---|---|---|---|
| (-648.5, -54.5) | 7.3328, bank:osm:relation/2315576, terrain | 7.3328, bank:osm:relation/2315576, terrain | 7.9186 | 7.3328 | bank:osm:relation/2315576 | 0.5858 |
| (-648.5, -53.5) | 7.5888, bank:osm:relation/2315576, terrain | 7.5888, bank:osm:relation/2315576, terrain | 7.9186 | 7.5888 | bank:osm:relation/2315576 | 0.3297 |
| (-647.5, -53.5) | 7.1672, bank:osm:relation/2315576, terrain | 7.1672, bank:osm:relation/2315576, terrain | 7.9186 | 7.1672 | bank:osm:relation/2315576 | 0.7514 |
| (-647.5, -52.5) | 7.4233, bank:osm:relation/2315576, terrain | 7.4233, bank:osm:relation/2315576, terrain | 7.9186 | 7.4233 | bank:osm:relation/2315576 | 0.4953 |
| (-647.5, -51.5) | 7.6793, bank:osm:relation/2315576, terrain | 7.6793, bank:osm:relation/2315576, terrain | 7.9186 | 7.6793 | bank:osm:relation/2315576 | 0.2392 |
| (-646.5, -51.5) | 7.2577, bank:osm:relation/2315576, terrain | 7.2577, bank:osm:relation/2315576, terrain | 7.9186 | 7.2577 | bank:osm:relation/2315576 | 0.6609 |
| (-646.5, -50.5) | 7.5138, bank:osm:relation/2315576, terrain | 7.5138, bank:osm:relation/2315576, terrain | 7.9186 | 7.5138 | bank:osm:relation/2315576 | 0.4048 |
| (-645.5, -50.5) | 7.0921, bank:osm:relation/2315576, terrain | 7.0921, bank:osm:relation/2315576, terrain | 7.9186 | 7.0921 | bank:osm:relation/2315576 | 0.8265 |
| (-645.5, -49.5) | 7.3482, bank:osm:relation/2315576, terrain | 7.3482, bank:osm:relation/2315576, terrain | 7.9186 | 7.3482 | bank:osm:relation/2315576 | 0.5704 |
| (-645.5, -48.5) | 7.6043, bank:osm:relation/2315576, terrain | 7.6043, bank:osm:relation/2315576, terrain | 7.9186 | 7.6043 | bank:osm:relation/2315576 | 0.3143 |
| (-644.5, -48.5) | 7.1826, bank:osm:relation/2315576, terrain | 7.1826, bank:osm:relation/2315576, terrain | 7.9186 | 7.1826 | bank:osm:relation/2315576 | 0.736 |
| (-644.5, -47.5) | 7.4387, bank:osm:relation/2315576, terrain | 7.4387, bank:osm:relation/2315576, terrain | 7.9186 | 7.4387 | bank:osm:relation/2315576 | 0.4799 |
| (-644.5, -46.5) | 7.6948, bank:osm:relation/2315576, terrain | 7.6948, bank:osm:relation/2315576, terrain | 7.9186 | 7.6948 | bank:osm:relation/2315576 | 0.2238 |
| (-643.5, -46.5) | 7.2731, bank:osm:relation/2315576, terrain | 7.2731, bank:osm:relation/2315576, terrain | 7.9186 | 7.2731 | bank:osm:relation/2315576 | 0.6455 |
| (-643.5, -45.5) | 7.5292, bank:osm:relation/2315576, terrain | 7.5292, bank:osm:relation/2315576, terrain | 7.9186 | 7.5292 | bank:osm:relation/2315576 | 0.3894 |
| (-642.5, -45.5) | 7.1075, bank:osm:relation/2315576, terrain | 7.1075, bank:osm:relation/2315576, terrain | 7.9186 | 7.1075 | bank:osm:relation/2315576 | 0.8111 |
| (-642.5, -44.5) | 7.3636, bank:osm:relation/2315576, terrain | 7.3636, bank:osm:relation/2315576, terrain | 7.9186 | 7.3636 | bank:osm:relation/2315576 | 0.555 |
| (-642.5, -43.5) | 7.6197, bank:osm:relation/2315576, terrain | 7.6197, bank:osm:relation/2315576, terrain | 7.9186 | 7.6197 | bank:osm:relation/2315576 | 0.2989 |
| (-641.5, -43.5) | 7.198, bank:osm:relation/2315576, terrain | 7.198, bank:osm:relation/2315576, terrain | 7.9186 | 7.198 | bank:osm:relation/2315576 | 0.7206 |
| (-641.5, -42.5) | 7.4488, bank:osm:relation/2315576, terrain | 7.4488, bank:osm:relation/2315576, terrain | 7.9186 | 7.4488 | bank:osm:relation/2315576 | 0.4698 |
| (-641.5, -41.5) | 7.6981, bank:osm:relation/2315576, terrain | 7.6981, bank:osm:relation/2315576, terrain | 7.9186 | 7.6981 | bank:osm:relation/2315576 | 0.2204 |
| (-640.5, -41.5) | 7.2725, bank:osm:relation/2315576, terrain | 7.2725, bank:osm:relation/2315576, terrain | 7.9186 | 7.2725 | bank:osm:relation/2315576 | 0.6461 |
| (-640.5, -40.5) | 7.5218, bank:osm:relation/2315576, terrain | 7.5218, bank:osm:relation/2315576, terrain | 7.9186 | 7.5218 | bank:osm:relation/2315576 | 0.3968 |
| (-639.5, -40.5) | 7.0961, bank:osm:relation/2315576, terrain | 7.0961, bank:osm:relation/2315576, terrain | 7.9186 | 7.0961 | bank:osm:relation/2315576 | 0.8225 |
| (-639.5, -39.5) | 7.3454, bank:osm:relation/2315576, terrain | 7.3454, bank:osm:relation/2315576, terrain | 7.9186 | 7.3454 | bank:osm:relation/2315576 | 0.5731 |
| (-639.5, -38.5) | 7.5948, bank:osm:relation/2315576, terrain | 7.5948, bank:osm:relation/2315576, terrain | 7.9186 | 7.5948 | bank:osm:relation/2315576 | 0.3238 |
| (-638.5, -38.5) | 7.1691, bank:osm:relation/2315576, terrain | 7.1691, bank:osm:relation/2315576, terrain | 7.9186 | 7.1691 | bank:osm:relation/2315576 | 0.7495 |
| (-638.5, -37.5) | 7.4184, bank:osm:relation/2315576, terrain | 7.4184, bank:osm:relation/2315576, terrain | 7.9186 | 7.4184 | bank:osm:relation/2315576 | 0.5002 |
| (-638.5, -36.5) | 7.6677, bank:osm:relation/2315576, terrain | 7.6677, bank:osm:relation/2315576, terrain | 7.9186 | 7.6677 | bank:osm:relation/2315576 | 0.2508 |
| (-637.5, -36.5) | 7.2421, bank:osm:relation/2315576, terrain | 7.2421, bank:osm:relation/2315576, terrain | 7.9186 | 7.2421 | bank:osm:relation/2315576 | 0.6765 |
| (-637.5, -35.5) | 7.4914, bank:osm:relation/2315576, terrain | 7.4914, bank:osm:relation/2315576, terrain | 7.9186 | 7.4914 | bank:osm:relation/2315576 | 0.4272 |
| (-636.5, -35.5) | 7.0657, bank:osm:relation/2315576, terrain | 7.0657, bank:osm:relation/2315576, terrain | 7.9186 | 7.0657 | bank:osm:relation/2315576 | 0.8529 |
| (-636.5, -34.5) | 7.315, bank:osm:relation/2315576, terrain | 7.315, bank:osm:relation/2315576, terrain | 7.9186 | 7.315 | bank:osm:relation/2315576 | 0.6035 |
| (-636.5, -33.5) | 7.5644, bank:osm:relation/2315576, terrain | 7.5644, bank:osm:relation/2315576, terrain | 7.9186 | 7.5644 | bank:osm:relation/2315576 | 0.3542 |
| (-635.5, -33.5) | 7.1387, bank:osm:relation/2315576, terrain | 7.1387, bank:osm:relation/2315576, terrain | 7.9186 | 7.1387 | bank:osm:relation/2315576 | 0.7799 |
| (-635.5, -32.5) | 7.388, bank:osm:relation/2315576, terrain | 7.388, bank:osm:relation/2315576, terrain | 7.9186 | 7.388 | bank:osm:relation/2315576 | 0.5306 |
| (-635.5, -31.5) | 7.6373, bank:osm:relation/2315576, terrain | 7.6373, bank:osm:relation/2315576, terrain | 7.9186 | 7.6373 | bank:osm:relation/2315576 | 0.2812 |
| (-634.5, -31.5) | 7.2117, bank:osm:relation/2315576, terrain | 7.2117, bank:osm:relation/2315576, terrain | 7.9186 | 7.2117 | bank:osm:relation/2315576 | 0.7069 |
| (-634.5, -30.5) | 7.4359, bank:osm:relation/2315576, terrain | 7.4359, bank:osm:relation/2315576, terrain | 7.9186 | 7.4359 | bank:osm:relation/2315576 | 0.4827 |
| (-634.5, -29.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-634.5, -28.5) | 10.5724, osm:way/4744407, bridge | 10.5724, osm:way/4744407, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-633.5, -29.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-634.5, -27.5) | 10.5735, osm:way/4744359, bridge | 10.5735, osm:way/4744359, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-633.5, -28.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-634.5, -26.5) | 9.5846, osm:way/4744407, bridge | 9.5846, osm:way/4744407, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-633.5, -27.5) | 9.6583, osm:way/4744407, bridge | 9.6583, osm:way/4744407, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-634.5, -25.5) | 9.592, osm:way/4744359, bridge | 9.592, osm:way/4744359, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-633.5, -26.5) | 9.6643, osm:way/4744407, bridge | 9.6643, osm:way/4744407, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-633.5, -25.5) | 9.6715, osm:way/4744359, bridge | 9.6715, osm:way/4744359, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-633.5, -24.5) | 10.6764, osm:way/4744407, bridge | 10.6764, osm:way/4744407, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-633.5, -23.5) | 9.69, osm:way/4744359, bridge | 9.69, osm:way/4744359, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, -24.5) | 9.7602, osm:way/4744359, bridge | 9.7602, osm:way/4744359, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-633.5, -22.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, -23.5) | 9.7695, osm:way/4744359, bridge | 9.7695, osm:way/4744359, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-633.5, -21.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, -22.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, -21.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, -20.5) | 7.2657, bank:osm:relation/2315576, terrain | 7.2657, bank:osm:relation/2315576, terrain | 7.9186 | 7.2657 | bank:osm:relation/2315576 | 0.6528 |
| (-632.5, -19.5) | 7.3459, bank:osm:relation/2315576, terrain | 7.3459, bank:osm:relation/2315576, terrain | 7.9186 | 7.3459 | bank:osm:relation/2315576 | 0.5727 |
| (-632.5, -18.5) | 7.4261, bank:osm:relation/2315576, terrain | 7.4261, bank:osm:relation/2315576, terrain | 7.9186 | 7.4261 | bank:osm:relation/2315576 | 0.4925 |
| (-632.5, -17.5) | 7.5062, bank:osm:relation/2315576, terrain | 7.5062, bank:osm:relation/2315576, terrain | 7.9186 | 7.5062 | bank:osm:relation/2315576 | 0.4124 |
| (-631.5, -18.5) | 6.9393, bank:osm:relation/2315576, terrain | 6.9393, bank:osm:relation/2315576, terrain | 7.9186 | 6.9393 | bank:osm:relation/2315576 | 0.9793 |
| (-632.5, -16.5) | 7.5886, bank:osm:relation/2315576, terrain | 7.5886, bank:osm:relation/2315576, terrain | 7.9186 | 7.5886 | bank:osm:relation/2315576 | 0.33 |
| (-631.5, -17.5) | 7.0194, bank:osm:relation/2315576, terrain | 7.0194, bank:osm:relation/2315576, terrain | 7.9186 | 7.0194 | bank:osm:relation/2315576 | 0.8991 |
| (-632.5, -15.5) | 7.6692, bank:osm:relation/2315576, terrain | 7.6692, bank:osm:relation/2315576, terrain | 7.9186 | 7.6692 | bank:osm:relation/2315576 | 0.2494 |
| (-631.5, -16.5) | 7.1033, bank:osm:relation/2315576, terrain | 7.1033, bank:osm:relation/2315576, terrain | 7.9186 | 7.1033 | bank:osm:relation/2315576 | 0.8153 |
| (-631.5, -15.5) | 7.1881, bank:osm:relation/2315576, terrain | 7.1881, bank:osm:relation/2315576, terrain | 7.9186 | 7.1881 | bank:osm:relation/2315576 | 0.7305 |
| (-631.5, -14.5) | 7.2775, bank:osm:relation/2315576, terrain | 7.2775, bank:osm:relation/2315576, terrain | 7.9186 | 7.2775 | bank:osm:relation/2315576 | 0.6411 |
| (-631.5, -13.5) | 7.3647, bank:osm:relation/2315576, terrain | 7.3647, bank:osm:relation/2315576, terrain | 7.9186 | 7.3647 | bank:osm:relation/2315576 | 0.5539 |
| (-631.5, -12.5) | 7.417, bank:osm:relation/2315576, terrain | 7.417, bank:osm:relation/2315576, terrain | 7.9186 | 7.417 | bank:osm:relation/2315576 | 0.5016 |
| (-631.5, -11.5) | 7.4147, bank:osm:relation/2315576, terrain | 7.4147, bank:osm:relation/2315576, terrain | 7.9186 | 7.4147 | bank:osm:relation/2315576 | 0.5039 |
| (-631.5, -10.5) | 7.4082, bank:osm:relation/2315576, terrain | 7.4082, bank:osm:relation/2315576, terrain | 7.9186 | 7.4082 | bank:osm:relation/2315576 | 0.5104 |
| (-631.5, -9.5) | 7.3989, bank:osm:relation/2315576, terrain | 7.3989, bank:osm:relation/2315576, terrain | 7.9186 | 7.3989 | bank:osm:relation/2315576 | 0.5197 |
| (-631.5, -8.5) | 7.3967, bank:osm:relation/2315576, terrain | 7.3967, bank:osm:relation/2315576, terrain | 7.9186 | 7.3967 | bank:osm:relation/2315576 | 0.5218 |
| (-631.5, -7.5) | 7.3946, bank:osm:relation/2315576, terrain | 7.3946, bank:osm:relation/2315576, terrain | 7.9186 | 7.3946 | bank:osm:relation/2315576 | 0.524 |
| (-631.5, -6.5) | 7.3924, bank:osm:relation/2315576, terrain | 7.3924, bank:osm:relation/2315576, terrain | 7.9186 | 7.3924 | bank:osm:relation/2315576 | 0.5262 |
| (-631.5, -5.5) | 7.3902, bank:osm:relation/2315576, terrain | 7.3902, bank:osm:relation/2315576, terrain | 7.9186 | 7.3902 | bank:osm:relation/2315576 | 0.5284 |
| (-631.5, -4.5) | 7.3881, bank:osm:relation/2315576, terrain | 7.3881, bank:osm:relation/2315576, terrain | 7.9186 | 7.3881 | bank:osm:relation/2315576 | 0.5305 |
| (-631.5, -3.5) | 7.3859, bank:osm:relation/2315576, terrain | 7.3859, bank:osm:relation/2315576, terrain | 7.9186 | 7.3859 | bank:osm:relation/2315576 | 0.5327 |
| (-631.5, -2.5) | 7.3837, bank:osm:relation/2315576, terrain | 7.3837, bank:osm:relation/2315576, terrain | 7.9186 | 7.3837 | bank:osm:relation/2315576 | 0.5349 |
| (-631.5, -1.5) | 7.3815, bank:osm:relation/2315576, terrain | 7.3815, bank:osm:relation/2315576, terrain | 7.9186 | 7.3815 | bank:osm:relation/2315576 | 0.5371 |
| (-631.5, -0.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 0.5) | 13.6129, osm:way/4752302, bridge | 13.6129, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, -0.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 1.5) | 13.6003, osm:way/4752302, bridge | 13.6003, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 0.5) | 13.6926, osm:way/4752302, bridge | 13.6926, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 2.5) | 13.5877, osm:way/4752302, bridge | 13.5877, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 1.5) | 13.68, osm:way/4752302, bridge | 13.68, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 3.5) | 13.5749, osm:way/4752302, bridge | 13.5749, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 2.5) | 13.6674, osm:way/4752302, bridge | 13.6674, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 4.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 3.5) | 13.6529, osm:way/4752302, bridge | 13.6529, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 5.5) | 7.3559, bank:osm:relation/2315576, terrain | 7.3559, bank:osm:relation/2315576, terrain | 7.9186 | 7.3559 | bank:osm:relation/2315576 | 0.5627 |
| (-632.5, 4.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 6.5) | 7.3538, bank:osm:relation/2315576, terrain | 7.3538, bank:osm:relation/2315576, terrain | 7.9186 | 7.3538 | bank:osm:relation/2315576 | 0.5648 |
| (-631.5, 7.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 8.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 7.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 9.5) | 13.9056, osm:way/33731358, bridge | 13.9056, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 8.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 10.5) | 13.9019, osm:way/33731358, bridge | 13.9019, osm:way/33731358, bridge | 7.9186 | 6.4003 | terrain:grid | 1.5183 |
| (-632.5, 9.5) | 13.9855, osm:way/33731358, bridge | 13.9855, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 10.5) | 13.9819, osm:way/33731358, bridge | 13.9819, osm:way/33731358, bridge | 7.9186 | 6.4003 | terrain:grid | 1.5183 |

#### `water_shore_step:col#27` (class D)

Blocked strips within reach (`shore_ramp_blocked_m` of the body: {'water:osm:relation/2315576': 192.5}):

* bank strip (-674.805, -24.664, 5.899) -> (-676.19, -25.953, 5.899) (1.892 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-676.19, -25.953, 5.899) -> (-677.574, -27.241, 5.899) (1.891 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-677.574, -27.241, 5.899) -> (-678.958, -28.529, 5.899) (1.891 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-678.958, -28.529, 5.899) -> (-680.343, -29.818, 5.899) (1.892 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-680.343, -29.818, 5.899) -> (-681.727, -31.106, 5.899) (1.891 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-681.727, -31.106, 5.899) -> (-683.112, -32.394, 5.899) (1.891 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-683.112, -32.394, 5.899) -> (-684.496, -33.683, 5.899) (1.891 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407

| Cell XY | Collision top (z, mb_id, class) | Visual top (z, owner, category) | Sheet z (col) | Outside z (col) | Outside owner | Offset (m) |
|---|---|---|---|---|---|---|
| (-682.5, -30.5) | 6.3942, terrain:grid, terrain | 6.3942, terrain:grid, terrain | 7.9186 | 6.3942 | terrain:grid | 1.5244 |
| (-681.5, -30.5) | 6.3942, terrain:grid, terrain | 6.3942, terrain:grid, terrain | 7.9186 | 6.3942 | terrain:grid | 1.5244 |
| (-681.5, -29.5) | 9.5118, osm:way/34575267, bridge | 9.5118, osm:way/34575267, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-680.5, -29.5) | 9.4328, osm:way/34575267, bridge | 9.4328, osm:way/34575267, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-680.5, -28.5) | 9.4401, osm:way/34575267, bridge | 9.4401, osm:way/34575267, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-679.5, -28.5) | 9.3611, osm:way/34575267, bridge | 9.3611, osm:way/34575267, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-679.5, -27.5) | 9.3684, osm:way/34575267, bridge | 9.3684, osm:way/34575267, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-678.5, -27.5) | 9.2876, osm:way/34575267, bridge | 9.2876, osm:way/34575267, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-678.5, -26.5) | 10.2949, osm:way/34575267, bridge | 10.2949, osm:way/34575267, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-677.5, -26.5) | 10.2134, osm:way/34575267, bridge | 10.2134, osm:way/34575267, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-677.5, -25.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-676.5, -25.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-676.5, -24.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-675.5, -24.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-675.5, -23.5) | 7.2445, bank:osm:relation/2315576, terrain | 7.2445, bank:osm:relation/2315576, terrain | 7.9186 | 7.2445 | bank:osm:relation/2315576 | 0.6741 |
| (-674.5, -23.5) | 7.5806, bank:osm:relation/2315576, terrain | 7.5806, bank:osm:relation/2315576, terrain | 7.9186 | 7.5806 | bank:osm:relation/2315576 | 0.338 |
| (-674.5, -22.5) | 7.2195, bank:osm:relation/2315576, terrain | 7.2195, bank:osm:relation/2315576, terrain | 7.9186 | 7.2195 | bank:osm:relation/2315576 | 0.6991 |
| (-673.5, -22.5) | 7.5852, bank:osm:relation/2315576, terrain | 7.5852, bank:osm:relation/2315576, terrain | 7.9186 | 7.5852 | bank:osm:relation/2315576 | 0.3333 |
| (-673.5, -21.5) | 7.2612, bank:osm:relation/2315576, terrain | 7.2612, bank:osm:relation/2315576, terrain | 7.9186 | 7.2612 | bank:osm:relation/2315576 | 0.6573 |
| (-672.5, -21.5) | 7.6333, bank:osm:relation/2315576, terrain | 7.6333, bank:osm:relation/2315576, terrain | 7.9186 | 7.6333 | bank:osm:relation/2315576 | 0.2853 |
| (-672.5, -20.5) | 7.3093, bank:osm:relation/2315576, terrain | 7.3093, bank:osm:relation/2315576, terrain | 7.9186 | 7.3093 | bank:osm:relation/2315576 | 0.6093 |
| (-671.5, -20.5) | 7.6813, bank:osm:relation/2315576, terrain | 7.6813, bank:osm:relation/2315576, terrain | 7.9186 | 7.6813 | bank:osm:relation/2315576 | 0.2373 |
| (-671.5, -19.5) | 7.3573, bank:osm:relation/2315576, terrain | 7.3573, bank:osm:relation/2315576, terrain | 7.9186 | 7.3573 | bank:osm:relation/2315576 | 0.5613 |

#### `water_shore_step:col#13` (class D)

Blocked strips within reach (`shore_ramp_blocked_m` of the body: {'water:osm:relation/2315576': 192.5}):

* bank strip (-655.257, 52.116, 5.899) -> (-655.458, 50.166, 5.899) (1.96 m): line 5.875 osm:way/23615351
* bank strip (-655.458, 50.166, 5.899) -> (-655.66, 48.217, 5.899) (1.959 m): line 5.875 osm:way/23615351
* bank strip (-656.062, 44.317, 5.899) -> (-656.264, 42.367, 5.899) (1.96 m): line 2.625 osm:way/317417201
* bank strip (-656.264, 42.367, 5.899) -> (-656.465, 40.418, 5.899) (1.959 m): line 2.625 osm:way/317417201
* bank strip (-656.465, 40.418, 5.899) -> (-656.666, 38.468, 5.899) (1.96 m): line 2.625 osm:way/317417201
* bank strip (-656.666, 38.468, 5.899) -> (-656.867, 36.518, 5.899) (1.96 m): line 2.625 osm:way/317417201
* bank strip (-657.874, 26.77, 5.899) -> (-658.075, 24.82, 5.899) (1.96 m): line 7.5 osm:way/34575500
* bank strip (-658.075, 24.82, 5.899) -> (-658.277, 22.87, 5.899) (1.96 m): line 7.5 osm:way/34575500
* bank strip (-658.277, 22.87, 5.899) -> (-658.478, 20.92, 5.899) (1.96 m): line 7.5 osm:way/34575500
* bank strip (-658.478, 20.92, 5.899) -> (-658.679, 18.971, 5.899) (1.959 m): line 7.5 osm:way/34575500
* bank strip (-658.679, 18.971, 5.899) -> (-658.881, 17.021, 5.899) (1.96 m): line 7.5 osm:way/34575500
* bank strip (-658.881, 17.021, 5.899) -> (-659.082, 15.071, 5.899) (1.96 m): line 7.5 osm:way/34575500; line 4.25 osm:way/33731358, osm:way/34575500
* bank strip (-659.082, 15.071, 5.899) -> (-659.283, 13.121, 5.899) (1.96 m): line 7.5 osm:way/34575500; line 4.25 osm:way/33731358, osm:way/34575500
* bank strip (-659.283, 13.121, 5.899) -> (-659.485, 11.172, 5.899) (1.959 m): line 7.5 osm:way/34575500; line 4.25 osm:way/33731358, osm:way/34575500
* bank strip (-659.485, 11.172, 5.899) -> (-659.686, 9.222, 5.899) (1.96 m): line 7.5 osm:way/34575500; line 4.25 osm:way/33731358, osm:way/34575500
* bank strip (-659.686, 9.222, 5.899) -> (-659.887, 7.272, 5.899) (1.96 m): line 4.25 osm:way/33731358, osm:way/34575500
* bank strip (-659.887, 7.272, 5.899) -> (-660.089, 5.323, 5.899) (1.959 m): line 4.25 osm:way/33731358, osm:way/34575500
* bank strip (-661.66, -1.986, 5.899) -> (-662.116, -3.772, 5.899) (1.843 m): line 2.625 osm:way/4752302
* bank strip (-662.116, -3.772, 5.899) -> (-662.573, -5.559, 5.899) (1.845 m): line 2.625 osm:way/4752302
* bank strip (-662.573, -5.559, 5.899) -> (-663.03, -7.345, 5.899) (1.844 m): line 2.625 osm:way/4752302
* bank strip (-663.03, -7.345, 5.899) -> (-663.859, -9.117, 5.899) (1.956 m): line 2.625 osm:way/4752302
* bank strip (-663.859, -9.117, 5.899) -> (-664.688, -10.889, 5.899) (1.956 m): line 2.625 osm:way/4752302
* bank strip (-664.688, -10.889, 5.899) -> (-665.517, -12.661, 5.899) (1.956 m): line 2.625 osm:way/4752302

| Cell XY | Collision top (z, mb_id, class) | Visual top (z, owner, category) | Sheet z (col) | Outside z (col) | Outside owner | Offset (m) |
|---|---|---|---|---|---|---|
| (-668.5, -16.5) | 7.5013, bank:osm:relation/2315576, terrain | 7.5013, bank:osm:relation/2315576, terrain | 7.9186 | 7.5013 | bank:osm:relation/2315576 | 0.4173 |
| (-668.5, -15.5) | 7.1773, bank:osm:relation/2315576, terrain | 7.1773, bank:osm:relation/2315576, terrain | 7.9186 | 7.1773 | bank:osm:relation/2315576 | 0.7413 |
| (-667.5, -15.5) | 7.6062, bank:osm:relation/2315576, terrain | 7.6062, bank:osm:relation/2315576, terrain | 7.9186 | 7.6062 | bank:osm:relation/2315576 | 0.3124 |
| (-667.5, -14.5) | 7.3971, bank:osm:relation/2315576, terrain | 7.3971, bank:osm:relation/2315576, terrain | 7.9186 | 7.3971 | bank:osm:relation/2315576 | 0.5215 |
| (-667.5, -13.5) | 7.188, bank:osm:relation/2315576, terrain | 7.188, bank:osm:relation/2315576, terrain | 7.9186 | 7.188 | bank:osm:relation/2315576 | 0.7306 |
| (-666.5, -13.5) | 7.6348, bank:osm:relation/2315576, terrain | 7.6348, bank:osm:relation/2315576, terrain | 7.9186 | 7.6348 | bank:osm:relation/2315576 | 0.2837 |
| (-666.5, -12.5) | 7.4257, bank:osm:relation/2315576, terrain | 7.4257, bank:osm:relation/2315576, terrain | 7.9186 | 7.4257 | bank:osm:relation/2315576 | 0.4928 |
| (-666.5, -11.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-665.5, -12.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-666.5, -10.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-665.5, -11.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-665.5, -10.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-665.5, -9.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-665.5, -8.5) | 15.0205, osm:way/4752302, bridge | 15.0205, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-664.5, -9.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-664.5, -8.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-664.5, -7.5) | 14.0357, osm:way/4752302, bridge | 14.0357, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-664.5, -6.5) | 14.0394, osm:way/4752302, bridge | 14.0394, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-663.5, -7.5) | 14.0471, osm:way/4752302, bridge | 14.0471, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-664.5, -5.5) | 14.0433, osm:way/4752302, bridge | 14.0433, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-663.5, -6.5) | 14.0508, osm:way/4752302, bridge | 14.0508, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-663.5, -5.5) | 14.0545, osm:way/4752302, bridge | 14.0545, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-663.5, -4.5) | 14.0584, osm:way/4752302, bridge | 14.0584, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-663.5, -3.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-662.5, -4.5) | 14.0696, osm:way/4752302, bridge | 14.0696, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-663.5, -2.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-662.5, -3.5) | 15.0735, osm:way/4752302, bridge | 15.0735, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-663.5, -1.5) | 6.9596, bank:osm:relation/2315576, terrain | 6.9596, bank:osm:relation/2315576, terrain | 7.9186 | 6.9596 | bank:osm:relation/2315576 | 0.959 |
| (-662.5, -2.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-662.5, -1.5) | 7.4376, bank:osm:relation/2315576, terrain | 7.4376, bank:osm:relation/2315576, terrain | 7.9186 | 7.4376 | bank:osm:relation/2315576 | 0.481 |
| (-662.5, -0.5) | 7.3154, bank:osm:relation/2315576, terrain | 7.3154, bank:osm:relation/2315576, terrain | 7.9186 | 7.3154 | bank:osm:relation/2315576 | 0.6032 |
| (-662.5, 0.5) | 7.1932, bank:osm:relation/2315576, terrain | 7.1932, bank:osm:relation/2315576, terrain | 7.9186 | 7.1932 | bank:osm:relation/2315576 | 0.7253 |
| (-662.5, 1.5) | 7.0711, bank:osm:relation/2315576, terrain | 7.0711, bank:osm:relation/2315576, terrain | 7.9186 | 7.0711 | bank:osm:relation/2315576 | 0.8475 |
| (-661.5, 0.5) | 7.6712, bank:osm:relation/2315576, terrain | 7.6712, bank:osm:relation/2315576, terrain | 7.9186 | 7.6712 | bank:osm:relation/2315576 | 0.2474 |
| (-662.5, 2.5) | 6.9489, bank:osm:relation/2315576, terrain | 6.9489, bank:osm:relation/2315576, terrain | 7.9186 | 6.9489 | bank:osm:relation/2315576 | 0.9697 |
| (-661.5, 1.5) | 7.549, bank:osm:relation/2315576, terrain | 7.549, bank:osm:relation/2315576, terrain | 7.9186 | 7.549 | bank:osm:relation/2315576 | 0.3695 |
| (-661.5, 2.5) | 7.4269, bank:osm:relation/2315576, terrain | 7.4269, bank:osm:relation/2315576, terrain | 7.9186 | 7.4269 | bank:osm:relation/2315576 | 0.4917 |
| (-661.5, 3.5) | 7.3047, bank:osm:relation/2315576, terrain | 7.3047, bank:osm:relation/2315576, terrain | 7.9186 | 7.3047 | bank:osm:relation/2315576 | 0.6139 |
| (-661.5, 4.5) | 7.2477, bank:osm:relation/2315576, terrain | 7.2477, bank:osm:relation/2315576, terrain | 7.9186 | 7.2477 | bank:osm:relation/2315576 | 0.6709 |
| (-661.5, 5.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-661.5, 6.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 5.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-661.5, 7.5) | 15.3671, osm:way/33731358, bridge | 15.3671, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 6.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-661.5, 8.5) | 14.3653, osm:way/33731358, bridge | 14.3653, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 7.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-661.5, 9.5) | 14.3636, osm:way/33731358, bridge | 14.3636, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 8.5) | 14.3266, osm:way/33731358, bridge | 14.3266, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-661.5, 10.5) | 14.3618, osm:way/33731358, bridge | 14.3618, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 9.5) | 14.3248, osm:way/33731358, bridge | 14.3248, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 10.5) | 14.3231, osm:way/33731358, bridge | 14.3231, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 11.5) | 15.3454, osm:way/34575500, bridge | 15.3454, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 12.5) | 14.3416, osm:way/34575500, bridge | 14.3416, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 11.5) | 14.2826, osm:way/33731358, bridge | 14.2826, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 13.5) | 14.3379, osm:way/34575500, bridge | 14.3379, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 12.5) | 14.3115, osm:way/34575500, bridge | 14.3115, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 14.5) | 14.3342, osm:way/34575500, bridge | 14.3342, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 13.5) | 14.3078, osm:way/34575500, bridge | 14.3078, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 15.5) | 14.3305, osm:way/34575500, bridge | 14.3305, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 14.5) | 14.304, osm:way/34575500, bridge | 14.304, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 16.5) | 14.3267, osm:way/34575500, bridge | 14.3267, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 15.5) | 14.3003, osm:way/34575500, bridge | 14.3003, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 17.5) | 14.323, osm:way/34575500, bridge | 14.323, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 16.5) | 14.2966, osm:way/34575500, bridge | 14.2966, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 18.5) | 14.3193, osm:way/34575500, bridge | 14.3193, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 17.5) | 14.2929, osm:way/34575500, bridge | 14.2929, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 19.5) | 14.3156, osm:way/34575500, bridge | 14.3156, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 18.5) | 14.2892, osm:way/34575500, bridge | 14.2892, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 20.5) | 14.3119, osm:way/34575500, bridge | 14.3119, osm:way/34575500, bridge | 7.9186 | 6.5191 | terrain:grid | 1.3995 |
| (-659.5, 19.5) | 14.2854, osm:way/34575500, bridge | 14.2854, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 20.5) | 14.2817, osm:way/34575500, bridge | 14.2817, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 21.5) | 14.278, osm:way/34575500, bridge | 14.278, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 22.5) | 14.2743, osm:way/34575500, bridge | 14.2743, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-658.5, 21.5) | 14.2478, osm:way/34575500, bridge | 14.2478, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 23.5) | 14.2705, osm:way/34575500, bridge | 14.2705, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-658.5, 22.5) | 14.2441, osm:way/34575500, bridge | 14.2441, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 24.5) | 14.2668, osm:way/34575500, bridge | 14.2668, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-658.5, 23.5) | 14.2404, osm:way/34575500, bridge | 14.2404, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 25.5) | 15.2631, osm:way/34575500, bridge | 15.2631, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-658.5, 24.5) | 14.2367, osm:way/34575500, bridge | 14.2367, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 26.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-658.5, 25.5) | 15.2329, osm:way/34575500, bridge | 15.233, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 27.5) | 7.1611, bank:osm:relation/2315576, terrain | 7.1611, bank:osm:relation/2315576, terrain | 7.9186 | 7.1611 | bank:osm:relation/2315576 | 0.7575 |
| (-658.5, 26.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 28.5) | 7.1005, bank:osm:relation/2315576, terrain | 7.1005, bank:osm:relation/2315576, terrain | 7.9186 | 7.1005 | bank:osm:relation/2315576 | 0.8181 |
| (-658.5, 27.5) | 7.5946, bank:osm:relation/2315576, terrain | 7.5946, bank:osm:relation/2315576, terrain | 7.9186 | 7.5946 | bank:osm:relation/2315576 | 0.324 |
| (-659.5, 29.5) | 7.0459, bank:osm:relation/2315576, terrain | 7.0459, bank:osm:relation/2315576, terrain | 7.9186 | 7.0459 | bank:osm:relation/2315576 | 0.8727 |
| (-658.5, 28.5) | 7.5453, bank:osm:relation/2315576, terrain | 7.5453, bank:osm:relation/2315576, terrain | 7.9186 | 7.5453 | bank:osm:relation/2315576 | 0.3733 |
| (-658.5, 29.5) | 7.4928, bank:osm:relation/2315576, terrain | 7.4928, bank:osm:relation/2315576, terrain | 7.9186 | 7.4928 | bank:osm:relation/2315576 | 0.4257 |
| (-658.5, 30.5) | 7.4356, bank:osm:relation/2315576, terrain | 7.4356, bank:osm:relation/2315576, terrain | 7.9186 | 7.4356 | bank:osm:relation/2315576 | 0.483 |
| (-658.5, 31.5) | 7.3795, bank:osm:relation/2315576, terrain | 7.3795, bank:osm:relation/2315576, terrain | 7.9186 | 7.3795 | bank:osm:relation/2315576 | 0.5391 |
| (-658.5, 32.5) | 7.3221, bank:osm:relation/2315576, terrain | 7.3221, bank:osm:relation/2315576, terrain | 7.9186 | 7.3221 | bank:osm:relation/2315576 | 0.5964 |
| (-658.5, 33.5) | 7.2688, bank:osm:relation/2315576, terrain | 7.2688, bank:osm:relation/2315576, terrain | 7.9186 | 7.2688 | bank:osm:relation/2315576 | 0.6498 |
| (-658.5, 34.5) | 7.2075, bank:osm:relation/2315576, terrain | 7.2075, bank:osm:relation/2315576, terrain | 7.9186 | 7.2075 | bank:osm:relation/2315576 | 0.7111 |
| (-658.5, 35.5) | 7.1535, bank:osm:relation/2315576, terrain | 7.1535, bank:osm:relation/2315576, terrain | 7.9186 | 7.1535 | bank:osm:relation/2315576 | 0.7651 |
| (-657.5, 34.5) | 7.6936, bank:osm:relation/2315576, terrain | 7.6936, bank:osm:relation/2315576, terrain | 7.9186 | 7.6936 | bank:osm:relation/2315576 | 0.225 |
| (-658.5, 36.5) | 7.0992, bank:osm:relation/2315576, terrain | 7.0992, bank:osm:relation/2315576, terrain | 7.9186 | 7.0992 | bank:osm:relation/2315576 | 0.8194 |
| (-657.5, 35.5) | 7.6413, bank:osm:relation/2315576, terrain | 7.6413, bank:osm:relation/2315576, terrain | 7.9186 | 7.6413 | bank:osm:relation/2315576 | 0.2773 |
| (-658.5, 37.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-657.5, 36.5) | 7.5895, bank:osm:relation/2315576, terrain | 7.5895, bank:osm:relation/2315576, terrain | 7.9186 | 7.5895 | bank:osm:relation/2315576 | 0.3291 |
| (-658.5, 38.5) | 19.7404, osm:way/317417201, bridge | 19.7404, osm:way/317417201, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-657.5, 37.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-658.5, 39.5) | 18.7502, osm:way/317417201, bridge | 18.7502, osm:way/317417201, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-657.5, 38.5) | 19.8198, osm:way/317417201, bridge | 19.8198, osm:way/317417201, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-657.5, 39.5) | 18.8296, osm:way/317417201, bridge | 18.8296, osm:way/317417201, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-657.5, 40.5) | 18.8393, osm:way/317417201, bridge | 18.8393, osm:way/317417201, bridge | 7.9186 | 6.4139 | terrain:grid | 1.5047 |
| (-657.5, 41.5) | 18.8491, osm:way/317417201, bridge | 18.8491, osm:way/317417201, bridge | 7.9186 | 6.4046 | terrain:grid | 1.514 |
| (-656.5, 40.5) | 18.9187, osm:way/317417201, bridge | 18.9187, osm:way/317417201, bridge | 7.9186 | 6.4139 | terrain:grid | 1.5047 |
| (-657.5, 42.5) | 19.8588, osm:way/317417201, bridge | 19.8588, osm:way/317417201, bridge | 7.9186 | 6.3953 | terrain:grid | 1.5233 |
| (-656.5, 41.5) | 18.9285, osm:way/317417201, bridge | 18.9285, osm:way/317417201, bridge | 7.9186 | 6.4046 | terrain:grid | 1.514 |
| (-656.5, 42.5) | 19.9382, osm:way/317417201, bridge | 19.9382, osm:way/317417201, bridge | 7.9186 | 6.3953 | terrain:grid | 1.5233 |
| (-656.5, 43.5) | 6.386, terrain:grid, terrain | 6.386, terrain:grid, terrain | 7.9186 | 6.386 | terrain:grid | 1.5326 |
| (-656.5, 44.5) | 7.6898, bank:osm:relation/2315576, terrain | 7.6898, bank:osm:relation/2315576, terrain | 7.9186 | 7.6898 | bank:osm:relation/2315576 | 0.2287 |
| (-656.5, 45.5) | 7.6427, bank:osm:relation/2315576, terrain | 7.6427, bank:osm:relation/2315576, terrain | 7.9186 | 7.6427 | bank:osm:relation/2315576 | 0.2759 |
| (-657.5, 44.5) | 7.2328, bank:osm:relation/2315576, terrain | 7.2328, bank:osm:relation/2315576, terrain | 7.9186 | 7.2328 | bank:osm:relation/2315576 | 0.6858 |
| (-656.5, 46.5) | 7.5854, bank:osm:relation/2315576, terrain | 7.5854, bank:osm:relation/2315576, terrain | 7.9186 | 7.5854 | bank:osm:relation/2315576 | 0.3332 |
| (-657.5, 45.5) | 7.1856, bank:osm:relation/2315576, terrain | 7.1856, bank:osm:relation/2315576, terrain | 7.9186 | 7.1856 | bank:osm:relation/2315576 | 0.733 |
| (-656.5, 47.5) | 7.5367, bank:osm:relation/2315576, terrain | 7.5367, bank:osm:relation/2315576, terrain | 7.9186 | 7.5367 | bank:osm:relation/2315576 | 0.3819 |
| (-657.5, 46.5) | 7.1132, bank:osm:relation/2315576, terrain | 7.1132, bank:osm:relation/2315576, terrain | 7.9186 | 7.1132 | bank:osm:relation/2315576 | 0.8054 |
| (-657.5, 47.5) | 7.0622, bank:osm:relation/2315576, terrain | 7.0622, bank:osm:relation/2315576, terrain | 7.9186 | 7.0622 | bank:osm:relation/2315576 | 0.8564 |

#### `water_shore_step:col#4` (class D)

Blocked strips within reach (`shore_ramp_blocked_m` of the body: {'water:osm:relation/2315576': 192.5}):

* bank strip (-607.922, 172.352, 5.899) -> (-608.825, 170.586, 5.899) (1.983 m): line 2.625 osm:way/4752301, osm:way/4758298
* bank strip (-608.825, 170.586, 5.899) -> (-609.727, 168.82, 5.899) (1.983 m): line 2.625 osm:way/4752301, osm:way/4758298
* bank strip (-609.727, 168.82, 5.899) -> (-610.63, 167.054, 5.899) (1.983 m): line 2.625 osm:way/4752301, osm:way/4758298
* bank strip (-610.63, 167.054, 5.899) -> (-611.532, 165.288, 5.899) (1.983 m): line 2.625 osm:way/4752301, osm:way/4758298
* bank strip (-611.532, 165.288, 5.899) -> (-612.435, 163.522, 5.899) (1.983 m): line 2.625 osm:way/4752301, osm:way/4758298
* bank strip (-634.955, 119.687, 5.899) -> (-635.93, 118.129, 5.899) (1.838 m): line 2.0 osm:way/83926163
* bank strip (-632.685, 24.949, 5.899) -> (-632.694, 26.933, 5.899) (1.984 m): line 7.5 osm:way/34575500
* bank strip (-632.694, 26.933, 5.899) -> (-632.702, 28.917, 5.899) (1.984 m): line 7.5 osm:way/34575500
* bank strip (-632.702, 28.917, 5.899) -> (-632.711, 30.901, 5.899) (1.984 m): line 7.5 osm:way/34575500
* bank strip (-632.753, 40.823, 5.899) -> (-632.762, 42.807, 5.899) (1.984 m): line 2.625 osm:way/317417201
* bank strip (-632.762, 42.807, 5.899) -> (-632.77, 44.791, 5.899) (1.984 m): line 2.625 osm:way/317417201
* bank strip (-632.77, 44.791, 5.899) -> (-632.778, 46.775, 5.899) (1.984 m): line 2.625 osm:way/317417201
* bank strip (-632.795, 50.744, 5.899) -> (-632.804, 52.728, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.804, 52.728, 5.899) -> (-632.812, 54.712, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.812, 54.712, 5.899) -> (-632.821, 56.696, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.821, 56.696, 5.899) -> (-632.829, 58.681, 5.899) (1.985 m): line 5.875 osm:way/23615351
* bank strip (-632.829, 58.681, 5.899) -> (-632.838, 60.665, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.838, 60.665, 5.899) -> (-632.846, 62.649, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.846, 62.649, 5.899) -> (-632.855, 64.633, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.855, 64.633, 5.899) -> (-632.863, 66.618, 5.899) (1.985 m): line 4.25 osm:way/214883367, osm:way/34575263; line 5.875 osm:way/23615351
* bank strip (-632.863, 66.618, 5.899) -> (-632.872, 68.602, 5.899) (1.984 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-632.872, 68.602, 5.899) -> (-632.88, 70.586, 5.899) (1.984 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-632.88, 70.586, 5.899) -> (-632.889, 72.57, 5.899) (1.984 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-632.889, 72.57, 5.899) -> (-632.897, 74.554, 5.899) (1.984 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-632.897, 74.554, 5.899) -> (-632.906, 76.539, 5.899) (1.985 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-616.292, 113.58, 5.899) -> (-615.439, 115.301, 5.899) (1.921 m): line 2.0 osm:way/83926163
* bank strip (-615.439, 115.301, 5.899) -> (-614.586, 117.021, 5.899) (1.92 m): line 2.0 osm:way/83926163
* bank strip (-614.586, 117.021, 5.899) -> (-613.733, 118.741, 5.899) (1.92 m): line 2.0 osm:way/83926163
* bank strip (-613.733, 118.741, 5.899) -> (-612.88, 120.462, 5.899) (1.921 m): line 2.0 osm:way/83926163
* bank strip (-600.557, 147.105, 5.899) -> (-599.763, 148.93, 5.899) (1.99 m): line 2.625 osm:way/4752301, osm:way/4758298
* bank strip (-599.763, 148.93, 5.899) -> (-598.97, 150.755, 5.899) (1.99 m): line 2.625 osm:way/4752301, osm:way/4758298
* bank strip (-598.97, 150.755, 5.899) -> (-598.176, 152.58, 5.899) (1.99 m): line 2.625 osm:way/4752301, osm:way/4758298
* bank strip (-598.176, 152.58, 5.899) -> (-597.382, 154.405, 5.899) (1.99 m): line 2.625 osm:way/4752301, osm:way/4758298
* bank strip (-597.382, 154.405, 5.899) -> (-596.588, 156.23, 5.899) (1.99 m): line 2.625 osm:way/4752301, osm:way/4758298

| Cell XY | Collision top (z, mb_id, class) | Visual top (z, owner, category) | Sheet z (col) | Outside z (col) | Outside owner | Offset (m) |
|---|---|---|---|---|---|---|
| (-632.5, 28.5) | 13.6103, osm:way/34575500, bridge | 13.6103, osm:way/34575500, bridge | 7.9186 | 6.3701 | terrain:grid | 1.5484 |
| (-632.5, 29.5) | 6.3811, terrain:grid, terrain | 6.3811, terrain:grid, terrain | 7.9186 | 6.3811 | terrain:grid | 1.5375 |
| (-631.5, 28.5) | 13.5309, osm:way/34575500, bridge | 13.5309, osm:way/34575500, bridge | 7.9186 | 6.3829 | terrain:grid | 1.5356 |
| (-632.5, 30.5) | 6.3866, terrain:grid, terrain | 6.3866, terrain:grid, terrain | 7.9186 | 6.3866 | terrain:grid | 1.532 |
| (-631.5, 29.5) | 6.3939, terrain:grid, terrain | 6.3939, terrain:grid, terrain | 7.9186 | 6.3939 | terrain:grid | 1.5247 |
| (-631.5, 30.5) | 6.3994, terrain:grid, terrain | 6.3994, terrain:grid, terrain | 7.9186 | 6.3994 | terrain:grid | 1.5192 |
| (-631.5, 31.5) | 7.3142, bank:osm:relation/2315576, terrain | 7.3142, bank:osm:relation/2315576, terrain | 7.9186 | 7.3142 | bank:osm:relation/2315576 | 0.6044 |
| (-631.5, 32.5) | 7.312, bank:osm:relation/2315576, terrain | 7.312, bank:osm:relation/2315576, terrain | 7.9186 | 7.312 | bank:osm:relation/2315576 | 0.6066 |
| (-631.5, 33.5) | 7.3096, bank:osm:relation/2315576, terrain | 7.3096, bank:osm:relation/2315576, terrain | 7.9186 | 7.3096 | bank:osm:relation/2315576 | 0.6089 |
| (-631.5, 34.5) | 7.3075, bank:osm:relation/2315576, terrain | 7.3075, bank:osm:relation/2315576, terrain | 7.9186 | 7.3075 | bank:osm:relation/2315576 | 0.6111 |
| (-631.5, 35.5) | 7.3051, bank:osm:relation/2315576, terrain | 7.3051, bank:osm:relation/2315576, terrain | 7.9186 | 7.3051 | bank:osm:relation/2315576 | 0.6135 |
| (-631.5, 36.5) | 7.3029, bank:osm:relation/2315576, terrain | 7.3029, bank:osm:relation/2315576, terrain | 7.9186 | 7.3029 | bank:osm:relation/2315576 | 0.6156 |
| (-631.5, 37.5) | 7.3005, bank:osm:relation/2315576, terrain | 7.3005, bank:osm:relation/2315576, terrain | 7.9186 | 7.3005 | bank:osm:relation/2315576 | 0.618 |
| (-631.5, 38.5) | 7.2984, bank:osm:relation/2315576, terrain | 7.2984, bank:osm:relation/2315576, terrain | 7.9186 | 7.2984 | bank:osm:relation/2315576 | 0.6202 |
| (-631.5, 39.5) | 7.3024, bank:osm:relation/2315576, terrain | 7.3024, bank:osm:relation/2315576, terrain | 7.9186 | 7.3024 | bank:osm:relation/2315576 | 0.6161 |
| (-631.5, 40.5) | 7.302, bank:osm:relation/2315576, terrain | 7.302, bank:osm:relation/2315576, terrain | 7.9186 | 7.302 | bank:osm:relation/2315576 | 0.6166 |
| (-631.5, 41.5) | 6.4158, terrain:grid, terrain | 6.4158, terrain:grid, terrain | 7.9186 | 6.4158 | terrain:grid | 1.5028 |
| (-631.5, 42.5) | 18.5019, osm:way/317417201, bridge | 18.5019, osm:way/317417201, bridge | 7.9186 | 6.4158 | terrain:grid | 1.5028 |
| (-632.5, 41.5) | 19.5829, osm:way/317417201, bridge | 19.5829, osm:way/317417201, bridge | 7.9186 | 6.4139 | terrain:grid | 1.5047 |
| (-631.5, 43.5) | 18.4931, osm:way/317417201, bridge | 18.4931, osm:way/317417201, bridge | 7.9186 | 6.4158 | terrain:grid | 1.5028 |
| (-632.5, 42.5) | 18.574, osm:way/317417201, bridge | 18.5741, osm:way/317417201, bridge | 7.9186 | 6.4139 | terrain:grid | 1.5047 |
| (-631.5, 44.5) | 18.4843, osm:way/317417201, bridge | 18.4843, osm:way/317417201, bridge | 7.9186 | 6.4158 | terrain:grid | 1.5028 |
| (-632.5, 43.5) | 18.5652, osm:way/317417201, bridge | 18.5652, osm:way/317417201, bridge | 7.9186 | 6.4139 | terrain:grid | 1.5047 |
| (-631.5, 45.5) | 18.4755, osm:way/317417201, bridge | 18.4755, osm:way/317417201, bridge | 7.9186 | 6.4158 | terrain:grid | 1.5028 |
| (-632.5, 44.5) | 18.5564, osm:way/317417201, bridge | 18.5564, osm:way/317417201, bridge | 7.9186 | 6.4139 | terrain:grid | 1.5047 |
| (-631.5, 46.5) | 6.4158, terrain:grid, terrain | 6.4158, terrain:grid, terrain | 7.9186 | 6.4158 | terrain:grid | 1.5028 |
| (-632.5, 45.5) | 19.5476, osm:way/317417201, bridge | 19.5476, osm:way/317417201, bridge | 7.9186 | 6.4139 | terrain:grid | 1.5047 |
| (-631.5, 47.5) | 7.2849, bank:osm:relation/2315576, terrain | 7.2849, bank:osm:relation/2315576, terrain | 7.9186 | 7.2849 | bank:osm:relation/2315576 | 0.6337 |
| (-632.5, 46.5) | 6.4139, terrain:grid, terrain | 6.4139, terrain:grid, terrain | 7.9186 | 6.4139 | terrain:grid | 1.5047 |
| (-631.5, 48.5) | 7.2827, bank:osm:relation/2315576, terrain | 7.2827, bank:osm:relation/2315576, terrain | 7.9186 | 7.2827 | bank:osm:relation/2315576 | 0.6358 |
| (-631.5, 49.5) | 7.2814, bank:osm:relation/2315576, terrain | 7.2814, bank:osm:relation/2315576, terrain | 7.9186 | 7.2814 | bank:osm:relation/2315576 | 0.6372 |
| (-631.5, 50.5) | 7.2795, bank:osm:relation/2315576, terrain | 7.2795, bank:osm:relation/2315576, terrain | 7.9186 | 7.2795 | bank:osm:relation/2315576 | 0.6391 |
| (-631.5, 51.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 52.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 51.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 53.5) | 15.1014, osm:way/23615351, bridge | 15.1014, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 52.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 54.5) | 14.1056, osm:way/23615351, bridge | 14.1056, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 53.5) | 14.0668, osm:way/23615351, bridge | 14.0668, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 55.5) | 14.1099, osm:way/23615351, bridge | 14.1099, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 54.5) | 14.071, osm:way/23615351, bridge | 14.071, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 56.5) | 14.1141, osm:way/23615351, bridge | 14.1141, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 55.5) | 14.0752, osm:way/23615351, bridge | 14.0752, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 57.5) | 14.1183, osm:way/23615351, bridge | 14.1183, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 56.5) | 14.0795, osm:way/23615351, bridge | 14.0795, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 58.5) | 14.1225, osm:way/23615351, bridge | 14.1226, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 57.5) | 14.0837, osm:way/23615351, bridge | 14.0837, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 59.5) | 14.1268, osm:way/23615351, bridge | 14.1268, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 58.5) | 14.0879, osm:way/23615351, bridge | 14.0879, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 60.5) | 14.131, osm:way/23615351, bridge | 14.131, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 59.5) | 14.0922, osm:way/23615351, bridge | 14.0922, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 61.5) | 14.1352, osm:way/23615351, bridge | 14.1352, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 60.5) | 14.0964, osm:way/23615351, bridge | 14.0964, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 62.5) | 14.1395, osm:way/23615351, bridge | 14.1395, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 61.5) | 14.1006, osm:way/23615351, bridge | 14.1006, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 63.5) | 14.1437, osm:way/23615351, bridge | 14.1437, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 62.5) | 14.1049, osm:way/23615351, bridge | 14.1049, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 64.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 63.5) | 14.1091, osm:way/23615351, bridge | 14.1091, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 65.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 64.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 66.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 65.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 67.5) | 10.0307, osm:way/214883367, bridge | 10.0307, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 66.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 68.5) | 10.0217, osm:way/214883367, bridge | 10.0217, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 67.5) | 10.1102, osm:way/214883367, bridge | 10.1102, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 69.5) | 10.0127, osm:way/214883367, bridge | 10.0127, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 68.5) | 10.1012, osm:way/214883367, bridge | 10.1012, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 70.5) | 10.0038, osm:way/214883367, bridge | 10.0038, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 69.5) | 10.0922, osm:way/214883367, bridge | 10.0922, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 71.5) | 9.9948, osm:way/214883367, bridge | 9.9948, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 70.5) | 10.0833, osm:way/214883367, bridge | 10.0833, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 72.5) | 9.9859, osm:way/214883367, bridge | 9.9859, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 71.5) | 10.0743, osm:way/214883367, bridge | 10.0743, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 73.5) | 9.9769, osm:way/214883367, bridge | 9.9769, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 72.5) | 10.0654, osm:way/214883367, bridge | 10.0654, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 74.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 73.5) | 10.0564, osm:way/214883367, bridge | 10.0564, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 75.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 74.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 76.5) | 7.2176, bank:osm:relation/2315576, terrain | 7.2176, bank:osm:relation/2315576, terrain | 7.9186 | 7.2176 | bank:osm:relation/2315576 | 0.701 |
| (-632.5, 75.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 77.5) | 7.3251, bank:osm:relation/2315576, terrain | 7.3251, bank:osm:relation/2315576, terrain | 7.9186 | 7.3251 | bank:osm:relation/2315576 | 0.5935 |
| (-632.5, 76.5) | 7.6991, bank:osm:relation/2315576, terrain | 7.6991, bank:osm:relation/2315576, terrain | 7.9186 | 7.6991 | bank:osm:relation/2315576 | 0.2195 |
| (-631.5, 78.5) | 7.4326, bank:osm:relation/2315576, terrain | 7.4326, bank:osm:relation/2315576, terrain | 7.9186 | 7.4326 | bank:osm:relation/2315576 | 0.486 |
| (-631.5, 79.5) | 7.5401, bank:osm:relation/2315576, terrain | 7.5401, bank:osm:relation/2315576, terrain | 7.9186 | 7.5401 | bank:osm:relation/2315576 | 0.3785 |
| (-630.5, 78.5) | 6.9511, bank:osm:relation/2315576, terrain | 6.9511, bank:osm:relation/2315576, terrain | 7.9186 | 6.9511 | bank:osm:relation/2315576 | 0.9674 |
| (-631.5, 80.5) | 7.6476, bank:osm:relation/2315576, terrain | 7.6476, bank:osm:relation/2315576, terrain | 7.9186 | 7.6476 | bank:osm:relation/2315576 | 0.271 |
| (-630.5, 79.5) | 7.0586, bank:osm:relation/2315576, terrain | 7.0586, bank:osm:relation/2315576, terrain | 7.9186 | 7.0586 | bank:osm:relation/2315576 | 0.8599 |
| (-630.5, 80.5) | 7.1661, bank:osm:relation/2315576, terrain | 7.1661, bank:osm:relation/2315576, terrain | 7.9186 | 7.1661 | bank:osm:relation/2315576 | 0.7524 |
| (-630.5, 81.5) | 7.2736, bank:osm:relation/2315576, terrain | 7.2736, bank:osm:relation/2315576, terrain | 7.9186 | 7.2736 | bank:osm:relation/2315576 | 0.6449 |
| (-630.5, 82.5) | 7.3811, bank:osm:relation/2315576, terrain | 7.3811, bank:osm:relation/2315576, terrain | 7.9186 | 7.3811 | bank:osm:relation/2315576 | 0.5374 |
| (-630.5, 83.5) | 7.4886, bank:osm:relation/2315576, terrain | 7.4886, bank:osm:relation/2315576, terrain | 7.9186 | 7.4886 | bank:osm:relation/2315576 | 0.43 |
| (-630.5, 84.5) | 7.5961, bank:osm:relation/2315576, terrain | 7.5961, bank:osm:relation/2315576, terrain | 7.9186 | 7.5961 | bank:osm:relation/2315576 | 0.3225 |
| (-629.5, 83.5) | 7.0072, bank:osm:relation/2315576, terrain | 7.0072, bank:osm:relation/2315576, terrain | 7.9186 | 7.0072 | bank:osm:relation/2315576 | 0.9114 |
| (-629.5, 84.5) | 7.1214, bank:osm:relation/2315576, terrain | 7.1214, bank:osm:relation/2315576, terrain | 7.9186 | 7.1214 | bank:osm:relation/2315576 | 0.7971 |
| (-629.5, 85.5) | 7.3219, bank:osm:relation/2315576, terrain | 7.3219, bank:osm:relation/2315576, terrain | 7.9186 | 7.3219 | bank:osm:relation/2315576 | 0.5967 |
| (-629.5, 86.5) | 7.5223, bank:osm:relation/2315576, terrain | 7.5223, bank:osm:relation/2315576, terrain | 7.9186 | 7.5223 | bank:osm:relation/2315576 | 0.3963 |
| (-628.5, 86.5) | 7.0715, bank:osm:relation/2315576, terrain | 7.0715, bank:osm:relation/2315576, terrain | 7.9186 | 7.0715 | bank:osm:relation/2315576 | 0.847 |
| (-628.5, 87.5) | 7.272, bank:osm:relation/2315576, terrain | 7.272, bank:osm:relation/2315576, terrain | 7.9186 | 7.272 | bank:osm:relation/2315576 | 0.6466 |
| (-628.5, 88.5) | 7.4724, bank:osm:relation/2315576, terrain | 7.4724, bank:osm:relation/2315576, terrain | 7.9186 | 7.4724 | bank:osm:relation/2315576 | 0.4462 |
| (-628.5, 89.5) | 7.6729, bank:osm:relation/2315576, terrain | 7.6729, bank:osm:relation/2315576, terrain | 7.9186 | 7.6729 | bank:osm:relation/2315576 | 0.2457 |
| (-627.5, 88.5) | 7.0216, bank:osm:relation/2315576, terrain | 7.0216, bank:osm:relation/2315576, terrain | 7.9186 | 7.0216 | bank:osm:relation/2315576 | 0.8969 |
| (-627.5, 89.5) | 7.2221, bank:osm:relation/2315576, terrain | 7.2221, bank:osm:relation/2315576, terrain | 7.9186 | 7.2221 | bank:osm:relation/2315576 | 0.6965 |
| (-627.5, 90.5) | 7.4225, bank:osm:relation/2315576, terrain | 7.4225, bank:osm:relation/2315576, terrain | 7.9186 | 7.4225 | bank:osm:relation/2315576 | 0.4961 |
| (-627.5, 91.5) | 7.6229, bank:osm:relation/2315576, terrain | 7.6229, bank:osm:relation/2315576, terrain | 7.9186 | 7.6229 | bank:osm:relation/2315576 | 0.2956 |
| (-626.5, 91.5) | 7.1904, bank:osm:relation/2315576, terrain | 7.1904, bank:osm:relation/2315576, terrain | 7.9186 | 7.1904 | bank:osm:relation/2315576 | 0.7282 |
| (-626.5, 92.5) | 7.4325, bank:osm:relation/2315576, terrain | 7.4325, bank:osm:relation/2315576, terrain | 7.9186 | 7.4325 | bank:osm:relation/2315576 | 0.4861 |
| (-626.5, 93.5) | 7.6746, bank:osm:relation/2315576, terrain | 7.6746, bank:osm:relation/2315576, terrain | 7.9186 | 7.6746 | bank:osm:relation/2315576 | 0.244 |
| (-625.5, 93.5) | 7.2447, bank:osm:relation/2315576, terrain | 7.2447, bank:osm:relation/2315576, terrain | 7.9186 | 7.2447 | bank:osm:relation/2315576 | 0.6739 |
| (-625.5, 94.5) | 7.4868, bank:osm:relation/2315576, terrain | 7.4868, bank:osm:relation/2315576, terrain | 7.9186 | 7.4868 | bank:osm:relation/2315576 | 0.4318 |
| (-624.5, 94.5) | 7.0569, bank:osm:relation/2315576, terrain | 7.0569, bank:osm:relation/2315576, terrain | 7.9186 | 7.0569 | bank:osm:relation/2315576 | 0.8617 |
| (-624.5, 95.5) | 7.299, bank:osm:relation/2315576, terrain | 7.299, bank:osm:relation/2315576, terrain | 7.9186 | 7.299 | bank:osm:relation/2315576 | 0.6196 |
| (-624.5, 96.5) | 7.5411, bank:osm:relation/2315576, terrain | 7.5411, bank:osm:relation/2315576, terrain | 7.9186 | 7.5411 | bank:osm:relation/2315576 | 0.3775 |
| (-623.5, 96.5) | 7.1112, bank:osm:relation/2315576, terrain | 7.1112, bank:osm:relation/2315576, terrain | 7.9186 | 7.1112 | bank:osm:relation/2315576 | 0.8074 |
| (-623.5, 97.5) | 7.3533, bank:osm:relation/2315576, terrain | 7.3533, bank:osm:relation/2315576, terrain | 7.9186 | 7.3533 | bank:osm:relation/2315576 | 0.5653 |
| (-623.5, 98.5) | 7.5954, bank:osm:relation/2315576, terrain | 7.5954, bank:osm:relation/2315576, terrain | 7.9186 | 7.5954 | bank:osm:relation/2315576 | 0.3232 |
| (-622.5, 98.5) | 7.1655, bank:osm:relation/2315576, terrain | 7.1655, bank:osm:relation/2315576, terrain | 7.9186 | 7.1655 | bank:osm:relation/2315576 | 0.7531 |
| (-622.5, 99.5) | 7.4076, bank:osm:relation/2315576, terrain | 7.4076, bank:osm:relation/2315576, terrain | 7.9186 | 7.4076 | bank:osm:relation/2315576 | 0.511 |
| (-622.5, 100.5) | 7.6496, bank:osm:relation/2315576, terrain | 7.6496, bank:osm:relation/2315576, terrain | 7.9186 | 7.6496 | bank:osm:relation/2315576 | 0.2689 |
| (-621.5, 100.5) | 7.2198, bank:osm:relation/2315576, terrain | 7.2198, bank:osm:relation/2315576, terrain | 7.9186 | 7.2198 | bank:osm:relation/2315576 | 0.6988 |
| (-621.5, 101.5) | 7.4619, bank:osm:relation/2315576, terrain | 7.4619, bank:osm:relation/2315576, terrain | 7.9186 | 7.4619 | bank:osm:relation/2315576 | 0.4567 |
| (-621.5, 102.5) | 7.7039, bank:osm:relation/2315576, terrain | 7.7039, bank:osm:relation/2315576, terrain | 7.9186 | 7.7039 | bank:osm:relation/2315576 | 0.2147 |
| (-620.5, 102.5) | 7.2741, bank:osm:relation/2315576, terrain | 7.2741, bank:osm:relation/2315576, terrain | 7.9186 | 7.2741 | bank:osm:relation/2315576 | 0.6445 |
| (-620.5, 103.5) | 7.5161, bank:osm:relation/2315576, terrain | 7.5161, bank:osm:relation/2315576, terrain | 7.9186 | 7.5161 | bank:osm:relation/2315576 | 0.4024 |
| (-619.5, 103.5) | 7.0863, bank:osm:relation/2315576, terrain | 7.0863, bank:osm:relation/2315576, terrain | 7.9186 | 7.0863 | bank:osm:relation/2315576 | 0.8323 |
| (-619.5, 104.5) | 7.3265, bank:osm:relation/2315576, terrain | 7.3265, bank:osm:relation/2315576, terrain | 7.9186 | 7.3265 | bank:osm:relation/2315576 | 0.5921 |
| (-619.5, 105.5) | 7.5456, bank:osm:relation/2315576, terrain | 7.5456, bank:osm:relation/2315576, terrain | 7.9186 | 7.5456 | bank:osm:relation/2315576 | 0.3729 |
| (-618.5, 105.5) | 7.1037, bank:osm:relation/2315576, terrain | 7.1037, bank:osm:relation/2315576, terrain | 7.9186 | 7.1037 | bank:osm:relation/2315576 | 0.8149 |
| (-618.5, 106.5) | 7.3228, bank:osm:relation/2315576, terrain | 7.3228, bank:osm:relation/2315576, terrain | 7.9186 | 7.3228 | bank:osm:relation/2315576 | 0.5958 |
| (-618.5, 107.5) | 7.542, bank:osm:relation/2315576, terrain | 7.542, bank:osm:relation/2315576, terrain | 7.9186 | 7.542 | bank:osm:relation/2315576 | 0.3766 |
| (-617.5, 107.5) | 7.1, bank:osm:relation/2315576, terrain | 7.1, bank:osm:relation/2315576, terrain | 7.9186 | 7.1 | bank:osm:relation/2315576 | 0.8186 |
| (-617.5, 108.5) | 7.3191, bank:osm:relation/2315576, terrain | 7.3191, bank:osm:relation/2315576, terrain | 7.9186 | 7.3191 | bank:osm:relation/2315576 | 0.5994 |
| (-617.5, 109.5) | 7.5383, bank:osm:relation/2315576, terrain | 7.5383, bank:osm:relation/2315576, terrain | 7.9186 | 7.5383 | bank:osm:relation/2315576 | 0.3803 |
| (-616.5, 109.5) | 7.0963, bank:osm:relation/2315576, terrain | 7.0963, bank:osm:relation/2315576, terrain | 7.9186 | 7.0963 | bank:osm:relation/2315576 | 0.8223 |
| (-616.5, 110.5) | 7.3155, bank:osm:relation/2315576, terrain | 7.3155, bank:osm:relation/2315576, terrain | 7.9186 | 7.3155 | bank:osm:relation/2315576 | 0.6031 |
| (-616.5, 111.5) | 7.5346, bank:osm:relation/2315576, terrain | 7.5346, bank:osm:relation/2315576, terrain | 7.9186 | 7.5346 | bank:osm:relation/2315576 | 0.384 |
| (-615.5, 111.5) | 7.0927, bank:osm:relation/2315576, terrain | 7.0927, bank:osm:relation/2315576, terrain | 7.9186 | 7.0927 | bank:osm:relation/2315576 | 0.8259 |
| (-615.5, 112.5) | 7.3118, bank:osm:relation/2315576, terrain | 7.3118, bank:osm:relation/2315576, terrain | 7.9186 | 7.3118 | bank:osm:relation/2315576 | 0.6068 |
| (-615.5, 113.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-615.5, 114.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-614.5, 113.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-614.5, 114.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-614.5, 115.5) | 12.629, osm:way/83926163, bridge | 12.629, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-614.5, 116.5) | 11.6299, osm:way/83926163, bridge | 11.6299, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-613.5, 115.5) | 12.549, osm:way/83926163, bridge | 12.549, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-613.5, 116.5) | 11.5499, osm:way/83926163, bridge | 11.5499, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-613.5, 117.5) | 11.5508, osm:way/83926163, bridge | 11.5508, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-613.5, 118.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-612.5, 117.5) | 11.4708, osm:way/83926163, bridge | 11.4708, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-612.5, 118.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-612.5, 119.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-611.5, 119.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-611.5, 120.5) | 7.2971, bank:osm:relation/2315576, terrain | 7.2971, bank:osm:relation/2315576, terrain | 7.9186 | 7.2971 | bank:osm:relation/2315576 | 0.6214 |
| (-611.5, 121.5) | 7.5163, bank:osm:relation/2315576, terrain | 7.5163, bank:osm:relation/2315576, terrain | 7.9186 | 7.5163 | bank:osm:relation/2315576 | 0.4023 |
| (-610.5, 121.5) | 7.0743, bank:osm:relation/2315576, terrain | 7.0743, bank:osm:relation/2315576, terrain | 7.9186 | 7.0743 | bank:osm:relation/2315576 | 0.8443 |
| (-610.5, 122.5) | 7.2935, bank:osm:relation/2315576, terrain | 7.2935, bank:osm:relation/2315576, terrain | 7.9186 | 7.2935 | bank:osm:relation/2315576 | 0.6251 |
| (-610.5, 123.5) | 7.5126, bank:osm:relation/2315576, terrain | 7.5126, bank:osm:relation/2315576, terrain | 7.9186 | 7.5126 | bank:osm:relation/2315576 | 0.406 |
| (-609.5, 123.5) | 7.0706, bank:osm:relation/2315576, terrain | 7.0706, bank:osm:relation/2315576, terrain | 7.9186 | 7.0706 | bank:osm:relation/2315576 | 0.8479 |
| (-609.5, 124.5) | 7.2898, bank:osm:relation/2315576, terrain | 7.2898, bank:osm:relation/2315576, terrain | 7.9186 | 7.2898 | bank:osm:relation/2315576 | 0.6288 |
| (-609.5, 125.5) | 7.509, bank:osm:relation/2315576, terrain | 7.509, bank:osm:relation/2315576, terrain | 7.9186 | 7.509 | bank:osm:relation/2315576 | 0.4096 |
| (-608.5, 125.5) | 7.067, bank:osm:relation/2315576, terrain | 7.067, bank:osm:relation/2315576, terrain | 7.9186 | 7.067 | bank:osm:relation/2315576 | 0.8516 |
| (-608.5, 126.5) | 7.2861, bank:osm:relation/2315576, terrain | 7.2861, bank:osm:relation/2315576, terrain | 7.9186 | 7.2861 | bank:osm:relation/2315576 | 0.6324 |
| (-608.5, 127.5) | 7.5053, bank:osm:relation/2315576, terrain | 7.5053, bank:osm:relation/2315576, terrain | 7.9186 | 7.5053 | bank:osm:relation/2315576 | 0.4133 |
| (-607.5, 127.5) | 7.0633, bank:osm:relation/2315576, terrain | 7.0633, bank:osm:relation/2315576, terrain | 7.9186 | 7.0633 | bank:osm:relation/2315576 | 0.8553 |
| (-607.5, 128.5) | 7.2825, bank:osm:relation/2315576, terrain | 7.2825, bank:osm:relation/2315576, terrain | 7.9186 | 7.2825 | bank:osm:relation/2315576 | 0.6361 |
| (-607.5, 129.5) | 7.5016, bank:osm:relation/2315576, terrain | 7.5016, bank:osm:relation/2315576, terrain | 7.9186 | 7.5016 | bank:osm:relation/2315576 | 0.417 |
| (-606.5, 129.5) | 7.0596, bank:osm:relation/2315576, terrain | 7.0596, bank:osm:relation/2315576, terrain | 7.9186 | 7.0596 | bank:osm:relation/2315576 | 0.8589 |
| (-606.5, 130.5) | 7.2788, bank:osm:relation/2315576, terrain | 7.2788, bank:osm:relation/2315576, terrain | 7.9186 | 7.2788 | bank:osm:relation/2315576 | 0.6398 |
| (-606.5, 131.5) | 7.498, bank:osm:relation/2315576, terrain | 7.498, bank:osm:relation/2315576, terrain | 7.9186 | 7.498 | bank:osm:relation/2315576 | 0.4206 |
| (-606.5, 132.5) | 7.713, bank:osm:relation/2315576, terrain | 7.713, bank:osm:relation/2315576, terrain | 7.9186 | 7.713 | bank:osm:relation/2315576 | 0.2056 |
| (-605.5, 131.5) | 7.056, bank:osm:relation/2315576, terrain | 7.056, bank:osm:relation/2315576, terrain | 7.9186 | 7.056 | bank:osm:relation/2315576 | 0.8626 |
| (-605.5, 132.5) | 7.2606, bank:osm:relation/2315576, terrain | 7.2606, bank:osm:relation/2315576, terrain | 7.9186 | 7.2606 | bank:osm:relation/2315576 | 0.658 |
| (-605.5, 133.5) | 7.4574, bank:osm:relation/2315576, terrain | 7.4574, bank:osm:relation/2315576, terrain | 7.9186 | 7.4574 | bank:osm:relation/2315576 | 0.4612 |
| (-605.5, 134.5) | 7.6542, bank:osm:relation/2315576, terrain | 7.6542, bank:osm:relation/2315576, terrain | 7.9186 | 7.6542 | bank:osm:relation/2315576 | 0.2644 |
| (-604.5, 133.5) | 7.005, bank:osm:relation/2315576, terrain | 7.005, bank:osm:relation/2315576, terrain | 7.9186 | 7.005 | bank:osm:relation/2315576 | 0.9136 |
| (-604.5, 134.5) | 7.2018, bank:osm:relation/2315576, terrain | 7.2018, bank:osm:relation/2315576, terrain | 7.9186 | 7.2018 | bank:osm:relation/2315576 | 0.7168 |
| (-604.5, 135.5) | 7.3986, bank:osm:relation/2315576, terrain | 7.3986, bank:osm:relation/2315576, terrain | 7.9186 | 7.3986 | bank:osm:relation/2315576 | 0.52 |
| (-604.5, 136.5) | 7.5953, bank:osm:relation/2315576, terrain | 7.5953, bank:osm:relation/2315576, terrain | 7.9186 | 7.5953 | bank:osm:relation/2315576 | 0.3232 |
| (-603.5, 136.5) | 7.143, bank:osm:relation/2315576, terrain | 7.143, bank:osm:relation/2315576, terrain | 7.9186 | 7.143 | bank:osm:relation/2315576 | 0.7756 |
| (-603.5, 137.5) | 7.3397, bank:osm:relation/2315576, terrain | 7.3397, bank:osm:relation/2315576, terrain | 7.9186 | 7.3397 | bank:osm:relation/2315576 | 0.5788 |
| (-603.5, 138.5) | 7.5365, bank:osm:relation/2315576, terrain | 7.5365, bank:osm:relation/2315576, terrain | 7.9186 | 7.5365 | bank:osm:relation/2315576 | 0.3821 |
| (-602.5, 138.5) | 7.0841, bank:osm:relation/2315576, terrain | 7.0841, bank:osm:relation/2315576, terrain | 7.9186 | 7.0841 | bank:osm:relation/2315576 | 0.8344 |
| (-602.5, 139.5) | 7.2809, bank:osm:relation/2315576, terrain | 7.2809, bank:osm:relation/2315576, terrain | 7.9186 | 7.2809 | bank:osm:relation/2315576 | 0.6377 |
| (-602.5, 140.5) | 7.4777, bank:osm:relation/2315576, terrain | 7.4777, bank:osm:relation/2315576, terrain | 7.9186 | 7.4777 | bank:osm:relation/2315576 | 0.4409 |
| (-602.5, 141.5) | 7.6745, bank:osm:relation/2315576, terrain | 7.6745, bank:osm:relation/2315576, terrain | 7.9186 | 7.6745 | bank:osm:relation/2315576 | 0.2441 |
| (-601.5, 140.5) | 7.0253, bank:osm:relation/2315576, terrain | 7.0253, bank:osm:relation/2315576, terrain | 7.9186 | 7.0253 | bank:osm:relation/2315576 | 0.8933 |
| (-601.5, 141.5) | 7.2221, bank:osm:relation/2315576, terrain | 7.2221, bank:osm:relation/2315576, terrain | 7.9186 | 7.2221 | bank:osm:relation/2315576 | 0.6965 |
| (-601.5, 142.5) | 7.4189, bank:osm:relation/2315576, terrain | 7.4189, bank:osm:relation/2315576, terrain | 7.9186 | 7.4189 | bank:osm:relation/2315576 | 0.4997 |
| (-601.5, 143.5) | 7.6157, bank:osm:relation/2315576, terrain | 7.6157, bank:osm:relation/2315576, terrain | 7.9186 | 7.6157 | bank:osm:relation/2315576 | 0.3029 |
| (-600.5, 143.5) | 7.1633, bank:osm:relation/2315576, terrain | 7.1633, bank:osm:relation/2315576, terrain | 7.9186 | 7.1633 | bank:osm:relation/2315576 | 0.7553 |
| (-600.5, 144.5) | 7.3601, bank:osm:relation/2315576, terrain | 7.3601, bank:osm:relation/2315576, terrain | 7.9186 | 7.3601 | bank:osm:relation/2315576 | 0.5585 |
| (-600.5, 145.5) | 7.5569, bank:osm:relation/2315576, terrain | 7.5569, bank:osm:relation/2315576, terrain | 7.9186 | 7.5569 | bank:osm:relation/2315576 | 0.3617 |
| (-599.5, 145.5) | 7.1045, bank:osm:relation/2315576, terrain | 7.1045, bank:osm:relation/2315576, terrain | 7.9186 | 7.1045 | bank:osm:relation/2315576 | 0.8141 |
| (-599.5, 146.5) | 7.3013, bank:osm:relation/2315576, terrain | 7.3013, bank:osm:relation/2315576, terrain | 7.9186 | 7.3013 | bank:osm:relation/2315576 | 0.6173 |
| (-599.5, 147.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-599.5, 148.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-598.5, 147.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-599.5, 149.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-598.5, 148.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-598.5, 149.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-598.5, 150.5) | 19.0592, osm:way/4752301, bridge | 19.0592, osm:way/4752301, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-598.5, 151.5) | 19.054, osm:way/4752301, bridge | 19.054, osm:way/4752301, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-597.5, 150.5) | 19.0645, osm:way/4752301, bridge | 19.0645, osm:way/4752301, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-597.5, 151.5) | 19.059, osm:way/4752301, bridge | 19.059, osm:way/4752301, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-597.5, 152.5) | 19.0532, osm:way/4752301, bridge | 19.0532, osm:way/4752301, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-597.5, 153.5) | 19.0473, osm:way/4752301, bridge | 19.0473, osm:way/4752301, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-596.5, 152.5) | 19.0582, osm:way/4752301, bridge | 19.0582, osm:way/4752301, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-596.5, 153.5) | 20.0524, osm:way/4752301, bridge | 20.0524, osm:way/4752301, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-596.5, 154.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-596.5, 155.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-595.5, 154.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-595.5, 155.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-595.5, 156.5) | 7.4596, bank:osm:relation/2315576, terrain | 7.4596, bank:osm:relation/2315576, terrain | 7.9186 | 7.4596 | bank:osm:relation/2315576 | 0.459 |
| (-595.5, 157.5) | 7.6563, bank:osm:relation/2315576, terrain | 7.6563, bank:osm:relation/2315576, terrain | 7.9186 | 7.6563 | bank:osm:relation/2315576 | 0.2622 |
| (-594.5, 156.5) | 7.0072, bank:osm:relation/2315576, terrain | 7.0072, bank:osm:relation/2315576, terrain | 7.9186 | 7.0072 | bank:osm:relation/2315576 | 0.9114 |
| (-594.5, 157.5) | 7.2039, bank:osm:relation/2315576, terrain | 7.2039, bank:osm:relation/2315576, terrain | 7.9186 | 7.2039 | bank:osm:relation/2315576 | 0.7146 |
| (-594.5, 158.5) | 7.4007, bank:osm:relation/2315576, terrain | 7.4007, bank:osm:relation/2315576, terrain | 7.9186 | 7.4007 | bank:osm:relation/2315576 | 0.5178 |
| (-594.5, 159.5) | 7.5975, bank:osm:relation/2315576, terrain | 7.5975, bank:osm:relation/2315576, terrain | 7.9186 | 7.5975 | bank:osm:relation/2315576 | 0.3211 |
| (-593.5, 159.5) | 7.1451, bank:osm:relation/2315576, terrain | 7.1451, bank:osm:relation/2315576, terrain | 7.9186 | 7.1451 | bank:osm:relation/2315576 | 0.7735 |
| (-593.5, 160.5) | 7.3419, bank:osm:relation/2315576, terrain | 7.3419, bank:osm:relation/2315576, terrain | 7.9186 | 7.3419 | bank:osm:relation/2315576 | 0.5767 |
| (-593.5, 161.5) | 7.5387, bank:osm:relation/2315576, terrain | 7.5387, bank:osm:relation/2315576, terrain | 7.9186 | 7.5387 | bank:osm:relation/2315576 | 0.3799 |
| (-592.5, 161.5) | 7.0863, bank:osm:relation/2315576, terrain | 7.0863, bank:osm:relation/2315576, terrain | 7.9186 | 7.0863 | bank:osm:relation/2315576 | 0.8323 |
| (-592.5, 162.5) | 7.2831, bank:osm:relation/2315576, terrain | 7.2831, bank:osm:relation/2315576, terrain | 7.9186 | 7.2831 | bank:osm:relation/2315576 | 0.6355 |
| (-592.5, 163.5) | 7.4799, bank:osm:relation/2315576, terrain | 7.4799, bank:osm:relation/2315576, terrain | 7.9186 | 7.4799 | bank:osm:relation/2315576 | 0.4387 |
| (-592.5, 164.5) | 7.6767, bank:osm:relation/2315576, terrain | 7.6767, bank:osm:relation/2315576, terrain | 7.9186 | 7.6767 | bank:osm:relation/2315576 | 0.2419 |
| (-591.5, 163.5) | 7.0275, bank:osm:relation/2315576, terrain | 7.0275, bank:osm:relation/2315576, terrain | 7.9186 | 7.0275 | bank:osm:relation/2315576 | 0.8911 |
| (-591.5, 164.5) | 7.2243, bank:osm:relation/2315576, terrain | 7.2243, bank:osm:relation/2315576, terrain | 7.9186 | 7.2243 | bank:osm:relation/2315576 | 0.6943 |
| (-591.5, 165.5) | 7.4211, bank:osm:relation/2315576, terrain | 7.4211, bank:osm:relation/2315576, terrain | 7.9186 | 7.4211 | bank:osm:relation/2315576 | 0.4975 |
| (-591.5, 166.5) | 7.6179, bank:osm:relation/2315576, terrain | 7.6179, bank:osm:relation/2315576, terrain | 7.9186 | 7.6179 | bank:osm:relation/2315576 | 0.3007 |
| (-590.5, 166.5) | 7.1655, bank:osm:relation/2315576, terrain | 7.1655, bank:osm:relation/2315576, terrain | 7.9186 | 7.1655 | bank:osm:relation/2315576 | 0.7531 |
| (-590.5, 167.5) | 7.3622, bank:osm:relation/2315576, terrain | 7.3622, bank:osm:relation/2315576, terrain | 7.9186 | 7.3622 | bank:osm:relation/2315576 | 0.5563 |
| (-590.5, 168.5) | 7.559, bank:osm:relation/2315576, terrain | 7.559, bank:osm:relation/2315576, terrain | 7.9186 | 7.559 | bank:osm:relation/2315576 | 0.3596 |
| (-589.5, 168.5) | 7.104, bank:osm:relation/2315576, terrain | 7.104, bank:osm:relation/2315576, terrain | 7.9186 | 7.104 | bank:osm:relation/2315576 | 0.8145 |
| (-589.5, 169.5) | 7.2788, bank:osm:relation/2315576, terrain | 7.2788, bank:osm:relation/2315576, terrain | 7.9186 | 7.2788 | bank:osm:relation/2315576 | 0.6398 |
| (-589.5, 170.5) | 7.4535, bank:osm:relation/2315576, terrain | 7.4535, bank:osm:relation/2315576, terrain | 7.9186 | 7.4535 | bank:osm:relation/2315576 | 0.4651 |
| (-589.5, 171.5) | 7.6282, bank:osm:relation/2315576, terrain | 7.6282, bank:osm:relation/2315576, terrain | 7.9186 | 7.6282 | bank:osm:relation/2315576 | 0.2903 |
| (-588.5, 170.5) | 6.9922, bank:osm:relation/2315576, terrain | 6.9922, bank:osm:relation/2315576, terrain | 7.9186 | 6.9922 | bank:osm:relation/2315576 | 0.9264 |
| (-588.5, 171.5) | 7.1669, bank:osm:relation/2315576, terrain | 7.1669, bank:osm:relation/2315576, terrain | 7.9186 | 7.1669 | bank:osm:relation/2315576 | 0.7517 |
| (-588.5, 172.5) | 12.1501, scatter:osm:relation/7099311#192, vegetation | 12.1501, scatter:osm:relation/7099311#192, vegetation | 7.9186 | 7.3416 | bank:osm:relation/2315576 | 0.577 |
| (-588.5, 173.5) | 12.3461, scatter:osm:relation/7099311#192, vegetation | 12.3461, scatter:osm:relation/7099311#192, vegetation | 7.9186 | 7.5164 | bank:osm:relation/2315576 | 0.4022 |
| (-588.5, 174.5) | 7.6911, bank:osm:relation/2315576, terrain | 7.6911, bank:osm:relation/2315576, terrain | 7.9186 | 7.6911 | bank:osm:relation/2315576 | 0.2275 |
| (-587.5, 173.5) | 14.2996, scatter:osm:relation/7099311#192, vegetation | 14.2996, scatter:osm:relation/7099311#192, vegetation | 7.9186 | 7.055 | bank:osm:relation/2315576 | 0.8636 |
| (-587.5, 174.5) | 12.7741, scatter:osm:relation/7099311#192, vegetation | 12.7741, scatter:osm:relation/7099311#192, vegetation | 7.9186 | 7.2297 | bank:osm:relation/2315576 | 0.6888 |
| (-587.5, 175.5) | 7.4045, bank:osm:relation/2315576, terrain | 7.4045, bank:osm:relation/2315576, terrain | 7.9186 | 7.4045 | bank:osm:relation/2315576 | 0.5141 |
| (-587.5, 176.5) | 7.5792, bank:osm:relation/2315576, terrain | 7.5792, bank:osm:relation/2315576, terrain | 7.9186 | 7.5792 | bank:osm:relation/2315576 | 0.3394 |
| (-586.5, 176.5) | 7.1179, bank:osm:relation/2315576, terrain | 7.1179, bank:osm:relation/2315576, terrain | 7.9186 | 7.1179 | bank:osm:relation/2315576 | 0.8007 |
| (-586.5, 177.5) | 7.2926, bank:osm:relation/2315576, terrain | 7.2926, bank:osm:relation/2315576, terrain | 7.9186 | 7.2926 | bank:osm:relation/2315576 | 0.626 |
| (-586.5, 178.5) | 7.4673, bank:osm:relation/2315576, terrain | 7.4673, bank:osm:relation/2315576, terrain | 7.9186 | 7.4673 | bank:osm:relation/2315576 | 0.4513 |
| (-586.5, 179.5) | 7.6421, bank:osm:relation/2315576, terrain | 7.6421, bank:osm:relation/2315576, terrain | 7.9186 | 7.6421 | bank:osm:relation/2315576 | 0.2765 |
| (-585.5, 178.5) | 7.006, bank:osm:relation/2315576, terrain | 7.006, bank:osm:relation/2315576, terrain | 7.9186 | 7.006 | bank:osm:relation/2315576 | 0.9126 |
| (-585.5, 179.5) | 7.1807, bank:osm:relation/2315576, terrain | 7.1807, bank:osm:relation/2315576, terrain | 7.9186 | 7.1807 | bank:osm:relation/2315576 | 0.7379 |
| (-585.5, 180.5) | 7.3554, bank:osm:relation/2315576, terrain | 7.3554, bank:osm:relation/2315576, terrain | 7.9186 | 7.3554 | bank:osm:relation/2315576 | 0.5631 |
| (-585.5, 181.5) | 7.5302, bank:osm:relation/2315576, terrain | 7.5302, bank:osm:relation/2315576, terrain | 7.9186 | 7.5302 | bank:osm:relation/2315576 | 0.3884 |
| (-585.5, 182.5) | 7.7049, bank:osm:relation/2315576, terrain | 7.7049, bank:osm:relation/2315576, terrain | 7.9186 | 7.7049 | bank:osm:relation/2315576 | 0.2137 |
| (-584.5, 181.5) | 11.4513, scatter:osm:relation/7099311#229, vegetation | 11.4513, scatter:osm:relation/7099311#229, vegetation | 7.9186 | 7.0688 | bank:osm:relation/2315576 | 0.8498 |
| (-584.5, 182.5) | 12.512, scatter:osm:relation/7099311#229, vegetation | 12.512, scatter:osm:relation/7099311#229, vegetation | 7.9186 | 7.2435 | bank:osm:relation/2315576 | 0.675 |
| (-584.5, 183.5) | 11.8709, scatter:osm:relation/7099311#229, vegetation | 11.8709, scatter:osm:relation/7099311#229, vegetation | 7.9186 | 7.4183 | bank:osm:relation/2315576 | 0.5003 |
| (-584.5, 184.5) | 7.593, bank:osm:relation/2315576, terrain | 7.593, bank:osm:relation/2315576, terrain | 7.9186 | 7.593 | bank:osm:relation/2315576 | 0.3256 |
| (-583.5, 184.5) | 11.4332, scatter:osm:relation/7099311#229, vegetation | 11.4332, scatter:osm:relation/7099311#229, vegetation | 7.9186 | 7.1317 | bank:osm:relation/2315576 | 0.7869 |
| (-583.5, 185.5) | 7.3064, bank:osm:relation/2315576, terrain | 7.3064, bank:osm:relation/2315576, terrain | 7.9186 | 7.3064 | bank:osm:relation/2315576 | 0.6122 |
| (-583.5, 186.5) | 7.4811, bank:osm:relation/2315576, terrain | 7.4811, bank:osm:relation/2315576, terrain | 7.9186 | 7.4811 | bank:osm:relation/2315576 | 0.4374 |
| (-583.5, 187.5) | 7.6559, bank:osm:relation/2315576, terrain | 7.6559, bank:osm:relation/2315576, terrain | 7.9186 | 7.6559 | bank:osm:relation/2315576 | 0.2627 |
| (-582.5, 186.5) | 7.0198, bank:osm:relation/2315576, terrain | 7.0198, bank:osm:relation/2315576, terrain | 7.9186 | 7.0198 | bank:osm:relation/2315576 | 0.8988 |
| (-582.5, 187.5) | 7.1945, bank:osm:relation/2315576, terrain | 7.1945, bank:osm:relation/2315576, terrain | 7.9186 | 7.1945 | bank:osm:relation/2315576 | 0.7241 |
| (-582.5, 188.5) | 7.3692, bank:osm:relation/2315576, terrain | 7.3692, bank:osm:relation/2315576, terrain | 7.9186 | 7.3692 | bank:osm:relation/2315576 | 0.5493 |
| (-582.5, 189.5) | 7.544, bank:osm:relation/2315576, terrain | 7.544, bank:osm:relation/2315576, terrain | 7.9186 | 7.544 | bank:osm:relation/2315576 | 0.3746 |
| (-581.5, 189.5) | 7.0826, bank:osm:relation/2315576, terrain | 7.0826, bank:osm:relation/2315576, terrain | 7.9186 | 7.0826 | bank:osm:relation/2315576 | 0.836 |
| (-581.5, 190.5) | 7.2574, bank:osm:relation/2315576, terrain | 7.2574, bank:osm:relation/2315576, terrain | 7.9186 | 7.2574 | bank:osm:relation/2315576 | 0.6612 |
| (-581.5, 191.5) | 7.4321, bank:osm:relation/2315576, terrain | 7.4321, bank:osm:relation/2315576, terrain | 7.9186 | 7.4321 | bank:osm:relation/2315576 | 0.4865 |
| (-581.5, 192.5) | 7.6068, bank:osm:relation/2315576, terrain | 7.6068, bank:osm:relation/2315576, terrain | 7.9186 | 7.6068 | bank:osm:relation/2315576 | 0.3118 |
| (-580.5, 192.5) | 7.1455, bank:osm:relation/2315576, terrain | 7.1455, bank:osm:relation/2315576, terrain | 7.9186 | 7.1455 | bank:osm:relation/2315576 | 0.7731 |
| (-580.5, 193.5) | 7.3202, bank:osm:relation/2315576, terrain | 7.3202, bank:osm:relation/2315576, terrain | 7.9186 | 7.3202 | bank:osm:relation/2315576 | 0.5984 |
| (-580.5, 194.5) | 7.4949, bank:osm:relation/2315576, terrain | 7.4949, bank:osm:relation/2315576, terrain | 7.9186 | 7.4949 | bank:osm:relation/2315576 | 0.4236 |
| (-580.5, 195.5) | 11.8255, scatter:osm:relation/7099311#302, vegetation | 11.8255, scatter:osm:relation/7099311#302, vegetation | 7.9186 | 7.6697 | bank:osm:relation/2315576 | 0.2489 |
| (-579.5, 194.5) | 7.0336, bank:osm:relation/2315576, terrain | 7.0336, bank:osm:relation/2315576, terrain | 7.9186 | 7.0336 | bank:osm:relation/2315576 | 0.885 |
| (-579.5, 195.5) | 13.0745, scatter:osm:relation/7099311#302, vegetation | 13.0745, scatter:osm:relation/7099311#302, vegetation | 7.9186 | 7.2083 | bank:osm:relation/2315576 | 0.7103 |
| (-579.5, 196.5) | 15.1588, scatter:osm:relation/7099311#302, vegetation | 15.1588, scatter:osm:relation/7099311#302, vegetation | 7.9186 | 7.3831 | bank:osm:relation/2315576 | 0.5355 |
| (-579.5, 197.5) | 15.004, scatter:osm:relation/7099311#302, vegetation | 15.004, scatter:osm:relation/7099311#302, vegetation | 7.9186 | 7.5578 | bank:osm:relation/2315576 | 0.3608 |
| (-578.5, 197.5) | 14.6554, scatter:osm:relation/7099311#302, vegetation | 14.6554, scatter:osm:relation/7099311#302, vegetation | 7.9186 | 7.0964 | bank:osm:relation/2315576 | 0.8221 |
| (-578.5, 198.5) | 12.8555, scatter:osm:relation/7099311#302, vegetation | 12.8555, scatter:osm:relation/7099311#302, vegetation | 7.9186 | 7.2712 | bank:osm:relation/2315576 | 0.6474 |
| (-578.5, 199.5) | 7.4459, bank:osm:relation/2315576, terrain | 7.4459, bank:osm:relation/2315576, terrain | 7.9186 | 7.4459 | bank:osm:relation/2315576 | 0.4727 |
| (-578.5, 200.5) | 7.6206, bank:osm:relation/2315576, terrain | 7.6206, bank:osm:relation/2315576, terrain | 7.9186 | 7.6206 | bank:osm:relation/2315576 | 0.2979 |
| (-577.5, 199.5) | 6.9846, bank:osm:relation/2315576, terrain | 6.9846, bank:osm:relation/2315576, terrain | 7.9186 | 6.9846 | bank:osm:relation/2315576 | 0.934 |
| (-577.5, 200.5) | 7.1593, bank:osm:relation/2315576, terrain | 7.1593, bank:osm:relation/2315576, terrain | 7.9186 | 7.1593 | bank:osm:relation/2315576 | 0.7593 |
| (-577.5, 201.5) | 7.334, bank:osm:relation/2315576, terrain | 7.334, bank:osm:relation/2315576, terrain | 7.9186 | 7.334 | bank:osm:relation/2315576 | 0.5846 |
| (-577.5, 202.5) | 7.5088, bank:osm:relation/2315576, terrain | 7.5088, bank:osm:relation/2315576, terrain | 7.9186 | 7.5088 | bank:osm:relation/2315576 | 0.4098 |
| (-577.5, 203.5) | 7.6835, bank:osm:relation/2315576, terrain | 7.6835, bank:osm:relation/2315576, terrain | 7.9186 | 7.6835 | bank:osm:relation/2315576 | 0.2351 |
| (-576.5, 202.5) | 7.0474, bank:osm:relation/2315576, terrain | 7.0474, bank:osm:relation/2315576, terrain | 7.9186 | 7.0474 | bank:osm:relation/2315576 | 0.8712 |
| (-576.5, 203.5) | 7.2221, bank:osm:relation/2315576, terrain | 7.2221, bank:osm:relation/2315576, terrain | 7.9186 | 7.2221 | bank:osm:relation/2315576 | 0.6964 |
| (-576.5, 204.5) | 7.3969, bank:osm:relation/2315576, terrain | 7.3969, bank:osm:relation/2315576, terrain | 7.9186 | 7.3969 | bank:osm:relation/2315576 | 0.5217 |
| (-576.5, 205.5) | 7.5716, bank:osm:relation/2315576, terrain | 7.5716, bank:osm:relation/2315576, terrain | 7.9186 | 7.5716 | bank:osm:relation/2315576 | 0.347 |
| (-575.5, 205.5) | 7.1102, bank:osm:relation/2315576, terrain | 7.1102, bank:osm:relation/2315576, terrain | 7.9186 | 7.1102 | bank:osm:relation/2315576 | 0.8083 |
| (-575.5, 206.5) | 7.362, bank:osm:relation/2315576, terrain | 7.362, bank:osm:relation/2315576, terrain | 7.9186 | 7.362 | bank:osm:relation/2315576 | 0.5566 |
| (-575.5, 207.5) | 7.6788, bank:osm:relation/2315576, terrain | 7.6788, bank:osm:relation/2315576, terrain | 7.9186 | 7.6788 | bank:osm:relation/2315576 | 0.2397 |
| (-574.5, 207.5) | 7.3007, bank:osm:relation/2315576, terrain | 7.3007, bank:osm:relation/2315576, terrain | 7.9186 | 7.3007 | bank:osm:relation/2315576 | 0.6179 |
| (-574.5, 208.5) | 7.6175, bank:osm:relation/2315576, terrain | 7.6175, bank:osm:relation/2315576, terrain | 7.9186 | 7.6175 | bank:osm:relation/2315576 | 0.301 |
| (-573.5, 208.5) | 7.2394, bank:osm:relation/2315576, terrain | 7.2394, bank:osm:relation/2315576, terrain | 7.9186 | 7.2394 | bank:osm:relation/2315576 | 0.6792 |
| (-573.5, 209.5) | 7.5563, bank:osm:relation/2315576, terrain | 7.5563, bank:osm:relation/2315576, terrain | 7.9186 | 7.5563 | bank:osm:relation/2315576 | 0.3623 |
| (-572.5, 209.5) | 7.1781, bank:osm:relation/2315576, terrain | 7.1781, bank:osm:relation/2315576, terrain | 7.9186 | 7.1781 | bank:osm:relation/2315576 | 0.7405 |
| (-572.5, 210.5) | 7.495, bank:osm:relation/2315576, terrain | 7.495, bank:osm:relation/2315576, terrain | 7.9186 | 7.495 | bank:osm:relation/2315576 | 0.4236 |

#### `water_shore_step:col#10` (class D)

Blocked strips within reach (`shore_ramp_blocked_m` of the body: {'water:osm:relation/2315576': 192.5}):

* bank strip (-634.955, 119.687, 5.899) -> (-635.93, 118.129, 5.899) (1.838 m): line 2.0 osm:way/83926163
* bank strip (-635.93, 118.129, 5.899) -> (-636.905, 116.57, 5.899) (1.839 m): line 2.0 osm:way/83926163
* bank strip (-636.905, 116.57, 5.899) -> (-637.88, 115.012, 5.899) (1.838 m): line 2.0 osm:way/83926163
* bank strip (-637.88, 115.012, 5.899) -> (-638.855, 113.454, 5.899) (1.838 m): line 2.0 osm:way/83926163
* bank strip (-653.042, 73.563, 5.899) -> (-653.244, 71.613, 5.899) (1.96 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-653.244, 71.613, 5.899) -> (-653.445, 69.664, 5.899) (1.959 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-653.445, 69.664, 5.899) -> (-653.646, 67.714, 5.899) (1.96 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-653.646, 67.714, 5.899) -> (-653.848, 65.764, 5.899) (1.96 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-653.848, 65.764, 5.899) -> (-654.049, 63.815, 5.899) (1.959 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-654.049, 63.815, 5.899) -> (-654.25, 61.865, 5.899) (1.96 m): line 5.875 osm:way/23615351; line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-654.25, 61.865, 5.899) -> (-654.452, 59.915, 5.899) (1.96 m): line 5.875 osm:way/23615351
* bank strip (-654.452, 59.915, 5.899) -> (-654.653, 57.965, 5.899) (1.96 m): line 5.875 osm:way/23615351
* bank strip (-654.653, 57.965, 5.899) -> (-654.854, 56.016, 5.899) (1.959 m): line 5.875 osm:way/23615351
* bank strip (-654.854, 56.016, 5.899) -> (-655.056, 54.066, 5.899) (1.96 m): line 5.875 osm:way/23615351
* bank strip (-632.812, 54.712, 5.899) -> (-632.821, 56.696, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.821, 56.696, 5.899) -> (-632.829, 58.681, 5.899) (1.985 m): line 5.875 osm:way/23615351
* bank strip (-632.829, 58.681, 5.899) -> (-632.838, 60.665, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.838, 60.665, 5.899) -> (-632.846, 62.649, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.846, 62.649, 5.899) -> (-632.855, 64.633, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.855, 64.633, 5.899) -> (-632.863, 66.618, 5.899) (1.985 m): line 4.25 osm:way/214883367, osm:way/34575263; line 5.875 osm:way/23615351
* bank strip (-632.863, 66.618, 5.899) -> (-632.872, 68.602, 5.899) (1.984 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-632.872, 68.602, 5.899) -> (-632.88, 70.586, 5.899) (1.984 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-632.88, 70.586, 5.899) -> (-632.889, 72.57, 5.899) (1.984 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-632.889, 72.57, 5.899) -> (-632.897, 74.554, 5.899) (1.984 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-632.897, 74.554, 5.899) -> (-632.906, 76.539, 5.899) (1.985 m): line 4.25 osm:way/214883367, osm:way/34575263

| Cell XY | Collision top (z, mb_id, class) | Visual top (z, owner, category) | Sheet z (col) | Outside z (col) | Outside owner | Offset (m) |
|---|---|---|---|---|---|---|
| (-656.5, 58.5) | 13.8306, osm:way/23615351, bridge | 13.8306, osm:way/23615351, bridge | 7.9186 | 6.3745 | terrain:grid | 1.5441 |
| (-655.5, 58.5) | 13.91, osm:way/23615351, bridge | 13.91, osm:way/23615351, bridge | 7.9186 | 6.3745 | terrain:grid | 1.5441 |
| (-655.5, 59.5) | 13.9196, osm:way/23615351, bridge | 13.9196, osm:way/23615351, bridge | 7.9186 | 6.4039 | terrain:grid | 1.5147 |
| (-655.5, 60.5) | 13.9292, osm:way/23615351, bridge | 13.9292, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 59.5) | 13.999, osm:way/23615351, bridge | 13.999, osm:way/23615351, bridge | 7.9186 | 6.4039 | terrain:grid | 1.5147 |
| (-655.5, 61.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 60.5) | 14.0086, osm:way/23615351, bridge | 14.0086, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-655.5, 62.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 61.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-655.5, 63.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 62.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-655.5, 64.5) | 11.969, osm:way/214883367, bridge | 11.969, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 63.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-655.5, 65.5) | 11.9591, osm:way/214883367, bridge | 11.9591, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 64.5) | 11.8892, osm:way/214883367, bridge | 11.8892, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-655.5, 66.5) | 11.9492, osm:way/214883367, bridge | 11.9492, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 65.5) | 11.8793, osm:way/214883367, bridge | 11.8793, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-655.5, 67.5) | 11.9393, osm:way/214883367, bridge | 11.9393, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 66.5) | 11.8694, osm:way/214883367, bridge | 11.8694, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-655.5, 68.5) | 11.9294, osm:way/214883367, bridge | 11.9294, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 67.5) | 11.8595, osm:way/214883367, bridge | 11.8595, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 68.5) | 11.8496, osm:way/214883367, bridge | 11.8496, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 69.5) | 11.8397, osm:way/214883367, bridge | 11.8397, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 70.5) | 11.8299, osm:way/214883367, bridge | 11.8299, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-653.5, 69.5) | 11.7607, osm:way/214883367, bridge | 11.7607, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 71.5) | 12.8201, osm:way/214883367, bridge | 12.8201, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-653.5, 70.5) | 11.7508, osm:way/214883367, bridge | 11.7508, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 72.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-653.5, 71.5) | 12.741, osm:way/214883367, bridge | 12.741, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 73.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-653.5, 72.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 74.5) | 7.1358, bank:osm:relation/2315576, terrain | 7.1358, bank:osm:relation/2315576, terrain | 7.9186 | 7.1358 | bank:osm:relation/2315576 | 0.7828 |
| (-653.5, 73.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 75.5) | 7.0852, bank:osm:relation/2315576, terrain | 7.0852, bank:osm:relation/2315576, terrain | 7.9186 | 7.0852 | bank:osm:relation/2315576 | 0.8334 |
| (-653.5, 74.5) | 7.6265, bank:osm:relation/2315576, terrain | 7.6265, bank:osm:relation/2315576, terrain | 7.9186 | 7.6265 | bank:osm:relation/2315576 | 0.292 |
| (-654.5, 76.5) | 7.0345, bank:osm:relation/2315576, terrain | 7.0345, bank:osm:relation/2315576, terrain | 7.9186 | 7.0345 | bank:osm:relation/2315576 | 0.8841 |
| (-653.5, 75.5) | 7.5759, bank:osm:relation/2315576, terrain | 7.5759, bank:osm:relation/2315576, terrain | 7.9186 | 7.5759 | bank:osm:relation/2315576 | 0.3427 |
| (-654.5, 77.5) | 6.9838, bank:osm:relation/2315576, terrain | 6.9838, bank:osm:relation/2315576, terrain | 7.9186 | 6.9838 | bank:osm:relation/2315576 | 0.9348 |
| (-653.5, 76.5) | 7.5252, bank:osm:relation/2315576, terrain | 7.5252, bank:osm:relation/2315576, terrain | 7.9186 | 7.5252 | bank:osm:relation/2315576 | 0.3934 |
| (-654.5, 78.5) | 6.9331, bank:osm:relation/2315576, terrain | 6.9331, bank:osm:relation/2315576, terrain | 7.9186 | 6.9331 | bank:osm:relation/2315576 | 0.9854 |
| (-653.5, 77.5) | 7.4745, bank:osm:relation/2315576, terrain | 7.4745, bank:osm:relation/2315576, terrain | 7.9186 | 7.4745 | bank:osm:relation/2315576 | 0.4441 |
| (-653.5, 78.5) | 7.4239, bank:osm:relation/2315576, terrain | 7.4239, bank:osm:relation/2315576, terrain | 7.9186 | 7.4239 | bank:osm:relation/2315576 | 0.4947 |
| (-653.5, 79.5) | 7.3732, bank:osm:relation/2315576, terrain | 7.3732, bank:osm:relation/2315576, terrain | 7.9186 | 7.3732 | bank:osm:relation/2315576 | 0.5454 |
| (-653.5, 80.5) | 7.3225, bank:osm:relation/2315576, terrain | 7.3225, bank:osm:relation/2315576, terrain | 7.9186 | 7.3225 | bank:osm:relation/2315576 | 0.5961 |
| (-653.5, 81.5) | 7.2719, bank:osm:relation/2315576, terrain | 7.2719, bank:osm:relation/2315576, terrain | 7.9186 | 7.2719 | bank:osm:relation/2315576 | 0.6467 |
| (-653.5, 82.5) | 7.2212, bank:osm:relation/2315576, terrain | 7.2212, bank:osm:relation/2315576, terrain | 7.9186 | 7.2212 | bank:osm:relation/2315576 | 0.6974 |
| (-653.5, 83.5) | 7.1683, bank:osm:relation/2315576, terrain | 7.1683, bank:osm:relation/2315576, terrain | 7.9186 | 7.1683 | bank:osm:relation/2315576 | 0.7502 |
| (-652.5, 82.5) | 7.7119, bank:osm:relation/2315576, terrain | 7.7119, bank:osm:relation/2315576, terrain | 7.9186 | 7.7119 | bank:osm:relation/2315576 | 0.2067 |
| (-653.5, 84.5) | 7.0215, bank:osm:relation/2315576, terrain | 7.0215, bank:osm:relation/2315576, terrain | 7.9186 | 7.0215 | bank:osm:relation/2315576 | 0.8971 |
| (-652.5, 83.5) | 7.6517, bank:osm:relation/2315576, terrain | 7.6517, bank:osm:relation/2315576, terrain | 7.9186 | 7.6517 | bank:osm:relation/2315576 | 0.2669 |
| (-652.5, 84.5) | 7.4863, bank:osm:relation/2315576, terrain | 7.4863, bank:osm:relation/2315576, terrain | 7.9186 | 7.4863 | bank:osm:relation/2315576 | 0.4323 |
| (-652.5, 85.5) | 7.3208, bank:osm:relation/2315576, terrain | 7.3208, bank:osm:relation/2315576, terrain | 7.9186 | 7.3208 | bank:osm:relation/2315576 | 0.5978 |
| (-652.5, 86.5) | 7.1554, bank:osm:relation/2315576, terrain | 7.1554, bank:osm:relation/2315576, terrain | 7.9186 | 7.1554 | bank:osm:relation/2315576 | 0.7632 |
| (-652.5, 87.5) | 6.9899, bank:osm:relation/2315576, terrain | 6.9899, bank:osm:relation/2315576, terrain | 7.9186 | 6.9899 | bank:osm:relation/2315576 | 0.9287 |
| (-651.5, 86.5) | 7.6201, bank:osm:relation/2315576, terrain | 7.6201, bank:osm:relation/2315576, terrain | 7.9186 | 7.6201 | bank:osm:relation/2315576 | 0.2984 |
| (-651.5, 87.5) | 7.4547, bank:osm:relation/2315576, terrain | 7.4547, bank:osm:relation/2315576, terrain | 7.9186 | 7.4547 | bank:osm:relation/2315576 | 0.4639 |
| (-651.5, 88.5) | 7.2893, bank:osm:relation/2315576, terrain | 7.2893, bank:osm:relation/2315576, terrain | 7.9186 | 7.2893 | bank:osm:relation/2315576 | 0.6293 |
| (-651.5, 89.5) | 7.1238, bank:osm:relation/2315576, terrain | 7.1238, bank:osm:relation/2315576, terrain | 7.9186 | 7.1238 | bank:osm:relation/2315576 | 0.7948 |
| (-650.5, 89.5) | 7.5886, bank:osm:relation/2315576, terrain | 7.5886, bank:osm:relation/2315576, terrain | 7.9186 | 7.5886 | bank:osm:relation/2315576 | 0.33 |
| (-650.5, 90.5) | 7.4232, bank:osm:relation/2315576, terrain | 7.4232, bank:osm:relation/2315576, terrain | 7.9186 | 7.4232 | bank:osm:relation/2315576 | 0.4954 |
| (-650.5, 91.5) | 7.2577, bank:osm:relation/2315576, terrain | 7.2577, bank:osm:relation/2315576, terrain | 7.9186 | 7.2577 | bank:osm:relation/2315576 | 0.6609 |
| (-650.5, 92.5) | 7.0923, bank:osm:relation/2315576, terrain | 7.0923, bank:osm:relation/2315576, terrain | 7.9186 | 7.0923 | bank:osm:relation/2315576 | 0.8263 |
| (-649.5, 92.5) | 7.557, bank:osm:relation/2315576, terrain | 7.557, bank:osm:relation/2315576, terrain | 7.9186 | 7.557 | bank:osm:relation/2315576 | 0.3615 |
| (-649.5, 93.5) | 7.3916, bank:osm:relation/2315576, terrain | 7.3916, bank:osm:relation/2315576, terrain | 7.9186 | 7.3916 | bank:osm:relation/2315576 | 0.527 |
| (-649.5, 94.5) | 7.2262, bank:osm:relation/2315576, terrain | 7.2262, bank:osm:relation/2315576, terrain | 7.9186 | 7.2262 | bank:osm:relation/2315576 | 0.6924 |
| (-649.5, 95.5) | 7.0607, bank:osm:relation/2315576, terrain | 7.0607, bank:osm:relation/2315576, terrain | 7.9186 | 7.0607 | bank:osm:relation/2315576 | 0.8578 |
| (-648.5, 94.5) | 7.6909, bank:osm:relation/2315576, terrain | 7.6909, bank:osm:relation/2315576, terrain | 7.9186 | 7.6909 | bank:osm:relation/2315576 | 0.2276 |
| (-648.5, 95.5) | 7.5255, bank:osm:relation/2315576, terrain | 7.5255, bank:osm:relation/2315576, terrain | 7.9186 | 7.5255 | bank:osm:relation/2315576 | 0.3931 |
| (-648.5, 96.5) | 7.3424, bank:osm:relation/2315576, terrain | 7.3424, bank:osm:relation/2315576, terrain | 7.9186 | 7.3424 | bank:osm:relation/2315576 | 0.5761 |
| (-648.5, 97.5) | 7.1283, bank:osm:relation/2315576, terrain | 7.1283, bank:osm:relation/2315576, terrain | 7.9186 | 7.1283 | bank:osm:relation/2315576 | 0.7903 |
| (-647.5, 97.5) | 7.5727, bank:osm:relation/2315576, terrain | 7.5727, bank:osm:relation/2315576, terrain | 7.9186 | 7.5727 | bank:osm:relation/2315576 | 0.3459 |
| (-647.5, 98.5) | 7.3586, bank:osm:relation/2315576, terrain | 7.3586, bank:osm:relation/2315576, terrain | 7.9186 | 7.3586 | bank:osm:relation/2315576 | 0.56 |
| (-647.5, 99.5) | 7.1444, bank:osm:relation/2315576, terrain | 7.1444, bank:osm:relation/2315576, terrain | 7.9186 | 7.1444 | bank:osm:relation/2315576 | 0.7742 |
| (-646.5, 99.5) | 7.5888, bank:osm:relation/2315576, terrain | 7.5888, bank:osm:relation/2315576, terrain | 7.9186 | 7.5888 | bank:osm:relation/2315576 | 0.3297 |
| (-646.5, 100.5) | 7.3747, bank:osm:relation/2315576, terrain | 7.3747, bank:osm:relation/2315576, terrain | 7.9186 | 7.3747 | bank:osm:relation/2315576 | 0.5439 |
| (-646.5, 101.5) | 7.1606, bank:osm:relation/2315576, terrain | 7.1606, bank:osm:relation/2315576, terrain | 7.9186 | 7.1606 | bank:osm:relation/2315576 | 0.758 |
| (-645.5, 101.5) | 7.605, bank:osm:relation/2315576, terrain | 7.605, bank:osm:relation/2315576, terrain | 7.9186 | 7.605 | bank:osm:relation/2315576 | 0.3136 |
| (-645.5, 102.5) | 7.3908, bank:osm:relation/2315576, terrain | 7.3908, bank:osm:relation/2315576, terrain | 7.9186 | 7.3908 | bank:osm:relation/2315576 | 0.5277 |
| (-645.5, 103.5) | 7.1767, bank:osm:relation/2315576, terrain | 7.1767, bank:osm:relation/2315576, terrain | 7.9186 | 7.1767 | bank:osm:relation/2315576 | 0.7419 |
| (-644.5, 103.5) | 7.6211, bank:osm:relation/2315576, terrain | 7.6211, bank:osm:relation/2315576, terrain | 7.9186 | 7.6211 | bank:osm:relation/2315576 | 0.2975 |
| (-644.5, 104.5) | 7.407, bank:osm:relation/2315576, terrain | 7.407, bank:osm:relation/2315576, terrain | 7.9186 | 7.407 | bank:osm:relation/2315576 | 0.5116 |
| (-644.5, 105.5) | 7.1928, bank:osm:relation/2315576, terrain | 7.1928, bank:osm:relation/2315576, terrain | 7.9186 | 7.1928 | bank:osm:relation/2315576 | 0.7258 |
| (-643.5, 105.5) | 7.6373, bank:osm:relation/2315576, terrain | 7.6373, bank:osm:relation/2315576, terrain | 7.9186 | 7.6373 | bank:osm:relation/2315576 | 0.2813 |
| (-643.5, 106.5) | 7.4231, bank:osm:relation/2315576, terrain | 7.4231, bank:osm:relation/2315576, terrain | 7.9186 | 7.4231 | bank:osm:relation/2315576 | 0.4955 |
| (-643.5, 107.5) | 7.209, bank:osm:relation/2315576, terrain | 7.209, bank:osm:relation/2315576, terrain | 7.9186 | 7.209 | bank:osm:relation/2315576 | 0.7096 |
| (-642.5, 107.5) | 7.6534, bank:osm:relation/2315576, terrain | 7.6534, bank:osm:relation/2315576, terrain | 7.9186 | 7.6534 | bank:osm:relation/2315576 | 0.2652 |
| (-642.5, 108.5) | 7.4393, bank:osm:relation/2315576, terrain | 7.4393, bank:osm:relation/2315576, terrain | 7.9186 | 7.4393 | bank:osm:relation/2315576 | 0.4793 |
| (-642.5, 109.5) | 7.2251, bank:osm:relation/2315576, terrain | 7.2251, bank:osm:relation/2315576, terrain | 7.9186 | 7.2251 | bank:osm:relation/2315576 | 0.6935 |
| (-642.5, 110.5) | 7.011, bank:osm:relation/2315576, terrain | 7.011, bank:osm:relation/2315576, terrain | 7.9186 | 7.011 | bank:osm:relation/2315576 | 0.9076 |
| (-641.5, 109.5) | 7.6695, bank:osm:relation/2315576, terrain | 7.6695, bank:osm:relation/2315576, terrain | 7.9186 | 7.6695 | bank:osm:relation/2315576 | 0.249 |
| (-641.5, 110.5) | 7.4554, bank:osm:relation/2315576, terrain | 7.4554, bank:osm:relation/2315576, terrain | 7.9186 | 7.4554 | bank:osm:relation/2315576 | 0.4632 |
| (-641.5, 111.5) | 7.2413, bank:osm:relation/2315576, terrain | 7.2413, bank:osm:relation/2315576, terrain | 7.9186 | 7.2413 | bank:osm:relation/2315576 | 0.6773 |
| (-640.5, 111.5) | 7.6857, bank:osm:relation/2315576, terrain | 7.6857, bank:osm:relation/2315576, terrain | 7.9186 | 7.6857 | bank:osm:relation/2315576 | 0.2329 |
| (-640.5, 112.5) | 7.4604, bank:osm:relation/2315576, terrain | 7.4604, bank:osm:relation/2315576, terrain | 7.9186 | 7.4604 | bank:osm:relation/2315576 | 0.4582 |
| (-640.5, 113.5) | 7.1987, bank:osm:relation/2315576, terrain | 7.1987, bank:osm:relation/2315576, terrain | 7.9186 | 7.1987 | bank:osm:relation/2315576 | 0.7199 |
| (-639.5, 113.5) | 7.6169, bank:osm:relation/2315576, terrain | 7.6169, bank:osm:relation/2315576, terrain | 7.9186 | 7.6169 | bank:osm:relation/2315576 | 0.3017 |
| (-639.5, 114.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-639.5, 115.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-638.5, 114.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-638.5, 115.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-638.5, 116.5) | 10.5611, osm:way/83926163, bridge | 10.5611, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-637.5, 116.5) | 10.6411, osm:way/83926163, bridge | 10.6411, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-637.5, 117.5) | 10.6402, osm:way/83926163, bridge | 10.6402, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-637.5, 118.5) | 11.6393, osm:way/83926163, bridge | 11.6393, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-636.5, 117.5) | 10.7202, osm:way/83926163, bridge | 10.7202, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-636.5, 118.5) | 11.7192, osm:way/83926163, bridge | 11.7192, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-636.5, 119.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-635.5, 119.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-635.5, 120.5) | 7.458, bank:osm:relation/2315576, terrain | 7.458, bank:osm:relation/2315576, terrain | 7.9186 | 7.458 | bank:osm:relation/2315576 | 0.4605 |
| (-635.5, 121.5) | 7.1964, bank:osm:relation/2315576, terrain | 7.1964, bank:osm:relation/2315576, terrain | 7.9186 | 7.1964 | bank:osm:relation/2315576 | 0.7222 |
| (-634.5, 121.5) | 7.6146, bank:osm:relation/2315576, terrain | 7.6146, bank:osm:relation/2315576, terrain | 7.9186 | 7.6146 | bank:osm:relation/2315576 | 0.304 |
| (-634.5, 122.5) | 7.3529, bank:osm:relation/2315576, terrain | 7.3529, bank:osm:relation/2315576, terrain | 7.9186 | 7.3529 | bank:osm:relation/2315576 | 0.5657 |
| (-634.5, 123.5) | 7.0912, bank:osm:relation/2315576, terrain | 7.0912, bank:osm:relation/2315576, terrain | 7.9186 | 7.0912 | bank:osm:relation/2315576 | 0.8273 |
| (-633.5, 123.5) | 7.5095, bank:osm:relation/2315576, terrain | 7.5095, bank:osm:relation/2315576, terrain | 7.9186 | 7.5095 | bank:osm:relation/2315576 | 0.4091 |
| (-633.5, 124.5) | 7.2478, bank:osm:relation/2315576, terrain | 7.2478, bank:osm:relation/2315576, terrain | 7.9186 | 7.2478 | bank:osm:relation/2315576 | 0.6708 |
| (-632.5, 124.5) | 7.666, bank:osm:relation/2315576, terrain | 7.666, bank:osm:relation/2315576, terrain | 7.9186 | 7.666 | bank:osm:relation/2315576 | 0.2526 |
| (-632.5, 125.5) | 7.4043, bank:osm:relation/2315576, terrain | 7.4043, bank:osm:relation/2315576, terrain | 7.9186 | 7.4043 | bank:osm:relation/2315576 | 0.5143 |
| (-632.5, 126.5) | 7.1427, bank:osm:relation/2315576, terrain | 7.1427, bank:osm:relation/2315576, terrain | 7.9186 | 7.1427 | bank:osm:relation/2315576 | 0.7759 |
| (-631.5, 126.5) | 7.5609, bank:osm:relation/2315576, terrain | 7.5609, bank:osm:relation/2315576, terrain | 7.9186 | 7.5609 | bank:osm:relation/2315576 | 0.3577 |
| (-631.5, 127.5) | 7.2992, bank:osm:relation/2315576, terrain | 7.2992, bank:osm:relation/2315576, terrain | 7.9186 | 7.2992 | bank:osm:relation/2315576 | 0.6194 |
| (-630.5, 127.5) | 7.7174, bank:osm:relation/2315576, terrain | 7.7174, bank:osm:relation/2315576, terrain | 7.9186 | 7.7174 | bank:osm:relation/2315576 | 0.2012 |
| (-630.5, 128.5) | 7.4557, bank:osm:relation/2315576, terrain | 7.4557, bank:osm:relation/2315576, terrain | 7.9186 | 7.4557 | bank:osm:relation/2315576 | 0.4628 |
| (-630.5, 129.5) | 7.1941, bank:osm:relation/2315576, terrain | 7.1941, bank:osm:relation/2315576, terrain | 7.9186 | 7.1941 | bank:osm:relation/2315576 | 0.7245 |
| (-629.5, 129.5) | 7.6123, bank:osm:relation/2315576, terrain | 7.6123, bank:osm:relation/2315576, terrain | 7.9186 | 7.6123 | bank:osm:relation/2315576 | 0.3063 |
| (-629.5, 130.5) | 7.3506, bank:osm:relation/2315576, terrain | 7.3506, bank:osm:relation/2315576, terrain | 7.9186 | 7.3506 | bank:osm:relation/2315576 | 0.568 |
| (-629.5, 131.5) | 7.1623, bank:osm:relation/2315576, terrain | 7.1623, bank:osm:relation/2315576, terrain | 7.9186 | 7.1623 | bank:osm:relation/2315576 | 0.7563 |
| (-629.5, 132.5) | 7.0864, bank:osm:relation/2315576, terrain | 7.0864, bank:osm:relation/2315576, terrain | 7.9186 | 7.0864 | bank:osm:relation/2315576 | 0.8321 |
| (-628.5, 131.5) | 7.6497, bank:osm:relation/2315576, terrain | 7.6497, bank:osm:relation/2315576, terrain | 7.9186 | 7.6497 | bank:osm:relation/2315576 | 0.2688 |
| (-629.5, 133.5) | 7.0106, bank:osm:relation/2315576, terrain | 7.0106, bank:osm:relation/2315576, terrain | 7.9186 | 7.0106 | bank:osm:relation/2315576 | 0.908 |
| (-628.5, 132.5) | 7.5739, bank:osm:relation/2315576, terrain | 7.5739, bank:osm:relation/2315576, terrain | 7.9186 | 7.5739 | bank:osm:relation/2315576 | 0.3447 |
| (-629.5, 134.5) | 6.9348, bank:osm:relation/2315576, terrain | 6.9348, bank:osm:relation/2315576, terrain | 7.9186 | 6.9348 | bank:osm:relation/2315576 | 0.9838 |
| (-628.5, 133.5) | 7.4981, bank:osm:relation/2315576, terrain | 7.4981, bank:osm:relation/2315576, terrain | 7.9186 | 7.4981 | bank:osm:relation/2315576 | 0.4205 |
| (-628.5, 134.5) | 7.4223, bank:osm:relation/2315576, terrain | 7.4223, bank:osm:relation/2315576, terrain | 7.9186 | 7.4223 | bank:osm:relation/2315576 | 0.4963 |
| (-628.5, 135.5) | 7.3464, bank:osm:relation/2315576, terrain | 7.3464, bank:osm:relation/2315576, terrain | 7.9186 | 7.3464 | bank:osm:relation/2315576 | 0.5721 |
| (-628.5, 136.5) | 7.2706, bank:osm:relation/2315576, terrain | 7.2706, bank:osm:relation/2315576, terrain | 7.9186 | 7.2706 | bank:osm:relation/2315576 | 0.648 |
| (-628.5, 137.5) | 7.1948, bank:osm:relation/2315576, terrain | 7.1948, bank:osm:relation/2315576, terrain | 7.9186 | 7.1948 | bank:osm:relation/2315576 | 0.7238 |
| (-628.5, 138.5) | 7.119, bank:osm:relation/2315576, terrain | 7.119, bank:osm:relation/2315576, terrain | 7.9186 | 7.119 | bank:osm:relation/2315576 | 0.7996 |
| (-627.5, 137.5) | 7.6823, bank:osm:relation/2315576, terrain | 7.6823, bank:osm:relation/2315576, terrain | 7.9186 | 7.6823 | bank:osm:relation/2315576 | 0.2363 |
| (-628.5, 139.5) | 7.0431, bank:osm:relation/2315576, terrain | 7.0431, bank:osm:relation/2315576, terrain | 7.9186 | 7.0431 | bank:osm:relation/2315576 | 0.8754 |
| (-627.5, 138.5) | 7.6064, bank:osm:relation/2315576, terrain | 7.6064, bank:osm:relation/2315576, terrain | 7.9186 | 7.6064 | bank:osm:relation/2315576 | 0.3122 |
| (-628.5, 140.5) | 6.9673, bank:osm:relation/2315576, terrain | 6.9673, bank:osm:relation/2315576, terrain | 7.9186 | 6.9673 | bank:osm:relation/2315576 | 0.9513 |
| (-627.5, 139.5) | 7.5306, bank:osm:relation/2315576, terrain | 7.5306, bank:osm:relation/2315576, terrain | 7.9186 | 7.5306 | bank:osm:relation/2315576 | 0.388 |
| (-627.5, 140.5) | 7.4548, bank:osm:relation/2315576, terrain | 7.4548, bank:osm:relation/2315576, terrain | 7.9186 | 7.4548 | bank:osm:relation/2315576 | 0.4638 |
| (-627.5, 141.5) | 7.3772, bank:osm:relation/2315576, terrain | 7.3772, bank:osm:relation/2315576, terrain | 7.9186 | 7.3772 | bank:osm:relation/2315576 | 0.5414 |
| (-627.5, 142.5) | 7.1783, bank:osm:relation/2315576, terrain | 7.1783, bank:osm:relation/2315576, terrain | 7.9186 | 7.1783 | bank:osm:relation/2315576 | 0.7403 |
| (-626.5, 142.5) | 7.6213, bank:osm:relation/2315576, terrain | 7.6213, bank:osm:relation/2315576, terrain | 7.9186 | 7.6213 | bank:osm:relation/2315576 | 0.2973 |
| (-626.5, 143.5) | 7.4043, bank:osm:relation/2315576, terrain | 7.4043, bank:osm:relation/2315576, terrain | 7.9186 | 7.4043 | bank:osm:relation/2315576 | 0.5143 |
| (-626.5, 144.5) | 7.1873, bank:osm:relation/2315576, terrain | 7.1873, bank:osm:relation/2315576, terrain | 7.9186 | 7.1873 | bank:osm:relation/2315576 | 0.7313 |
| (-625.5, 144.5) | 7.6303, bank:osm:relation/2315576, terrain | 7.6303, bank:osm:relation/2315576, terrain | 7.9186 | 7.6303 | bank:osm:relation/2315576 | 0.2883 |
| (-625.5, 145.5) | 7.4133, bank:osm:relation/2315576, terrain | 7.4133, bank:osm:relation/2315576, terrain | 7.9186 | 7.4133 | bank:osm:relation/2315576 | 0.5053 |
| (-625.5, 146.5) | 7.1963, bank:osm:relation/2315576, terrain | 7.1963, bank:osm:relation/2315576, terrain | 7.9186 | 7.1963 | bank:osm:relation/2315576 | 0.7223 |
| (-624.5, 146.5) | 7.6393, bank:osm:relation/2315576, terrain | 7.6393, bank:osm:relation/2315576, terrain | 7.9186 | 7.6393 | bank:osm:relation/2315576 | 0.2793 |
| (-624.5, 147.5) | 7.4223, bank:osm:relation/2315576, terrain | 7.4223, bank:osm:relation/2315576, terrain | 7.9186 | 7.4223 | bank:osm:relation/2315576 | 0.4963 |
| (-624.5, 148.5) | 7.1556, bank:osm:relation/2315576, terrain | 7.1556, bank:osm:relation/2315576, terrain | 7.9186 | 7.1556 | bank:osm:relation/2315576 | 0.763 |
| (-623.5, 148.5) | 7.5408, bank:osm:relation/2315576, terrain | 7.5408, bank:osm:relation/2315576, terrain | 7.9186 | 7.5408 | bank:osm:relation/2315576 | 0.3778 |
| (-623.5, 149.5) | 7.2325, bank:osm:relation/2315576, terrain | 7.2325, bank:osm:relation/2315576, terrain | 7.9186 | 7.2325 | bank:osm:relation/2315576 | 0.6861 |
| (-622.5, 149.5) | 7.6177, bank:osm:relation/2315576, terrain | 7.6177, bank:osm:relation/2315576, terrain | 7.9186 | 7.6177 | bank:osm:relation/2315576 | 0.3009 |
| (-622.5, 150.5) | 7.3094, bank:osm:relation/2315576, terrain | 7.3094, bank:osm:relation/2315576, terrain | 7.9186 | 7.3094 | bank:osm:relation/2315576 | 0.6092 |
| (-621.5, 150.5) | 7.6946, bank:osm:relation/2315576, terrain | 7.6946, bank:osm:relation/2315576, terrain | 7.9186 | 7.6946 | bank:osm:relation/2315576 | 0.224 |
| (-621.5, 151.5) | 7.3863, bank:osm:relation/2315576, terrain | 7.3863, bank:osm:relation/2315576, terrain | 7.9186 | 7.3863 | bank:osm:relation/2315576 | 0.5323 |

#### `water_shore_step:vis#15` (class D)

Blocked strips within reach (`shore_ramp_blocked_m` of the body: {'water:osm:relation/2315576': 192.5}):

* bank strip (-635.415, -30.307, 5.899) -> (-635.094, -28.356, 5.899) (1.977 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-635.094, -28.356, 5.899) -> (-634.773, -26.406, 5.899) (1.976 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-634.773, -26.406, 5.899) -> (-634.451, -24.455, 5.899) (1.977 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-634.451, -24.455, 5.899) -> (-634.13, -22.505, 5.899) (1.976 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-634.13, -22.505, 5.899) -> (-633.809, -20.554, 5.899) (1.977 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-632.575, -0.846, 5.899) -> (-632.583, 1.138, 5.899) (1.984 m): line 2.625 osm:way/4752302
* bank strip (-632.583, 1.138, 5.899) -> (-632.592, 3.122, 5.899) (1.984 m): line 2.625 osm:way/4752302
* bank strip (-632.592, 3.122, 5.899) -> (-632.6, 5.106, 5.899) (1.984 m): line 2.625 osm:way/4752302
* bank strip (-632.609, 7.091, 5.899) -> (-632.617, 9.075, 5.899) (1.984 m): line 4.25 osm:way/33731358, osm:way/34575500
* bank strip (-632.617, 9.075, 5.899) -> (-632.626, 11.059, 5.899) (1.984 m): line 4.25 osm:way/33731358, osm:way/34575500
* bank strip (-632.626, 11.059, 5.899) -> (-632.634, 13.043, 5.899) (1.984 m): line 4.25 osm:way/33731358, osm:way/34575500
* bank strip (-632.634, 13.043, 5.899) -> (-632.643, 15.028, 5.899) (1.985 m): line 7.5 osm:way/34575500; line 4.25 osm:way/33731358, osm:way/34575500

| Cell XY | Collision top (z, mb_id, class) | Visual top (z, owner, category) | Sheet z (vis) | Outside z (vis) | Outside owner | Offset (m) |
|---|---|---|---|---|---|---|
| (-648.5, -54.5) | 7.3328, bank:osm:relation/2315576, terrain | 7.3328, bank:osm:relation/2315576, terrain | 7.9186 | 7.3328 | bank:osm:relation/2315576 | 0.5858 |
| (-648.5, -53.5) | 7.5888, bank:osm:relation/2315576, terrain | 7.5888, bank:osm:relation/2315576, terrain | 7.9186 | 7.5888 | bank:osm:relation/2315576 | 0.3297 |
| (-647.5, -53.5) | 7.1672, bank:osm:relation/2315576, terrain | 7.1672, bank:osm:relation/2315576, terrain | 7.9186 | 7.1672 | bank:osm:relation/2315576 | 0.7514 |
| (-647.5, -52.5) | 7.4233, bank:osm:relation/2315576, terrain | 7.4233, bank:osm:relation/2315576, terrain | 7.9186 | 7.4233 | bank:osm:relation/2315576 | 0.4953 |
| (-647.5, -51.5) | 7.6793, bank:osm:relation/2315576, terrain | 7.6793, bank:osm:relation/2315576, terrain | 7.9186 | 7.6793 | bank:osm:relation/2315576 | 0.2392 |
| (-646.5, -51.5) | 7.2577, bank:osm:relation/2315576, terrain | 7.2577, bank:osm:relation/2315576, terrain | 7.9186 | 7.2577 | bank:osm:relation/2315576 | 0.6609 |
| (-646.5, -50.5) | 7.5138, bank:osm:relation/2315576, terrain | 7.5138, bank:osm:relation/2315576, terrain | 7.9186 | 7.5138 | bank:osm:relation/2315576 | 0.4048 |
| (-645.5, -50.5) | 7.0921, bank:osm:relation/2315576, terrain | 7.0921, bank:osm:relation/2315576, terrain | 7.9186 | 7.0921 | bank:osm:relation/2315576 | 0.8265 |
| (-645.5, -49.5) | 7.3482, bank:osm:relation/2315576, terrain | 7.3482, bank:osm:relation/2315576, terrain | 7.9186 | 7.3482 | bank:osm:relation/2315576 | 0.5704 |
| (-645.5, -48.5) | 7.6043, bank:osm:relation/2315576, terrain | 7.6043, bank:osm:relation/2315576, terrain | 7.9186 | 7.6043 | bank:osm:relation/2315576 | 0.3143 |
| (-644.5, -48.5) | 7.1826, bank:osm:relation/2315576, terrain | 7.1826, bank:osm:relation/2315576, terrain | 7.9186 | 7.1826 | bank:osm:relation/2315576 | 0.736 |
| (-644.5, -47.5) | 7.4387, bank:osm:relation/2315576, terrain | 7.4387, bank:osm:relation/2315576, terrain | 7.9186 | 7.4387 | bank:osm:relation/2315576 | 0.4799 |
| (-644.5, -46.5) | 7.6948, bank:osm:relation/2315576, terrain | 7.6948, bank:osm:relation/2315576, terrain | 7.9186 | 7.6948 | bank:osm:relation/2315576 | 0.2238 |
| (-643.5, -46.5) | 7.2731, bank:osm:relation/2315576, terrain | 7.2731, bank:osm:relation/2315576, terrain | 7.9186 | 7.2731 | bank:osm:relation/2315576 | 0.6455 |
| (-643.5, -45.5) | 7.5292, bank:osm:relation/2315576, terrain | 7.5292, bank:osm:relation/2315576, terrain | 7.9186 | 7.5292 | bank:osm:relation/2315576 | 0.3894 |
| (-642.5, -45.5) | 7.1075, bank:osm:relation/2315576, terrain | 7.1075, bank:osm:relation/2315576, terrain | 7.9186 | 7.1075 | bank:osm:relation/2315576 | 0.8111 |
| (-642.5, -44.5) | 7.3636, bank:osm:relation/2315576, terrain | 7.3636, bank:osm:relation/2315576, terrain | 7.9186 | 7.3636 | bank:osm:relation/2315576 | 0.555 |
| (-642.5, -43.5) | 7.6197, bank:osm:relation/2315576, terrain | 7.6197, bank:osm:relation/2315576, terrain | 7.9186 | 7.6197 | bank:osm:relation/2315576 | 0.2989 |
| (-641.5, -43.5) | 7.198, bank:osm:relation/2315576, terrain | 7.198, bank:osm:relation/2315576, terrain | 7.9186 | 7.198 | bank:osm:relation/2315576 | 0.7206 |
| (-641.5, -42.5) | 7.4488, bank:osm:relation/2315576, terrain | 7.4488, bank:osm:relation/2315576, terrain | 7.9186 | 7.4488 | bank:osm:relation/2315576 | 0.4698 |
| (-641.5, -41.5) | 7.6981, bank:osm:relation/2315576, terrain | 7.6981, bank:osm:relation/2315576, terrain | 7.9186 | 7.6981 | bank:osm:relation/2315576 | 0.2204 |
| (-640.5, -41.5) | 7.2725, bank:osm:relation/2315576, terrain | 7.2725, bank:osm:relation/2315576, terrain | 7.9186 | 7.2725 | bank:osm:relation/2315576 | 0.6461 |
| (-640.5, -40.5) | 7.5218, bank:osm:relation/2315576, terrain | 7.5218, bank:osm:relation/2315576, terrain | 7.9186 | 7.5218 | bank:osm:relation/2315576 | 0.3968 |
| (-639.5, -40.5) | 7.0961, bank:osm:relation/2315576, terrain | 7.0961, bank:osm:relation/2315576, terrain | 7.9186 | 7.0961 | bank:osm:relation/2315576 | 0.8225 |
| (-639.5, -39.5) | 7.3454, bank:osm:relation/2315576, terrain | 7.3454, bank:osm:relation/2315576, terrain | 7.9186 | 7.3454 | bank:osm:relation/2315576 | 0.5731 |
| (-639.5, -38.5) | 7.5948, bank:osm:relation/2315576, terrain | 7.5948, bank:osm:relation/2315576, terrain | 7.9186 | 7.5948 | bank:osm:relation/2315576 | 0.3238 |
| (-638.5, -38.5) | 7.1691, bank:osm:relation/2315576, terrain | 7.1691, bank:osm:relation/2315576, terrain | 7.9186 | 7.1691 | bank:osm:relation/2315576 | 0.7495 |
| (-638.5, -37.5) | 7.4184, bank:osm:relation/2315576, terrain | 7.4184, bank:osm:relation/2315576, terrain | 7.9186 | 7.4184 | bank:osm:relation/2315576 | 0.5002 |
| (-638.5, -36.5) | 7.6677, bank:osm:relation/2315576, terrain | 7.6677, bank:osm:relation/2315576, terrain | 7.9186 | 7.6677 | bank:osm:relation/2315576 | 0.2508 |
| (-637.5, -36.5) | 7.2421, bank:osm:relation/2315576, terrain | 7.2421, bank:osm:relation/2315576, terrain | 7.9186 | 7.2421 | bank:osm:relation/2315576 | 0.6765 |
| (-637.5, -35.5) | 7.4914, bank:osm:relation/2315576, terrain | 7.4914, bank:osm:relation/2315576, terrain | 7.9186 | 7.4914 | bank:osm:relation/2315576 | 0.4272 |
| (-636.5, -35.5) | 7.0657, bank:osm:relation/2315576, terrain | 7.0657, bank:osm:relation/2315576, terrain | 7.9186 | 7.0657 | bank:osm:relation/2315576 | 0.8529 |
| (-636.5, -34.5) | 7.315, bank:osm:relation/2315576, terrain | 7.315, bank:osm:relation/2315576, terrain | 7.9186 | 7.315 | bank:osm:relation/2315576 | 0.6035 |
| (-636.5, -33.5) | 7.5644, bank:osm:relation/2315576, terrain | 7.5644, bank:osm:relation/2315576, terrain | 7.9186 | 7.5644 | bank:osm:relation/2315576 | 0.3542 |
| (-635.5, -33.5) | 7.1387, bank:osm:relation/2315576, terrain | 7.1387, bank:osm:relation/2315576, terrain | 7.9186 | 7.1387 | bank:osm:relation/2315576 | 0.7799 |
| (-635.5, -32.5) | 7.388, bank:osm:relation/2315576, terrain | 7.388, bank:osm:relation/2315576, terrain | 7.9186 | 7.388 | bank:osm:relation/2315576 | 0.5306 |
| (-635.5, -31.5) | 7.6373, bank:osm:relation/2315576, terrain | 7.6373, bank:osm:relation/2315576, terrain | 7.9186 | 7.6373 | bank:osm:relation/2315576 | 0.2812 |
| (-634.5, -31.5) | 7.2117, bank:osm:relation/2315576, terrain | 7.2117, bank:osm:relation/2315576, terrain | 7.9186 | 7.2117 | bank:osm:relation/2315576 | 0.7069 |
| (-634.5, -30.5) | 7.4359, bank:osm:relation/2315576, terrain | 7.4359, bank:osm:relation/2315576, terrain | 7.9186 | 7.4359 | bank:osm:relation/2315576 | 0.4827 |
| (-634.5, -29.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-634.5, -28.5) | 10.5724, osm:way/4744407, bridge | 10.5724, osm:way/4744407, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-633.5, -29.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-634.5, -27.5) | 10.5735, osm:way/4744359, bridge | 10.5735, osm:way/4744359, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-633.5, -28.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-634.5, -26.5) | 9.5846, osm:way/4744407, bridge | 9.5846, osm:way/4744407, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-633.5, -27.5) | 9.6583, osm:way/4744407, bridge | 9.6583, osm:way/4744407, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-634.5, -25.5) | 9.592, osm:way/4744359, bridge | 9.592, osm:way/4744359, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-633.5, -26.5) | 9.6643, osm:way/4744407, bridge | 9.6643, osm:way/4744407, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-633.5, -25.5) | 9.6715, osm:way/4744359, bridge | 9.6715, osm:way/4744359, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-633.5, -24.5) | 10.6764, osm:way/4744407, bridge | 10.6764, osm:way/4744407, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-633.5, -23.5) | 9.69, osm:way/4744359, bridge | 9.69, osm:way/4744359, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, -24.5) | 9.7602, osm:way/4744359, bridge | 9.7602, osm:way/4744359, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-633.5, -22.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, -23.5) | 9.7695, osm:way/4744359, bridge | 9.7695, osm:way/4744359, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-633.5, -21.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, -22.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, -21.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, -20.5) | 7.2657, bank:osm:relation/2315576, terrain | 7.2657, bank:osm:relation/2315576, terrain | 7.9186 | 7.2657 | bank:osm:relation/2315576 | 0.6528 |
| (-632.5, -19.5) | 7.3459, bank:osm:relation/2315576, terrain | 7.3459, bank:osm:relation/2315576, terrain | 7.9186 | 7.3459 | bank:osm:relation/2315576 | 0.5727 |
| (-632.5, -18.5) | 7.4261, bank:osm:relation/2315576, terrain | 7.4261, bank:osm:relation/2315576, terrain | 7.9186 | 7.4261 | bank:osm:relation/2315576 | 0.4925 |
| (-632.5, -17.5) | 7.5062, bank:osm:relation/2315576, terrain | 7.5062, bank:osm:relation/2315576, terrain | 7.9186 | 7.5062 | bank:osm:relation/2315576 | 0.4124 |
| (-631.5, -18.5) | 6.9393, bank:osm:relation/2315576, terrain | 6.9393, bank:osm:relation/2315576, terrain | 7.9186 | 6.9393 | bank:osm:relation/2315576 | 0.9793 |
| (-632.5, -16.5) | 7.5886, bank:osm:relation/2315576, terrain | 7.5886, bank:osm:relation/2315576, terrain | 7.9186 | 7.5886 | bank:osm:relation/2315576 | 0.33 |
| (-631.5, -17.5) | 7.0194, bank:osm:relation/2315576, terrain | 7.0194, bank:osm:relation/2315576, terrain | 7.9186 | 7.0194 | bank:osm:relation/2315576 | 0.8991 |
| (-632.5, -15.5) | 7.6692, bank:osm:relation/2315576, terrain | 7.6692, bank:osm:relation/2315576, terrain | 7.9186 | 7.6692 | bank:osm:relation/2315576 | 0.2494 |
| (-631.5, -16.5) | 7.1033, bank:osm:relation/2315576, terrain | 7.1033, bank:osm:relation/2315576, terrain | 7.9186 | 7.1033 | bank:osm:relation/2315576 | 0.8153 |
| (-631.5, -15.5) | 7.1881, bank:osm:relation/2315576, terrain | 7.1881, bank:osm:relation/2315576, terrain | 7.9186 | 7.1881 | bank:osm:relation/2315576 | 0.7305 |
| (-631.5, -14.5) | 7.2775, bank:osm:relation/2315576, terrain | 7.2775, bank:osm:relation/2315576, terrain | 7.9186 | 7.2775 | bank:osm:relation/2315576 | 0.6411 |
| (-631.5, -13.5) | 7.3647, bank:osm:relation/2315576, terrain | 7.3647, bank:osm:relation/2315576, terrain | 7.9186 | 7.3647 | bank:osm:relation/2315576 | 0.5539 |
| (-631.5, -12.5) | 7.417, bank:osm:relation/2315576, terrain | 7.417, bank:osm:relation/2315576, terrain | 7.9186 | 7.417 | bank:osm:relation/2315576 | 0.5016 |
| (-631.5, -11.5) | 7.4147, bank:osm:relation/2315576, terrain | 7.4147, bank:osm:relation/2315576, terrain | 7.9186 | 7.4147 | bank:osm:relation/2315576 | 0.5039 |
| (-631.5, -10.5) | 7.4082, bank:osm:relation/2315576, terrain | 7.4082, bank:osm:relation/2315576, terrain | 7.9186 | 7.4082 | bank:osm:relation/2315576 | 0.5104 |
| (-631.5, -9.5) | 7.3989, bank:osm:relation/2315576, terrain | 7.3989, bank:osm:relation/2315576, terrain | 7.9186 | 7.3989 | bank:osm:relation/2315576 | 0.5197 |
| (-631.5, -8.5) | 7.3967, bank:osm:relation/2315576, terrain | 7.3967, bank:osm:relation/2315576, terrain | 7.9186 | 7.3967 | bank:osm:relation/2315576 | 0.5218 |
| (-631.5, -7.5) | 7.3946, bank:osm:relation/2315576, terrain | 7.3946, bank:osm:relation/2315576, terrain | 7.9186 | 7.3946 | bank:osm:relation/2315576 | 0.524 |
| (-631.5, -6.5) | 7.3924, bank:osm:relation/2315576, terrain | 7.3924, bank:osm:relation/2315576, terrain | 7.9186 | 7.3924 | bank:osm:relation/2315576 | 0.5262 |
| (-631.5, -5.5) | 7.3902, bank:osm:relation/2315576, terrain | 7.3902, bank:osm:relation/2315576, terrain | 7.9186 | 7.3902 | bank:osm:relation/2315576 | 0.5284 |
| (-631.5, -4.5) | 7.3881, bank:osm:relation/2315576, terrain | 7.3881, bank:osm:relation/2315576, terrain | 7.9186 | 7.3881 | bank:osm:relation/2315576 | 0.5305 |
| (-631.5, -3.5) | 7.3859, bank:osm:relation/2315576, terrain | 7.3859, bank:osm:relation/2315576, terrain | 7.9186 | 7.3859 | bank:osm:relation/2315576 | 0.5327 |
| (-631.5, -2.5) | 7.3837, bank:osm:relation/2315576, terrain | 7.3837, bank:osm:relation/2315576, terrain | 7.9186 | 7.3837 | bank:osm:relation/2315576 | 0.5349 |
| (-631.5, -1.5) | 7.3815, bank:osm:relation/2315576, terrain | 7.3815, bank:osm:relation/2315576, terrain | 7.9186 | 7.3815 | bank:osm:relation/2315576 | 0.5371 |
| (-631.5, -0.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 0.5) | 13.6129, osm:way/4752302, bridge | 13.6129, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, -0.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 1.5) | 13.6003, osm:way/4752302, bridge | 13.6003, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 0.5) | 13.6926, osm:way/4752302, bridge | 13.6926, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 2.5) | 13.5877, osm:way/4752302, bridge | 13.5877, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 1.5) | 13.68, osm:way/4752302, bridge | 13.68, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 3.5) | 13.5749, osm:way/4752302, bridge | 13.5749, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 2.5) | 13.6674, osm:way/4752302, bridge | 13.6674, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 4.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 3.5) | 13.6529, osm:way/4752302, bridge | 13.6529, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 5.5) | 7.3559, bank:osm:relation/2315576, terrain | 7.3559, bank:osm:relation/2315576, terrain | 7.9186 | 7.3559 | bank:osm:relation/2315576 | 0.5627 |
| (-632.5, 4.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 6.5) | 7.3538, bank:osm:relation/2315576, terrain | 7.3538, bank:osm:relation/2315576, terrain | 7.9186 | 7.3538 | bank:osm:relation/2315576 | 0.5648 |
| (-631.5, 7.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 8.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 7.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 9.5) | 13.9056, osm:way/33731358, bridge | 13.9056, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 8.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 10.5) | 13.9019, osm:way/33731358, bridge | 13.9019, osm:way/33731358, bridge | 7.9186 | 6.4003 | terrain:grid | 1.5183 |
| (-632.5, 9.5) | 13.9855, osm:way/33731358, bridge | 13.9855, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 10.5) | 13.9819, osm:way/33731358, bridge | 13.9819, osm:way/33731358, bridge | 7.9186 | 6.4003 | terrain:grid | 1.5183 |

#### `water_shore_step:vis#27` (class D)

Blocked strips within reach (`shore_ramp_blocked_m` of the body: {'water:osm:relation/2315576': 192.5}):

* bank strip (-674.805, -24.664, 5.899) -> (-676.19, -25.953, 5.899) (1.892 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-676.19, -25.953, 5.899) -> (-677.574, -27.241, 5.899) (1.891 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-677.574, -27.241, 5.899) -> (-678.958, -28.529, 5.899) (1.891 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-678.958, -28.529, 5.899) -> (-680.343, -29.818, 5.899) (1.892 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-680.343, -29.818, 5.899) -> (-681.727, -31.106, 5.899) (1.891 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-681.727, -31.106, 5.899) -> (-683.112, -32.394, 5.899) (1.891 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407
* bank strip (-683.112, -32.394, 5.899) -> (-684.496, -33.683, 5.899) (1.891 m): line 2.625 osm:way/34575267, osm:way/4744359, osm:way/4744407

| Cell XY | Collision top (z, mb_id, class) | Visual top (z, owner, category) | Sheet z (vis) | Outside z (vis) | Outside owner | Offset (m) |
|---|---|---|---|---|---|---|
| (-682.5, -30.5) | 6.3942, terrain:grid, terrain | 6.3942, terrain:grid, terrain | 7.9186 | 6.3942 | terrain:grid | 1.5244 |
| (-681.5, -30.5) | 6.3942, terrain:grid, terrain | 6.3942, terrain:grid, terrain | 7.9186 | 6.3942 | terrain:grid | 1.5244 |
| (-681.5, -29.5) | 9.5118, osm:way/34575267, bridge | 9.5118, osm:way/34575267, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-680.5, -29.5) | 9.4328, osm:way/34575267, bridge | 9.4328, osm:way/34575267, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-680.5, -28.5) | 9.4401, osm:way/34575267, bridge | 9.4401, osm:way/34575267, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-679.5, -28.5) | 9.3611, osm:way/34575267, bridge | 9.3611, osm:way/34575267, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-679.5, -27.5) | 9.3684, osm:way/34575267, bridge | 9.3684, osm:way/34575267, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-678.5, -27.5) | 9.2876, osm:way/34575267, bridge | 9.2876, osm:way/34575267, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-678.5, -26.5) | 10.2949, osm:way/34575267, bridge | 10.2949, osm:way/34575267, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-677.5, -26.5) | 10.2134, osm:way/34575267, bridge | 10.2134, osm:way/34575267, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-677.5, -25.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-676.5, -25.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-676.5, -24.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-675.5, -24.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-675.5, -23.5) | 7.2445, bank:osm:relation/2315576, terrain | 7.2445, bank:osm:relation/2315576, terrain | 7.9186 | 7.2445 | bank:osm:relation/2315576 | 0.6741 |
| (-674.5, -23.5) | 7.5806, bank:osm:relation/2315576, terrain | 7.5806, bank:osm:relation/2315576, terrain | 7.9186 | 7.5806 | bank:osm:relation/2315576 | 0.338 |
| (-674.5, -22.5) | 7.2195, bank:osm:relation/2315576, terrain | 7.2195, bank:osm:relation/2315576, terrain | 7.9186 | 7.2195 | bank:osm:relation/2315576 | 0.6991 |
| (-673.5, -22.5) | 7.5852, bank:osm:relation/2315576, terrain | 7.5852, bank:osm:relation/2315576, terrain | 7.9186 | 7.5852 | bank:osm:relation/2315576 | 0.3333 |
| (-673.5, -21.5) | 7.2612, bank:osm:relation/2315576, terrain | 7.2612, bank:osm:relation/2315576, terrain | 7.9186 | 7.2612 | bank:osm:relation/2315576 | 0.6573 |
| (-672.5, -21.5) | 7.6333, bank:osm:relation/2315576, terrain | 7.6333, bank:osm:relation/2315576, terrain | 7.9186 | 7.6333 | bank:osm:relation/2315576 | 0.2853 |
| (-672.5, -20.5) | 7.3093, bank:osm:relation/2315576, terrain | 7.3093, bank:osm:relation/2315576, terrain | 7.9186 | 7.3093 | bank:osm:relation/2315576 | 0.6093 |
| (-671.5, -20.5) | 7.6813, bank:osm:relation/2315576, terrain | 7.6813, bank:osm:relation/2315576, terrain | 7.9186 | 7.6813 | bank:osm:relation/2315576 | 0.2373 |
| (-671.5, -19.5) | 7.3573, bank:osm:relation/2315576, terrain | 7.3573, bank:osm:relation/2315576, terrain | 7.9186 | 7.3573 | bank:osm:relation/2315576 | 0.5613 |

#### `water_shore_step:vis#13` (class D)

Blocked strips within reach (`shore_ramp_blocked_m` of the body: {'water:osm:relation/2315576': 192.5}):

* bank strip (-655.257, 52.116, 5.899) -> (-655.458, 50.166, 5.899) (1.96 m): line 5.875 osm:way/23615351
* bank strip (-655.458, 50.166, 5.899) -> (-655.66, 48.217, 5.899) (1.959 m): line 5.875 osm:way/23615351
* bank strip (-656.062, 44.317, 5.899) -> (-656.264, 42.367, 5.899) (1.96 m): line 2.625 osm:way/317417201
* bank strip (-656.264, 42.367, 5.899) -> (-656.465, 40.418, 5.899) (1.959 m): line 2.625 osm:way/317417201
* bank strip (-656.465, 40.418, 5.899) -> (-656.666, 38.468, 5.899) (1.96 m): line 2.625 osm:way/317417201
* bank strip (-656.666, 38.468, 5.899) -> (-656.867, 36.518, 5.899) (1.96 m): line 2.625 osm:way/317417201
* bank strip (-657.874, 26.77, 5.899) -> (-658.075, 24.82, 5.899) (1.96 m): line 7.5 osm:way/34575500
* bank strip (-658.075, 24.82, 5.899) -> (-658.277, 22.87, 5.899) (1.96 m): line 7.5 osm:way/34575500
* bank strip (-658.277, 22.87, 5.899) -> (-658.478, 20.92, 5.899) (1.96 m): line 7.5 osm:way/34575500
* bank strip (-658.478, 20.92, 5.899) -> (-658.679, 18.971, 5.899) (1.959 m): line 7.5 osm:way/34575500
* bank strip (-658.679, 18.971, 5.899) -> (-658.881, 17.021, 5.899) (1.96 m): line 7.5 osm:way/34575500
* bank strip (-658.881, 17.021, 5.899) -> (-659.082, 15.071, 5.899) (1.96 m): line 7.5 osm:way/34575500; line 4.25 osm:way/33731358, osm:way/34575500
* bank strip (-659.082, 15.071, 5.899) -> (-659.283, 13.121, 5.899) (1.96 m): line 7.5 osm:way/34575500; line 4.25 osm:way/33731358, osm:way/34575500
* bank strip (-659.283, 13.121, 5.899) -> (-659.485, 11.172, 5.899) (1.959 m): line 7.5 osm:way/34575500; line 4.25 osm:way/33731358, osm:way/34575500
* bank strip (-659.485, 11.172, 5.899) -> (-659.686, 9.222, 5.899) (1.96 m): line 7.5 osm:way/34575500; line 4.25 osm:way/33731358, osm:way/34575500
* bank strip (-659.686, 9.222, 5.899) -> (-659.887, 7.272, 5.899) (1.96 m): line 4.25 osm:way/33731358, osm:way/34575500
* bank strip (-659.887, 7.272, 5.899) -> (-660.089, 5.323, 5.899) (1.959 m): line 4.25 osm:way/33731358, osm:way/34575500
* bank strip (-661.66, -1.986, 5.899) -> (-662.116, -3.772, 5.899) (1.843 m): line 2.625 osm:way/4752302
* bank strip (-662.116, -3.772, 5.899) -> (-662.573, -5.559, 5.899) (1.845 m): line 2.625 osm:way/4752302
* bank strip (-662.573, -5.559, 5.899) -> (-663.03, -7.345, 5.899) (1.844 m): line 2.625 osm:way/4752302
* bank strip (-663.03, -7.345, 5.899) -> (-663.859, -9.117, 5.899) (1.956 m): line 2.625 osm:way/4752302
* bank strip (-663.859, -9.117, 5.899) -> (-664.688, -10.889, 5.899) (1.956 m): line 2.625 osm:way/4752302
* bank strip (-664.688, -10.889, 5.899) -> (-665.517, -12.661, 5.899) (1.956 m): line 2.625 osm:way/4752302

| Cell XY | Collision top (z, mb_id, class) | Visual top (z, owner, category) | Sheet z (vis) | Outside z (vis) | Outside owner | Offset (m) |
|---|---|---|---|---|---|---|
| (-668.5, -16.5) | 7.5013, bank:osm:relation/2315576, terrain | 7.5013, bank:osm:relation/2315576, terrain | 7.9186 | 7.5013 | bank:osm:relation/2315576 | 0.4173 |
| (-668.5, -15.5) | 7.1773, bank:osm:relation/2315576, terrain | 7.1773, bank:osm:relation/2315576, terrain | 7.9186 | 7.1773 | bank:osm:relation/2315576 | 0.7413 |
| (-667.5, -15.5) | 7.6062, bank:osm:relation/2315576, terrain | 7.6062, bank:osm:relation/2315576, terrain | 7.9186 | 7.6062 | bank:osm:relation/2315576 | 0.3124 |
| (-667.5, -14.5) | 7.3971, bank:osm:relation/2315576, terrain | 7.3971, bank:osm:relation/2315576, terrain | 7.9186 | 7.3971 | bank:osm:relation/2315576 | 0.5215 |
| (-667.5, -13.5) | 7.188, bank:osm:relation/2315576, terrain | 7.188, bank:osm:relation/2315576, terrain | 7.9186 | 7.188 | bank:osm:relation/2315576 | 0.7306 |
| (-666.5, -13.5) | 7.6348, bank:osm:relation/2315576, terrain | 7.6348, bank:osm:relation/2315576, terrain | 7.9186 | 7.6348 | bank:osm:relation/2315576 | 0.2837 |
| (-666.5, -12.5) | 7.4257, bank:osm:relation/2315576, terrain | 7.4257, bank:osm:relation/2315576, terrain | 7.9186 | 7.4257 | bank:osm:relation/2315576 | 0.4928 |
| (-666.5, -11.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-665.5, -12.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-666.5, -10.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-665.5, -11.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-665.5, -10.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-665.5, -9.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-665.5, -8.5) | 15.0205, osm:way/4752302, bridge | 15.0205, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-664.5, -9.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-664.5, -8.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-664.5, -7.5) | 14.0357, osm:way/4752302, bridge | 14.0357, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-664.5, -6.5) | 14.0394, osm:way/4752302, bridge | 14.0394, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-663.5, -7.5) | 14.0471, osm:way/4752302, bridge | 14.0471, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-664.5, -5.5) | 14.0433, osm:way/4752302, bridge | 14.0433, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-663.5, -6.5) | 14.0508, osm:way/4752302, bridge | 14.0508, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-663.5, -5.5) | 14.0545, osm:way/4752302, bridge | 14.0545, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-663.5, -4.5) | 14.0584, osm:way/4752302, bridge | 14.0584, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-663.5, -3.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-662.5, -4.5) | 14.0696, osm:way/4752302, bridge | 14.0696, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-663.5, -2.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-662.5, -3.5) | 15.0735, osm:way/4752302, bridge | 15.0735, osm:way/4752302, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-663.5, -1.5) | 6.9596, bank:osm:relation/2315576, terrain | 6.9596, bank:osm:relation/2315576, terrain | 7.9186 | 6.9596 | bank:osm:relation/2315576 | 0.959 |
| (-662.5, -2.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-662.5, -1.5) | 7.4376, bank:osm:relation/2315576, terrain | 7.4376, bank:osm:relation/2315576, terrain | 7.9186 | 7.4376 | bank:osm:relation/2315576 | 0.481 |
| (-662.5, -0.5) | 7.3154, bank:osm:relation/2315576, terrain | 7.3154, bank:osm:relation/2315576, terrain | 7.9186 | 7.3154 | bank:osm:relation/2315576 | 0.6032 |
| (-662.5, 0.5) | 7.1932, bank:osm:relation/2315576, terrain | 7.1932, bank:osm:relation/2315576, terrain | 7.9186 | 7.1932 | bank:osm:relation/2315576 | 0.7253 |
| (-662.5, 1.5) | 7.0711, bank:osm:relation/2315576, terrain | 7.0711, bank:osm:relation/2315576, terrain | 7.9186 | 7.0711 | bank:osm:relation/2315576 | 0.8475 |
| (-661.5, 0.5) | 7.6712, bank:osm:relation/2315576, terrain | 7.6712, bank:osm:relation/2315576, terrain | 7.9186 | 7.6712 | bank:osm:relation/2315576 | 0.2474 |
| (-662.5, 2.5) | 6.9489, bank:osm:relation/2315576, terrain | 6.9489, bank:osm:relation/2315576, terrain | 7.9186 | 6.9489 | bank:osm:relation/2315576 | 0.9697 |
| (-661.5, 1.5) | 7.549, bank:osm:relation/2315576, terrain | 7.549, bank:osm:relation/2315576, terrain | 7.9186 | 7.549 | bank:osm:relation/2315576 | 0.3695 |
| (-661.5, 2.5) | 7.4269, bank:osm:relation/2315576, terrain | 7.4269, bank:osm:relation/2315576, terrain | 7.9186 | 7.4269 | bank:osm:relation/2315576 | 0.4917 |
| (-661.5, 3.5) | 7.3047, bank:osm:relation/2315576, terrain | 7.3047, bank:osm:relation/2315576, terrain | 7.9186 | 7.3047 | bank:osm:relation/2315576 | 0.6139 |
| (-661.5, 4.5) | 7.2477, bank:osm:relation/2315576, terrain | 7.2477, bank:osm:relation/2315576, terrain | 7.9186 | 7.2477 | bank:osm:relation/2315576 | 0.6709 |
| (-661.5, 5.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-661.5, 6.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 5.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-661.5, 7.5) | 15.3671, osm:way/33731358, bridge | 15.3671, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 6.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-661.5, 8.5) | 14.3653, osm:way/33731358, bridge | 14.3653, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 7.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-661.5, 9.5) | 14.3636, osm:way/33731358, bridge | 14.3636, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 8.5) | 14.3266, osm:way/33731358, bridge | 14.3266, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-661.5, 10.5) | 14.3618, osm:way/33731358, bridge | 14.3618, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 9.5) | 14.3248, osm:way/33731358, bridge | 14.3248, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 10.5) | 14.3231, osm:way/33731358, bridge | 14.3231, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 11.5) | 15.3454, osm:way/34575500, bridge | 15.3454, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 12.5) | 14.3416, osm:way/34575500, bridge | 14.3416, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 11.5) | 14.2826, osm:way/33731358, bridge | 14.2826, osm:way/33731358, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 13.5) | 14.3379, osm:way/34575500, bridge | 14.3379, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 12.5) | 14.3115, osm:way/34575500, bridge | 14.3115, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 14.5) | 14.3342, osm:way/34575500, bridge | 14.3342, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 13.5) | 14.3078, osm:way/34575500, bridge | 14.3078, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 15.5) | 14.3305, osm:way/34575500, bridge | 14.3305, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 14.5) | 14.304, osm:way/34575500, bridge | 14.304, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 16.5) | 14.3267, osm:way/34575500, bridge | 14.3267, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 15.5) | 14.3003, osm:way/34575500, bridge | 14.3003, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 17.5) | 14.323, osm:way/34575500, bridge | 14.323, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 16.5) | 14.2966, osm:way/34575500, bridge | 14.2966, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 18.5) | 14.3193, osm:way/34575500, bridge | 14.3193, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 17.5) | 14.2929, osm:way/34575500, bridge | 14.2929, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 19.5) | 14.3156, osm:way/34575500, bridge | 14.3156, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 18.5) | 14.2892, osm:way/34575500, bridge | 14.2892, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-660.5, 20.5) | 14.3119, osm:way/34575500, bridge | 14.3119, osm:way/34575500, bridge | 7.9186 | 6.5191 | terrain:grid | 1.3995 |
| (-659.5, 19.5) | 14.2854, osm:way/34575500, bridge | 14.2854, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 20.5) | 14.2817, osm:way/34575500, bridge | 14.2817, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 21.5) | 14.278, osm:way/34575500, bridge | 14.278, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 22.5) | 14.2743, osm:way/34575500, bridge | 14.2743, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-658.5, 21.5) | 14.2478, osm:way/34575500, bridge | 14.2478, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 23.5) | 14.2705, osm:way/34575500, bridge | 14.2705, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-658.5, 22.5) | 14.2441, osm:way/34575500, bridge | 14.2441, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 24.5) | 14.2668, osm:way/34575500, bridge | 14.2668, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-658.5, 23.5) | 14.2404, osm:way/34575500, bridge | 14.2404, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 25.5) | 15.2631, osm:way/34575500, bridge | 15.2631, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-658.5, 24.5) | 14.2367, osm:way/34575500, bridge | 14.2367, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 26.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-658.5, 25.5) | 15.2329, osm:way/34575500, bridge | 15.233, osm:way/34575500, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 27.5) | 7.1611, bank:osm:relation/2315576, terrain | 7.1611, bank:osm:relation/2315576, terrain | 7.9186 | 7.1611 | bank:osm:relation/2315576 | 0.7575 |
| (-658.5, 26.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-659.5, 28.5) | 7.1005, bank:osm:relation/2315576, terrain | 7.1005, bank:osm:relation/2315576, terrain | 7.9186 | 7.1005 | bank:osm:relation/2315576 | 0.8181 |
| (-658.5, 27.5) | 7.5946, bank:osm:relation/2315576, terrain | 7.5946, bank:osm:relation/2315576, terrain | 7.9186 | 7.5946 | bank:osm:relation/2315576 | 0.324 |
| (-659.5, 29.5) | 7.0459, bank:osm:relation/2315576, terrain | 7.0459, bank:osm:relation/2315576, terrain | 7.9186 | 7.0459 | bank:osm:relation/2315576 | 0.8727 |
| (-658.5, 28.5) | 7.5453, bank:osm:relation/2315576, terrain | 7.5453, bank:osm:relation/2315576, terrain | 7.9186 | 7.5453 | bank:osm:relation/2315576 | 0.3733 |
| (-658.5, 29.5) | 7.4928, bank:osm:relation/2315576, terrain | 7.4928, bank:osm:relation/2315576, terrain | 7.9186 | 7.4928 | bank:osm:relation/2315576 | 0.4257 |
| (-658.5, 30.5) | 7.4356, bank:osm:relation/2315576, terrain | 7.4356, bank:osm:relation/2315576, terrain | 7.9186 | 7.4356 | bank:osm:relation/2315576 | 0.483 |
| (-658.5, 31.5) | 7.3795, bank:osm:relation/2315576, terrain | 7.3795, bank:osm:relation/2315576, terrain | 7.9186 | 7.3795 | bank:osm:relation/2315576 | 0.5391 |
| (-658.5, 32.5) | 7.3221, bank:osm:relation/2315576, terrain | 7.3221, bank:osm:relation/2315576, terrain | 7.9186 | 7.3221 | bank:osm:relation/2315576 | 0.5964 |
| (-658.5, 33.5) | 7.2688, bank:osm:relation/2315576, terrain | 7.2688, bank:osm:relation/2315576, terrain | 7.9186 | 7.2688 | bank:osm:relation/2315576 | 0.6498 |
| (-658.5, 34.5) | 7.2075, bank:osm:relation/2315576, terrain | 7.2075, bank:osm:relation/2315576, terrain | 7.9186 | 7.2075 | bank:osm:relation/2315576 | 0.7111 |
| (-658.5, 35.5) | 7.1535, bank:osm:relation/2315576, terrain | 7.1535, bank:osm:relation/2315576, terrain | 7.9186 | 7.1535 | bank:osm:relation/2315576 | 0.7651 |
| (-657.5, 34.5) | 7.6936, bank:osm:relation/2315576, terrain | 7.6936, bank:osm:relation/2315576, terrain | 7.9186 | 7.6936 | bank:osm:relation/2315576 | 0.225 |
| (-658.5, 36.5) | 7.0992, bank:osm:relation/2315576, terrain | 7.0992, bank:osm:relation/2315576, terrain | 7.9186 | 7.0992 | bank:osm:relation/2315576 | 0.8194 |
| (-657.5, 35.5) | 7.6413, bank:osm:relation/2315576, terrain | 7.6413, bank:osm:relation/2315576, terrain | 7.9186 | 7.6413 | bank:osm:relation/2315576 | 0.2773 |
| (-658.5, 37.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-657.5, 36.5) | 7.5895, bank:osm:relation/2315576, terrain | 7.5895, bank:osm:relation/2315576, terrain | 7.9186 | 7.5895 | bank:osm:relation/2315576 | 0.3291 |
| (-658.5, 38.5) | 19.7404, osm:way/317417201, bridge | 19.7404, osm:way/317417201, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-657.5, 37.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-658.5, 39.5) | 18.7502, osm:way/317417201, bridge | 18.7502, osm:way/317417201, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-657.5, 38.5) | 19.8198, osm:way/317417201, bridge | 19.8198, osm:way/317417201, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-657.5, 39.5) | 18.8296, osm:way/317417201, bridge | 18.8296, osm:way/317417201, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-657.5, 40.5) | 18.8393, osm:way/317417201, bridge | 18.8393, osm:way/317417201, bridge | 7.9186 | 6.4139 | terrain:grid | 1.5047 |
| (-657.5, 41.5) | 18.8491, osm:way/317417201, bridge | 18.8491, osm:way/317417201, bridge | 7.9186 | 6.4046 | terrain:grid | 1.514 |
| (-656.5, 40.5) | 18.9187, osm:way/317417201, bridge | 18.9187, osm:way/317417201, bridge | 7.9186 | 6.4139 | terrain:grid | 1.5047 |
| (-657.5, 42.5) | 19.8588, osm:way/317417201, bridge | 19.8588, osm:way/317417201, bridge | 7.9186 | 6.3953 | terrain:grid | 1.5233 |
| (-656.5, 41.5) | 18.9285, osm:way/317417201, bridge | 18.9285, osm:way/317417201, bridge | 7.9186 | 6.4046 | terrain:grid | 1.514 |
| (-656.5, 42.5) | 19.9382, osm:way/317417201, bridge | 19.9382, osm:way/317417201, bridge | 7.9186 | 6.3953 | terrain:grid | 1.5233 |
| (-656.5, 43.5) | 6.386, terrain:grid, terrain | 6.386, terrain:grid, terrain | 7.9186 | 6.386 | terrain:grid | 1.5326 |
| (-656.5, 44.5) | 7.6898, bank:osm:relation/2315576, terrain | 7.6898, bank:osm:relation/2315576, terrain | 7.9186 | 7.6898 | bank:osm:relation/2315576 | 0.2287 |
| (-656.5, 45.5) | 7.6427, bank:osm:relation/2315576, terrain | 7.6427, bank:osm:relation/2315576, terrain | 7.9186 | 7.6427 | bank:osm:relation/2315576 | 0.2759 |
| (-657.5, 44.5) | 7.2328, bank:osm:relation/2315576, terrain | 7.2328, bank:osm:relation/2315576, terrain | 7.9186 | 7.2328 | bank:osm:relation/2315576 | 0.6858 |
| (-656.5, 46.5) | 7.5854, bank:osm:relation/2315576, terrain | 7.5854, bank:osm:relation/2315576, terrain | 7.9186 | 7.5854 | bank:osm:relation/2315576 | 0.3332 |
| (-657.5, 45.5) | 7.1856, bank:osm:relation/2315576, terrain | 7.1856, bank:osm:relation/2315576, terrain | 7.9186 | 7.1856 | bank:osm:relation/2315576 | 0.733 |
| (-656.5, 47.5) | 7.5367, bank:osm:relation/2315576, terrain | 7.5367, bank:osm:relation/2315576, terrain | 7.9186 | 7.5367 | bank:osm:relation/2315576 | 0.3819 |
| (-657.5, 46.5) | 7.1132, bank:osm:relation/2315576, terrain | 7.1132, bank:osm:relation/2315576, terrain | 7.9186 | 7.1132 | bank:osm:relation/2315576 | 0.8054 |
| (-657.5, 47.5) | 7.0622, bank:osm:relation/2315576, terrain | 7.0622, bank:osm:relation/2315576, terrain | 7.9186 | 7.0622 | bank:osm:relation/2315576 | 0.8564 |

#### `water_shore_step:vis#4` (class D)

Blocked strips within reach (`shore_ramp_blocked_m` of the body: {'water:osm:relation/2315576': 192.5}):

* bank strip (-607.922, 172.352, 5.899) -> (-608.825, 170.586, 5.899) (1.983 m): line 2.625 osm:way/4752301, osm:way/4758298
* bank strip (-608.825, 170.586, 5.899) -> (-609.727, 168.82, 5.899) (1.983 m): line 2.625 osm:way/4752301, osm:way/4758298
* bank strip (-609.727, 168.82, 5.899) -> (-610.63, 167.054, 5.899) (1.983 m): line 2.625 osm:way/4752301, osm:way/4758298
* bank strip (-610.63, 167.054, 5.899) -> (-611.532, 165.288, 5.899) (1.983 m): line 2.625 osm:way/4752301, osm:way/4758298
* bank strip (-611.532, 165.288, 5.899) -> (-612.435, 163.522, 5.899) (1.983 m): line 2.625 osm:way/4752301, osm:way/4758298
* bank strip (-634.955, 119.687, 5.899) -> (-635.93, 118.129, 5.899) (1.838 m): line 2.0 osm:way/83926163
* bank strip (-632.685, 24.949, 5.899) -> (-632.694, 26.933, 5.899) (1.984 m): line 7.5 osm:way/34575500
* bank strip (-632.694, 26.933, 5.899) -> (-632.702, 28.917, 5.899) (1.984 m): line 7.5 osm:way/34575500
* bank strip (-632.702, 28.917, 5.899) -> (-632.711, 30.901, 5.899) (1.984 m): line 7.5 osm:way/34575500
* bank strip (-632.753, 40.823, 5.899) -> (-632.762, 42.807, 5.899) (1.984 m): line 2.625 osm:way/317417201
* bank strip (-632.762, 42.807, 5.899) -> (-632.77, 44.791, 5.899) (1.984 m): line 2.625 osm:way/317417201
* bank strip (-632.77, 44.791, 5.899) -> (-632.778, 46.775, 5.899) (1.984 m): line 2.625 osm:way/317417201
* bank strip (-632.795, 50.744, 5.899) -> (-632.804, 52.728, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.804, 52.728, 5.899) -> (-632.812, 54.712, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.812, 54.712, 5.899) -> (-632.821, 56.696, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.821, 56.696, 5.899) -> (-632.829, 58.681, 5.899) (1.985 m): line 5.875 osm:way/23615351
* bank strip (-632.829, 58.681, 5.899) -> (-632.838, 60.665, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.838, 60.665, 5.899) -> (-632.846, 62.649, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.846, 62.649, 5.899) -> (-632.855, 64.633, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.855, 64.633, 5.899) -> (-632.863, 66.618, 5.899) (1.985 m): line 4.25 osm:way/214883367, osm:way/34575263; line 5.875 osm:way/23615351
* bank strip (-632.863, 66.618, 5.899) -> (-632.872, 68.602, 5.899) (1.984 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-632.872, 68.602, 5.899) -> (-632.88, 70.586, 5.899) (1.984 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-632.88, 70.586, 5.899) -> (-632.889, 72.57, 5.899) (1.984 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-632.889, 72.57, 5.899) -> (-632.897, 74.554, 5.899) (1.984 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-632.897, 74.554, 5.899) -> (-632.906, 76.539, 5.899) (1.985 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-616.292, 113.58, 5.899) -> (-615.439, 115.301, 5.899) (1.921 m): line 2.0 osm:way/83926163
* bank strip (-615.439, 115.301, 5.899) -> (-614.586, 117.021, 5.899) (1.92 m): line 2.0 osm:way/83926163
* bank strip (-614.586, 117.021, 5.899) -> (-613.733, 118.741, 5.899) (1.92 m): line 2.0 osm:way/83926163
* bank strip (-613.733, 118.741, 5.899) -> (-612.88, 120.462, 5.899) (1.921 m): line 2.0 osm:way/83926163
* bank strip (-600.557, 147.105, 5.899) -> (-599.763, 148.93, 5.899) (1.99 m): line 2.625 osm:way/4752301, osm:way/4758298
* bank strip (-599.763, 148.93, 5.899) -> (-598.97, 150.755, 5.899) (1.99 m): line 2.625 osm:way/4752301, osm:way/4758298
* bank strip (-598.97, 150.755, 5.899) -> (-598.176, 152.58, 5.899) (1.99 m): line 2.625 osm:way/4752301, osm:way/4758298
* bank strip (-598.176, 152.58, 5.899) -> (-597.382, 154.405, 5.899) (1.99 m): line 2.625 osm:way/4752301, osm:way/4758298
* bank strip (-597.382, 154.405, 5.899) -> (-596.588, 156.23, 5.899) (1.99 m): line 2.625 osm:way/4752301, osm:way/4758298

| Cell XY | Collision top (z, mb_id, class) | Visual top (z, owner, category) | Sheet z (vis) | Outside z (vis) | Outside owner | Offset (m) |
|---|---|---|---|---|---|---|
| (-632.5, 28.5) | 13.6103, osm:way/34575500, bridge | 13.6103, osm:way/34575500, bridge | 7.9186 | 6.3701 | terrain:grid | 1.5484 |
| (-632.5, 29.5) | 6.3811, terrain:grid, terrain | 6.3811, terrain:grid, terrain | 7.9186 | 6.3811 | terrain:grid | 1.5375 |
| (-631.5, 28.5) | 13.5309, osm:way/34575500, bridge | 13.5309, osm:way/34575500, bridge | 7.9186 | 6.3829 | terrain:grid | 1.5356 |
| (-632.5, 30.5) | 6.3866, terrain:grid, terrain | 6.3866, terrain:grid, terrain | 7.9186 | 6.3866 | terrain:grid | 1.532 |
| (-631.5, 29.5) | 6.3939, terrain:grid, terrain | 6.3939, terrain:grid, terrain | 7.9186 | 6.3939 | terrain:grid | 1.5247 |
| (-631.5, 30.5) | 6.3994, terrain:grid, terrain | 6.3994, terrain:grid, terrain | 7.9186 | 6.3994 | terrain:grid | 1.5192 |
| (-631.5, 31.5) | 7.3142, bank:osm:relation/2315576, terrain | 7.3142, bank:osm:relation/2315576, terrain | 7.9186 | 7.3142 | bank:osm:relation/2315576 | 0.6044 |
| (-631.5, 32.5) | 7.312, bank:osm:relation/2315576, terrain | 7.312, bank:osm:relation/2315576, terrain | 7.9186 | 7.312 | bank:osm:relation/2315576 | 0.6066 |
| (-631.5, 33.5) | 7.3096, bank:osm:relation/2315576, terrain | 7.3096, bank:osm:relation/2315576, terrain | 7.9186 | 7.3096 | bank:osm:relation/2315576 | 0.6089 |
| (-631.5, 34.5) | 7.3075, bank:osm:relation/2315576, terrain | 7.3075, bank:osm:relation/2315576, terrain | 7.9186 | 7.3075 | bank:osm:relation/2315576 | 0.6111 |
| (-631.5, 35.5) | 7.3051, bank:osm:relation/2315576, terrain | 7.3051, bank:osm:relation/2315576, terrain | 7.9186 | 7.3051 | bank:osm:relation/2315576 | 0.6135 |
| (-631.5, 36.5) | 7.3029, bank:osm:relation/2315576, terrain | 7.3029, bank:osm:relation/2315576, terrain | 7.9186 | 7.3029 | bank:osm:relation/2315576 | 0.6156 |
| (-631.5, 37.5) | 7.3005, bank:osm:relation/2315576, terrain | 7.3005, bank:osm:relation/2315576, terrain | 7.9186 | 7.3005 | bank:osm:relation/2315576 | 0.618 |
| (-631.5, 38.5) | 7.2984, bank:osm:relation/2315576, terrain | 7.2984, bank:osm:relation/2315576, terrain | 7.9186 | 7.2984 | bank:osm:relation/2315576 | 0.6202 |
| (-631.5, 39.5) | 7.3024, bank:osm:relation/2315576, terrain | 7.3024, bank:osm:relation/2315576, terrain | 7.9186 | 7.3024 | bank:osm:relation/2315576 | 0.6161 |
| (-631.5, 40.5) | 7.302, bank:osm:relation/2315576, terrain | 7.302, bank:osm:relation/2315576, terrain | 7.9186 | 7.302 | bank:osm:relation/2315576 | 0.6166 |
| (-631.5, 41.5) | 6.4158, terrain:grid, terrain | 6.4158, terrain:grid, terrain | 7.9186 | 6.4158 | terrain:grid | 1.5028 |
| (-631.5, 42.5) | 18.5019, osm:way/317417201, bridge | 18.5019, osm:way/317417201, bridge | 7.9186 | 6.4158 | terrain:grid | 1.5028 |
| (-632.5, 41.5) | 19.5829, osm:way/317417201, bridge | 19.5829, osm:way/317417201, bridge | 7.9186 | 6.4139 | terrain:grid | 1.5047 |
| (-631.5, 43.5) | 18.4931, osm:way/317417201, bridge | 18.4931, osm:way/317417201, bridge | 7.9186 | 6.4158 | terrain:grid | 1.5028 |
| (-632.5, 42.5) | 18.574, osm:way/317417201, bridge | 18.5741, osm:way/317417201, bridge | 7.9186 | 6.4139 | terrain:grid | 1.5047 |
| (-631.5, 44.5) | 18.4843, osm:way/317417201, bridge | 18.4843, osm:way/317417201, bridge | 7.9186 | 6.4158 | terrain:grid | 1.5028 |
| (-632.5, 43.5) | 18.5652, osm:way/317417201, bridge | 18.5652, osm:way/317417201, bridge | 7.9186 | 6.4139 | terrain:grid | 1.5047 |
| (-631.5, 45.5) | 18.4755, osm:way/317417201, bridge | 18.4755, osm:way/317417201, bridge | 7.9186 | 6.4158 | terrain:grid | 1.5028 |
| (-632.5, 44.5) | 18.5564, osm:way/317417201, bridge | 18.5564, osm:way/317417201, bridge | 7.9186 | 6.4139 | terrain:grid | 1.5047 |
| (-631.5, 46.5) | 6.4158, terrain:grid, terrain | 6.4158, terrain:grid, terrain | 7.9186 | 6.4158 | terrain:grid | 1.5028 |
| (-632.5, 45.5) | 19.5476, osm:way/317417201, bridge | 19.5476, osm:way/317417201, bridge | 7.9186 | 6.4139 | terrain:grid | 1.5047 |
| (-631.5, 47.5) | 7.2849, bank:osm:relation/2315576, terrain | 7.2849, bank:osm:relation/2315576, terrain | 7.9186 | 7.2849 | bank:osm:relation/2315576 | 0.6337 |
| (-632.5, 46.5) | 6.4139, terrain:grid, terrain | 6.4139, terrain:grid, terrain | 7.9186 | 6.4139 | terrain:grid | 1.5047 |
| (-631.5, 48.5) | 7.2827, bank:osm:relation/2315576, terrain | 7.2827, bank:osm:relation/2315576, terrain | 7.9186 | 7.2827 | bank:osm:relation/2315576 | 0.6358 |
| (-631.5, 49.5) | 7.2814, bank:osm:relation/2315576, terrain | 7.2814, bank:osm:relation/2315576, terrain | 7.9186 | 7.2814 | bank:osm:relation/2315576 | 0.6372 |
| (-631.5, 50.5) | 7.2795, bank:osm:relation/2315576, terrain | 7.2795, bank:osm:relation/2315576, terrain | 7.9186 | 7.2795 | bank:osm:relation/2315576 | 0.6391 |
| (-631.5, 51.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 52.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 51.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 53.5) | 15.1014, osm:way/23615351, bridge | 15.1014, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 52.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 54.5) | 14.1056, osm:way/23615351, bridge | 14.1056, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 53.5) | 14.0668, osm:way/23615351, bridge | 14.0668, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 55.5) | 14.1099, osm:way/23615351, bridge | 14.1099, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 54.5) | 14.071, osm:way/23615351, bridge | 14.071, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 56.5) | 14.1141, osm:way/23615351, bridge | 14.1141, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 55.5) | 14.0752, osm:way/23615351, bridge | 14.0752, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 57.5) | 14.1183, osm:way/23615351, bridge | 14.1183, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 56.5) | 14.0795, osm:way/23615351, bridge | 14.0795, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 58.5) | 14.1225, osm:way/23615351, bridge | 14.1226, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 57.5) | 14.0837, osm:way/23615351, bridge | 14.0837, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 59.5) | 14.1268, osm:way/23615351, bridge | 14.1268, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 58.5) | 14.0879, osm:way/23615351, bridge | 14.0879, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 60.5) | 14.131, osm:way/23615351, bridge | 14.131, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 59.5) | 14.0922, osm:way/23615351, bridge | 14.0922, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 61.5) | 14.1352, osm:way/23615351, bridge | 14.1352, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 60.5) | 14.0964, osm:way/23615351, bridge | 14.0964, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 62.5) | 14.1395, osm:way/23615351, bridge | 14.1395, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 61.5) | 14.1006, osm:way/23615351, bridge | 14.1006, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 63.5) | 14.1437, osm:way/23615351, bridge | 14.1437, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 62.5) | 14.1049, osm:way/23615351, bridge | 14.1049, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 64.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 63.5) | 14.1091, osm:way/23615351, bridge | 14.1091, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 65.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 64.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 66.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 65.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 67.5) | 10.0307, osm:way/214883367, bridge | 10.0307, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 66.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 68.5) | 10.0217, osm:way/214883367, bridge | 10.0217, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 67.5) | 10.1102, osm:way/214883367, bridge | 10.1102, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 69.5) | 10.0127, osm:way/214883367, bridge | 10.0127, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 68.5) | 10.1012, osm:way/214883367, bridge | 10.1012, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 70.5) | 10.0038, osm:way/214883367, bridge | 10.0038, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 69.5) | 10.0922, osm:way/214883367, bridge | 10.0922, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 71.5) | 9.9948, osm:way/214883367, bridge | 9.9948, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 70.5) | 10.0833, osm:way/214883367, bridge | 10.0833, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 72.5) | 9.9859, osm:way/214883367, bridge | 9.9859, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 71.5) | 10.0743, osm:way/214883367, bridge | 10.0743, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 73.5) | 9.9769, osm:way/214883367, bridge | 9.9769, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 72.5) | 10.0654, osm:way/214883367, bridge | 10.0654, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 74.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 73.5) | 10.0564, osm:way/214883367, bridge | 10.0564, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 75.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-632.5, 74.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 76.5) | 7.2176, bank:osm:relation/2315576, terrain | 7.2176, bank:osm:relation/2315576, terrain | 7.9186 | 7.2176 | bank:osm:relation/2315576 | 0.701 |
| (-632.5, 75.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-631.5, 77.5) | 7.3251, bank:osm:relation/2315576, terrain | 7.3251, bank:osm:relation/2315576, terrain | 7.9186 | 7.3251 | bank:osm:relation/2315576 | 0.5935 |
| (-632.5, 76.5) | 7.6991, bank:osm:relation/2315576, terrain | 7.6991, bank:osm:relation/2315576, terrain | 7.9186 | 7.6991 | bank:osm:relation/2315576 | 0.2195 |
| (-631.5, 78.5) | 7.4326, bank:osm:relation/2315576, terrain | 7.4326, bank:osm:relation/2315576, terrain | 7.9186 | 7.4326 | bank:osm:relation/2315576 | 0.486 |
| (-631.5, 79.5) | 7.5401, bank:osm:relation/2315576, terrain | 7.5401, bank:osm:relation/2315576, terrain | 7.9186 | 7.5401 | bank:osm:relation/2315576 | 0.3785 |
| (-630.5, 78.5) | 6.9511, bank:osm:relation/2315576, terrain | 6.9511, bank:osm:relation/2315576, terrain | 7.9186 | 6.9511 | bank:osm:relation/2315576 | 0.9674 |
| (-631.5, 80.5) | 7.6476, bank:osm:relation/2315576, terrain | 7.6476, bank:osm:relation/2315576, terrain | 7.9186 | 7.6476 | bank:osm:relation/2315576 | 0.271 |
| (-630.5, 79.5) | 7.0586, bank:osm:relation/2315576, terrain | 7.0586, bank:osm:relation/2315576, terrain | 7.9186 | 7.0586 | bank:osm:relation/2315576 | 0.8599 |
| (-630.5, 80.5) | 7.1661, bank:osm:relation/2315576, terrain | 7.1661, bank:osm:relation/2315576, terrain | 7.9186 | 7.1661 | bank:osm:relation/2315576 | 0.7524 |
| (-630.5, 81.5) | 7.2736, bank:osm:relation/2315576, terrain | 7.2736, bank:osm:relation/2315576, terrain | 7.9186 | 7.2736 | bank:osm:relation/2315576 | 0.6449 |
| (-630.5, 82.5) | 7.3811, bank:osm:relation/2315576, terrain | 7.3811, bank:osm:relation/2315576, terrain | 7.9186 | 7.3811 | bank:osm:relation/2315576 | 0.5374 |
| (-630.5, 83.5) | 7.4886, bank:osm:relation/2315576, terrain | 7.4886, bank:osm:relation/2315576, terrain | 7.9186 | 7.4886 | bank:osm:relation/2315576 | 0.43 |
| (-630.5, 84.5) | 7.5961, bank:osm:relation/2315576, terrain | 7.5961, bank:osm:relation/2315576, terrain | 7.9186 | 7.5961 | bank:osm:relation/2315576 | 0.3225 |
| (-629.5, 83.5) | 7.0072, bank:osm:relation/2315576, terrain | 7.0072, bank:osm:relation/2315576, terrain | 7.9186 | 7.0072 | bank:osm:relation/2315576 | 0.9114 |
| (-629.5, 84.5) | 7.1214, bank:osm:relation/2315576, terrain | 7.1214, bank:osm:relation/2315576, terrain | 7.9186 | 7.1214 | bank:osm:relation/2315576 | 0.7971 |
| (-629.5, 85.5) | 7.3219, bank:osm:relation/2315576, terrain | 7.3219, bank:osm:relation/2315576, terrain | 7.9186 | 7.3219 | bank:osm:relation/2315576 | 0.5967 |
| (-629.5, 86.5) | 7.5223, bank:osm:relation/2315576, terrain | 7.5223, bank:osm:relation/2315576, terrain | 7.9186 | 7.5223 | bank:osm:relation/2315576 | 0.3963 |
| (-628.5, 86.5) | 7.0715, bank:osm:relation/2315576, terrain | 7.0715, bank:osm:relation/2315576, terrain | 7.9186 | 7.0715 | bank:osm:relation/2315576 | 0.847 |
| (-628.5, 87.5) | 7.272, bank:osm:relation/2315576, terrain | 7.272, bank:osm:relation/2315576, terrain | 7.9186 | 7.272 | bank:osm:relation/2315576 | 0.6466 |
| (-628.5, 88.5) | 7.4724, bank:osm:relation/2315576, terrain | 7.4724, bank:osm:relation/2315576, terrain | 7.9186 | 7.4724 | bank:osm:relation/2315576 | 0.4462 |
| (-628.5, 89.5) | 7.6729, bank:osm:relation/2315576, terrain | 7.6729, bank:osm:relation/2315576, terrain | 7.9186 | 7.6729 | bank:osm:relation/2315576 | 0.2457 |
| (-627.5, 88.5) | 7.0216, bank:osm:relation/2315576, terrain | 7.0216, bank:osm:relation/2315576, terrain | 7.9186 | 7.0216 | bank:osm:relation/2315576 | 0.8969 |
| (-627.5, 89.5) | 7.2221, bank:osm:relation/2315576, terrain | 7.2221, bank:osm:relation/2315576, terrain | 7.9186 | 7.2221 | bank:osm:relation/2315576 | 0.6965 |
| (-627.5, 90.5) | 7.4225, bank:osm:relation/2315576, terrain | 7.4225, bank:osm:relation/2315576, terrain | 7.9186 | 7.4225 | bank:osm:relation/2315576 | 0.4961 |
| (-627.5, 91.5) | 7.6229, bank:osm:relation/2315576, terrain | 7.6229, bank:osm:relation/2315576, terrain | 7.9186 | 7.6229 | bank:osm:relation/2315576 | 0.2956 |
| (-626.5, 91.5) | 7.1904, bank:osm:relation/2315576, terrain | 7.1904, bank:osm:relation/2315576, terrain | 7.9186 | 7.1904 | bank:osm:relation/2315576 | 0.7282 |
| (-626.5, 92.5) | 7.4325, bank:osm:relation/2315576, terrain | 7.4325, bank:osm:relation/2315576, terrain | 7.9186 | 7.4325 | bank:osm:relation/2315576 | 0.4861 |
| (-626.5, 93.5) | 7.6746, bank:osm:relation/2315576, terrain | 7.6746, bank:osm:relation/2315576, terrain | 7.9186 | 7.6746 | bank:osm:relation/2315576 | 0.244 |
| (-625.5, 93.5) | 7.2447, bank:osm:relation/2315576, terrain | 7.2447, bank:osm:relation/2315576, terrain | 7.9186 | 7.2447 | bank:osm:relation/2315576 | 0.6739 |
| (-625.5, 94.5) | 7.4868, bank:osm:relation/2315576, terrain | 7.4868, bank:osm:relation/2315576, terrain | 7.9186 | 7.4868 | bank:osm:relation/2315576 | 0.4318 |
| (-624.5, 94.5) | 7.0569, bank:osm:relation/2315576, terrain | 7.0569, bank:osm:relation/2315576, terrain | 7.9186 | 7.0569 | bank:osm:relation/2315576 | 0.8617 |
| (-624.5, 95.5) | 7.299, bank:osm:relation/2315576, terrain | 7.299, bank:osm:relation/2315576, terrain | 7.9186 | 7.299 | bank:osm:relation/2315576 | 0.6196 |
| (-624.5, 96.5) | 7.5411, bank:osm:relation/2315576, terrain | 7.5411, bank:osm:relation/2315576, terrain | 7.9186 | 7.5411 | bank:osm:relation/2315576 | 0.3775 |
| (-623.5, 96.5) | 7.1112, bank:osm:relation/2315576, terrain | 7.1112, bank:osm:relation/2315576, terrain | 7.9186 | 7.1112 | bank:osm:relation/2315576 | 0.8074 |
| (-623.5, 97.5) | 7.3533, bank:osm:relation/2315576, terrain | 7.3533, bank:osm:relation/2315576, terrain | 7.9186 | 7.3533 | bank:osm:relation/2315576 | 0.5653 |
| (-623.5, 98.5) | 7.5954, bank:osm:relation/2315576, terrain | 7.5954, bank:osm:relation/2315576, terrain | 7.9186 | 7.5954 | bank:osm:relation/2315576 | 0.3232 |
| (-622.5, 98.5) | 7.1655, bank:osm:relation/2315576, terrain | 7.1655, bank:osm:relation/2315576, terrain | 7.9186 | 7.1655 | bank:osm:relation/2315576 | 0.7531 |
| (-622.5, 99.5) | 7.4076, bank:osm:relation/2315576, terrain | 7.4076, bank:osm:relation/2315576, terrain | 7.9186 | 7.4076 | bank:osm:relation/2315576 | 0.511 |
| (-622.5, 100.5) | 7.6496, bank:osm:relation/2315576, terrain | 7.6496, bank:osm:relation/2315576, terrain | 7.9186 | 7.6496 | bank:osm:relation/2315576 | 0.2689 |
| (-621.5, 100.5) | 7.2198, bank:osm:relation/2315576, terrain | 7.2198, bank:osm:relation/2315576, terrain | 7.9186 | 7.2198 | bank:osm:relation/2315576 | 0.6988 |
| (-621.5, 101.5) | 7.4619, bank:osm:relation/2315576, terrain | 7.4619, bank:osm:relation/2315576, terrain | 7.9186 | 7.4619 | bank:osm:relation/2315576 | 0.4567 |
| (-621.5, 102.5) | 7.7039, bank:osm:relation/2315576, terrain | 7.7039, bank:osm:relation/2315576, terrain | 7.9186 | 7.7039 | bank:osm:relation/2315576 | 0.2147 |
| (-620.5, 102.5) | 7.2741, bank:osm:relation/2315576, terrain | 7.2741, bank:osm:relation/2315576, terrain | 7.9186 | 7.2741 | bank:osm:relation/2315576 | 0.6445 |
| (-620.5, 103.5) | 7.5161, bank:osm:relation/2315576, terrain | 7.5161, bank:osm:relation/2315576, terrain | 7.9186 | 7.5161 | bank:osm:relation/2315576 | 0.4024 |
| (-619.5, 103.5) | 7.0863, bank:osm:relation/2315576, terrain | 7.0863, bank:osm:relation/2315576, terrain | 7.9186 | 7.0863 | bank:osm:relation/2315576 | 0.8323 |
| (-619.5, 104.5) | 7.3265, bank:osm:relation/2315576, terrain | 7.3265, bank:osm:relation/2315576, terrain | 7.9186 | 7.3265 | bank:osm:relation/2315576 | 0.5921 |
| (-619.5, 105.5) | 7.5456, bank:osm:relation/2315576, terrain | 7.5456, bank:osm:relation/2315576, terrain | 7.9186 | 7.5456 | bank:osm:relation/2315576 | 0.3729 |
| (-618.5, 105.5) | 7.1037, bank:osm:relation/2315576, terrain | 7.1037, bank:osm:relation/2315576, terrain | 7.9186 | 7.1037 | bank:osm:relation/2315576 | 0.8149 |
| (-618.5, 106.5) | 7.3228, bank:osm:relation/2315576, terrain | 7.3228, bank:osm:relation/2315576, terrain | 7.9186 | 7.3228 | bank:osm:relation/2315576 | 0.5958 |
| (-618.5, 107.5) | 7.542, bank:osm:relation/2315576, terrain | 7.542, bank:osm:relation/2315576, terrain | 7.9186 | 7.542 | bank:osm:relation/2315576 | 0.3766 |
| (-617.5, 107.5) | 7.1, bank:osm:relation/2315576, terrain | 7.1, bank:osm:relation/2315576, terrain | 7.9186 | 7.1 | bank:osm:relation/2315576 | 0.8186 |
| (-617.5, 108.5) | 7.3191, bank:osm:relation/2315576, terrain | 7.3191, bank:osm:relation/2315576, terrain | 7.9186 | 7.3191 | bank:osm:relation/2315576 | 0.5994 |
| (-617.5, 109.5) | 7.5383, bank:osm:relation/2315576, terrain | 7.5383, bank:osm:relation/2315576, terrain | 7.9186 | 7.5383 | bank:osm:relation/2315576 | 0.3803 |
| (-616.5, 109.5) | 7.0963, bank:osm:relation/2315576, terrain | 7.0963, bank:osm:relation/2315576, terrain | 7.9186 | 7.0963 | bank:osm:relation/2315576 | 0.8223 |
| (-616.5, 110.5) | 7.3155, bank:osm:relation/2315576, terrain | 7.3155, bank:osm:relation/2315576, terrain | 7.9186 | 7.3155 | bank:osm:relation/2315576 | 0.6031 |
| (-616.5, 111.5) | 7.5346, bank:osm:relation/2315576, terrain | 7.5346, bank:osm:relation/2315576, terrain | 7.9186 | 7.5346 | bank:osm:relation/2315576 | 0.384 |
| (-615.5, 111.5) | 7.0927, bank:osm:relation/2315576, terrain | 7.0927, bank:osm:relation/2315576, terrain | 7.9186 | 7.0927 | bank:osm:relation/2315576 | 0.8259 |
| (-615.5, 112.5) | 7.3118, bank:osm:relation/2315576, terrain | 7.3118, bank:osm:relation/2315576, terrain | 7.9186 | 7.3118 | bank:osm:relation/2315576 | 0.6068 |
| (-615.5, 113.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-615.5, 114.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-614.5, 113.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-614.5, 114.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-614.5, 115.5) | 12.629, osm:way/83926163, bridge | 12.629, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-614.5, 116.5) | 11.6299, osm:way/83926163, bridge | 11.6299, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-613.5, 115.5) | 12.549, osm:way/83926163, bridge | 12.549, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-613.5, 116.5) | 11.5499, osm:way/83926163, bridge | 11.5499, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-613.5, 117.5) | 11.5508, osm:way/83926163, bridge | 11.5508, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-613.5, 118.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-612.5, 117.5) | 11.4708, osm:way/83926163, bridge | 11.4708, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-612.5, 118.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-612.5, 119.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-611.5, 119.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-611.5, 120.5) | 7.2971, bank:osm:relation/2315576, terrain | 7.2971, bank:osm:relation/2315576, terrain | 7.9186 | 7.2971 | bank:osm:relation/2315576 | 0.6214 |
| (-611.5, 121.5) | 7.5163, bank:osm:relation/2315576, terrain | 7.5163, bank:osm:relation/2315576, terrain | 7.9186 | 7.5163 | bank:osm:relation/2315576 | 0.4023 |
| (-610.5, 121.5) | 7.0743, bank:osm:relation/2315576, terrain | 7.0743, bank:osm:relation/2315576, terrain | 7.9186 | 7.0743 | bank:osm:relation/2315576 | 0.8443 |
| (-610.5, 122.5) | 7.2935, bank:osm:relation/2315576, terrain | 7.2935, bank:osm:relation/2315576, terrain | 7.9186 | 7.2935 | bank:osm:relation/2315576 | 0.6251 |
| (-610.5, 123.5) | 7.5126, bank:osm:relation/2315576, terrain | 7.5126, bank:osm:relation/2315576, terrain | 7.9186 | 7.5126 | bank:osm:relation/2315576 | 0.406 |
| (-609.5, 123.5) | 7.0706, bank:osm:relation/2315576, terrain | 7.0706, bank:osm:relation/2315576, terrain | 7.9186 | 7.0706 | bank:osm:relation/2315576 | 0.8479 |
| (-609.5, 124.5) | 7.2898, bank:osm:relation/2315576, terrain | 7.2898, bank:osm:relation/2315576, terrain | 7.9186 | 7.2898 | bank:osm:relation/2315576 | 0.6288 |
| (-609.5, 125.5) | 7.509, bank:osm:relation/2315576, terrain | 7.509, bank:osm:relation/2315576, terrain | 7.9186 | 7.509 | bank:osm:relation/2315576 | 0.4096 |
| (-608.5, 125.5) | 7.067, bank:osm:relation/2315576, terrain | 7.067, bank:osm:relation/2315576, terrain | 7.9186 | 7.067 | bank:osm:relation/2315576 | 0.8516 |
| (-608.5, 126.5) | 7.2861, bank:osm:relation/2315576, terrain | 7.2861, bank:osm:relation/2315576, terrain | 7.9186 | 7.2861 | bank:osm:relation/2315576 | 0.6324 |
| (-608.5, 127.5) | 7.5053, bank:osm:relation/2315576, terrain | 7.5053, bank:osm:relation/2315576, terrain | 7.9186 | 7.5053 | bank:osm:relation/2315576 | 0.4133 |
| (-607.5, 127.5) | 7.0633, bank:osm:relation/2315576, terrain | 7.0633, bank:osm:relation/2315576, terrain | 7.9186 | 7.0633 | bank:osm:relation/2315576 | 0.8553 |
| (-607.5, 128.5) | 7.2825, bank:osm:relation/2315576, terrain | 7.2825, bank:osm:relation/2315576, terrain | 7.9186 | 7.2825 | bank:osm:relation/2315576 | 0.6361 |
| (-607.5, 129.5) | 7.5016, bank:osm:relation/2315576, terrain | 7.5016, bank:osm:relation/2315576, terrain | 7.9186 | 7.5016 | bank:osm:relation/2315576 | 0.417 |
| (-606.5, 129.5) | 7.0596, bank:osm:relation/2315576, terrain | 7.0596, bank:osm:relation/2315576, terrain | 7.9186 | 7.0596 | bank:osm:relation/2315576 | 0.8589 |
| (-606.5, 130.5) | 7.2788, bank:osm:relation/2315576, terrain | 7.2788, bank:osm:relation/2315576, terrain | 7.9186 | 7.2788 | bank:osm:relation/2315576 | 0.6398 |
| (-606.5, 131.5) | 7.498, bank:osm:relation/2315576, terrain | 7.498, bank:osm:relation/2315576, terrain | 7.9186 | 7.498 | bank:osm:relation/2315576 | 0.4206 |
| (-606.5, 132.5) | 7.713, bank:osm:relation/2315576, terrain | 7.713, bank:osm:relation/2315576, terrain | 7.9186 | 7.713 | bank:osm:relation/2315576 | 0.2056 |
| (-605.5, 131.5) | 7.056, bank:osm:relation/2315576, terrain | 7.056, bank:osm:relation/2315576, terrain | 7.9186 | 7.056 | bank:osm:relation/2315576 | 0.8626 |
| (-605.5, 132.5) | 7.2606, bank:osm:relation/2315576, terrain | 7.2606, bank:osm:relation/2315576, terrain | 7.9186 | 7.2606 | bank:osm:relation/2315576 | 0.658 |
| (-605.5, 133.5) | 7.4574, bank:osm:relation/2315576, terrain | 7.4574, bank:osm:relation/2315576, terrain | 7.9186 | 7.4574 | bank:osm:relation/2315576 | 0.4612 |
| (-605.5, 134.5) | 7.6542, bank:osm:relation/2315576, terrain | 7.6542, bank:osm:relation/2315576, terrain | 7.9186 | 7.6542 | bank:osm:relation/2315576 | 0.2644 |
| (-604.5, 133.5) | 7.005, bank:osm:relation/2315576, terrain | 7.005, bank:osm:relation/2315576, terrain | 7.9186 | 7.005 | bank:osm:relation/2315576 | 0.9136 |
| (-604.5, 134.5) | 7.2018, bank:osm:relation/2315576, terrain | 7.2018, bank:osm:relation/2315576, terrain | 7.9186 | 7.2018 | bank:osm:relation/2315576 | 0.7168 |
| (-604.5, 135.5) | 7.3986, bank:osm:relation/2315576, terrain | 7.3986, bank:osm:relation/2315576, terrain | 7.9186 | 7.3986 | bank:osm:relation/2315576 | 0.52 |
| (-604.5, 136.5) | 7.5953, bank:osm:relation/2315576, terrain | 7.5953, bank:osm:relation/2315576, terrain | 7.9186 | 7.5953 | bank:osm:relation/2315576 | 0.3232 |
| (-603.5, 136.5) | 7.143, bank:osm:relation/2315576, terrain | 7.143, bank:osm:relation/2315576, terrain | 7.9186 | 7.143 | bank:osm:relation/2315576 | 0.7756 |
| (-603.5, 137.5) | 7.3397, bank:osm:relation/2315576, terrain | 7.3397, bank:osm:relation/2315576, terrain | 7.9186 | 7.3397 | bank:osm:relation/2315576 | 0.5788 |
| (-603.5, 138.5) | 7.5365, bank:osm:relation/2315576, terrain | 7.5365, bank:osm:relation/2315576, terrain | 7.9186 | 7.5365 | bank:osm:relation/2315576 | 0.3821 |
| (-602.5, 138.5) | 7.0841, bank:osm:relation/2315576, terrain | 7.0841, bank:osm:relation/2315576, terrain | 7.9186 | 7.0841 | bank:osm:relation/2315576 | 0.8344 |
| (-602.5, 139.5) | 7.2809, bank:osm:relation/2315576, terrain | 7.2809, bank:osm:relation/2315576, terrain | 7.9186 | 7.2809 | bank:osm:relation/2315576 | 0.6377 |
| (-602.5, 140.5) | 7.4777, bank:osm:relation/2315576, terrain | 7.4777, bank:osm:relation/2315576, terrain | 7.9186 | 7.4777 | bank:osm:relation/2315576 | 0.4409 |
| (-602.5, 141.5) | 7.6745, bank:osm:relation/2315576, terrain | 7.6745, bank:osm:relation/2315576, terrain | 7.9186 | 7.6745 | bank:osm:relation/2315576 | 0.2441 |
| (-601.5, 140.5) | 7.0253, bank:osm:relation/2315576, terrain | 7.0253, bank:osm:relation/2315576, terrain | 7.9186 | 7.0253 | bank:osm:relation/2315576 | 0.8933 |
| (-601.5, 141.5) | 7.2221, bank:osm:relation/2315576, terrain | 7.2221, bank:osm:relation/2315576, terrain | 7.9186 | 7.2221 | bank:osm:relation/2315576 | 0.6965 |
| (-601.5, 142.5) | 7.4189, bank:osm:relation/2315576, terrain | 7.4189, bank:osm:relation/2315576, terrain | 7.9186 | 7.4189 | bank:osm:relation/2315576 | 0.4997 |
| (-601.5, 143.5) | 7.6157, bank:osm:relation/2315576, terrain | 7.6157, bank:osm:relation/2315576, terrain | 7.9186 | 7.6157 | bank:osm:relation/2315576 | 0.3029 |
| (-600.5, 143.5) | 7.1633, bank:osm:relation/2315576, terrain | 7.1633, bank:osm:relation/2315576, terrain | 7.9186 | 7.1633 | bank:osm:relation/2315576 | 0.7553 |
| (-600.5, 144.5) | 7.3601, bank:osm:relation/2315576, terrain | 7.3601, bank:osm:relation/2315576, terrain | 7.9186 | 7.3601 | bank:osm:relation/2315576 | 0.5585 |
| (-600.5, 145.5) | 7.5569, bank:osm:relation/2315576, terrain | 7.5569, bank:osm:relation/2315576, terrain | 7.9186 | 7.5569 | bank:osm:relation/2315576 | 0.3617 |
| (-599.5, 145.5) | 7.1045, bank:osm:relation/2315576, terrain | 7.1045, bank:osm:relation/2315576, terrain | 7.9186 | 7.1045 | bank:osm:relation/2315576 | 0.8141 |
| (-599.5, 146.5) | 7.3013, bank:osm:relation/2315576, terrain | 7.3013, bank:osm:relation/2315576, terrain | 7.9186 | 7.3013 | bank:osm:relation/2315576 | 0.6173 |
| (-599.5, 147.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-599.5, 148.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-598.5, 147.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-599.5, 149.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-598.5, 148.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-598.5, 149.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-598.5, 150.5) | 19.0592, osm:way/4752301, bridge | 19.0592, osm:way/4752301, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-598.5, 151.5) | 19.054, osm:way/4752301, bridge | 19.054, osm:way/4752301, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-597.5, 150.5) | 19.0645, osm:way/4752301, bridge | 19.0645, osm:way/4752301, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-597.5, 151.5) | 19.059, osm:way/4752301, bridge | 19.059, osm:way/4752301, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-597.5, 152.5) | 19.0532, osm:way/4752301, bridge | 19.0532, osm:way/4752301, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-597.5, 153.5) | 19.0473, osm:way/4752301, bridge | 19.0473, osm:way/4752301, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-596.5, 152.5) | 19.0582, osm:way/4752301, bridge | 19.0582, osm:way/4752301, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-596.5, 153.5) | 20.0524, osm:way/4752301, bridge | 20.0524, osm:way/4752301, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-596.5, 154.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-596.5, 155.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-595.5, 154.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-595.5, 155.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-595.5, 156.5) | 7.4596, bank:osm:relation/2315576, terrain | 7.4596, bank:osm:relation/2315576, terrain | 7.9186 | 7.4596 | bank:osm:relation/2315576 | 0.459 |
| (-595.5, 157.5) | 7.6563, bank:osm:relation/2315576, terrain | 7.6563, bank:osm:relation/2315576, terrain | 7.9186 | 7.6563 | bank:osm:relation/2315576 | 0.2622 |
| (-594.5, 156.5) | 7.0072, bank:osm:relation/2315576, terrain | 7.0072, bank:osm:relation/2315576, terrain | 7.9186 | 7.0072 | bank:osm:relation/2315576 | 0.9114 |
| (-594.5, 157.5) | 7.2039, bank:osm:relation/2315576, terrain | 7.2039, bank:osm:relation/2315576, terrain | 7.9186 | 7.2039 | bank:osm:relation/2315576 | 0.7146 |
| (-594.5, 158.5) | 7.4007, bank:osm:relation/2315576, terrain | 7.4007, bank:osm:relation/2315576, terrain | 7.9186 | 7.4007 | bank:osm:relation/2315576 | 0.5178 |
| (-594.5, 159.5) | 7.5975, bank:osm:relation/2315576, terrain | 7.5975, bank:osm:relation/2315576, terrain | 7.9186 | 7.5975 | bank:osm:relation/2315576 | 0.3211 |
| (-593.5, 159.5) | 7.1451, bank:osm:relation/2315576, terrain | 7.1451, bank:osm:relation/2315576, terrain | 7.9186 | 7.1451 | bank:osm:relation/2315576 | 0.7735 |
| (-593.5, 160.5) | 7.3419, bank:osm:relation/2315576, terrain | 7.3419, bank:osm:relation/2315576, terrain | 7.9186 | 7.3419 | bank:osm:relation/2315576 | 0.5767 |
| (-593.5, 161.5) | 7.5387, bank:osm:relation/2315576, terrain | 7.5387, bank:osm:relation/2315576, terrain | 7.9186 | 7.5387 | bank:osm:relation/2315576 | 0.3799 |
| (-592.5, 161.5) | 7.0863, bank:osm:relation/2315576, terrain | 7.0863, bank:osm:relation/2315576, terrain | 7.9186 | 7.0863 | bank:osm:relation/2315576 | 0.8323 |
| (-592.5, 162.5) | 7.2831, bank:osm:relation/2315576, terrain | 7.2831, bank:osm:relation/2315576, terrain | 7.9186 | 7.2831 | bank:osm:relation/2315576 | 0.6355 |
| (-592.5, 163.5) | 7.4799, bank:osm:relation/2315576, terrain | 7.4799, bank:osm:relation/2315576, terrain | 7.9186 | 7.4799 | bank:osm:relation/2315576 | 0.4387 |
| (-592.5, 164.5) | 7.6767, bank:osm:relation/2315576, terrain | 7.6767, bank:osm:relation/2315576, terrain | 7.9186 | 7.6767 | bank:osm:relation/2315576 | 0.2419 |
| (-591.5, 163.5) | 7.0275, bank:osm:relation/2315576, terrain | 7.0275, bank:osm:relation/2315576, terrain | 7.9186 | 7.0275 | bank:osm:relation/2315576 | 0.8911 |
| (-591.5, 164.5) | 7.2243, bank:osm:relation/2315576, terrain | 7.2243, bank:osm:relation/2315576, terrain | 7.9186 | 7.2243 | bank:osm:relation/2315576 | 0.6943 |
| (-591.5, 165.5) | 7.4211, bank:osm:relation/2315576, terrain | 7.4211, bank:osm:relation/2315576, terrain | 7.9186 | 7.4211 | bank:osm:relation/2315576 | 0.4975 |
| (-591.5, 166.5) | 7.6179, bank:osm:relation/2315576, terrain | 7.6179, bank:osm:relation/2315576, terrain | 7.9186 | 7.6179 | bank:osm:relation/2315576 | 0.3007 |
| (-590.5, 166.5) | 7.1655, bank:osm:relation/2315576, terrain | 7.1655, bank:osm:relation/2315576, terrain | 7.9186 | 7.1655 | bank:osm:relation/2315576 | 0.7531 |
| (-590.5, 167.5) | 7.3622, bank:osm:relation/2315576, terrain | 7.3622, bank:osm:relation/2315576, terrain | 7.9186 | 7.3622 | bank:osm:relation/2315576 | 0.5563 |
| (-590.5, 168.5) | 7.559, bank:osm:relation/2315576, terrain | 7.559, bank:osm:relation/2315576, terrain | 7.9186 | 7.559 | bank:osm:relation/2315576 | 0.3596 |
| (-589.5, 168.5) | 7.104, bank:osm:relation/2315576, terrain | 7.104, bank:osm:relation/2315576, terrain | 7.9186 | 7.104 | bank:osm:relation/2315576 | 0.8145 |
| (-589.5, 169.5) | 7.2788, bank:osm:relation/2315576, terrain | 7.2788, bank:osm:relation/2315576, terrain | 7.9186 | 7.2788 | bank:osm:relation/2315576 | 0.6398 |
| (-589.5, 170.5) | 7.4535, bank:osm:relation/2315576, terrain | 7.4535, bank:osm:relation/2315576, terrain | 7.9186 | 7.4535 | bank:osm:relation/2315576 | 0.4651 |
| (-589.5, 171.5) | 7.6282, bank:osm:relation/2315576, terrain | 7.6282, bank:osm:relation/2315576, terrain | 7.9186 | 7.6282 | bank:osm:relation/2315576 | 0.2903 |
| (-588.5, 170.5) | 6.9922, bank:osm:relation/2315576, terrain | 6.9922, bank:osm:relation/2315576, terrain | 7.9186 | 6.9922 | bank:osm:relation/2315576 | 0.9264 |
| (-588.5, 171.5) | 7.1669, bank:osm:relation/2315576, terrain | 7.1669, bank:osm:relation/2315576, terrain | 7.9186 | 7.1669 | bank:osm:relation/2315576 | 0.7517 |
| (-588.5, 172.5) | 12.1501, scatter:osm:relation/7099311#192, vegetation | 12.1501, scatter:osm:relation/7099311#192, vegetation | 7.9186 | 7.3416 | bank:osm:relation/2315576 | 0.577 |
| (-588.5, 173.5) | 12.3461, scatter:osm:relation/7099311#192, vegetation | 12.3461, scatter:osm:relation/7099311#192, vegetation | 7.9186 | 7.5164 | bank:osm:relation/2315576 | 0.4022 |
| (-588.5, 174.5) | 7.6911, bank:osm:relation/2315576, terrain | 7.6911, bank:osm:relation/2315576, terrain | 7.9186 | 7.6911 | bank:osm:relation/2315576 | 0.2275 |
| (-587.5, 173.5) | 14.2996, scatter:osm:relation/7099311#192, vegetation | 14.2996, scatter:osm:relation/7099311#192, vegetation | 7.9186 | 7.055 | bank:osm:relation/2315576 | 0.8636 |
| (-587.5, 174.5) | 12.7741, scatter:osm:relation/7099311#192, vegetation | 12.7741, scatter:osm:relation/7099311#192, vegetation | 7.9186 | 7.2297 | bank:osm:relation/2315576 | 0.6888 |
| (-587.5, 175.5) | 7.4045, bank:osm:relation/2315576, terrain | 7.4045, bank:osm:relation/2315576, terrain | 7.9186 | 7.4045 | bank:osm:relation/2315576 | 0.5141 |
| (-587.5, 176.5) | 7.5792, bank:osm:relation/2315576, terrain | 7.5792, bank:osm:relation/2315576, terrain | 7.9186 | 7.5792 | bank:osm:relation/2315576 | 0.3394 |
| (-586.5, 176.5) | 7.1179, bank:osm:relation/2315576, terrain | 7.1179, bank:osm:relation/2315576, terrain | 7.9186 | 7.1179 | bank:osm:relation/2315576 | 0.8007 |
| (-586.5, 177.5) | 7.2926, bank:osm:relation/2315576, terrain | 7.2926, bank:osm:relation/2315576, terrain | 7.9186 | 7.2926 | bank:osm:relation/2315576 | 0.626 |
| (-586.5, 178.5) | 7.4673, bank:osm:relation/2315576, terrain | 7.4673, bank:osm:relation/2315576, terrain | 7.9186 | 7.4673 | bank:osm:relation/2315576 | 0.4513 |
| (-586.5, 179.5) | 7.6421, bank:osm:relation/2315576, terrain | 7.6421, bank:osm:relation/2315576, terrain | 7.9186 | 7.6421 | bank:osm:relation/2315576 | 0.2765 |
| (-585.5, 178.5) | 7.006, bank:osm:relation/2315576, terrain | 7.006, bank:osm:relation/2315576, terrain | 7.9186 | 7.006 | bank:osm:relation/2315576 | 0.9126 |
| (-585.5, 179.5) | 7.1807, bank:osm:relation/2315576, terrain | 7.1807, bank:osm:relation/2315576, terrain | 7.9186 | 7.1807 | bank:osm:relation/2315576 | 0.7379 |
| (-585.5, 180.5) | 7.3554, bank:osm:relation/2315576, terrain | 7.3554, bank:osm:relation/2315576, terrain | 7.9186 | 7.3554 | bank:osm:relation/2315576 | 0.5631 |
| (-585.5, 181.5) | 7.5302, bank:osm:relation/2315576, terrain | 7.5302, bank:osm:relation/2315576, terrain | 7.9186 | 7.5302 | bank:osm:relation/2315576 | 0.3884 |
| (-585.5, 182.5) | 7.7049, bank:osm:relation/2315576, terrain | 7.7049, bank:osm:relation/2315576, terrain | 7.9186 | 7.7049 | bank:osm:relation/2315576 | 0.2137 |
| (-584.5, 181.5) | 11.4513, scatter:osm:relation/7099311#229, vegetation | 11.4513, scatter:osm:relation/7099311#229, vegetation | 7.9186 | 7.0688 | bank:osm:relation/2315576 | 0.8498 |
| (-584.5, 182.5) | 12.512, scatter:osm:relation/7099311#229, vegetation | 12.512, scatter:osm:relation/7099311#229, vegetation | 7.9186 | 7.2435 | bank:osm:relation/2315576 | 0.675 |
| (-584.5, 183.5) | 11.8709, scatter:osm:relation/7099311#229, vegetation | 11.8709, scatter:osm:relation/7099311#229, vegetation | 7.9186 | 7.4183 | bank:osm:relation/2315576 | 0.5003 |
| (-584.5, 184.5) | 7.593, bank:osm:relation/2315576, terrain | 7.593, bank:osm:relation/2315576, terrain | 7.9186 | 7.593 | bank:osm:relation/2315576 | 0.3256 |
| (-583.5, 184.5) | 11.4332, scatter:osm:relation/7099311#229, vegetation | 11.4332, scatter:osm:relation/7099311#229, vegetation | 7.9186 | 7.1317 | bank:osm:relation/2315576 | 0.7869 |
| (-583.5, 185.5) | 7.3064, bank:osm:relation/2315576, terrain | 7.3064, bank:osm:relation/2315576, terrain | 7.9186 | 7.3064 | bank:osm:relation/2315576 | 0.6122 |
| (-583.5, 186.5) | 7.4811, bank:osm:relation/2315576, terrain | 7.4811, bank:osm:relation/2315576, terrain | 7.9186 | 7.4811 | bank:osm:relation/2315576 | 0.4374 |
| (-583.5, 187.5) | 7.6559, bank:osm:relation/2315576, terrain | 7.6559, bank:osm:relation/2315576, terrain | 7.9186 | 7.6559 | bank:osm:relation/2315576 | 0.2627 |
| (-582.5, 186.5) | 7.0198, bank:osm:relation/2315576, terrain | 7.0198, bank:osm:relation/2315576, terrain | 7.9186 | 7.0198 | bank:osm:relation/2315576 | 0.8988 |
| (-582.5, 187.5) | 7.1945, bank:osm:relation/2315576, terrain | 7.1945, bank:osm:relation/2315576, terrain | 7.9186 | 7.1945 | bank:osm:relation/2315576 | 0.7241 |
| (-582.5, 188.5) | 7.3692, bank:osm:relation/2315576, terrain | 7.3692, bank:osm:relation/2315576, terrain | 7.9186 | 7.3692 | bank:osm:relation/2315576 | 0.5493 |
| (-582.5, 189.5) | 7.544, bank:osm:relation/2315576, terrain | 7.544, bank:osm:relation/2315576, terrain | 7.9186 | 7.544 | bank:osm:relation/2315576 | 0.3746 |
| (-581.5, 189.5) | 7.0826, bank:osm:relation/2315576, terrain | 7.0826, bank:osm:relation/2315576, terrain | 7.9186 | 7.0826 | bank:osm:relation/2315576 | 0.836 |
| (-581.5, 190.5) | 7.2574, bank:osm:relation/2315576, terrain | 7.2574, bank:osm:relation/2315576, terrain | 7.9186 | 7.2574 | bank:osm:relation/2315576 | 0.6612 |
| (-581.5, 191.5) | 7.4321, bank:osm:relation/2315576, terrain | 7.4321, bank:osm:relation/2315576, terrain | 7.9186 | 7.4321 | bank:osm:relation/2315576 | 0.4865 |
| (-581.5, 192.5) | 7.6068, bank:osm:relation/2315576, terrain | 7.6068, bank:osm:relation/2315576, terrain | 7.9186 | 7.6068 | bank:osm:relation/2315576 | 0.3118 |
| (-580.5, 192.5) | 7.1455, bank:osm:relation/2315576, terrain | 7.1455, bank:osm:relation/2315576, terrain | 7.9186 | 7.1455 | bank:osm:relation/2315576 | 0.7731 |
| (-580.5, 193.5) | 7.3202, bank:osm:relation/2315576, terrain | 7.3202, bank:osm:relation/2315576, terrain | 7.9186 | 7.3202 | bank:osm:relation/2315576 | 0.5984 |
| (-580.5, 194.5) | 7.4949, bank:osm:relation/2315576, terrain | 7.4949, bank:osm:relation/2315576, terrain | 7.9186 | 7.4949 | bank:osm:relation/2315576 | 0.4236 |
| (-580.5, 195.5) | 11.8255, scatter:osm:relation/7099311#302, vegetation | 11.8255, scatter:osm:relation/7099311#302, vegetation | 7.9186 | 7.6697 | bank:osm:relation/2315576 | 0.2489 |
| (-579.5, 194.5) | 7.0336, bank:osm:relation/2315576, terrain | 7.0336, bank:osm:relation/2315576, terrain | 7.9186 | 7.0336 | bank:osm:relation/2315576 | 0.885 |
| (-579.5, 195.5) | 13.0745, scatter:osm:relation/7099311#302, vegetation | 13.0745, scatter:osm:relation/7099311#302, vegetation | 7.9186 | 7.2083 | bank:osm:relation/2315576 | 0.7103 |
| (-579.5, 196.5) | 15.1588, scatter:osm:relation/7099311#302, vegetation | 15.1588, scatter:osm:relation/7099311#302, vegetation | 7.9186 | 7.3831 | bank:osm:relation/2315576 | 0.5355 |
| (-579.5, 197.5) | 15.004, scatter:osm:relation/7099311#302, vegetation | 15.004, scatter:osm:relation/7099311#302, vegetation | 7.9186 | 7.5578 | bank:osm:relation/2315576 | 0.3608 |
| (-578.5, 197.5) | 14.6554, scatter:osm:relation/7099311#302, vegetation | 14.6554, scatter:osm:relation/7099311#302, vegetation | 7.9186 | 7.0964 | bank:osm:relation/2315576 | 0.8221 |
| (-578.5, 198.5) | 12.8555, scatter:osm:relation/7099311#302, vegetation | 12.8555, scatter:osm:relation/7099311#302, vegetation | 7.9186 | 7.2712 | bank:osm:relation/2315576 | 0.6474 |
| (-578.5, 199.5) | 7.4459, bank:osm:relation/2315576, terrain | 7.4459, bank:osm:relation/2315576, terrain | 7.9186 | 7.4459 | bank:osm:relation/2315576 | 0.4727 |
| (-578.5, 200.5) | 7.6206, bank:osm:relation/2315576, terrain | 7.6206, bank:osm:relation/2315576, terrain | 7.9186 | 7.6206 | bank:osm:relation/2315576 | 0.2979 |
| (-577.5, 199.5) | 6.9846, bank:osm:relation/2315576, terrain | 6.9846, bank:osm:relation/2315576, terrain | 7.9186 | 6.9846 | bank:osm:relation/2315576 | 0.934 |
| (-577.5, 200.5) | 7.1593, bank:osm:relation/2315576, terrain | 7.1593, bank:osm:relation/2315576, terrain | 7.9186 | 7.1593 | bank:osm:relation/2315576 | 0.7593 |
| (-577.5, 201.5) | 7.334, bank:osm:relation/2315576, terrain | 7.334, bank:osm:relation/2315576, terrain | 7.9186 | 7.334 | bank:osm:relation/2315576 | 0.5846 |
| (-577.5, 202.5) | 7.5088, bank:osm:relation/2315576, terrain | 7.5088, bank:osm:relation/2315576, terrain | 7.9186 | 7.5088 | bank:osm:relation/2315576 | 0.4098 |
| (-577.5, 203.5) | 7.6835, bank:osm:relation/2315576, terrain | 7.6835, bank:osm:relation/2315576, terrain | 7.9186 | 7.6835 | bank:osm:relation/2315576 | 0.2351 |
| (-576.5, 202.5) | 7.0474, bank:osm:relation/2315576, terrain | 7.0474, bank:osm:relation/2315576, terrain | 7.9186 | 7.0474 | bank:osm:relation/2315576 | 0.8712 |
| (-576.5, 203.5) | 7.2221, bank:osm:relation/2315576, terrain | 7.2221, bank:osm:relation/2315576, terrain | 7.9186 | 7.2221 | bank:osm:relation/2315576 | 0.6964 |
| (-576.5, 204.5) | 7.3969, bank:osm:relation/2315576, terrain | 7.3969, bank:osm:relation/2315576, terrain | 7.9186 | 7.3969 | bank:osm:relation/2315576 | 0.5217 |
| (-576.5, 205.5) | 7.5716, bank:osm:relation/2315576, terrain | 7.5716, bank:osm:relation/2315576, terrain | 7.9186 | 7.5716 | bank:osm:relation/2315576 | 0.347 |
| (-575.5, 205.5) | 7.1102, bank:osm:relation/2315576, terrain | 7.1102, bank:osm:relation/2315576, terrain | 7.9186 | 7.1102 | bank:osm:relation/2315576 | 0.8083 |
| (-575.5, 206.5) | 7.362, bank:osm:relation/2315576, terrain | 7.362, bank:osm:relation/2315576, terrain | 7.9186 | 7.362 | bank:osm:relation/2315576 | 0.5566 |
| (-575.5, 207.5) | 7.6788, bank:osm:relation/2315576, terrain | 7.6788, bank:osm:relation/2315576, terrain | 7.9186 | 7.6788 | bank:osm:relation/2315576 | 0.2397 |
| (-574.5, 207.5) | 7.3007, bank:osm:relation/2315576, terrain | 7.3007, bank:osm:relation/2315576, terrain | 7.9186 | 7.3007 | bank:osm:relation/2315576 | 0.6179 |
| (-574.5, 208.5) | 7.6175, bank:osm:relation/2315576, terrain | 7.6175, bank:osm:relation/2315576, terrain | 7.9186 | 7.6175 | bank:osm:relation/2315576 | 0.301 |
| (-573.5, 208.5) | 7.2394, bank:osm:relation/2315576, terrain | 7.2394, bank:osm:relation/2315576, terrain | 7.9186 | 7.2394 | bank:osm:relation/2315576 | 0.6792 |
| (-573.5, 209.5) | 7.5563, bank:osm:relation/2315576, terrain | 7.5563, bank:osm:relation/2315576, terrain | 7.9186 | 7.5563 | bank:osm:relation/2315576 | 0.3623 |
| (-572.5, 209.5) | 7.1781, bank:osm:relation/2315576, terrain | 7.1781, bank:osm:relation/2315576, terrain | 7.9186 | 7.1781 | bank:osm:relation/2315576 | 0.7405 |
| (-572.5, 210.5) | 7.495, bank:osm:relation/2315576, terrain | 7.495, bank:osm:relation/2315576, terrain | 7.9186 | 7.495 | bank:osm:relation/2315576 | 0.4236 |

#### `water_shore_step:vis#10` (class D)

Blocked strips within reach (`shore_ramp_blocked_m` of the body: {'water:osm:relation/2315576': 192.5}):

* bank strip (-634.955, 119.687, 5.899) -> (-635.93, 118.129, 5.899) (1.838 m): line 2.0 osm:way/83926163
* bank strip (-635.93, 118.129, 5.899) -> (-636.905, 116.57, 5.899) (1.839 m): line 2.0 osm:way/83926163
* bank strip (-636.905, 116.57, 5.899) -> (-637.88, 115.012, 5.899) (1.838 m): line 2.0 osm:way/83926163
* bank strip (-637.88, 115.012, 5.899) -> (-638.855, 113.454, 5.899) (1.838 m): line 2.0 osm:way/83926163
* bank strip (-653.042, 73.563, 5.899) -> (-653.244, 71.613, 5.899) (1.96 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-653.244, 71.613, 5.899) -> (-653.445, 69.664, 5.899) (1.959 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-653.445, 69.664, 5.899) -> (-653.646, 67.714, 5.899) (1.96 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-653.646, 67.714, 5.899) -> (-653.848, 65.764, 5.899) (1.96 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-653.848, 65.764, 5.899) -> (-654.049, 63.815, 5.899) (1.959 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-654.049, 63.815, 5.899) -> (-654.25, 61.865, 5.899) (1.96 m): line 5.875 osm:way/23615351; line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-654.25, 61.865, 5.899) -> (-654.452, 59.915, 5.899) (1.96 m): line 5.875 osm:way/23615351
* bank strip (-654.452, 59.915, 5.899) -> (-654.653, 57.965, 5.899) (1.96 m): line 5.875 osm:way/23615351
* bank strip (-654.653, 57.965, 5.899) -> (-654.854, 56.016, 5.899) (1.959 m): line 5.875 osm:way/23615351
* bank strip (-654.854, 56.016, 5.899) -> (-655.056, 54.066, 5.899) (1.96 m): line 5.875 osm:way/23615351
* bank strip (-632.812, 54.712, 5.899) -> (-632.821, 56.696, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.821, 56.696, 5.899) -> (-632.829, 58.681, 5.899) (1.985 m): line 5.875 osm:way/23615351
* bank strip (-632.829, 58.681, 5.899) -> (-632.838, 60.665, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.838, 60.665, 5.899) -> (-632.846, 62.649, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.846, 62.649, 5.899) -> (-632.855, 64.633, 5.899) (1.984 m): line 5.875 osm:way/23615351
* bank strip (-632.855, 64.633, 5.899) -> (-632.863, 66.618, 5.899) (1.985 m): line 4.25 osm:way/214883367, osm:way/34575263; line 5.875 osm:way/23615351
* bank strip (-632.863, 66.618, 5.899) -> (-632.872, 68.602, 5.899) (1.984 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-632.872, 68.602, 5.899) -> (-632.88, 70.586, 5.899) (1.984 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-632.88, 70.586, 5.899) -> (-632.889, 72.57, 5.899) (1.984 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-632.889, 72.57, 5.899) -> (-632.897, 74.554, 5.899) (1.984 m): line 4.25 osm:way/214883367, osm:way/34575263
* bank strip (-632.897, 74.554, 5.899) -> (-632.906, 76.539, 5.899) (1.985 m): line 4.25 osm:way/214883367, osm:way/34575263

| Cell XY | Collision top (z, mb_id, class) | Visual top (z, owner, category) | Sheet z (vis) | Outside z (vis) | Outside owner | Offset (m) |
|---|---|---|---|---|---|---|
| (-656.5, 58.5) | 13.8306, osm:way/23615351, bridge | 13.8306, osm:way/23615351, bridge | 7.9186 | 6.3745 | terrain:grid | 1.5441 |
| (-655.5, 58.5) | 13.91, osm:way/23615351, bridge | 13.91, osm:way/23615351, bridge | 7.9186 | 6.3745 | terrain:grid | 1.5441 |
| (-655.5, 59.5) | 13.9196, osm:way/23615351, bridge | 13.9196, osm:way/23615351, bridge | 7.9186 | 6.4039 | terrain:grid | 1.5147 |
| (-655.5, 60.5) | 13.9292, osm:way/23615351, bridge | 13.9292, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 59.5) | 13.999, osm:way/23615351, bridge | 13.999, osm:way/23615351, bridge | 7.9186 | 6.4039 | terrain:grid | 1.5147 |
| (-655.5, 61.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 60.5) | 14.0086, osm:way/23615351, bridge | 14.0086, osm:way/23615351, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-655.5, 62.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 61.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-655.5, 63.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 62.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-655.5, 64.5) | 11.969, osm:way/214883367, bridge | 11.969, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 63.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-655.5, 65.5) | 11.9591, osm:way/214883367, bridge | 11.9591, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 64.5) | 11.8892, osm:way/214883367, bridge | 11.8892, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-655.5, 66.5) | 11.9492, osm:way/214883367, bridge | 11.9492, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 65.5) | 11.8793, osm:way/214883367, bridge | 11.8793, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-655.5, 67.5) | 11.9393, osm:way/214883367, bridge | 11.9393, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 66.5) | 11.8694, osm:way/214883367, bridge | 11.8694, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-655.5, 68.5) | 11.9294, osm:way/214883367, bridge | 11.9294, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 67.5) | 11.8595, osm:way/214883367, bridge | 11.8595, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 68.5) | 11.8496, osm:way/214883367, bridge | 11.8496, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 69.5) | 11.8397, osm:way/214883367, bridge | 11.8397, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 70.5) | 11.8299, osm:way/214883367, bridge | 11.8299, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-653.5, 69.5) | 11.7607, osm:way/214883367, bridge | 11.7607, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 71.5) | 12.8201, osm:way/214883367, bridge | 12.8201, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-653.5, 70.5) | 11.7508, osm:way/214883367, bridge | 11.7508, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 72.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-653.5, 71.5) | 12.741, osm:way/214883367, bridge | 12.741, osm:way/214883367, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 73.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-653.5, 72.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 74.5) | 7.1358, bank:osm:relation/2315576, terrain | 7.1358, bank:osm:relation/2315576, terrain | 7.9186 | 7.1358 | bank:osm:relation/2315576 | 0.7828 |
| (-653.5, 73.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-654.5, 75.5) | 7.0852, bank:osm:relation/2315576, terrain | 7.0852, bank:osm:relation/2315576, terrain | 7.9186 | 7.0852 | bank:osm:relation/2315576 | 0.8334 |
| (-653.5, 74.5) | 7.6265, bank:osm:relation/2315576, terrain | 7.6265, bank:osm:relation/2315576, terrain | 7.9186 | 7.6265 | bank:osm:relation/2315576 | 0.292 |
| (-654.5, 76.5) | 7.0345, bank:osm:relation/2315576, terrain | 7.0345, bank:osm:relation/2315576, terrain | 7.9186 | 7.0345 | bank:osm:relation/2315576 | 0.8841 |
| (-653.5, 75.5) | 7.5759, bank:osm:relation/2315576, terrain | 7.5759, bank:osm:relation/2315576, terrain | 7.9186 | 7.5759 | bank:osm:relation/2315576 | 0.3427 |
| (-654.5, 77.5) | 6.9838, bank:osm:relation/2315576, terrain | 6.9838, bank:osm:relation/2315576, terrain | 7.9186 | 6.9838 | bank:osm:relation/2315576 | 0.9348 |
| (-653.5, 76.5) | 7.5252, bank:osm:relation/2315576, terrain | 7.5252, bank:osm:relation/2315576, terrain | 7.9186 | 7.5252 | bank:osm:relation/2315576 | 0.3934 |
| (-654.5, 78.5) | 6.9331, bank:osm:relation/2315576, terrain | 6.9331, bank:osm:relation/2315576, terrain | 7.9186 | 6.9331 | bank:osm:relation/2315576 | 0.9854 |
| (-653.5, 77.5) | 7.4745, bank:osm:relation/2315576, terrain | 7.4745, bank:osm:relation/2315576, terrain | 7.9186 | 7.4745 | bank:osm:relation/2315576 | 0.4441 |
| (-653.5, 78.5) | 7.4239, bank:osm:relation/2315576, terrain | 7.4239, bank:osm:relation/2315576, terrain | 7.9186 | 7.4239 | bank:osm:relation/2315576 | 0.4947 |
| (-653.5, 79.5) | 7.3732, bank:osm:relation/2315576, terrain | 7.3732, bank:osm:relation/2315576, terrain | 7.9186 | 7.3732 | bank:osm:relation/2315576 | 0.5454 |
| (-653.5, 80.5) | 7.3225, bank:osm:relation/2315576, terrain | 7.3225, bank:osm:relation/2315576, terrain | 7.9186 | 7.3225 | bank:osm:relation/2315576 | 0.5961 |
| (-653.5, 81.5) | 7.2719, bank:osm:relation/2315576, terrain | 7.2719, bank:osm:relation/2315576, terrain | 7.9186 | 7.2719 | bank:osm:relation/2315576 | 0.6467 |
| (-653.5, 82.5) | 7.2212, bank:osm:relation/2315576, terrain | 7.2212, bank:osm:relation/2315576, terrain | 7.9186 | 7.2212 | bank:osm:relation/2315576 | 0.6974 |
| (-653.5, 83.5) | 7.1683, bank:osm:relation/2315576, terrain | 7.1683, bank:osm:relation/2315576, terrain | 7.9186 | 7.1683 | bank:osm:relation/2315576 | 0.7502 |
| (-652.5, 82.5) | 7.7119, bank:osm:relation/2315576, terrain | 7.7119, bank:osm:relation/2315576, terrain | 7.9186 | 7.7119 | bank:osm:relation/2315576 | 0.2067 |
| (-653.5, 84.5) | 7.0215, bank:osm:relation/2315576, terrain | 7.0215, bank:osm:relation/2315576, terrain | 7.9186 | 7.0215 | bank:osm:relation/2315576 | 0.8971 |
| (-652.5, 83.5) | 7.6517, bank:osm:relation/2315576, terrain | 7.6517, bank:osm:relation/2315576, terrain | 7.9186 | 7.6517 | bank:osm:relation/2315576 | 0.2669 |
| (-652.5, 84.5) | 7.4863, bank:osm:relation/2315576, terrain | 7.4863, bank:osm:relation/2315576, terrain | 7.9186 | 7.4863 | bank:osm:relation/2315576 | 0.4323 |
| (-652.5, 85.5) | 7.3208, bank:osm:relation/2315576, terrain | 7.3208, bank:osm:relation/2315576, terrain | 7.9186 | 7.3208 | bank:osm:relation/2315576 | 0.5978 |
| (-652.5, 86.5) | 7.1554, bank:osm:relation/2315576, terrain | 7.1554, bank:osm:relation/2315576, terrain | 7.9186 | 7.1554 | bank:osm:relation/2315576 | 0.7632 |
| (-652.5, 87.5) | 6.9899, bank:osm:relation/2315576, terrain | 6.9899, bank:osm:relation/2315576, terrain | 7.9186 | 6.9899 | bank:osm:relation/2315576 | 0.9287 |
| (-651.5, 86.5) | 7.6201, bank:osm:relation/2315576, terrain | 7.6201, bank:osm:relation/2315576, terrain | 7.9186 | 7.6201 | bank:osm:relation/2315576 | 0.2984 |
| (-651.5, 87.5) | 7.4547, bank:osm:relation/2315576, terrain | 7.4547, bank:osm:relation/2315576, terrain | 7.9186 | 7.4547 | bank:osm:relation/2315576 | 0.4639 |
| (-651.5, 88.5) | 7.2893, bank:osm:relation/2315576, terrain | 7.2893, bank:osm:relation/2315576, terrain | 7.9186 | 7.2893 | bank:osm:relation/2315576 | 0.6293 |
| (-651.5, 89.5) | 7.1238, bank:osm:relation/2315576, terrain | 7.1238, bank:osm:relation/2315576, terrain | 7.9186 | 7.1238 | bank:osm:relation/2315576 | 0.7948 |
| (-650.5, 89.5) | 7.5886, bank:osm:relation/2315576, terrain | 7.5886, bank:osm:relation/2315576, terrain | 7.9186 | 7.5886 | bank:osm:relation/2315576 | 0.33 |
| (-650.5, 90.5) | 7.4232, bank:osm:relation/2315576, terrain | 7.4232, bank:osm:relation/2315576, terrain | 7.9186 | 7.4232 | bank:osm:relation/2315576 | 0.4954 |
| (-650.5, 91.5) | 7.2577, bank:osm:relation/2315576, terrain | 7.2577, bank:osm:relation/2315576, terrain | 7.9186 | 7.2577 | bank:osm:relation/2315576 | 0.6609 |
| (-650.5, 92.5) | 7.0923, bank:osm:relation/2315576, terrain | 7.0923, bank:osm:relation/2315576, terrain | 7.9186 | 7.0923 | bank:osm:relation/2315576 | 0.8263 |
| (-649.5, 92.5) | 7.557, bank:osm:relation/2315576, terrain | 7.557, bank:osm:relation/2315576, terrain | 7.9186 | 7.557 | bank:osm:relation/2315576 | 0.3615 |
| (-649.5, 93.5) | 7.3916, bank:osm:relation/2315576, terrain | 7.3916, bank:osm:relation/2315576, terrain | 7.9186 | 7.3916 | bank:osm:relation/2315576 | 0.527 |
| (-649.5, 94.5) | 7.2262, bank:osm:relation/2315576, terrain | 7.2262, bank:osm:relation/2315576, terrain | 7.9186 | 7.2262 | bank:osm:relation/2315576 | 0.6924 |
| (-649.5, 95.5) | 7.0607, bank:osm:relation/2315576, terrain | 7.0607, bank:osm:relation/2315576, terrain | 7.9186 | 7.0607 | bank:osm:relation/2315576 | 0.8578 |
| (-648.5, 94.5) | 7.6909, bank:osm:relation/2315576, terrain | 7.6909, bank:osm:relation/2315576, terrain | 7.9186 | 7.6909 | bank:osm:relation/2315576 | 0.2276 |
| (-648.5, 95.5) | 7.5255, bank:osm:relation/2315576, terrain | 7.5255, bank:osm:relation/2315576, terrain | 7.9186 | 7.5255 | bank:osm:relation/2315576 | 0.3931 |
| (-648.5, 96.5) | 7.3424, bank:osm:relation/2315576, terrain | 7.3424, bank:osm:relation/2315576, terrain | 7.9186 | 7.3424 | bank:osm:relation/2315576 | 0.5761 |
| (-648.5, 97.5) | 7.1283, bank:osm:relation/2315576, terrain | 7.1283, bank:osm:relation/2315576, terrain | 7.9186 | 7.1283 | bank:osm:relation/2315576 | 0.7903 |
| (-647.5, 97.5) | 7.5727, bank:osm:relation/2315576, terrain | 7.5727, bank:osm:relation/2315576, terrain | 7.9186 | 7.5727 | bank:osm:relation/2315576 | 0.3459 |
| (-647.5, 98.5) | 7.3586, bank:osm:relation/2315576, terrain | 7.3586, bank:osm:relation/2315576, terrain | 7.9186 | 7.3586 | bank:osm:relation/2315576 | 0.56 |
| (-647.5, 99.5) | 7.1444, bank:osm:relation/2315576, terrain | 7.1444, bank:osm:relation/2315576, terrain | 7.9186 | 7.1444 | bank:osm:relation/2315576 | 0.7742 |
| (-646.5, 99.5) | 7.5888, bank:osm:relation/2315576, terrain | 7.5888, bank:osm:relation/2315576, terrain | 7.9186 | 7.5888 | bank:osm:relation/2315576 | 0.3297 |
| (-646.5, 100.5) | 7.3747, bank:osm:relation/2315576, terrain | 7.3747, bank:osm:relation/2315576, terrain | 7.9186 | 7.3747 | bank:osm:relation/2315576 | 0.5439 |
| (-646.5, 101.5) | 7.1606, bank:osm:relation/2315576, terrain | 7.1606, bank:osm:relation/2315576, terrain | 7.9186 | 7.1606 | bank:osm:relation/2315576 | 0.758 |
| (-645.5, 101.5) | 7.605, bank:osm:relation/2315576, terrain | 7.605, bank:osm:relation/2315576, terrain | 7.9186 | 7.605 | bank:osm:relation/2315576 | 0.3136 |
| (-645.5, 102.5) | 7.3908, bank:osm:relation/2315576, terrain | 7.3908, bank:osm:relation/2315576, terrain | 7.9186 | 7.3908 | bank:osm:relation/2315576 | 0.5277 |
| (-645.5, 103.5) | 7.1767, bank:osm:relation/2315576, terrain | 7.1767, bank:osm:relation/2315576, terrain | 7.9186 | 7.1767 | bank:osm:relation/2315576 | 0.7419 |
| (-644.5, 103.5) | 7.6211, bank:osm:relation/2315576, terrain | 7.6211, bank:osm:relation/2315576, terrain | 7.9186 | 7.6211 | bank:osm:relation/2315576 | 0.2975 |
| (-644.5, 104.5) | 7.407, bank:osm:relation/2315576, terrain | 7.407, bank:osm:relation/2315576, terrain | 7.9186 | 7.407 | bank:osm:relation/2315576 | 0.5116 |
| (-644.5, 105.5) | 7.1928, bank:osm:relation/2315576, terrain | 7.1928, bank:osm:relation/2315576, terrain | 7.9186 | 7.1928 | bank:osm:relation/2315576 | 0.7258 |
| (-643.5, 105.5) | 7.6373, bank:osm:relation/2315576, terrain | 7.6373, bank:osm:relation/2315576, terrain | 7.9186 | 7.6373 | bank:osm:relation/2315576 | 0.2813 |
| (-643.5, 106.5) | 7.4231, bank:osm:relation/2315576, terrain | 7.4231, bank:osm:relation/2315576, terrain | 7.9186 | 7.4231 | bank:osm:relation/2315576 | 0.4955 |
| (-643.5, 107.5) | 7.209, bank:osm:relation/2315576, terrain | 7.209, bank:osm:relation/2315576, terrain | 7.9186 | 7.209 | bank:osm:relation/2315576 | 0.7096 |
| (-642.5, 107.5) | 7.6534, bank:osm:relation/2315576, terrain | 7.6534, bank:osm:relation/2315576, terrain | 7.9186 | 7.6534 | bank:osm:relation/2315576 | 0.2652 |
| (-642.5, 108.5) | 7.4393, bank:osm:relation/2315576, terrain | 7.4393, bank:osm:relation/2315576, terrain | 7.9186 | 7.4393 | bank:osm:relation/2315576 | 0.4793 |
| (-642.5, 109.5) | 7.2251, bank:osm:relation/2315576, terrain | 7.2251, bank:osm:relation/2315576, terrain | 7.9186 | 7.2251 | bank:osm:relation/2315576 | 0.6935 |
| (-642.5, 110.5) | 7.011, bank:osm:relation/2315576, terrain | 7.011, bank:osm:relation/2315576, terrain | 7.9186 | 7.011 | bank:osm:relation/2315576 | 0.9076 |
| (-641.5, 109.5) | 7.6695, bank:osm:relation/2315576, terrain | 7.6695, bank:osm:relation/2315576, terrain | 7.9186 | 7.6695 | bank:osm:relation/2315576 | 0.249 |
| (-641.5, 110.5) | 7.4554, bank:osm:relation/2315576, terrain | 7.4554, bank:osm:relation/2315576, terrain | 7.9186 | 7.4554 | bank:osm:relation/2315576 | 0.4632 |
| (-641.5, 111.5) | 7.2413, bank:osm:relation/2315576, terrain | 7.2413, bank:osm:relation/2315576, terrain | 7.9186 | 7.2413 | bank:osm:relation/2315576 | 0.6773 |
| (-640.5, 111.5) | 7.6857, bank:osm:relation/2315576, terrain | 7.6857, bank:osm:relation/2315576, terrain | 7.9186 | 7.6857 | bank:osm:relation/2315576 | 0.2329 |
| (-640.5, 112.5) | 7.4604, bank:osm:relation/2315576, terrain | 7.4604, bank:osm:relation/2315576, terrain | 7.9186 | 7.4604 | bank:osm:relation/2315576 | 0.4582 |
| (-640.5, 113.5) | 7.1987, bank:osm:relation/2315576, terrain | 7.1987, bank:osm:relation/2315576, terrain | 7.9186 | 7.1987 | bank:osm:relation/2315576 | 0.7199 |
| (-639.5, 113.5) | 7.6169, bank:osm:relation/2315576, terrain | 7.6169, bank:osm:relation/2315576, terrain | 7.9186 | 7.6169 | bank:osm:relation/2315576 | 0.3017 |
| (-639.5, 114.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-639.5, 115.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-638.5, 114.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-638.5, 115.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-638.5, 116.5) | 10.5611, osm:way/83926163, bridge | 10.5611, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-637.5, 116.5) | 10.6411, osm:way/83926163, bridge | 10.6411, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-637.5, 117.5) | 10.6402, osm:way/83926163, bridge | 10.6402, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-637.5, 118.5) | 11.6393, osm:way/83926163, bridge | 11.6393, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-636.5, 117.5) | 10.7202, osm:way/83926163, bridge | 10.7202, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-636.5, 118.5) | 11.7192, osm:way/83926163, bridge | 11.7192, osm:way/83926163, bridge | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-636.5, 119.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-635.5, 119.5) | 6.4186, terrain:grid, terrain | 6.4186, terrain:grid, terrain | 7.9186 | 6.4186 | terrain:grid | 1.5 |
| (-635.5, 120.5) | 7.458, bank:osm:relation/2315576, terrain | 7.458, bank:osm:relation/2315576, terrain | 7.9186 | 7.458 | bank:osm:relation/2315576 | 0.4605 |
| (-635.5, 121.5) | 7.1964, bank:osm:relation/2315576, terrain | 7.1964, bank:osm:relation/2315576, terrain | 7.9186 | 7.1964 | bank:osm:relation/2315576 | 0.7222 |
| (-634.5, 121.5) | 7.6146, bank:osm:relation/2315576, terrain | 7.6146, bank:osm:relation/2315576, terrain | 7.9186 | 7.6146 | bank:osm:relation/2315576 | 0.304 |
| (-634.5, 122.5) | 7.3529, bank:osm:relation/2315576, terrain | 7.3529, bank:osm:relation/2315576, terrain | 7.9186 | 7.3529 | bank:osm:relation/2315576 | 0.5657 |
| (-634.5, 123.5) | 7.0912, bank:osm:relation/2315576, terrain | 7.0912, bank:osm:relation/2315576, terrain | 7.9186 | 7.0912 | bank:osm:relation/2315576 | 0.8273 |
| (-633.5, 123.5) | 7.5095, bank:osm:relation/2315576, terrain | 7.5095, bank:osm:relation/2315576, terrain | 7.9186 | 7.5095 | bank:osm:relation/2315576 | 0.4091 |
| (-633.5, 124.5) | 7.2478, bank:osm:relation/2315576, terrain | 7.2478, bank:osm:relation/2315576, terrain | 7.9186 | 7.2478 | bank:osm:relation/2315576 | 0.6708 |
| (-632.5, 124.5) | 7.666, bank:osm:relation/2315576, terrain | 7.666, bank:osm:relation/2315576, terrain | 7.9186 | 7.666 | bank:osm:relation/2315576 | 0.2526 |
| (-632.5, 125.5) | 7.4043, bank:osm:relation/2315576, terrain | 7.4043, bank:osm:relation/2315576, terrain | 7.9186 | 7.4043 | bank:osm:relation/2315576 | 0.5143 |
| (-632.5, 126.5) | 7.1427, bank:osm:relation/2315576, terrain | 7.1427, bank:osm:relation/2315576, terrain | 7.9186 | 7.1427 | bank:osm:relation/2315576 | 0.7759 |
| (-631.5, 126.5) | 7.5609, bank:osm:relation/2315576, terrain | 7.5609, bank:osm:relation/2315576, terrain | 7.9186 | 7.5609 | bank:osm:relation/2315576 | 0.3577 |
| (-631.5, 127.5) | 7.2992, bank:osm:relation/2315576, terrain | 7.2992, bank:osm:relation/2315576, terrain | 7.9186 | 7.2992 | bank:osm:relation/2315576 | 0.6194 |
| (-630.5, 127.5) | 7.7174, bank:osm:relation/2315576, terrain | 7.7174, bank:osm:relation/2315576, terrain | 7.9186 | 7.7174 | bank:osm:relation/2315576 | 0.2012 |
| (-630.5, 128.5) | 7.4557, bank:osm:relation/2315576, terrain | 7.4557, bank:osm:relation/2315576, terrain | 7.9186 | 7.4557 | bank:osm:relation/2315576 | 0.4628 |
| (-630.5, 129.5) | 7.1941, bank:osm:relation/2315576, terrain | 7.1941, bank:osm:relation/2315576, terrain | 7.9186 | 7.1941 | bank:osm:relation/2315576 | 0.7245 |
| (-629.5, 129.5) | 7.6123, bank:osm:relation/2315576, terrain | 7.6123, bank:osm:relation/2315576, terrain | 7.9186 | 7.6123 | bank:osm:relation/2315576 | 0.3063 |
| (-629.5, 130.5) | 7.3506, bank:osm:relation/2315576, terrain | 7.3506, bank:osm:relation/2315576, terrain | 7.9186 | 7.3506 | bank:osm:relation/2315576 | 0.568 |
| (-629.5, 131.5) | 7.1623, bank:osm:relation/2315576, terrain | 7.1623, bank:osm:relation/2315576, terrain | 7.9186 | 7.1623 | bank:osm:relation/2315576 | 0.7563 |
| (-629.5, 132.5) | 7.0864, bank:osm:relation/2315576, terrain | 7.0864, bank:osm:relation/2315576, terrain | 7.9186 | 7.0864 | bank:osm:relation/2315576 | 0.8321 |
| (-628.5, 131.5) | 7.6497, bank:osm:relation/2315576, terrain | 7.6497, bank:osm:relation/2315576, terrain | 7.9186 | 7.6497 | bank:osm:relation/2315576 | 0.2688 |
| (-629.5, 133.5) | 7.0106, bank:osm:relation/2315576, terrain | 7.0106, bank:osm:relation/2315576, terrain | 7.9186 | 7.0106 | bank:osm:relation/2315576 | 0.908 |
| (-628.5, 132.5) | 7.5739, bank:osm:relation/2315576, terrain | 7.5739, bank:osm:relation/2315576, terrain | 7.9186 | 7.5739 | bank:osm:relation/2315576 | 0.3447 |
| (-629.5, 134.5) | 6.9348, bank:osm:relation/2315576, terrain | 6.9348, bank:osm:relation/2315576, terrain | 7.9186 | 6.9348 | bank:osm:relation/2315576 | 0.9838 |
| (-628.5, 133.5) | 7.4981, bank:osm:relation/2315576, terrain | 7.4981, bank:osm:relation/2315576, terrain | 7.9186 | 7.4981 | bank:osm:relation/2315576 | 0.4205 |
| (-628.5, 134.5) | 7.4223, bank:osm:relation/2315576, terrain | 7.4223, bank:osm:relation/2315576, terrain | 7.9186 | 7.4223 | bank:osm:relation/2315576 | 0.4963 |
| (-628.5, 135.5) | 7.3464, bank:osm:relation/2315576, terrain | 7.3464, bank:osm:relation/2315576, terrain | 7.9186 | 7.3464 | bank:osm:relation/2315576 | 0.5721 |
| (-628.5, 136.5) | 7.2706, bank:osm:relation/2315576, terrain | 7.2706, bank:osm:relation/2315576, terrain | 7.9186 | 7.2706 | bank:osm:relation/2315576 | 0.648 |
| (-628.5, 137.5) | 7.1948, bank:osm:relation/2315576, terrain | 7.1948, bank:osm:relation/2315576, terrain | 7.9186 | 7.1948 | bank:osm:relation/2315576 | 0.7238 |
| (-628.5, 138.5) | 7.119, bank:osm:relation/2315576, terrain | 7.119, bank:osm:relation/2315576, terrain | 7.9186 | 7.119 | bank:osm:relation/2315576 | 0.7996 |
| (-627.5, 137.5) | 7.6823, bank:osm:relation/2315576, terrain | 7.6823, bank:osm:relation/2315576, terrain | 7.9186 | 7.6823 | bank:osm:relation/2315576 | 0.2363 |
| (-628.5, 139.5) | 7.0431, bank:osm:relation/2315576, terrain | 7.0431, bank:osm:relation/2315576, terrain | 7.9186 | 7.0431 | bank:osm:relation/2315576 | 0.8754 |
| (-627.5, 138.5) | 7.6064, bank:osm:relation/2315576, terrain | 7.6064, bank:osm:relation/2315576, terrain | 7.9186 | 7.6064 | bank:osm:relation/2315576 | 0.3122 |
| (-628.5, 140.5) | 6.9673, bank:osm:relation/2315576, terrain | 6.9673, bank:osm:relation/2315576, terrain | 7.9186 | 6.9673 | bank:osm:relation/2315576 | 0.9513 |
| (-627.5, 139.5) | 7.5306, bank:osm:relation/2315576, terrain | 7.5306, bank:osm:relation/2315576, terrain | 7.9186 | 7.5306 | bank:osm:relation/2315576 | 0.388 |
| (-627.5, 140.5) | 7.4548, bank:osm:relation/2315576, terrain | 7.4548, bank:osm:relation/2315576, terrain | 7.9186 | 7.4548 | bank:osm:relation/2315576 | 0.4638 |
| (-627.5, 141.5) | 7.3772, bank:osm:relation/2315576, terrain | 7.3772, bank:osm:relation/2315576, terrain | 7.9186 | 7.3772 | bank:osm:relation/2315576 | 0.5414 |
| (-627.5, 142.5) | 7.1783, bank:osm:relation/2315576, terrain | 7.1783, bank:osm:relation/2315576, terrain | 7.9186 | 7.1783 | bank:osm:relation/2315576 | 0.7403 |
| (-626.5, 142.5) | 7.6213, bank:osm:relation/2315576, terrain | 7.6213, bank:osm:relation/2315576, terrain | 7.9186 | 7.6213 | bank:osm:relation/2315576 | 0.2973 |
| (-626.5, 143.5) | 7.4043, bank:osm:relation/2315576, terrain | 7.4043, bank:osm:relation/2315576, terrain | 7.9186 | 7.4043 | bank:osm:relation/2315576 | 0.5143 |
| (-626.5, 144.5) | 7.1873, bank:osm:relation/2315576, terrain | 7.1873, bank:osm:relation/2315576, terrain | 7.9186 | 7.1873 | bank:osm:relation/2315576 | 0.7313 |
| (-625.5, 144.5) | 7.6303, bank:osm:relation/2315576, terrain | 7.6303, bank:osm:relation/2315576, terrain | 7.9186 | 7.6303 | bank:osm:relation/2315576 | 0.2883 |
| (-625.5, 145.5) | 7.4133, bank:osm:relation/2315576, terrain | 7.4133, bank:osm:relation/2315576, terrain | 7.9186 | 7.4133 | bank:osm:relation/2315576 | 0.5053 |
| (-625.5, 146.5) | 7.1963, bank:osm:relation/2315576, terrain | 7.1963, bank:osm:relation/2315576, terrain | 7.9186 | 7.1963 | bank:osm:relation/2315576 | 0.7223 |
| (-624.5, 146.5) | 7.6393, bank:osm:relation/2315576, terrain | 7.6393, bank:osm:relation/2315576, terrain | 7.9186 | 7.6393 | bank:osm:relation/2315576 | 0.2793 |
| (-624.5, 147.5) | 7.4223, bank:osm:relation/2315576, terrain | 7.4223, bank:osm:relation/2315576, terrain | 7.9186 | 7.4223 | bank:osm:relation/2315576 | 0.4963 |
| (-624.5, 148.5) | 7.1556, bank:osm:relation/2315576, terrain | 7.1556, bank:osm:relation/2315576, terrain | 7.9186 | 7.1556 | bank:osm:relation/2315576 | 0.763 |
| (-623.5, 148.5) | 7.5408, bank:osm:relation/2315576, terrain | 7.5408, bank:osm:relation/2315576, terrain | 7.9186 | 7.5408 | bank:osm:relation/2315576 | 0.3778 |
| (-623.5, 149.5) | 7.2325, bank:osm:relation/2315576, terrain | 7.2325, bank:osm:relation/2315576, terrain | 7.9186 | 7.2325 | bank:osm:relation/2315576 | 0.6861 |
| (-622.5, 149.5) | 7.6177, bank:osm:relation/2315576, terrain | 7.6177, bank:osm:relation/2315576, terrain | 7.9186 | 7.6177 | bank:osm:relation/2315576 | 0.3009 |
| (-622.5, 150.5) | 7.3094, bank:osm:relation/2315576, terrain | 7.3094, bank:osm:relation/2315576, terrain | 7.9186 | 7.3094 | bank:osm:relation/2315576 | 0.6092 |
| (-621.5, 150.5) | 7.6946, bank:osm:relation/2315576, terrain | 7.6946, bank:osm:relation/2315576, terrain | 7.9186 | 7.6946 | bank:osm:relation/2315576 | 0.224 |
| (-621.5, 151.5) | 7.3863, bank:osm:relation/2315576, terrain | 7.3863, bank:osm:relation/2315576, terrain | 7.9186 | 7.3863 | bank:osm:relation/2315576 | 0.5323 |


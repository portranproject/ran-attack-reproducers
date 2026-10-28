# 모드 B 재현 로그 분석 (현재 분석 도구로 재계산)

원본: tool/runs/ocu-saturation-window.log (501줄, [RRC] 필터, 2026-10-19T22:03:31~22:10:08)
셀 용량 12 (설정으로 96에서 축소), 보유 시간 t300 2000 + CU 가드 5000 = 7000 ms

## OCC-t3 — 목표 점유 3  [22:06:47 ~ 22:07:17)
```
window [2026-10-19T22:06:47, 2026-10-19T22:07:17) (30.0 s)
evidence uncertain: initial occupancy is unknown; reconstructed from available records
unmatched endings 0; repeated live starts 0 (through window end)
observed carry-in 0
started        6  (0.2/s wall)
peak occupancy 3   at 2026-10-19T22:07:09.530461 (observed)
still live     3 (observed, just before window end)
end reasons    {'timed out': 3}
hold time wall median 6999 ms  p90 6999 ms (matched endings only)
observed occupancy (capacity reference 12, requested window 30.0 s)
  >=   3      7.0 s of  30.0 s (  23%)   longest observed plateau   6.75 s
  >=   6      0.0 s of  30.0 s (   0%)   longest observed plateau   0.00 s
  >=   9      0.0 s of  30.0 s (   0%)   longest observed plateau   0.00 s
  >=  12      0.0 s of  30.0 s (   0%)   longest observed plateau   0.00 s
window [2026-10-19T22:06:47, 2026-10-19T22:07:17) (30.0 s)
rrcReject                       0      0.0/s
not able to serve               0      0.0/s
rrcSetupComplete                0      0.0/s
InitialUEMessage                0      0.0/s
no rrcReject observed in this window
```

## OCC-t6 — 목표 점유 6  [22:07:57 ~ 22:08:27)
```
window [2026-10-19T22:07:57, 2026-10-19T22:08:27) (30.0 s)
evidence uncertain: initial occupancy is unknown; reconstructed from available records
unmatched endings 0; repeated live starts 0 (through window end)
observed carry-in 0
started        7  (0.2/s wall)
peak occupancy 6   at 2026-10-19T22:08:20.231726 (observed)
still live     3 (observed, just before window end)
end reasons    {'timed out': 4}
hold time wall median 6999 ms  p90 6999 ms (matched endings only)
observed occupancy (capacity reference 12, requested window 30.0 s)
  >=   3      7.1 s of  30.0 s (  24%)   longest observed plateau   7.12 s
  >=   6      6.5 s of  30.0 s (  22%)   longest observed plateau   6.45 s
  >=   9      0.0 s of  30.0 s (   0%)   longest observed plateau   0.00 s
  >=  12      0.0 s of  30.0 s (   0%)   longest observed plateau   0.00 s
window [2026-10-19T22:07:57, 2026-10-19T22:08:27) (30.0 s)
rrcReject                       0      0.0/s
not able to serve               0      0.0/s
rrcSetupComplete                0      0.0/s
InitialUEMessage                0      0.0/s
no rrcReject observed in this window
```

## OCC-t12 — 목표 점유 12 (= 용량 100%)  [22:09:13 ~ 22:09:43)
```
window [2026-10-19T22:09:13, 2026-10-19T22:09:43) (30.0 s)
evidence uncertain: initial occupancy is unknown; reconstructed from available records
unmatched endings 0; repeated live starts 0 (through window end)
observed carry-in 0
started        12  (0.4/s wall)
peak occupancy 12   at 2026-10-19T22:09:36.646543 (observed)
still live     6 (observed, just before window end)
end reasons    {'timed out': 6}
hold time wall median 6999 ms  p90 6999 ms (matched endings only)
observed occupancy (capacity reference 12, requested window 30.0 s)
  >=   3      7.4 s of  30.0 s (  25%)   longest observed plateau   7.39 s
  >=   6      7.1 s of  30.0 s (  24%)   longest observed plateau   7.07 s
  >=   9      6.5 s of  30.0 s (  22%)   longest observed plateau   6.45 s
  >=  12      5.8 s of  30.0 s (  19%)   longest observed plateau   5.77 s
window [2026-10-19T22:09:13, 2026-10-19T22:09:43) (30.0 s)
rrcReject                       3      0.1/s
not able to serve               1      0.0/s
rrcSetupComplete                0      0.0/s
InitialUEMessage                0      0.0/s
observed rejection cadence (rrcReject)
```

## SAT2 — 간격 20ms 자유 주행  [22:03:35 ~ 22:04:08)
```
window [2026-10-19T22:03:35, 2026-10-19T22:04:08) (33.0 s)
evidence uncertain: initial occupancy is unknown; reconstructed from available records
unmatched endings 0; repeated live starts 0 (through window end)
observed carry-in 12
started        48  (1.5/s wall)
peak occupancy 12   at 2026-10-19T22:03:35 (observed)
still live     12 (observed, just before window end)
end reasons    {'timed out': 48}
hold time wall median 6999 ms  p90 7000 ms (matched endings only)
observed occupancy (capacity reference 12, requested window 33.0 s)
  >=   3     31.7 s of  33.0 s (  96%)   longest observed plateau   8.46 s
  >=   6     27.7 s of  33.0 s (  84%)   longest observed plateau   7.12 s
  >=   9     24.8 s of  33.0 s (  75%)   longest observed plateau   6.46 s
  >=  12     21.2 s of  33.0 s (  64%)   longest observed plateau   5.48 s
window [2026-10-19T22:03:35, 2026-10-19T22:04:08) (33.0 s)
rrcReject                      69      2.1/s
not able to serve              23      0.7/s
rrcSetupComplete                0      0.0/s
InitialUEMessage                0      0.0/s
observed rejection cadence (rrcReject)
```

## 전체 창 (세 데모 연속)
```
window [2026-10-19T22:03:35, 2026-10-19T22:10:05) (390.0 s)
evidence uncertain: initial occupancy is unknown; reconstructed from available records
unmatched endings 0; repeated live starts 0 (through window end)
observed carry-in 12
started        171  (0.4/s wall)
peak occupancy 12   at 2026-10-19T22:03:35 (observed)
still live     12 (observed, just before window end)
end reasons    {'timed out': 171}
hold time wall median 6999 ms  p90 7000 ms (matched endings only)
observed occupancy (capacity reference 12, requested window 390.0 s)
  >=   3    157.8 s of 390.0 s (  40%)   longest observed plateau  28.80 s
  >=   6     97.2 s of 390.0 s (  25%)   longest observed plateau   7.13 s
  >=   9     70.3 s of 390.0 s (  18%)   longest observed plateau   6.59 s
  >=  12     56.2 s of 390.0 s (  14%)   longest observed plateau   5.80 s
```

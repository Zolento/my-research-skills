# 存量项目布局审计（dry-run，2026-11-20）

命令：`python3 scripts/layout_guard.py audit --root <项目> --json`。
**只读**：本报告不修改任何项目。`block` 需逐条核对后再决定登记例外或整改。

| 项目 | 退出码 | block | warn | 主要规则 |
|---|---|---|---|---|
| MoSA | 3 | 216 | 88 | DI-5=269, ROOT-1=17, DI-8=16, AGENTS-1=1, ROUTE-1=1 |
| UC-Mamba-MRI | 3 | 24 | 12 | DI-5=16, DI-8=11, ROOT-1=8, AGENTS-1=1 |
| PCD-SSDU | 3 | 8 | 10 | DI-5=8, ROOT-1=6, DI-8=2, AGENTS-1=1, ROUTE-1=1 |
| SSDU-theorem | 3 | 3 | 5 | ROOT-1=4, DI-8=3, AGENTS-1=1 |
| 3D_ZS_SSL | 3 | 340 | 366 | DI-5=411, DI-8=250, DI-3=20, ROOT-1=9, DI-4=6, ROUTE-1=5 |
| FusionSENSE-Lite | 3 | 5 | 0 | DI-5=4, ROOT-1=1 |

## 逐项目的主要 block 项

### MoSA

- **DI-5**（203 项）：`experiments/A/TPOT-balanced-20261018/` 目录名不是合法 XID；`experiments/A/TPOT-time-physical-20261017/` 目录名不是合法 XID；`experiments/A/UNet-200k-20261018/` 目录名不是合法 XID
- **ROOT-1**（12 项）：`archive/` 未声明的顶层目录；`config.py` 未声明的根级文件（根级只留 AGENTS/README/INDEX）；`infer_fbs.py` 未声明的根级文件（根级只留 AGENTS/README/INDEX）
- **AGENTS-1**（1 项）：`AGENTS.md` 43258 B 超过上限 20480 B：AGENTS.md 管执行边界，不承载 RLP 规则副本

### UC-Mamba-MRI

- **DI-5**（16 项）：`experiments/GCLD/` 必须是 <area>/<路线>/；`experiments/GGCSA/` 必须是 <area>/<路线>/；`experiments/RS_DC/` 必须是 <area>/<路线>/
- **ROOT-1**（7 项）：`QUEUE_PLAN.md` 未声明的根级文件（根级只留 AGENTS/README/INDEX）；`code/` 未声明的顶层目录；`data/` 未声明的顶层目录
- **AGENTS-1**（1 项）：`AGENTS.md` 38229 B 超过上限 20480 B：AGENTS.md 管执行边界，不承载 RLP 规则副本

### PCD-SSDU

- **ROOT-1**（5 项）：`pcd_ss/` 未声明的顶层目录；`reports/` 未声明的顶层目录；`runs/` 未声明的顶层目录
- **DI-5**（3 项）：`results/baselines/` 必须是 <area>/<路线>/；`logs/jssl/` 必须是 <area>/<路线>/；`logs/ops/` 必须是 <area>/<路线>/

### SSDU-theorem

- **ROOT-1**（3 项）：`figures/` 未声明的顶层目录；`research/` 未声明的顶层目录；`texput.log` 未声明的根级文件（根级只留 AGENTS/README/INDEX）

### 3D_ZS_SSL

- **DI-5**（304 项）：`experiments/C/X16/` X16 未登记（未登记）；`experiments/C/X43b/` 目录名不是合法 XID；`experiments/C/X43c/` 目录名不是合法 XID
- **DI-3**（20 项）：`.research-lifecycle-protocol/routes/E/research-state.v109.backup.json` 一条路线只允许一个 canonical state；历史进 history/；`.research-lifecycle-protocol/routes/E/research-state.v110.backup.json` 一条路线只允许一个 canonical state；历史进 history/；`.research-lifecycle-protocol/routes/E/research-state.v111.backup.json` 一条路线只允许一个 canonical state；历史进 history/
- **ROOT-1**（8 项）：`models/` 未声明的顶层目录；`out.json` 未声明的根级文件（根级只留 AGENTS/README/INDEX）；`pred` 未声明的根级文件（根级只留 AGENTS/README/INDEX）
- **DI-4**（6 项）：`routes/A/README.md` 路线三件套缺失；`routes/A/STATUS.md` 路线三件套缺失；`routes/B/STATUS.md` 路线三件套缺失
- **ROOT-3**（1 项）：`log/` 日志统一用 logs/，禁止 log/ 与 logs/ 并存
- **AGENTS-1**（1 项）：`AGENTS.md` 39287 B 超过上限 20480 B：AGENTS.md 管执行边界，不承载 RLP 规则副本

### FusionSENSE-Lite

- **DI-5**（4 项）：`results/audit/` 必须是 <area>/<路线>/；`results/web-run/` 必须是 <area>/<路线>/；`results/x1-outcome/` 必须是 <area>/<路线>/
- **ROOT-1**（1 项）：`FUSIONSENSE_INDEPENDENT_AUDIT.md` 未声明的根级文件（根级只留 AGENTS/README/INDEX）

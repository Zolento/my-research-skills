# 速写模板库（高频论文方法图模式）

**这是模板库，不是强制清单。** 用法：

1. 先从 [sketch-primitives.md](sketch-primitives.md) §1 的**形状图例**选形状；
2. 再从这里挑一个**结构模式**照排；
3. **组合 4–8 个原语即可**，不要为每个节点发明新形状。

> ⚠️ **所有模板都以 ASCII 标签书写**，因为中文字符占 2 列。
> 换成中文标签时必须**按 2×字数补齐空格**，否则右边框会歪
> （见 [ascii-design-language.md](ascii-design-language.md) §3）。
> `scripts/check_draft.py` 会以 W4 报告对齐问题。

**形状速记：**

```text
data      ┌────┐        model      ╔════╗        loss      ╭────╮
          │ d  │                   ║ m  ║                  │ L  │
          └────┘                   ╚════╝                  ╰────╯

operator  [ FFT ]       state      x_k（不加框）   stage     ▢ 大外框
```

---

## 1. 输入对象

### 1.1 单张图像 / slice

```text
┌──────────────┐
│   MRI Input  │
│   [slice]    │
└──────────────┘
```

### 1.2 slice batch（tensor 堆叠）

```text
      ┌──────────┐
    ┌──────────┐ │
  ┌──────────┐ │ │
  │ MRI      │ │ │
  │ slices   │ │ │
  └──────────┘ │ │
    └──────────┘ │
      └──────────┘
```

### 1.3 3D volume（伪 3D 块）

```text
    _____________
   /           /|
  /  MRI Vol  / |
 /___________/  |
 |           |  |
 |    3D     |  /
 |___________| /
```

**选择规则：** 2D slice → 单框；slice batch → tensor 堆叠；3D volume → 伪 3D 块。

---

## 2. 算子与状态

### 2.1 方括号算子（轻量节点）

```text
x ──▶ [ FFT ] ──▶ k
```

适合：`FFT` / `IFFT` / `Mask` / `Norm` / `Add` / `Concat` / `Projection`。

### 2.2 强调一个数学算子

```text
┌──────────────┐
│     AᴴA      │
│   Operator   │
└──────────────┘
```

### 2.3 state 变量不加框

```text
x_k ──▶ [ DC ] ──▶ x_{k+1}
```

**变量不用框**，靠 Unicode 下标表达。加框会把它误读成模块。

---

## 3. 模型块与冻结状态

### 3.1 模型块（默认形状）

```text
╔════════════════╗
║  Flow Prior θ  ║
╚════════════════╝
```

### 3.2 冻结

```text
╔════════════════╗
║  Source Prior  ║
║    [FROZEN]    ║
╚════════════════╝
```

### 3.3 可训练

```text
╔════════════════╗
║ Adapted Prior  ║
║  [TRAINABLE]   ║
╚════════════════╝
```

> `[FROZEN]` 比 emoji 稳（见 [ascii-design-language.md](ascii-design-language.md) §1）。

---

## 4. tensor 与尺寸变化

### 4.1 多尺度特征

```text
      ┌────────────┐
    ┌────────────┐ │
  ┌────────────┐ │ │
  │  Features  │ │ │
  │  C x H x W │ │ │
  └────────────┘ │ │
    └────────────┘ │
      └────────────┘
```

### 4.2 尺寸变化靠框宽缩放（U-Net 必备）

```text
┌────────────────┐
│   H x W x 32   │
└───────┬────────┘
        ▼
  ┌────────────┐
  │ H/2 x W/2  │
  │    x 64    │
  └─────┬──────┘
        ▼
    ┌────────┐
    │ H/4 x  │
    │ W/4    │
    └────────┘
```

**不写真实 `B×C×H×W`**；用框宽表达空间分辨率，用层数表达通道。

---

## 5. 网络结构

### 5.1 U-Net 极简（只标 Enc/Dec 级别）

```text
Input
  │
  ▼
┌───────┐
│ Enc 1 │──────────────┐
└───┬───┘              │
    ▼                  │
  ┌─────┐              │ skip
  │Enc 2│────────┐     │
  └──┬──┘        │     │
     ▼           │     │
   ┌────┐        │     │
   │Mid │        │     │
   └─┬──┘        │     │
     ▼           │     │
  ┌─────┐◀───────┘     │
  │Dec 2│              │
  └──┬──┘              │
     ▼                 │
┌───────┐◀─────────────┘
│ Dec 1 │
└───┬───┘
    ▼
 Output
```

### 5.2 Encoder → latent → decoder（带 tensor）

```text
                ┌──────────┐
              ┌──────────┐ │
┌─────────┐   │ Latent z │ │   ┌─────────┐
│ Encoder │──▶└──────────┘ │──▶│ Decoder │
└─────────┘     └──────────┘   └─────────┘
```

### 5.3 多尺度 feature pyramid

```text
                ┌──────────────────┐
             ┌─▶│ Fine Features    │
             │  └──────────────────┘
┌─────────┐  │
│  Input  │──┼────▶┌────────────┐
└─────────┘  │     │ Mid-scale  │
             │     └────────────┘
             │
             └────────▶┌────────┐
                       │ Coarse │
                       └────────┘
```

### 5.4 coarse-to-fine

```text
     ┌────────────┐
     │   Coarse   │
     └────────────┘
       ┌────────┐
       │ Medium │
       └────────┘
         ┌──────┐
         │ Fine │
         └──────┘
```

### 5.5 级联块（横向）

```text
Input ─▶╔═══════╗─▶╔═══════╗─▶╔═══════╗─▶ Output
        ║Stage 1║  ║Stage 2║  ║Stage 3║
        ╚═══════╝  ╚═══════╝  ╚═══════╝
```

### 5.6 重复块 ×K（不要真画 20 次）

```text
         ┌────────────────────┐
x_0 ────▶│ Reconstruction Step│────▶ x_K
         │   DC + Prior       │
         └────────────────────┘
                  x K
```

---

## 6. 数据流控制

### 6.1 Split / branching

```text
                 ┌────▶ Branch A ────┐
                 │                   │
Input ───────────┤                   ├──▶ Merge
                 │                   │
                 └────▶ Branch B ────┘
```

### 6.2 Fusion

```text
Branch A ───┐
            ├──▶ [ Fusion ] ───▶ Output
Branch B ───┘
```

### 6.3 Residual block

```text
x ─────┬──────────────▶ ( + ) ──▶ y
       │                  ▲
       ▼                  │
   ┌────────┐             │
   │  F(x)  │─────────────┘
   └────────┘
```

### 6.4 Skip connection

```text
x ───▶ [Block 1] ───▶ [Block 2] ───▶ y
│                                     ▲
└────────────── skip ─────────────────┘
```

---

## 7. 逆问题 / MRI 重建

### 7.1 Iterative solver（横向，论文最常用）

```text
x_k ──▶ [ Data Step ] ──▶ [ Prior Step ] ──▶ x_{k+1}
 ▲                                              │
 └──────────────── repeat K steps ──────────────┘
```

### 7.2 纵向版（强调 DC 与 prior 的交替）

```text
x_k
 │
 ▼
┌──────────────────┐
│ Data Consistency │
└─────────┬────────┘
          ▼
╔══════════════════╗
║      Prior       ║
╚═════════╤════════╝
          │
          ▼
       x_{k+1}
          │
          └──────────────┐
                         │
          ◀── repeat K ──┘
```

### 7.3 Unrolled reconstruction（共享权重）

```text
          shared θ
        ───────────
           │  │  │
           ▼  ▼  ▼
y ──▶ [S_1] ─▶ [S_2] ─▶ [S_3] ──▶ x_hat
```

### 7.4 Data consistency + learned prior

```text
              measurement y
                    │
                    ▼
x_k ───────▶┌──────────────┐
            │ Data Fidelity│
            │ Aᴴ(Ax - y)   │
            └──────┬───────┘
                   ▼
                x'_k
                   │
                   ▼
            ╔══════════════╗
            ║ Learned Prior║
            ║      θ       ║
            ╚══════╤═══════╝
                   ▼
                x_{k+1}
```

### 7.5 Measurement operator

```text
Image x
   │
   ▼
┌──────────────┐
│ Forward A    │
│ FFT + Mask   │
└──────┬───────┘
       ▼
Measurement y
```

### 7.6 Mask / k-space（极简）

```text
x ──FFT──▶ k ──x M──▶ y
```

### 7.7 Multi-coil

```text
              ┌──▶ Coil 1 ─┐
              ├──▶ Coil 2 ─┤
Image x ──S──▶├──▶  ...    ├──▶ FFT ─▶ Mask ─▶ y
              └──▶ Coil C ─┘
```

---

## 8. 训练与监督

### 8.1 Loss 节点（圆角框，与模型块区分）

```text
Prediction x_hat ────┐
                     ▼
                  ╭──────╮
Target x ────────▶│ Loss │
                  ╰───┬──╯
                      │
                      ▼
                   update θ
```

### 8.2 多个 loss

```text
                 ┌──▶ L_rec ──┐
Prediction ──────┤             │
                 ├──▶ L_ss  ──┼──▶ L_total
Features ────────┤             │
                 └──▶ L_reg ──┘
```

### 8.3 Self-supervision / held-out split

```text
Measurement y
      │
      ▼
 ┌─────────┐
 │ Split Ω │
 └────┬────┘
      │
  ────┴────
  │        │
  ▼        ▼
 Ω_train  Ω_loss
  │        │
  ▼        │
 Recon     │
  │        │
  ▼        │
 A x_hat ──┘
  │
  ▼
 SSL Loss
```

### 8.4 Train / inference 分栏（**强烈建议默认使用**）

```text
┌──────────── TRAINING ────────────┐
│                                  │
│ Input ─▶ Model ─▶ Prediction     │
│                  │               │
│ Target ─────────▶ Loss           │
│                  │               │
│                  ▼               │
│                update θ          │
└──────────────────────────────────┘

                  │ learned θ
                  ▼

┌──────────── INFERENCE ───────────┐
│                                  │
│ Input ─▶ Model θ ─▶ Output       │
│                                  │
└──────────────────────────────────┘
```

> 这个模板能避免大量科学错误（GT 泄漏、训练监督画成推理输入）。

### 8.5 Teacher–Student

```text
Input
  │
  ├────────▶╔══════════╗
  │         ║ Teacher  ║
  │         ╚════╤═════╝
  │              │ pseudo target
  │              ▼
  │            ╭─────╮
  │            │Loss │
  │            ╰──▲──╯
  │               │
  └────────▶╔═════╧════╗
            ║ Student  ║
            ╚══════════╝
```

### 8.6 Siamese / two-view SSL

```text
             ┌── aug a ─▶ View 1 ─▶ Enc ─▶ z_1 ─┐
Input x ─────┤                                   ├──▶ Loss
             └── aug b ─▶ View 2 ─▶ Enc ─▶ z_2 ─┘
```

### 8.7 Memory bank / queue

```text
Features ───▶┌───────────────┐
             │ Memory Queue  │
             │ [z1 z2 ... zN]│
             └───────┬───────┘
                     ▼
               Contrastive Loss
```

### 8.8 Stop-gradient

```text
Teacher output
      │
      ▼
 [ stop-grad ]
      │
      ▼
    target
      │
      ▼
   ╭──────╮
   │ Loss │
   ╰──▲───╯
      │
Student output
```

---

## 9. 域适配 / 多模态

### 9.1 Source → target adaptation（source-free）

```text
┌─ Source Domain ─────────────────┐
│                                 │
│ Source Data ─▶ Pretraining      │
│                                 │
└───────────────┼─────────────────┘
                │
       ╔════════════════╗
       ║ Checkpoint θ_0 ║
       ║    [FROZEN]    ║
       ╚═══════╤════════╝
               │
        checkpoint only
               │
────────────────┼────────────────
    NO SOURCE DATA AVAILABLE
────────────────┼────────────────
                ▼
┌─ Target Domain ─────────────────┐
│                                 │
│ Target Data ─▶ Adaptation       │
│                                 │
│ θ*                              │
└─────────────────────────────────┘
```

### 9.2 Feature alignment（共享 encoder）

```text
                  ╔══════════╗
Source ──────────▶║          ║──▶ z_s ─┐
                  ║ Encoder  ║         ├──▶ L_align
Target ──────────▶║    θ     ║──▶ z_t ─┘
                  ╚══════════╝
```

### 9.3 多模态输入

```text
CT  ───────▶ [Enc CT ] ──┐
                         ├──▶ Shared Representation
MRI ──────▶ [Enc MRI] ──┘
```

### 9.4 Paired vs unpaired（不可配对）

```text
Source domain         Target domain

S_1                   T_1
S_2       x pair      T_2
S_3      unavailable  T_3
S_4                   T_4
```

### 9.5 Complex-valued MRI

```text
x in C
 │
 ├────▶ |x| ─────▶ structural feature
 │
 └────▶ angle(x)
```

---

## 10. 生成模型 / 扩散 / 流

### 10.1 Conditioning

```text
x_t ──────────────┐
                  │
condition c ──────┼──▶╔════════════╗
                  │   ║ Model v_θ  ║──▶ prediction
time t ───────────┘   ╚════════════╝
```

### 10.2 时间轴

```text
t_0        t_1        t_2        t_3        t_4
│          │          │          │          │
●──────────●──────────●──────────●──────────●
x_0        x_1        x_2        x_3        x_4
```

### 10.3 Forward / reverse process

```text
Forward:
x_0 ──▶ x_1 ──▶ x_2 ──▶ ... ──▶ x_T

Reverse:
x_T ◀── x_{T-1} ◀── ... ◀── x_1 ◀── x_0
```

### 10.4 Gradient path（含截断反传）

```text
forward:
θ ─▶ Model ─▶ Solver ─▶ x_K ─▶ Loss

backward:
θ ◀──────────── ∂L/∂θ ◀──────────┘
```

截断：

```text
x_0 → x_1 → x_2 → ... → x_25 → ... → x_100
                        ▲
                        │
                backprop starts here

          ◀──── gradient horizon ────
```

---

## 11. 论文叙事

### 11.1 Stage A / B / C（数据可用性不同）

```text
Stage A                 Stage B                Stage C
────────                ────────               ────────
Source data             Target only            Measurement
    │                       │                       │
    ▼                       ▼                       ▼
Pretrain θ_0 ───────▶ Adapt θ* ─────────────▶ Reconstruction
```

### 11.2 主路径 + 仅训练辅助分支

```text
                    ┌ - - - TRAIN ONLY - - - ┐
                    │                        │
                    ▼                        │
Input ──▶ Model ──▶ Output ─ - - ▶ Aux Loss │
                    │                        │
                    └────────────────────────┘
```

### 11.3 核心贡献高亮（不用颜色）

```text
        ┌──────────────────────────┐
        │     STANDARD PIPELINE    │
        └────────────┬─────────────┘
                     ▼
        ╔══════════════════════════╗
        ║    OUR CORE MODULE       ║
        ║   Structural Adapter     ║
        ╚════════════╤═════════════╝
                     ▼
               [ Reconstruction ]
```

### 11.4 Baseline vs Proposed

```text
Baseline
────────
Input ─▶ Prior ─▶ Solver ─▶ Output

Proposed
────────
Input ─▶ Prior ─▶ [Adaptation] ─▶ Solver ─▶ Output
                    ▲
                    │
                  Target
```

> **不要故意让 proposed 复杂十倍**（见 `SKILL.md` §0.2 夸大包装禁令）。

### 11.5 Motivation：失败链 → 修正

```text
Pretrained Prior
      │
      ▼
Distribution Mismatch
      │
      ▼
Poor Target Alignment
      │
      ▼
Reconstruction Bias
```

修正：

```text
Pretrained Prior
      │
      ▼
╔══════════════════╗
║ Target Adaptation║
╚═════════╤════════╝
          ▼
 Better Target Prior
          │
          ▼
 Reconstruction
```

### 11.6 概念 / 等式节点（不是 network 也不是数据）

```text
┌────────────────────────┐
│  p_source != p_target  │
│ Distribution Mismatch  │
└────────────────────────┘
```

---

## 12. Traceback：怎么选模板

| 你要表达 | 用哪节 |
|---|---|
| 输入是图像 / batch / volume | §1 |
| 轻量算子、变量 | §2 |
| 网络块、冻结状态 | §3 |
| 特征图、分辨率变化 | §4 |
| U-Net、金字塔、级联 | §5 |
| 分支、融合、残差、skip | §6 |
| MRI 重建、逆问题、unrolled | §7 |
| loss、SSL、teacher-student | §8 |
| 域适配、多模态 | §9 |
| 扩散 / 流 / 梯度 | §10 |
| 贡献叙事、motivation、对比 | §11 |

**没有合适的模板时**：回到 [sketch-primitives.md](sketch-primitives.md) §1 的图例，
用 4–8 个原语自己组合；**不要发明新字形**。

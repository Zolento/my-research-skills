# skills

我的 agent skill 集合。**每个子目录 = 一个独立的 skill**，入口是它自己的 `SKILL.md`；
子目录里可以各带 `references/`、`scripts/`、`templates/`、`examples/` 与自己的 `.gitignore`。

## 子目录

| 目录 | 是什么 |
|---|---|
| [`research-idea-pipeline/`](research-idea-pipeline/) | 面向 CVPR / ICML / NeurIPS / MICCAI 投稿的研究创意全流程流水线：文献调研 → idea 发现 → 方案生成 → 多套路叙事生成与审稿 → 方案复核。含可运行的多源检索脚本与离线测试。 |

## 约定

- 一个子目录一个 skill，互不依赖。
- skill 之间不共享代码；公共约定写在各子目录自己的文档里。

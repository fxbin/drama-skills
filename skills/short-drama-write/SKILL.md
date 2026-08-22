---
name: short-drama-write
description: 编写或修订可拍摄的中文短剧、漫剧单集 Markdown 剧本，也负责保留作者原文地规范化现成剧本。用户提出“写/改一集短剧”“把大纲写成剧本”“优化场景/对白”“去模板感”“去 AI 味润色”“续写下一集”或提供剧本要求进入后续制作时使用；不负责资产、分镜、媒体提示词或终审。
license: MIT
---

# 短剧写作

把单集意图写成可表演、可拍摄、会改变故事状态的剧本；不负责资产、分镜、媒体提示词或终审。

## Quick Start

新项目和独立任务只写 `创作内容/剧集/<EP>/剧本.md`。不要另建 episode card、beats、block index、
录音表、QA 或接受记录。场景 ID 写在 Markdown 标题即可；下游明确需要机器索引时再临时生成。
通用边界见核心技能的 `references/creator-workflow.md` 与 `creator-documents.md`。

已有结构化单集继续使用原来的 `screenplay.md`、卡片、节拍和索引，不迁移成第二套格式。

## 入口

- 有分集规划：读取本集进入状态、目标、转折、回报和交接事实。
- 只有想法/大纲：在本轮上下文中形成最小单集契约和因果节拍，再直接写剧本。
- 已有剧本：保留作者语言，做用户点名的定点修订。
- 非规范文本要进入制作：保留原文，只做必要的场景、动作、对白和生产标签规范化；不补造剧情。

开发大纲和长篇分析都是可选上游。当前材料足够写时直接写。

## 工作流

1. **锁定本集作用**：谁现在要什么、阻力是什么、这一集必须兑现什么、结束后什么不可逆地改变。
2. **在上下文中排因果节拍**：每拍回答“因为—行动—结果—下一股压力”，不单独落盘节拍表。
3. **逐场确定功能**：谁的议程对撞、哪个可见行动承载冲突、场尾状态怎样推动下一场。
4. **写正文**：场景标题、动作、对白、画外音和必要声音事实都进入同一份 `剧本.md`。
5. **自动续跑**：用户要求整集就写完整集；场景只是内部批次，中途不逐场请求确认。
6. **修订与自检**：局部修订保留不相关段落；直接修正明确问题，只把真实剧情分叉交给用户。

格式见 [screenplay-format.md](references/screenplay-format.md)；可拍摄行动与场景设计见
[script-craft.md](references/script-craft.md)；对白见 [dialogue-craft.md](references/dialogue-craft.md)；
声音见 [scene-sound-dramaturgy.md](references/scene-sound-dramaturgy.md)。

## 写作要求

- 每场都改变信息、权力、关系、情绪、物理状态或风险；没有变化的场删掉或合并。
- 对白必须在争取、回避、试探、逼迫或重新定义关系，不用解释替代行动。
- 用人物能看见、听见、触到的行为表现状态；不写无法拍摄的内心结论。
- 人物声音靠策略、词汇、句长、回避方式和权力位置区分，不靠口头禅标签。
- 钩子来自未解决压力或新事实，不机械停在一句“你竟然”。
- 不用统一字数、镜头数或节拍数填模板；长度服从本集戏剧动作。
- 用户原文优先；“去 AI 味”是定点修订，不抹平作者个性。

遇到功能必须保留但实现可替换的桥段，使用
[substitutable-realization.md](references/substitutable-realization.md) 区分功能与拍法。只有长单集确实
跨上下文中断时才读取 [scene-handoff-capsule.md](references/scene-handoff-capsule.md)，且胶囊留在工作
上下文，不作为默认项目文件。

## 时长估算（按需）

用户问时长时才估算。creator-first 项目把索引放在临时目录，读完删除，不污染单集目录：

```bash
TMP_DIR=$(mktemp -d)
python3 scripts/screenplay_index.py 创作内容/剧集/EP001/剧本.md --output "$TMP_DIR/index.jsonl"
python3 scripts/duration_estimate.py 创作内容/剧集/EP001/剧本.md \
  --index "$TMP_DIR/index.jsonl" --project short-drama.json
rm -rf "$TMP_DIR"
```

估算是给创作者看的参考，不是门禁。项目没有声明语速或动作段速率时只报告可数事实，不猜秒数。

## 旧项目兼容

已有结构化项目按原文件继续：`assets/episode-card*.json`、`assets/beats.jsonl`、
`assets/screenplay.md`、`screenplay_index.py` 和 `voice_sheet_check.py` 都保留可用。只有现有消费者明确
需要时才发布索引或配音表；不要因为安装了模板就在新项目复制它们。

## 完成

点名范围已写入、场景因果连贯、对白与行动可表演、承诺有兑现或有意延迟、结尾状态明确，即完成。
回报关键变化和真实未决项；资产、分镜、审查与生产只有用户点名时开始。

## 安装维护

安装、升级或旧项目排障时才运行 `python3 scripts/selftest.py`；旧配音表用
[voice_sheet_check.py](scripts/voice_sheet_check.py) 校验。普通 creator-first 写作不运行它们。

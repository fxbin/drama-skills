---
name: short-drama
description: 基于文件系统初始化、继续和交付短剧或漫剧项目，并提供面向创作者的本地 Dashboard；也负责项目级制作形态、视觉方向和 Look Development 路由。用户提出“创建/继续短剧项目”“看进度/下一步”“做 Look Development”“打开 dashboard/短剧创作台”“导出制作资料”，或任务跨多个环节而需要判断负责技能时使用；明确的写作、资产、提示词、分镜或审查请求由对应子 skill 直接处理。
license: MIT
---

# 短剧创作路由

本技能只负责项目级路由、初始化、状态、Dashboard 和交付；各阶段正文由对应 owner 完成。

## Quick Start

新项目和独立任务遵守 [creator-first 工作流](references/creator-workflow.md)：每集最多五份创作者
Markdown，按需创建，不为了流程完整生成 JSON/JSONL、索引、指纹、QA 或交接文件。五份文档格式
见 [creator-documents.md](references/creator-documents.md)。

已经存在 `screenplay.md`、`*.json` 或 `*.jsonl` 权威产物的项目继续原布局；不迁移、不同时维护
两套真相。`short-drama.json` 和工具写入的隐藏运行状态不算创作产物。

## 路由

| 用户要做什么 | owner / 行为 |
|---|---|
| 开发点子、系列承诺、改编和分集地图 | `$short-drama-develop`，仅在用户需要时 |
| 已有多集完整剧本/散稿，需要识别分集并续跑 | `$short-drama-develop` 按实际边界建立索引 |
| 分析长篇原著 | `$short-drama-novel-analyze`，仅在用户需要时 |
| 写或改单集剧本 | `$short-drama-write` → `剧本.md` |
| 拆人物、造型、地点、道具 | `$short-drama-assets` → `视觉设定.md` |
| 写资产图片提示词 | `$short-drama-image-prompts` → `图片提示词.md` |
| 做镜头和冻结关键帧 | `$short-drama-storyboard` → `分镜.md` |
| 写视频/时间线音乐提示词 | `$short-drama-video-prompts` → `视频提示词.md` |
| 实际生成媒体 | `$short-drama-produce`，先预览，再显式确认，最后运行 |
| 审稿或校验 | `$short-drama-review`，只有用户点名或交付明确需要时 |
| 初始化、状态、Dashboard、导出 | 本技能 |

直接入场合法：现成剧本可直接拆资产；已有视觉事实可直接写图片提示词或分镜；已有分镜可直接写
视频提示词。不要补造没有创作价值的上游文件。

## 执行请求

1. 找到用户给出的项目/资料，只读当前任务的直接输入。
2. 把用户点名的完整范围交给相应 owner；批次只用于内部控制上下文，自动续跑。
3. 只有真实创作分叉才询问；不要拿 schema、目录、事务或检查器询问创作者。
4. 范围完成后一次回报：完成内容、关键决定、真实未决项、可选下一步。
5. 不自动开始用户没点名的审查、交付或生产。

## 初始化

需要项目配置时运行：

```bash
python3 {技能目录}/scripts/project_tool.py init ./my-drama --title "示例短剧"
```

`init` 只建立配置和空目录，不生成故事。creator-first 文档在第一次被请求时直接写入
`创作内容/剧集/<EP>/`；不要预建五个空文件。

## 旧项目生命周期

旧布局继续使用现有命令，不改行为：

```text
project_tool.py status <project>
project_tool.py publish <project> ...
project_tool.py accept <project> ...
project_tool.py review <project> ...
project_tool.py package <project> ...
project_tool.py verify <delivery>
```

这些命令服务已有结构化项目；creator-first 普通创作不为了使用它们而复制 Markdown。命令参数和
安全边界见 [lifecycle-commands.md](references/lifecycle-commands.md)。

## Dashboard

用户明确要求 Dashboard 时，从技能目录运行：

```bash
python3 scripts/dashboard_server.py --workspace <workspace> --port 0 --open
```

Dashboard 只展示它能识别的现有项目文件，不负责工作流编排、媒体生产或创作者接受。

## 项目级创作决定

制作形态、视觉方向、播放面和集长目标确实会约束多个阶段时，先展示选择及影响，再由用户决定。
旧项目可用 `set-authority` 写入已接受决定；creator-first 文档只引用决定结果，不复制审批过程。
Look Development 是可选分支，不是进入图片提示词或分镜的固定门槛。

## 生产与交付边界

外部生产永远保留 `preview -> explicit confirm -> run`。交付只包含用户点名的当前文档和成品，排除
私有输入、凭据、绝对路径和隐藏运行状态；校验和只能证明字节未变，不能证明创作质量。

## 安装维护

只有安装、升级或排障时运行：

```bash
python3 scripts/selftest.py
```

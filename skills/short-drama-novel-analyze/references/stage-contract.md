# 原著分析阶段契约

## 目录

- [运行时预检](#运行时预检)
- [所有权边界](#所有权边界)
- [材料授权与只读转化](#材料授权与只读转化)
- [本阶段规则](#本阶段规则)

本文件是本技能的自包含契约：预检、所有权、材料边界与规则表都在这里，
不需要读取其他技能的文件。

## 运行时预检

进入本阶段前完成同一套短预检；它只确认安装、项目位置和当前直接输入，不评价创作内容。

1. **验证安装**：从本技能的 `suite-ref.json` 找到同一安装中的 core，运行
   `python3 <core>/scripts/suite_verify.py <core>`。混装、缺件或清单校验失败时停止写入。
2. **读取状态**：定位项目根后运行 `python3 <core>/scripts/project_tool.py status <project>`；
   使用返回的目录布局，只读取本任务需要的直接输入。
3. **通过公开命令写入**：owner 用 `publish` 发布产物并用 `--input <path>` 声明直接输入；
   创作者用 `accept` 决定当前版本，reviewer 用 `review` 记录结论。输入或输出变化时该产物显示
   `update_needed`，重新发布即可，不递归改写无关产物。
4. **保持职责分离**：创作者确认、内容修订和复核是不同动作；reviewer 提修改要求，owner 改文件。
   `package` 只收录当前已确认且复核通过的文本/JSON。

## 所有权边界

- **本阶段拥有**：`项目开发/source-analysis/` 下的章节索引、改编价值快评、逐章提取、
  剧情单元、节奏情绪、人物与设定候选、改编价值评估与分集候选。
- **本阶段继承**：创作者提供的原始材料与授权说明、项目语言、已接受的形式约束与制作形态。
- **本阶段不越权**：不改写 `输入/`；不写改编契约、创作简报、故事引擎或
  `adaptation-map.jsonl`（`$short-drama-develop` 拥有）；不建资产身份；不写场景、台词、
  分镜与提示词；不生成媒体；不批准自己的产物。

分析层与决策层分开的理由很直接：**分析可以被推翻，契约不能**。把两者写进同一份文件，
创作者就再也无法只推翻分析而保留已确认的改编承诺。

## 材料授权与只读转化

- 只处理创作者声明**合法持有、拥有使用权**的作品；授权不清时保留问题，不替创作者定案。
- 分析是转化性的：提取结构与功能，不复制原文成段落，不模仿原作文风生成新文本。
- 引用采用最短必要片段，并绑定 span 与 hash。功能摘要必须是**去引用**的重述。
- 通俗题材的暴力、复仇、背叛、情爱张力与黑暗伦理照常提取；个别片段无法处理时跳过并记录，
  不中止整章或整本。
- `输入/` 与其中的原始材料不进入交付包。

## 本阶段规则

### `NVA`

| ID | Class | Knowledge |
|---|---|---|
| NVA-01 | structural_invariant | All stages slice the source through one chapter index bound to the source hash; a changed source invalidates the index and everything derived from it. |
| NVA-02 | structural_invariant | Every extracted claim carries a source locator and span; a claim with no span cannot be cited downstream. |
| NVA-03 | structural_invariant | Aggregation may not start while chapter coverage is incomplete; missing chapters are named in every aggregate that inherits the gap. |
| NVA-04 | structural_invariant | Analysis records de-quoted function summaries, never copied source paragraphs. |
| NVA-05 | structural_invariant | A sampled stage states its own coverage and confines every claim to the chapters it read. |
| NVA-06 | reviewed_invariant | A function summary states what a passage does to character choice, information, power or relationship, not what happens in it. |
| NVA-07 | reviewed_invariant | Hard facts — levels, counts, distances, who said what, which chapters a character appears in — trace back to a description line or the source; an unsupported one is written as unstated, never filled in by plausibility. |
| NVA-08 | reviewed_invariant | Character merges preserve dramatic role, knowledge scope, relational position and causal bridge; only proper names and evidenced nicknames may merge, never descriptors or titles. |
| NVA-09 | reviewed_invariant | Adaptation value distinguishes what the screen can show from what only prose can deliver, and names the new carrier for each function it keeps. |
| NVA-10 | reviewed_invariant | Episode candidates are cut on local dramatic result and precise handoff, not on chapter count or word budget. |
| NVA-11 | craft_default | Triage a deterministic spread of chapters across the whole book and stop for the creator before committing to a full pass. |
| NVA-12 | taste_option | Where to open, which line to keep and which ending to promise remain creator choices; analysis may argue but never blocks. |

规则分级由高到低：`structural_invariant`（结构缺陷，阻断）、
`reviewed_invariant`（需证据判断）、`craft_default`（常用做法，可覆盖）、
`taste_option`（创作者选择，不作缺陷）。创作者已接受的事实优先于本表。

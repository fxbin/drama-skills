# 开发阶段契约

## 目录

- [运行时预检](#运行时预检)
- [所有权边界](#所有权边界)
- [制作形态需要什么](#制作形态需要什么)
- [本阶段规则](#本阶段规则)

本文件是本技能的自包含契约：预检、所有权、形态输入与规则表都在这里，
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

- **本阶段拥有**：系列承诺、冲突引擎、弧线、已规划的单集契约；已规划的知识/目标/关系/
  交接状态；改编取舍与题材选择。
- **本阶段继承**：创作者已接受的方向、约束、题材与受众承诺。
- **本阶段不越权**：不写逐镜事实，不指定供应商字段，不代替剧本决定场景怎么演。剧本环节
  只投影本契约，不复制它；契约变化时由本阶段发出修订，让下游刷新引用。

## 制作形态需要什么

视觉风格不是贴在提示词前面的标签。创作者已接受的视觉方向与制作形态由项目层决定并传入，
**本技能不加载形态卡，也不自行选择形态**；本节只说明本阶段需要形态回答什么、以及拿到
答案后投影成哪些字段。

形态决定属于 `craft_default`：创作者说明理由即可覆盖。形态不能创造新的
`structural_invariant`，也不能改写身份、地理、持物归属与可读文字政策。审查者不得单凭
形态偏好阻断交付。

不要用“加一句风格前缀”处理形态差异。前缀只改变检索标签；形态改变的是**必须出现和
可以省略的字段**，只有后者会被执行，也只有后者能被审查。

本阶段要向形态决定问三件事，答案写进创作简报，不写进剧本：

- **叙事职责**：这种形态要帮观众更快看懂什么、感到什么——不能只写“高级”“电影感”。
- **运动预算**：哪些段落必须全动作，哪些可以靠保持姿态、局部循环、视差或剪辑完成。
  这直接决定分集地图里哪些场面写得起、哪些要换写法。
- **未决试验**：哪些形态能力还没验证过，需要先做小样。

本阶段新增：叙事职责、形态假设、运动预算与未决试验。不产出形、材质、光或镜头层字段。

## 本阶段规则

### `STY`

| ID | Class | Knowledge |
|---|---|---|
| STY-01 | craft_default | State the promise as protagonist, pursuit, costly opposition, and recurring payoff. |
| STY-02 | craft_default | Build a repeatable conflict engine whose pressure can change power, knowledge, relationship, exposure, cost, or time. |
| STY-03 | reviewed_invariant | A beat/episode escalation must change a story state rather than repeat the same pressure louder. |
| STY-04 | craft_default | Enter with pressure active and deliver part of the promised payoff before the outgoing hook. |
| STY-05 | structural_invariant | Incoming/setup/payoff references resolve to known records or are explicitly unresolved. |
| STY-06 | taste_option | Hook, arc shape, episode count, and climax position follow the creator's format. |
| STY-07 | reviewed_invariant | Character/scene merges preserve dramatic function, knowledge permissions, relationship position, and causal bridges. |
| STY-08 | craft_default | Translate exposition through consequential behavior, evidence, spatial pressure, or dialogue strategy before adding neutral explanation. |
| STY-09 | reviewed_invariant | A reveal/reversal grows from established facts and changes a plan, explanation, relationship, or costly choice. |
| STY-10 | craft_default | Establish the recurring-payoff promise once the opening pressure makes it legible; an opening may imply, delay, or state it according to genre and creator intent. Plan each outgoing hook from the episode's local result rather than repeating a type by quota. |
| STY-11 | craft_default | Build only the prior-world reservoir needed to predict present choices, then enter where an established strategy begins to create visible cost. |
| STY-12 | reviewed_invariant | Claimed character progression cites a pressure test, choice or retreat, local result, cost, and changed visible strategy. |
| STY-13 | reviewed_invariant | Each episode produces a local dramatic result before its outgoing hook; serialization cannot rely only on pausing an unfinished action. |
| STY-14 | craft_default | Maintain compact serial memory for character strategy/state, relationships, information permissions, setup debt, rhythm, and exact handoff. |
| STY-15 | reviewed_invariant | Calibrate each information release to what its visible carrier directly supports, while keeping unproved identity, cause, motive, or mechanism explicit as unresolved inference. |
| STY-16 | craft_default | Before scene work, estimate each planned episode's shot and duration magnitude from the project's own accepted ratios, and resolve order-of-magnitude outliers in the map; the estimate informs the creator and never blocks delivery. |
| STY-17 | reviewed_invariant | A premise device separates its creator-accepted contract (scope, failure conditions, cost, whether its own declarations are reliable) from in-fiction disclosure; the contract is accepted before the device first takes effect, while disclosure may lag, stay partial, or be misstated by a character or the device itself. Every later device ability or exemption traces to a contract clause—an untraceable one is retroactive widening—and the audience not yet knowing every boundary is never itself a defect. |
| STY-18 | structural_invariant | A multi-episode source is read through a verified exact-byte episode index; source drift invalidates every old span, and resume derives missing IDs from the current episode map rather than a last-completed guess. |
| STY-19 | craft_default | For a multi-episode source, the Agent chooses each batch from this file's measured episode spans, semantic complexity, and available context, then reads only the current slices and compact accepted handoff; no fixed episode quota substitutes for that judgment. |

规则分级由高到低：`structural_invariant`（结构缺陷，阻断）、
`reviewed_invariant`（需证据判断）、`craft_default`（常用做法，可覆盖）、
`taste_option`（创作者选择，不作缺陷）。创作者已接受的事实优先于本表。

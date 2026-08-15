# 运行时预检与发布纪律

所有入口使用同一套短预检。它只确认安装、项目位置和当前直接输入，不评价创作质量。

## 1. 验证安装

从当前技能的 `suite-ref.json` 找到同一安装中的 core，并运行：

```text
python3 <core>/scripts/suite_verify.py <core>
```

混装、缺件、额外可执行文件或清单校验失败时停止写入；不要从别的源码目录临时借文件。

## 2. 读取项目状态

定位 `short-drama.json` 后运行：

```text
python3 <core>/scripts/project_tool.py status <project>
```

使用 `status.layout.roots` 返回的项目目录。`mode=mixed` 表示中英文阶段目录并存，应先合并；
空项目在第一次阶段发布时固定布局。只读取本次任务需要的直接输入。

## 3. 通过公开命令写入

- owner 用 `publish` 原子发布一项产物，并用可重复的 `--input <project-path>` 声明直接输入。
- `accept` 只记录创作者对当前输出的接受或拒绝。
- `review` 只记录当前输出的复核结论；reviewer 不直接改 owner 文件。
- 输入或输出变化后，该产物显示 `update_needed`，重新发布即可；不递归改写下游状态。
- `package` 只收录当前 `approved` 的文本/JSON，不能替代接受或复核。

完整参数见 [lifecycle-commands.md](lifecycle-commands.md)，权威边界见
[contract-and-ownership.md](contract-and-ownership.md)。

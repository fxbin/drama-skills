你是隔离的新会话盲评审。你不知道 A/B 的版本身份，不得猜测来源，也不得参考其他案例或评审。先独立评分 A、B，再比较；不要因为更长、机关更多、验证更复杂而加分。严格使用下列量表。

{{RUBRIC}}

# 固定题面

{{CASE_SPEC}}

# 作品 A

{{ARTIFACT_A}}

# 作品 B

{{ARTIFACT_B}}

# 输出要求

只输出一个 JSON 对象，不要代码围栏或解释。所有分数为整数。每个维度对 A/B 各给具体文本证据。`overfit_evidence` 的键必须与 `overfit_flags` 完全一致；没有标签时两者分别为 `[]` 和 `{}`。`preference` 必须与总分一致，同分写 `TIE`。下面模板的身份字段和 SHA 必须原样保留，只替换分数、证据、诊断和 `preference`：

{{REPORT_TEMPLATE}}

import json
import re
import unittest
from pathlib import Path


SUITE = Path(__file__).resolve().parents[1]
SKILLS = SUITE / "skills"


def fenced_json(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"```json\n(\{.*?\})\n```", text, re.DOTALL)
    if match is None:
        raise AssertionError(f"missing fenced JSON object: {path}")
    return json.loads(match.group(1))


class ContentEffectWorkflowTests(unittest.TestCase):
    def test_new_content_jobs_are_discoverable_from_skill_frontmatter(self) -> None:
        expectations = {
            "short-drama": ("Look Development", "生产观察校准"),
            "short-drama-image-prompts": ("Look Development", "风格帧"),
            "short-drama-storyboard": ("场次视觉计划", "Coverage Audition"),
            "short-drama-review": ("生产观察", "项目校准"),
        }
        for skill_name, phrases in expectations.items():
            header = (SKILLS / skill_name / "SKILL.md").read_text(
                encoding="utf-8"
            ).split("---", 2)[1]
            for phrase in phrases:
                with self.subTest(skill=skill_name, phrase=phrase):
                    self.assertIn(phrase, header)

    def test_preview_preserves_order_duration_endpoints_and_moving_geography(self) -> None:
        storyboard = (SKILLS / "short-drama-storyboard" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        video = (SKILLS / "short-drama-video-prompts" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        continuity = (
            SKILLS
            / "short-drama-video-prompts/references/camera-audio-continuity.md"
        ).read_text(encoding="utf-8")

        for phrase in (
            "冻结首帧不得提前包含",
            "候选预览也必须精确加总",
            "宁可省略总时长",
            "候选选择清单必须覆盖正文中全部新增导演选择",
        ):
            self.assertIn(phrase, storyboard)
        for phrase in (
            "动作接触、物件归属、位置或可观察结果",
            "抽象的“处理、履行、完成”",
            "跨镜头重读完整来源顺序",
            "上游串行事件不得因压缩而并发",
            "上一镜结束边界与下一镜冻结首帧逐项相等",
            "同一句对白在相邻镜头中的开始、延续、停顿与结束",
        ):
            self.assertIn(phrase, video)
        for phrase in (
            "同一句 accepted dialogue",
            "不得在前镜声称已经说完",
            "移动不能重置地理",
        ):
            self.assertIn(phrase, continuity)

    def test_preview_acceptance_summary_is_complete_without_repeating_every_shot(self) -> None:
        storyboard = (SKILLS / "short-drama-storyboard" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        video = (SKILLS / "short-drama-video-prompts" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        normalized = re.sub(r"\s+", "", storyboard)
        for phrase in (
            "按选择类别总括",
            "不逐镜复述",
            "高影响例外",
            "正文中未由来源接受的执行选择仍全部保持候选",
            "手势/目光/表演信号",
            "因果顺序",
            "观众立场/信息时机",
            "代表帧/最强画面/场尾落点",
            "正文新增项若既不在类别范围内也未被点名",
            "播放面避让核验保持 `blocked`",
            "不要罗列与本次候选判断无关的正式发布先决条件",
        ):
            self.assertIn(re.sub(r"\s+", "", phrase), normalized)
        for phrase in (
            "动作/表演、摄影、声音与相对节奏选择也按类别总括",
            "未被总括的新增选择",
        ):
            self.assertIn(phrase, video)

    def test_missing_production_inputs_block_only_the_claims_they_support(self) -> None:
        image_recipe = (
            SKILLS / "short-drama-image-prompts/references/common-recipe.md"
        ).read_text(encoding="utf-8")
        video_skill = (SKILLS / "short-drama-video-prompts/SKILL.md").read_text(
            encoding="utf-8"
        )
        quality_gates = (
            SKILLS
            / "short-drama-review/references/production-quality-gates.md"
        ).read_text(encoding="utf-8")
        normalized_image = re.sub(r"\s+", "", image_recipe)
        normalized_video = re.sub(r"\s+", "", video_skill)
        normalized_gates = re.sub(r"\s+", "", quality_gates)

        for phrase in (
            "语义上必须出现签名",
            "不等于已经拥有可复制的正式签名字形",
            "阻断 `readable`",
            "仅在已接受文字政策允许 `postproduction` 时",
            "不得一面保留空白承载区、一面让人物认出签名",
            "<正式签名字形-ref>",
        ):
            self.assertIn(re.sub(r"\s+", "", phrase), normalized_image)
        for phrase in (
            "逐字台词缺失",
            "逐镜按实际声明的 scope",
            "不依赖逐字语速",
            "具体总时长可演",
            "中间镜不能省略声音状态",
        ):
            self.assertIn(re.sub(r"\s+", "", phrase), normalized_video)
        for phrase in (
            "正式签名字形",
            "只阻断它所支持的交付判断",
            "不阻断文本候选预览",
            "只阻断具体时长、台词表演与口型可行性",
            "只阻断该承载面的 `readable` 文字投产",
            "只阻断播放面避让核验与整体 `delivery-ready`",
            "只有全部适用范围都为 `ready`",
            "空白承载区却让人物认出",
        ):
            self.assertIn(re.sub(r"\s+", "", phrase), normalized_gates)
        stage_contract = (
            SKILLS / "short-drama-video-prompts/references/stage-contract.md"
        ).read_text(encoding="utf-8")
        self.assertIn("scope-aware", stage_contract)
        self.assertIn("all applicable scopes", stage_contract)

    def test_knowhow_cards_require_evidence_for_result_observations(self) -> None:
        cards = (
            SUITE
            / "maintainers/skills/short-drama-knowhow/references/cards-and-coverage.md"
        ).read_text(encoding="utf-8")
        for phrase in (
            "一张卡不能混合",
            "input_reference_observation",
            "generated_result_observation",
            "evidence_mode: none | creator_reported | authorized_media_inspection",
            "bounded_regions_or_intervals",
            "valid_only_for",
            "不能进入生产校准",
        ):
            self.assertIn(phrase, cards)
        self.assertIn("version_refs:", cards)
        self.assertIn("observation_kind: none", cards)
        self.assertIn("generated_result evidence fragment", cards)
        self.assertIn("input_reference evidence fragment", cards)
        self.assertIn("observer_media_observed: true", cards)
        self.assertIn("agent 自身", cards)
        none_section = cards.split("observation_kind: none", 1)[1].split(
            "generated_result evidence fragment", 1
        )[0]
        self.assertNotIn("observation_evidence:", none_section)

    def test_scene_visual_plan_and_coverage_audition_are_optional_pre_shot_layers(self) -> None:
        skill_dir = SKILLS / "short-drama-storyboard"
        skill = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        for reference in ("scene-visual-plan.md", "coverage-audition.md"):
            self.assertIn(f"references/{reference}", skill)

        plan = json.loads(
            (skill_dir / "assets/scene-visual-plan.example.jsonl").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(
            {
                "scene_ref",
                "dramatic_turn",
                "audience_alignment",
                "spatial_pressure",
                "visual_progression",
                "camera_strategy",
                "reaction_landing",
                "sound_strategy",
            }
            <= set(plan)
        )
        audition = json.loads(
            (skill_dir / "assets/coverage-audition.example.jsonl").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn("approaches", audition)
        self.assertNotIn("creator_selection_ref", audition)
        self.assertNotIn("shot_count", audition)
        self.assertNotIn("does_not_define", audition)
        self.assertRegex(audition["scene_ref"]["record_id"], r"^BLK-.+-H\d+$")
        for field in (
            "visual_direction_ref",
            "production_profile_ref",
            "location_binding",
            "asset_bindings",
        ):
            self.assertIn(field, audition)

        for field in (
            "source_block_refs",
            "visual_direction_ref",
            "production_profile_ref",
            "location_binding",
            "asset_bindings",
            "source_audition_ref",
            "creator_selection_ref",
        ):
            self.assertIn(field, plan)
        self.assertNotIn("does_not_own", plan)
        self.assertRegex(plan["scene_ref"]["record_id"], r"^BLK-.+-H\d+$")

        shot = json.loads(
            (skill_dir / "assets/shot-template.jsonl").read_text(encoding="utf-8")
        )
        self.assertNotIn("scene_visual_plan_ref", shot)
        self.assertNotIn("revision_lineage", shot)
        lineage = json.loads(
            (skill_dir / "assets/revision-lineage.fragment.json").read_text(
                encoding="utf-8"
            )
        )["revision_lineage"]
        self.assertTrue(
            {"change", "predecessor_shot_ids", "retired_shot_ids", "reason"}
            <= set(lineage)
        )

        plan_reference = (skill_dir / "references/scene-visual-plan.md").read_text(
            encoding="utf-8"
        )
        audition_reference = (skill_dir / "references/coverage-audition.md").read_text(
            encoding="utf-8"
        )
        for phrase in ("不是第二份剧本", "不拥有镜头边界", "普通场景"):
            self.assertIn(phrase, plan_reference)
        for phrase in ("真正不同", "固定宫格", "创作者"):
            self.assertIn(phrase, audition_reference)
        for phrase in ("不把事后选择写回自身", "selected_approach_id", "hash 循环"):
            self.assertIn(phrase, audition_reference)

    def test_lookdev_projects_creator_direction_without_gaining_story_authority(self) -> None:
        core = SKILLS / "short-drama"
        image = SKILLS / "short-drama-image-prompts"
        self.assertIn(
            "references/look-development.md",
            (core / "SKILL.md").read_text(encoding="utf-8"),
        )
        lookdev = (core / "references/look-development.md").read_text(
            encoding="utf-8"
        )
        for phrase in ("人物表现测试帧", "核心地点测试帧", "高压力场景测试帧"):
            self.assertIn(phrase, lookdev)
        for protected in ("角色身份", "场景地理", "剧情状态"):
            self.assertIn(protected, lookdev)
        workflow = (core / "references/creator-workflow.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("A style-only test can begin", workflow)
        self.assertIn("Direction-only exploration remains a creator choice", workflow)

        base_spec = fenced_json(image / "assets/image-prompt-spec.jsonl.md")
        for lookdev_only in (
            "lookdev_axis",
            "direction_ref",
            "production_profile_ref",
            "lookdev_subject_bindings",
            "story_context_refs",
        ):
            self.assertNotIn(lookdev_only, base_spec)

        spec = fenced_json(image / "assets/lookdev-frame-spec.jsonl.md")
        self.assertEqual(spec["purpose"], "lookdev_frame")
        self.assertIn("lookdev_axis", spec)
        self.assertIn("production_profile_ref", spec)
        self.assertIn("story_context_refs", spec)
        self.assertIn("subject_bindings", spec)
        self.assertNotIn("asset_binding", spec)
        self.assertNotIn("lookdev_subject_bindings", spec)
        self.assertRegex(
            spec["story_context_refs"][0]["record_id"], r"^BLK-"
        )
        binding = spec["reference_bindings"][0]
        self.assertEqual({"slot_id", "order"} - set(binding), set())
        self.assertIn("项目开发/lookdev-image-prompt-specs.jsonl", (
            image / "SKILL.md"
        ).read_text(encoding="utf-8"))
        self.assertIn("assets/lookdev-prompts.md", (
            image / "SKILL.md"
        ).read_text(encoding="utf-8"))
        self.assertTrue((image / "assets/lookdev-prompts.md").is_file())
        self.assertIn(
            "| IMG-12 | reviewed_invariant |",
            (image / "references/stage-contract.md").read_text(encoding="utf-8"),
        )

        decision_records = [
            json.loads(line)
            for line in (core / "assets/creator-decision.example.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        audition_decision = next(
            row for row in decision_records if "selected_approach_id" in row
        )
        self.assertEqual(
            audition_decision["decision_kind"], "artifact_acceptance"
        )
        self.assertIn("selected_audition_record_id", audition_decision)

    def test_multi_actor_performance_is_optional_and_scene_plan_is_inherited_from_shot(self) -> None:
        video = SKILLS / "short-drama-video-prompts"
        motion = fenced_json(video / "assets/motion-spec.jsonl.md")
        self.assertNotIn("scene_visual_plan_ref", motion)
        self.assertNotIn("purpose_ref", motion)
        self.assertNotIn("coverage_scope", motion)
        self.assertNotIn("performance_arcs", motion)
        self.assertNotIn("attention_handoffs", motion)
        self.assertNotIn("text_readiness", motion)
        self.assertEqual(
            {"slot_id", "order"} - set(motion["reference_bindings"][0]), set()
        )

        performance = (video / "references/performance-action-timing.md").read_text(
            encoding="utf-8"
        )
        video_skill = (video / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("若本镜确有表演变化", video_skill)
        self.assertIn("存在表演变化时弧线可见", video_skill)
        self.assertNotIn("动作物理可行、表演弧可见", video_skill)
        for phrase in ("receive", "mask", "visible_leak", "attention_handoffs"):
            self.assertIn(phrase, performance)
        fragment = json.loads(
            (video / "assets/performance.fragment.json").read_text(encoding="utf-8")
        )
        actor_ref = fragment["performance_arcs"][0]["actor_ref"]
        self.assertTrue(
            {"owner", "artifact", "hash", "record_id"} <= set(actor_ref)
        )
        handoff = fragment["attention_handoffs"][0]
        self.assertTrue(
            {"from_ref", "trigger_ref", "to_ref", "signal", "readability"}
            <= set(handoff)
        )
        for endpoint in ("from_ref", "to_ref"):
            self.assertEqual(
                handoff[endpoint]["artifact"],
                "<exact-versioned-attention-owner-artifact>",
            )
            self.assertEqual(
                handoff[endpoint]["record_id"],
                "<exact-attention-owner-record-id>",
            )
        self.assertIn(
            "角色、道具、证据、声源或已建立的空间区域",
            performance,
        )
        self.assertIn(
            "| VID-17 | reviewed_invariant |",
            (video / "references/stage-contract.md").read_text(encoding="utf-8"),
        )

        write = SKILLS / "short-drama-write"
        self.assertIn(
            "references/scene-sound-dramaturgy.md",
            (write / "SKILL.md").read_text(encoding="utf-8"),
        )
        sound = (write / "references/scene-sound-dramaturgy.md").read_text(
            encoding="utf-8"
        )
        for phrase in ("主动留白", "sound bridge", "画外声", "不替代表演"):
            self.assertIn(phrase, sound)

    def test_production_observations_are_scoped_and_not_quality_inference(self) -> None:
        core = SKILLS / "short-drama"
        observation = json.loads(
            (core / "assets/production-observation.example.jsonl").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(observation["observation_kind"], "generated_result")
        input_observation = json.loads(
            (core / "assets/reference-observation.example.jsonl").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(input_observation["observation_kind"], "input_reference")
        self.assertNotIn("status", input_observation)
        self.assertEqual(input_observation["evidence_state"], "active")
        self.assertIn("prompt_or_spec_refs", observation)
        self.assertIn("production_configuration", observation)
        self.assertIn("valid_only_for", observation)
        self.assertIn("limitations", observation)
        self.assertNotIn("status", observation)
        self.assertEqual(observation["evidence_state"], "active")

        review = SKILLS / "short-drama-review"
        review_skill = (review / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("references/project-calibration.md", review_skill)
        calibration = (review / "references/project-calibration.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "input_reference",
            "generated_result",
            "每次只改变",
            "preserve_set",
            "项目内",
            "不声称看见",
        ):
            self.assertIn(phrase, calibration)

    def test_secondary_contracts_preserve_end_frame_and_shot_identity_semantics(self) -> None:
        media = (
            SKILLS / "short-drama/references/reference-media-and-pickups.md"
        ).read_text(encoding="utf-8")
        self.assertIn("默认 start", media)
        self.assertIn("boundary_role: end", media)
        self.assertIn("end_boundary", media)
        self.assertNotIn("当前套件只定义绑定 accepted shot start", media)

        identity = (
            SKILLS / "short-drama-storyboard/references/shot-revision-identity.md"
        ).read_text(encoding="utf-8")
        for phrase in ("重排", "插入", "拆分", "合并", "retire", "coverage"):
            self.assertIn(phrase, identity)


if __name__ == "__main__":
    unittest.main()

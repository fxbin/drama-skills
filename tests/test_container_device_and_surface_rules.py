import json
import re
import unittest
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]
SKILLS = SUITE / "skills"
INDEX = SKILLS / "short-drama/references/knowhow-index.md"

CONTAINER_TEMPLATE = (
    SKILLS / "short-drama-video-prompts/assets/delivery-container.jsonl.md"
)
MOTION_TEMPLATE = SKILLS / "short-drama-video-prompts/assets/motion-spec.jsonl.md"
PREMISE = SKILLS / "short-drama-develop/references/premise-devices.md"
BLOCKING = SKILLS / "short-drama-storyboard/references/blocking-playbooks.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def fenced_json(path: Path) -> dict:
    match = re.search(r"```json\n(\{.*?\})\n```", read(path), re.DOTALL)
    if match is None:
        raise AssertionError(f"missing fenced JSON template: {path}")
    return json.loads(match.group(1))


def index_rules() -> dict[str, str]:
    """Rules live in each skill's own stage contract, not in the core index."""

    pattern = re.compile(
        r"^\| ((?:STY|SCR|AST|IMG|SHT|VID|CON|REV)-\d{2}) \| ([a-z_]+) \|",
        re.MULTILINE,
    )
    rules: dict[str, str] = {}
    for path in sorted(SKILLS.glob("*/references/stage-contract.md")):
        rules.update(pattern.findall(read(path)))
    return rules


class NewRuleRegistrationTests(unittest.TestCase):
    def test_new_rules_are_registered_with_their_intended_class(self) -> None:
        rules = index_rules()
        expected = {
            "STY-16": "craft_default",
            "STY-17": "reviewed_invariant",
            "SCR-09": "craft_default",
            "IMG-10": "reviewed_invariant",
            "SHT-15": "reviewed_invariant",
            "VID-13": "structural_invariant",
            "VID-14": "craft_default",
            "SHT-16": "structural_invariant",
            "SHT-17": "structural_invariant",
            "VID-15": "structural_invariant",
            "VID-19": "reviewed_invariant",
            "VID-20": "reviewed_invariant",
            "REV-11": "reviewed_invariant",
        }
        for rule_id, classification in expected.items():
            with self.subTest(rule=rule_id):
                self.assertEqual(rules.get(rule_id), classification)

    def test_segment_sum_rule_names_the_shot_not_the_container(self) -> None:
        """VID-04 and VID-13 apply to different objects; the text must say which."""

        contract = SKILLS / "short-drama-video-prompts/references/stage-contract.md"
        self.assertIn("sums exactly to its shot's accepted duration", read(contract))


class DeliveryContainerRecordTests(unittest.TestCase):
    """VID-13 is structural, so a canonical record must carry resolvable evidence."""

    def shot_template(self) -> dict:
        return json.loads(
            (SKILLS / "short-drama-storyboard/assets/shot-template.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )

    def test_container_template_carries_members_durations_and_profile_ref(self) -> None:
        document = fenced_json(CONTAINER_TEMPLATE)
        self.assertEqual(document["status"], "candidate")
        for key in ("container_id", "members", "container_duration", "membership_basis"):
            with self.subTest(key=key):
                self.assertIn(key, document)
        member = document["members"][0]
        for key in (
            "order",
            "shot_ref",
            "motion_ref",
            "accepted_duration_ref",
            "location_binding_ref",
            "asset_bindings_ref",
        ):
            with self.subTest(member_key=key):
                self.assertIn(key, member)
        self.assertEqual(member["shot_ref"]["owner"], "short-drama-storyboard")
        self.assertEqual(member["motion_ref"]["owner"], "short-drama-video-prompts")

    def test_every_shot_field_pointer_resolves_on_the_shot_template(self) -> None:
        """A field pointer that names a non-existent key cannot be verified later."""

        shot = self.shot_template()
        member = fenced_json(CONTAINER_TEMPLATE)["members"][0]
        for key in ("accepted_duration_ref", "location_binding_ref", "asset_bindings_ref"):
            ref = member[key]
            with self.subTest(ref=key):
                self.assertEqual(ref["artifact"], "剧集/<EP>/storyboard/shots.jsonl")
                pointer = ref["field"]
                self.assertTrue(pointer.startswith("/"))
                self.assertIn(pointer.lstrip("/"), shot)

    def test_binding_chain_is_proved_per_member_not_from_one_record(self) -> None:
        basis = fenced_json(CONTAINER_TEMPLATE)["membership_basis"]
        self.assertIn("binding_chain_equal", basis)
        self.assertNotIn("binding_chain_ref", basis)
        self.assertIn("只引用其中一条成员记录不构成证明", read(CONTAINER_TEMPLATE))

    def test_container_and_motion_do_not_form_a_hash_cycle(self) -> None:
        """Two files that carry each other's hash can never both settle."""

        container = fenced_json(CONTAINER_TEMPLATE)
        motion = fenced_json(MOTION_TEMPLATE)

        def hashed_artifacts(value: object, found: set[str]) -> set[str]:
            if isinstance(value, dict):
                artifact, digest = value.get("artifact"), value.get("hash")
                if isinstance(artifact, str) and isinstance(digest, str):
                    found.add(artifact)
                for child in value.values():
                    hashed_artifacts(child, found)
            elif isinstance(value, list):
                for child in value:
                    hashed_artifacts(child, found)
            return found

        container_file = "剧集/<EP>/storyboard/delivery-containers.jsonl"
        motion_file = "剧集/<EP>/storyboard/motion-specs.jsonl"
        self.assertIn(motion_file, hashed_artifacts(container, set()))
        self.assertNotIn(container_file, hashed_artifacts(motion, set()))
        self.assertNotIn("container_ref", motion)
        self.assertIn("不带指回交付容器的引用", read(MOTION_TEMPLATE))

    def test_container_owner_is_registered_and_published(self) -> None:
        ownership = read(SKILLS / "short-drama/references/contract-and-ownership.md")
        self.assertIn("delivery-containers.jsonl", ownership)
        skill = read(SKILLS / "short-drama-video-prompts/SKILL.md")
        self.assertIn("delivery-containers.jsonl", skill)


class PremiseDeviceLayerTests(unittest.TestCase):
    """STY-17 must not collapse creator contract into in-fiction disclosure."""

    def test_contract_and_disclosure_are_named_as_separate_layers(self) -> None:
        text = read(PREMISE)
        self.assertIn("装置契约（创作者层）", text)
        self.assertIn("披露状态（剧中层）", text)

    def test_partial_disclosure_is_explicitly_not_a_defect(self) -> None:
        self.assertIn("本身从不构成缺陷", read(PREMISE))
        rubric = read(SKILLS / "short-drama-review/references/rubric-story-script.md")
        self.assertIn("Never report partial disclosure as a defect", rubric)

    def test_unreliable_declarations_remain_a_legitimate_design(self) -> None:
        self.assertIn("不可靠", read(PREMISE))

    def test_blocking_condition_is_untraceable_widening(self) -> None:
        self.assertIn("追溯不到即为", read(PREMISE))

    def test_story_engine_carries_an_addressable_device_contract(self) -> None:
        engine = read(SKILLS / "short-drama-develop/assets/story-engine.md")
        self.assertIn("前提装置契约", engine)
        for field in ("条款 ID", "能力范围", "失效条件", "使用代价", "可靠性"):
            with self.subTest(field=field):
                self.assertIn(field, engine)
        self.assertRegex(engine, r"DEV-0\d")
        self.assertIn("事后再回填条款", engine)

    def test_episode_map_records_which_clauses_are_disclosed(self) -> None:
        episode = json.loads(
            (SKILLS / "short-drama-develop/assets/episode-map.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )
        disclosure = episode["premise_device_disclosure"]
        for key in (
            "clause_ids_disclosed_so_far",
            "clause_ids_newly_disclosed",
            "who_knows",
            "misstated",
        ):
            with self.subTest(key=key):
                self.assertIn(key, disclosure)


class DeliverySurfaceTests(unittest.TestCase):
    """SHT-15 must stay inactive rather than fall back to a guessed safe frame."""

    def test_undeclared_surface_leaves_the_rule_inactive(self) -> None:
        text = read(BLOCKING)
        self.assertIn("没有声明就没有这条约束", text)
        self.assertIn("不因为猜测的区域改变构图", text)

    def test_no_default_occupied_region_is_assumed(self) -> None:
        text = read(BLOCKING)
        self.assertNotIn("上下两端与一侧边缘可能被占用", text)

    def test_declaration_is_owned_by_the_creator_production_authority(self) -> None:
        project = json.loads(
            (SKILLS / "short-drama/assets/project-template/short-drama.json")
            .read_text(encoding="utf-8")
        )
        surface = project["creator_authority"]["delivery_surface"]
        self.assertEqual(surface["status"], "unset")
        for key in ("aspect", "overlay_regions", "source_ref"):
            with self.subTest(key=key):
                self.assertIn(key, surface)

    def test_shot_and_keyframe_bind_the_declared_surface_version(self) -> None:
        for name in ("shot-template.jsonl", "keyframe-template.jsonl"):
            document = json.loads(
                (SKILLS / f"short-drama-storyboard/assets/{name}")
                .read_text(encoding="utf-8")
                .strip()
            )
            with self.subTest(template=name):
                ref = document["delivery_surface_ref"]
                self.assertEqual(ref["owner"], "short-drama")
                self.assertEqual(ref["artifact"], "short-drama.json")
                self.assertEqual(ref["field"], "/creator_authority/delivery_surface")
                self.assertIn("hash", ref)


class TextOnlyReviewBoundaryTests(unittest.TestCase):
    """VID-14 review wording cannot require inspecting rendered media."""

    def test_music_gate_stops_at_prompt_text_or_authorized_observation(self) -> None:
        gates = read(
            SKILLS / "short-drama-review/references/production-quality-gates.md"
        )
        self.assertIn("不能由本环节判断", gates)
        self.assertIn("unverified", gates)
        rubric = read(SKILLS / "short-drama-review/references/rubric-visual-motion.md")
        self.assertIn("not decidable here", rubric)


class DialogueSplitExampleTests(unittest.TestCase):
    """SCR-09's repaired example must not smuggle the action back into a parenthetical."""

    def test_repaired_example_keeps_visible_action_on_its_own_line(self) -> None:
        text = read(SKILLS / "short-drama-write/references/dialogue-craft.md")
        blocks = re.findall(r"```text\n(.*?)\n```", text, re.DOTALL)
        repaired = [b for b in blocks if b.count("▲") == 1 and "【角色甲】" in b]
        self.assertTrue(repaired, "no repaired dialogue-split example found")
        for block in repaired:
            for line in block.splitlines():
                if line.startswith("▲"):
                    continue
                parenthetical = re.search(r"\(([^)]*)\)", line)
                if parenthetical is None:
                    continue
                for verb in ("摆手", "抬手", "转头", "翻", "递", "推开", "指"):
                    with self.subTest(verb=verb):
                        self.assertNotIn(verb, parenthetical.group(1))


class EpisodeDurationArithmeticTests(unittest.TestCase):
    COVERAGE = SKILLS / "short-drama-storyboard/assets/coverage-template.json"
    PROJECT = SKILLS / "short-drama/assets/project-template/short-drama.json"
    SHOT = SKILLS / "short-drama-storyboard/assets/shot-template.jsonl"

    def coverage(self) -> dict:
        return json.loads(read(self.COVERAGE))

    def test_coverage_carries_a_total_and_an_explicit_unresolved_list(self) -> None:
        """A shot with no duration yet must be visible as suspended, because a
        silently dropped shot and a settled episode look identical otherwise."""

        duration = self.coverage()["episode_duration"]
        for key in (
            "shot_seconds_total",
            "counted_shot_ids",
            "unresolved_durations",
            "target_seconds",
            "delta_seconds",
            "disposition",
        ):
            with self.subTest(key=key):
                self.assertIn(key, duration)

    def test_the_summed_field_is_the_one_shots_actually_carry(self) -> None:
        shot = json.loads(read(self.SHOT).splitlines()[0])
        self.assertIn("duration_seconds", shot)

    def test_the_target_pointer_resolves_inside_the_project_template(self) -> None:
        """A target field that names a non-existent key can never be compared."""

        ref = self.coverage()["episode_duration"]["target_ref"]
        self.assertEqual(ref["owner"], "short-drama")
        self.assertEqual(ref["artifact"], "short-drama.json")
        document = json.loads(read(self.PROJECT))
        for token in ref["field"].lstrip("/").split("/"):
            self.assertIsInstance(document, dict)
            self.assertIn(token, document)
            document = document[token]

    def test_the_delta_is_reported_and_never_blocks_on_its_own(self) -> None:
        grammar = read(
            SKILLS / "short-drama-storyboard/references/production-shot-grammar.md"
        )
        self.assertIn("不阻断交付", grammar)
        rubric = read(
            SKILLS / "short-drama-review/references/production-quality-gates.md"
        )
        self.assertIn("差值本身不写成阻断项", rubric)

    def test_first_episode_gets_a_measurement_even_without_a_baseline(self) -> None:
        """STY-16 skips episode one for lack of a ratio; the arithmetic must not."""

        design = read(SKILLS / "short-drama-develop/references/episode-design.md")
        self.assertIn("跳过估算不等于第一集没有时长兜底", design)

    def test_container_accounting_is_stated_at_episode_scope(self) -> None:
        profile = read(
            SKILLS / "short-drama-video-prompts/references/delivery-profile.md"
        )
        self.assertIn("VID-15", profile)
        self.assertIn("不重不漏", profile)


class ExecutionRouteAndTriggerTokenTests(unittest.TestCase):
    """Routes decide where a generation starts; tokens decide whether it routes."""

    PROFILE = SKILLS / "short-drama-video-prompts/references/delivery-profile.md"
    CONTRACT = SKILLS / "short-drama-video-prompts/references/stage-contract.md"
    GRAMMAR = (
        SKILLS / "short-drama-video-prompts/references/production-prompt-grammar.md"
    )

    @staticmethod
    def table_rows(text: str, header_cell: str) -> list[list[str]]:
        """Body rows of the first markdown table whose header names `header_cell`."""

        rows: list[list[str]] = []
        collecting = False
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|"):
                if collecting:
                    break
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not collecting:
                collecting = header_cell in cells
                continue
            if set("".join(cells)) <= set("-: "):
                continue
            rows.append(cells)
        return rows

    def test_exactly_one_route_starts_from_a_generated_result(self) -> None:
        """The evidence obligation attaches to that route and no other. Asserting
        the shape of the table survives rewording; asserting its prose does not."""

        rows = self.table_rows(read(self.PROFILE), "路由")
        self.assertEqual(len(rows), 4, [r[0] for r in rows])
        from_result = [r for r in rows if "已生成" in r[1] or "结果" in r[1]]
        self.assertEqual(len(from_result), 1, [r[1] for r in rows])
        self.assertIn("续接", from_result[0][0])

    def test_long_form_generation_is_billed_under_the_container_rules(self) -> None:
        """Otherwise it is a documented way around two structural invariants:
        VID-13's scene-boundary constraint and VID-15's episode accounting."""

        vid20 = next(
            line for line in read(self.CONTRACT).splitlines()
            if line.startswith("| VID-20 |")
        )
        self.assertIn("VID-13", vid20)
        self.assertIn("VID-15", vid20)
        self.assertRegex(vid20, r"long-form generation.*\bis\b.*container")

    def test_continuation_start_is_evidence_not_an_accepted_artifact(self) -> None:
        """A generated result has no authority, so it cannot become a boundary."""

        vid20 = next(
            line for line in read(self.CONTRACT).splitlines()
            if line.startswith("| VID-20 |")
        )
        self.assertIn("not an accepted artifact", vid20)
        self.assertIn("`unverified`", vid20)

    def test_trigger_tokens_are_a_sibling_of_the_dialogue_fence(self) -> None:
        """Both are 'text that must survive rewriting', so they belong under one
        heading; splitting them apart is what let tokens go unmodelled before."""

        headings = [
            line.strip() for line in read(self.PROFILE).splitlines()
            if line.startswith(("## ", "### "))
        ]
        fence = next(i for i, h in enumerate(headings) if "逐字对白围栏" in h)
        token = next(i for i, h in enumerate(headings) if "执行触发词" in h)
        self.assertTrue(headings[fence].startswith("### "))
        self.assertTrue(headings[token].startswith("### "))
        parent = max(
            i for i, h in enumerate(headings[:fence]) if h.startswith("## ")
        )
        self.assertFalse(
            any(h.startswith("## ") for h in headings[parent + 1 : token]),
            "the token subsection drifted out from under the dialogue-fence H2",
        )

    def test_the_suite_invents_no_token_of_its_own(self) -> None:
        """Tokens are surface facts; inventing one prints words on screen."""

        vid19 = next(
            line for line in read(self.CONTRACT).splitlines()
            if line.startswith("| VID-19 |")
        )
        self.assertIn("invents none", vid19)

    def test_capability_has_three_bands_not_two(self) -> None:
        """Supported/unsupported hides the band that is legal but retry-hungry."""

        rows = self.table_rows(read(self.GRAMMAR), "区域")
        self.assertEqual(len(rows), 3, [r[0] for r in rows])
        self.assertTrue(any("不稳定" in r[0] for r in rows), [r[0] for r in rows])

    def test_no_conservative_number_is_invented_from_a_range(self) -> None:
        grammar = read(self.GRAMMAR).replace("\n", "")
        self.assertIn("不自行推断一个更保守的数字当成事实", grammar)

    def test_execution_side_outcomes_are_not_asserted_as_fact(self) -> None:
        """The suite calls no generation service, so it cannot know what a given
        surface does. Rules may say what to preserve, never what will happen."""

        for path in (self.PROFILE, self.CONTRACT, self.GRAMMAR):
            text = read(path).replace("\n", "")
            with self.subTest(reference=path.name):
                self.assertNotIn("静默退回默认路径", text)
                self.assertNotIn("因为它不报错", text)


class CalibrationDispositionTests(unittest.TestCase):
    """Diagnosis names the defect; disposition decides who should pay to fix it."""

    CALIBRATION = SKILLS / "short-drama-review/references/project-calibration.md"
    CONTRACT = SKILLS / "short-drama-review/references/stage-contract.md"

    def test_all_five_dispositions_are_offered(self) -> None:
        calibration = read(self.CALIBRATION)
        for disposition in ("保留", "后期处理", "局部编辑", "重新提交", "改写"):
            with self.subTest(disposition=disposition):
                self.assertIn(f"| {disposition} |", calibration)

    def test_the_finding_record_can_actually_carry_a_disposition(self) -> None:
        """REV-11 is unenforceable if the canonical record has no slot for it."""

        finding = json.loads(
            read(SKILLS / "short-drama-review/assets/finding-template.jsonl").strip()
        )
        self.assertIn("disposition", finding)
        self.assertIn("disposition_rationale", finding)
        offered = {v.strip() for v in finding["disposition"].split("|")}
        self.assertEqual(
            offered,
            {"keep", "post_production", "targeted_edit", "resubmit", "rewrite",
             "not_applicable"},
        )
        keys = list(finding)
        self.assertLess(
            keys.index("disposition"),
            keys.index("required_change"),
            "disposition must precede revision text (REV-11)",
        )

    def test_disposition_precedes_revision_text(self) -> None:
        """Skipping it silently assumes every defect is the prompt's fault."""

        calibration = read(self.CALIBRATION)
        self.assertLess(
            calibration.index("## 诊断之后先定处置，再谈修订"),
            calibration.index("## 单变量有界修订"),
        )
        self.assertIn(
            "before any revision text", read(self.CONTRACT).replace("\n", " ")
        )

    def test_resubmission_and_adjectives_are_not_repairs(self) -> None:
        """Both change the bill without changing an executable fact."""

        calibration = read(self.CALIBRATION).replace("\n", "")
        self.assertIn("不要用增加形容词的方式回应重复缺陷", calibration)
        self.assertIn("是在为同一个错误反复付费，而每次都不产生新信息", calibration)

        contract = read(self.CONTRACT).replace("\n", " ")
        self.assertIn("are not repairs", contract)

    def test_post_production_is_a_first_class_outcome(self) -> None:
        """Defects outside text should not be answered by editing the prompt."""

        calibration = read(self.CALIBRATION).replace("\n", "")
        self.assertIn("缺陷是否落在文字能控制的范围内", calibration)
        self.assertIn("改提示词只会引入新变量", calibration)

    def test_pickup_bookkeeping_starts_only_after_a_disposition(self) -> None:
        calibration = read(self.CALIBRATION).replace("\n", "")
        self.assertIn("只有选择了局部编辑或改写", calibration)


class EndKeyframeContractTests(unittest.TestCase):
    KEYFRAME = SKILLS / "short-drama-storyboard/assets/keyframe-template.jsonl"
    SHOT = SKILLS / "short-drama-storyboard/assets/shot-template.jsonl"
    CRAFT = SKILLS / "short-drama-storyboard/references/keyframe-craft.md"

    def keyframe(self) -> dict:
        return json.loads(read(self.KEYFRAME).splitlines()[0])

    def test_a_keyframe_states_which_boundary_it_freezes(self) -> None:
        record = self.keyframe()
        self.assertIn("boundary_role", record)
        self.assertEqual(set(record["boundary_role"].split(" | ")), {"start", "end"})

    def test_both_boundary_fields_exist_on_the_shot_it_points_at(self) -> None:
        """An end frame is useless if the field it projects does not exist."""

        shot = json.loads(read(self.SHOT).splitlines()[0])
        pointers = self.keyframe()["boundary_ref"]["field"].split(" | ")
        self.assertEqual(len(pointers), 2)
        for pointer in pointers:
            with self.subTest(pointer=pointer):
                self.assertIn(pointer.lstrip("/"), shot)

    def test_the_end_frame_is_a_projection_not_a_second_authority(self) -> None:
        # Prose wraps, so compare against the unwrapped text rather than making
        # the sentence fit one source line.
        craft = read(self.CRAFT).replace("\n", "")
        self.assertIn("不是新的终点事实", craft)
        self.assertIn("尾帧与镜头终点不一致时，错的是尾帧", craft)

    def test_the_interpolation_cost_is_stated_on_both_sides(self) -> None:
        """Handing over two ends silently delegates the motion between them, so
        the stage that owns motion must be told, not only the one that draws."""

        self.assertIn("插值", read(self.CRAFT))
        motion = read(
            SKILLS / "short-drama-video-prompts/references/camera-audio-continuity.md"
        )
        self.assertIn("不对照尾帧", motion)

    def test_keyframe_count_is_not_turned_into_a_quota(self) -> None:
        rubric = read(
            SKILLS / "short-drama-review/references/production-quality-gates.md"
        )
        self.assertIn("关键帧数量不是检查项", rubric)


class SelfContainedReferenceTests(unittest.TestCase):
    """References added by this work must not reach into a sibling skill's tree."""

    def test_new_references_carry_no_cross_skill_links(self) -> None:
        for path in (PREMISE, CONTAINER_TEMPLATE):
            with self.subTest(path=path.name):
                self.assertNotIn("../../", read(path))


if __name__ == "__main__":
    unittest.main()

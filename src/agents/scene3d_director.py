"""Free-tier visual director.

Splits the approved script into beats (deterministically, so narration alignment stays exact), asks the
LLM to design a 3D scene for each beat using the renderer's documented vocabulary, then validates the
plan by dry-running it in the real renderer and asking the LLM to repair anything that fails.
"""
import json
import os
import re
from typing import Any, Dict, List, Optional

from src.models.schemas import ReelGenerationTier, ReelScript, SceneBeat, Storyboard
from src.models.scene3d import ReelVisualPlan
from src.services.config_loader import load_json, load_looks, load_text
from src.services.image_resolver import resolve_images
from src.services.llm_factory import LLMFactory
from src.engines.render.tier_free.studio3d_engine import Studio3DEngine


class Scene3DPlanError(RuntimeError):
    pass


class Scene3DDirector:
    @staticmethod
    def split_beats(script: ReelScript) -> List[Dict[str, Any]]:
        """Group sentences into beats sized by config/pacing.json. Never rewrites the narration."""
        pace = load_json("pacing.json")
        wps = pace["words_per_second"]
        lo, target, hi = (pace["beat_seconds"][k] * wps for k in ("min", "target", "max"))
        beats: List[Dict[str, Any]] = []
        cur: List[str] = []; cur_act = 1; cur_title = ""

        def flush():
            nonlocal cur
            if cur:
                beats.append({"text": " ".join(cur), "act": cur_act, "act_title": cur_title})
                cur = []

        for act in script.acts:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", act.spoken_text.strip()) if s.strip()]
            for sent in sentences:
                words = len(sent.split())
                have = sum(len(c.split()) for c in cur)
                if cur and have >= lo and (have + words > hi or have >= target):
                    flush()
                if not cur:
                    cur_act, cur_title = act.act_number, act.title
                if words > hi:  # very long sentence: split on clause boundaries
                    for part in re.split(r"(?<=[,;:])\s+", sent):
                        if cur and sum(len(c.split()) for c in cur) + len(part.split()) > hi:
                            flush(); cur_act, cur_title = act.act_number, act.title
                        cur.append(part)
                else:
                    cur.append(sent)
            if sum(len(c.split()) for c in cur) >= lo:
                flush()
        flush()
        # Merge a too-short trailing beat into its predecessor
        if len(beats) > 1 and len(beats[-1]["text"].split()) < lo and len(beats[-2]["text"].split()) + len(beats[-1]["text"].split()) <= hi * 1.3:
            tail = beats.pop(); beats[-1]["text"] += " " + tail["text"]
        for i, b in enumerate(beats, 1):
            b["beat"] = i
            b["seconds"] = round(len(b["text"].split()) / wps, 1)
        return beats

    @classmethod
    def _system_prompt(cls, pack_name: Optional[str] = None) -> str:
        from src.services.concept_router import get_pack, pack_prompt
        pack = get_pack(pack_name)
        pack_text = pack_prompt(pack_name)
        if pack.get("layout_hint") or pack.get("look_hint"):
            pack_text += f"\nSuggested layout: {pack.get('layout_hint')}; suggested look: {pack.get('look_hint')}. Change them only when the topic clearly needs another."
        if "{{CHEM_RECIPES}}" in pack_text:   # worked particle_lab setups (config/chem_recipes.json)
            recipes = load_json("chem_recipes.json")
            pack_text = pack_text.replace("{{CHEM_RECIPES}}", "\n".join(f"- {n}: {r['about']} Hint: {r['hint']}\n  params = {json.dumps(r['params'], separators=(',', ':'))}" for n, r in recipes.items()))
        looks = load_looks()
        look_lines = "\n".join(f"- {n}: {l['description']} Materials: {', '.join(l['materials'])}. Palette names: {', '.join(l['palette'])}." for n, l in looks.items())
        import glob, os
        from src.services.config_loader import CONFIG_DIR
        examples = []
        for path in sorted(glob.glob(os.path.join(CONFIG_DIR, "prompts", "scene3d_example*.json"))):
            examples.append(f"Example {len(examples) + 1}:\n" + open(path, encoding="utf-8").read())
        pack_example = os.path.join(CONFIG_DIR, "prompts", "packs", "examples", f"{pack_name}.json") if pack_name else ""
        if pack_example and os.path.exists(pack_example):
            examples.append(f"Example {len(examples) + 1} (a {pack['label']} reel; follow its style closely):\n" + open(pack_example, encoding="utf-8").read())
        example = "\n\n".join(examples)
        return (
            load_text("prompts", "scene3d_director.md")
            .replace("{{PACK}}", pack_text)
            .replace("{{PACK_LABEL}}", pack["label"])
            .replace("{{VOCABULARY}}", json.dumps(load_json("scene_vocabulary.json"), indent=1))
            .replace("{{PROPS}}", cls._prop_library())
            .replace("{{LAYOUTS}}", cls._layouts_text(bool((pack.get("persona") or {}).get("status") == "ready")))
            .replace("{{SIM_RECIPES}}", cls._sim_recipes())
            .replace("{{LOOKS}}", look_lines)
            .replace("{{EXAMPLES}}", example)
        )

    @classmethod
    def _layouts_text(cls, narrator: bool = False) -> str:
        """Layout manual with the real visible-frame geometry of each layout's 3D window."""
        import glob, math, os
        from src.services.config_loader import CONFIG_DIR
        lines = []
        for path in sorted(glob.glob(os.path.join(CONFIG_DIR, "layouts", "*.json"))):
            lay = load_json("layouts", os.path.basename(path))
            w = lay["window"]; aspect = w["width"] / w["height"]
            k = 2 * math.tan(math.radians(20))  # visible height per unit distance at fov 40
            lines.append(
                f"- {lay['name']}: {lay['description']} The 3D window is {w['width']}x{w['height']} px (width/height = {aspect:.2f}). "
                f"At fov 40 and camera distance d the window shows {k * aspect:.2f}*d units wide by {k:.2f}*d tall. "
                f"{'Cards and tags are placed inside the window. ' if lay['name'] != 'full' else ''}"
                f"{(lay['header'].get('hint') or 'Provide `header`: 1 to 2 short lines of at most 3 words each (the second line is highlighted).') if lay.get('header') else 'No header.'}"
                f"{cls._narrator_note(lay, w) if narrator and lay.get('narrator') else ''}"
            )
        return "\n".join(lines)

    @staticmethod
    def _narrator_note(lay: Dict[str, Any], w: Dict[str, Any]) -> str:
        """A narrator character occupies a lower corner of the 3D window in this reel: tell the director how much to keep free."""
        slot = lay["narrator"]; width = min(0.5, slot["heightFrac"] * w["height"] / 1.25 / w["width"] + slot["marginFrac"])
        height = max(0.1, slot["heightFrac"] + slot["bottomFrac"])
        return (f" A narrator character stands in the lower {slot['side']} corner of the window, about {round(width * 100)}% of its width and "
                f"{round(height * 100)}% of its height. Keep the hero subject, formulas' targets and tags out of that corner.")

    @staticmethod
    def _sim_recipes() -> str:
        """Motion-simulator recipes (config/sim_recipes.json): worked `sim` blocks the director can adapt."""
        recipes = load_json("sim_recipes.json")
        return "\n".join(f"- {name}: {r['about']} Hint: {r['hint']}\n  sim = {json.dumps(r['sim'], separators=(',', ':'))}" for name, r in recipes.items())

    @staticmethod
    def _prop_library() -> str:
        """Prefab and pose manual, generated from config/props/*.json and config/poses.json."""
        import glob, math, os
        from src.services.config_loader import CONFIG_DIR
        lines = []
        for path in sorted(glob.glob(os.path.join(CONFIG_DIR, "props", "*.json"))):
            name = os.path.basename(path)[:-5]
            pf = load_json("props", os.path.basename(path))
            docs = "; ".join(f"{k}: {v}" for k, v in pf.get("params_doc", {}).items())
            framing = ""
            if pf.get("bounds"):
                bw, bh = pf["bounds"]["size"]; cx, cy = pf["bounds"]["center"]
                k = 2 * math.tan(math.radians(20))
                rec = ", ".join(
                    f"{lay['name']}: distance >= {max(bh / k, bw / (k * lay['window']['width'] / lay['window']['height'])) * 1.15:.1f}"
                    for lay in (load_json("layouts", os.path.basename(lp)) for lp in sorted(glob.glob(os.path.join(CONFIG_DIR, "layouts", "*.json"))))
                )
                framing = f" Extent about {bw} x {bh} units centred at ({cx}, {cy}) relative to its origin; to show it whole at fov 40 keep the camera at {rec} (camera target near its centre)."
            lines.append(f"- {name}: {pf['about']} Params: {docs}{framing}")
        poses = ", ".join(load_json("poses.json").keys())
        return "\n".join(lines) + f"\nHumanoid poses: {poses}. A pose is animated automatically; combine it with `position` expressions to make the person walk across the scene."

    @staticmethod
    def _user_prompt(script: ReelScript, subject: str, class_level: Optional[int], exam_type: str, beats: List[Dict[str, Any]]) -> str:
        lines = "\n".join(f"Beat {b['beat']} | act {b['act']} ({b['act_title']}) | ~{b['seconds']}s | \"{b['text']}\"" for b in beats)
        total = sum(b["seconds"] for b in beats)
        return (
            f"Topic: {script.topic_title}\nSubject: {subject} | Class: {class_level or 'general'} | Exam: {exam_type}\n"
            f"Hook: {script.hook}\nKey takeaway: {script.key_takeaway}\nTotal narration: about {total:.0f} seconds in {len(beats)} beats.\n\n"
            f"Design one 3D scene per beat:\n{lines}"
        )

    # ---------- validation helpers ----------
    SOFT_MARKERS = ("the subject fills only", "behind the narrator's portrait", "should be a plain number or expression, not a list", "Unknown material preset", "Unknown pose", "pop word", "cropped by the edge", "card", "sits on a bright area", "washed out", "overlap each other", "tiny on screen")

    @staticmethod
    def _norm(msg: str) -> str:
        return re.sub(r"\d+%", "N%", msg)

    @classmethod
    def _lint_beats(cls, designs: Dict[int, Dict[str, Any]], beats: List[Dict[str, Any]], look: str, layout: str, header: Optional[List[str]]) -> Dict[int, List[str]]:
        """Runs the real renderer over the designs; returns problems grouped by beat (0 = not attributable)."""
        t = 0.0; scenes = []; lines = []
        for b in beats:
            d = dict(designs[b["beat"]]); d.update({"id": f"beat_{b['beat']}", "start": t, "end": t + b["seconds"]}); lines.append((b.get("text", ""), t, t + b["seconds"])); t += b["seconds"]
            scenes.append(d)
        spec = {"version": 1, "look": look, "layout": layout, "header": header or [], "duration": t, "scenes": scenes, "captions": Studio3DEngine.estimate_captions(lines)}
        out: Dict[int, List[str]] = {}
        try:
            problems = Studio3DEngine.lint(spec)
        except Exception as e:
            problems = [f"renderer lint could not run: {e}"]
        for msg in problems:
            m = re.search(r"\(beat (\d+)\)", msg)
            beat = int(m.group(1)) if m else 0
            key = cls._norm(msg)
            if key not in [cls._norm(x) for x in out.get(beat, [])]:
                out.setdefault(beat, []).append(msg)
        return out

    LAB_FIXED = ("a", "b", "c", "d", "nA", "nB", "nC", "nD", "cA", "cB", "cC", "cD", "lA", "lB", "lC", "lD", "rA", "rB", "rC", "rD", "maxN", "rc", "h0")

    @classmethod
    def _unify_labs(cls, designs: Dict[int, Dict[str, Any]]) -> None:
        """The same particle_lab across scenes is one experiment: reaction, reference counts, colours and legend are fixed by
        its first appearance; scenes may only change what is being done to it (vol, dA..dD, Kt, spd, gauge)."""
        first: Dict[str, Dict[str, Any]] = {}
        for beat in sorted(designs):
            for o in designs[beat].get("objects", []):
                if o.get("prefab") != "particle_lab":
                    continue
                params = o.setdefault("params", {})
                ref = first.setdefault(o.get("id") or "lab", {k: params[k] for k in cls.LAB_FIXED if k in params})
                for k in cls.LAB_FIXED:
                    if k in ref:
                        params[k] = ref[k]
                    else:
                        params.pop(k, None)

    @classmethod
    def _is_soft(cls, msg: str) -> bool:
        return any(k in msg for k in cls.SOFT_MARKERS)

    @classmethod
    def _redesign_beats(
        cls, topic_title: str, jobs: List[Dict[str, Any]], look: str, layout: str, header: Optional[List[str]],
        tier: ReelGenerationTier, provider: str, pack: Optional[str] = None,
    ) -> Dict[int, Dict[str, Any]]:
        """ONE LLM call that re-designs several beats. jobs: [{beat: {beat, text, seconds}, current, instruction}]."""
        blocks = "\n\n".join(
            f"Beat {j['beat']['beat']} | ~{j['beat']['seconds']}s | \"{j['beat']['text']}\"\nWhat must change: {j['instruction']}\nThe current design:\n{json.dumps(j['current'])}"
            for j in jobs
        )
        user = (
            f"Topic: {topic_title}\nUse the look \"{look}\" and the layout \"{layout}\"" + (f" with header {header}" if header else "") + ".\n\n"
            f"Re-design ONLY these {len(jobs)} beat(s). Return `scenes` with exactly one entry per listed beat, and repeat look, layout and header unchanged.\n\n{blocks}"
        )
        plan = LLMFactory.generate_json(system_prompt=cls._system_prompt(pack), user_prompt=user, response_model=ReelVisualPlan, tier=tier, provider=provider, profile="director")
        got = {sc.beat: sc.model_dump(exclude_none=True) for sc in plan.scenes}
        missing = [j["beat"]["beat"] for j in jobs if j["beat"]["beat"] not in got]
        if missing:
            raise Scene3DPlanError(f"re-design returned no scene for beats {missing}")
        return {j["beat"]["beat"]: got[j["beat"]["beat"]] for j in jobs}

    @classmethod
    def _redesign_beat(
        cls, topic_title: str, beat: Dict[str, Any], current: Dict[str, Any], look: str, layout: str, header: Optional[List[str]],
        instruction: str, tier: ReelGenerationTier, provider: str, pack: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Single-beat wrapper (Gate 1 re-roll)."""
        return cls._redesign_beats(topic_title, [{"beat": beat, "current": current, "instruction": instruction}], look, layout, header, tier, provider, pack)[beat["beat"]]

    @classmethod
    def direct_storyboard(
        cls,
        script: ReelScript,
        subject: str,
        class_level: Optional[int],
        exam_type: str,
        assets_dir: str,
        tier: ReelGenerationTier = ReelGenerationTier.FREE,
        provider: str = "AUTO",
        route: Optional[Dict[str, Any]] = None,
    ) -> Storyboard:
        if route is None:
            from src.services.concept_router import route as route_topic
            route = route_topic(subject, script.topic_title, tier=tier, provider=provider)
        beats = cls.split_beats(script)
        if not beats:
            raise Scene3DPlanError("Script has no narration to visualise.")
        system = cls._system_prompt(route["pack"])
        user = cls._user_prompt(script, subject, class_level, exam_type, beats)
        plan = LLMFactory.generate_json(system_prompt=system, user_prompt=user, response_model=ReelVisualPlan, tier=tier, provider=provider, profile="director")

        # Whole-plan structure check (look exists, every beat covered once); one whole-plan repair if it fails
        looks = load_looks(); want = [b["beat"] for b in beats]
        physics = bool(route.get("requires_sim"))
        physics_prefabs = {"pulley_fixed", "pulley_compound", "graph", "pulley_wheel"}
        def structure(p: ReelVisualPlan) -> List[str]:
            out = []
            if p.look not in looks:
                out.append(f"Unknown look '{p.look}'. Available: {', '.join(looks)}")
            if sorted(s.beat for s in p.scenes) != want:
                out.append(f"scenes must cover beats {want} exactly once each; got {sorted(s.beat for s in p.scenes)}")
            if physics and not any(("sim" in (sc.model_extra or {})) or any(getattr(o, "model_extra", {}).get("prefab") in physics_prefabs for o in sc.objects) for sc in p.scenes):
                out.append("This is a physics reel but no scene uses the motion simulator (`sim`), a mechanism prefab or the graph prefab. Show motion, forces, energy and fields with the simulator and graphs (see the physics section and recipes) instead of decorative shapes, and fill `physics_plan` first.")
            return out
        qa_pre: List[str] = []
        problems = structure(plan)
        if problems:
            repair = user + "\n\nYour previous plan had these problems. Return the corrected full plan.\n- " + "\n- ".join(problems) + "\n\nPrevious plan:\n" + plan.model_dump_json()
            plan = LLMFactory.generate_json(system_prompt=system, user_prompt=repair, response_model=ReelVisualPlan, tier=tier, provider=provider, profile="director")
            problems = structure(plan)
            soft = [m for m in problems if m.startswith("This is a physics reel")]
            problems = [m for m in problems if m not in soft]
            if problems:
                raise Scene3DPlanError("3D scene plan failed validation:\n- " + "\n- ".join(problems))
            if soft:
                qa_pre.append("physics reel without the motion simulator after one repair: " + soft[0][:120])

        designs = {s.beat: s.model_dump(exclude_none=True) for s in plan.scenes}
        cls._unify_labs(designs)
        qa_notes: List[str] = list(qa_pre)
        # Per-beat renderer checks, one auto-retry per failing beat
        report = cls._lint_beats(designs, beats, plan.look, plan.layout, plan.header)
        retries = int(load_json("qa.json").get("max_retries_per_beat", 1))
        for attempt in range(retries):
            failing = sorted(b for b in report if b != 0)
            if not failing:
                break
            jobs = [{"beat": next(x for x in beats if x["beat"] == b), "current": designs[b],
                     "instruction": "Fix these problems found by the renderer: " + "; ".join(report[b])} for b in failing]
            designs.update(cls._redesign_beats(script.topic_title, jobs, plan.look, plan.layout, plan.header, tier, provider, route["pack"]))
            cls._unify_labs(designs)
            report = cls._lint_beats(designs, beats, plan.look, plan.layout, plan.header)
        hard = [m for b, msgs in report.items() for m in msgs if not cls._is_soft(m)]
        if hard:
            try:   # keep the failing plan for diagnosis
                os.makedirs(os.path.join(os.path.dirname(assets_dir), "debug"), exist_ok=True)
                with open(os.path.join(os.path.dirname(assets_dir), "debug", "failed_plan.json"), "w", encoding="utf-8") as f:
                    json.dump({"look": plan.look, "layout": plan.layout, "header": plan.header, "designs": designs, "problems": hard}, f, indent=1)
            except Exception:
                pass
            raise Scene3DPlanError("3D scene plan failed validation:\n- " + "\n- ".join(hard[:15]))
        qa_notes += [m for msgs in report.values() for m in msgs]

        t = 0.0; scenes: List[SceneBeat] = []
        for b in beats:
            direction = designs[b["beat"]]
            scenes.append(SceneBeat(
                scene_number=b["beat"], act_number=b["act"], start_sec=t, end_sec=t + b["seconds"],
                spoken_line=b["text"], visual_prompt=direction.get("intent") or b["text"],
                style_bible=plan.look, scene3d=direction,
            ))
            t += b["seconds"]
        resolve_problems = []
        for sc in scenes:
            resolve_problems += resolve_images(sc.scene3d["objects"], assets_dir, narration=sc.spoken_line)
        if resolve_problems:
            print("⚠️ Image resolution:", "; ".join(resolve_problems))
            qa_notes += resolve_problems
        return Storyboard(topic_title=script.topic_title, total_scenes=len(scenes), style_bible=plan.look, layout=plan.layout,
                          header=plan.header, qa=qa_notes or None, route=route, scenes=scenes)

    @classmethod
    def vision_review(
        cls,
        storyboard: Storyboard,
        assets_dir: str,
        frames_dir: str,
        tier: ReelGenerationTier = ReelGenerationTier.FREE,
        provider: str = "AUTO",
        judge=None,
    ) -> List[str]:
        """Renders one frame per beat, has a vision model score ALL frames in one request, re-designs low-scoring beats
        in one request, re-judges only those in one request. Leaves the preview frames in frames_dir (scene_NN.png)
        and returns the findings that remain after the single retry.
        """
        qa = load_json("qa.json")
        if judge is None:
            from src.services.frame_qa import judge_frames as judge
        note = load_json("layouts", f"{storyboard.layout or 'full'}.json").get("qa_note", "")
        remaining: List[str] = []
        look, layout, header = storyboard.style_bible, storyboard.layout or "full", storyboard.header

        def render(scenes: List[SceneBeat]) -> Dict[int, str]:
            sb = storyboard.model_copy(update={"scenes": scenes})
            spec = Studio3DEngine.build_spec(sb, look=look)
            mids = [sc.start_sec + 0.55 * (sc.end_sec - sc.start_sec) for sc in scenes]
            stills = Studio3DEngine.render_stills(spec, mids, frames_dir, assets_dir=assets_dir)
            out = {}
            for sc, st in zip(scenes, stills):
                target = os.path.join(frames_dir, f"scene_{sc.scene_number:02d}.png")
                os.replace(st, target); out[sc.scene_number] = target
            return out

        def items(scenes: List[SceneBeat], paths: Dict[int, str]) -> List[Dict[str, Any]]:
            return [{"beat": sc.scene_number, "path": paths[sc.scene_number], "narration": sc.spoken_line,
                     "intent": (sc.scene3d or {}).get("intent", "")} for sc in scenes]

        paths = render(storyboard.scenes)
        try:
            verdicts = judge(items(storyboard.scenes, paths), note)
        except Exception as e:
            for sc in storyboard.scenes:
                sc.image_path = paths[sc.scene_number]
            return [f"vision QA unavailable ({e})"]
        weak = [sc for sc in storyboard.scenes if verdicts[sc.scene_number]["score"] < qa["pass_score"]]
        if weak and qa.get("max_retries_per_beat", 1) > 0:
            beats_by_no = {sc.scene_number: {"beat": sc.scene_number, "text": sc.spoken_line, "seconds": round(max(2.0, sc.end_sec - sc.start_sec), 1)} for sc in weak}
            jobs = [{"beat": beats_by_no[sc.scene_number], "current": sc.scene3d,
                     "instruction": f"A reviewer scored this frame {verdicts[sc.scene_number]['score']}/10. Fix: " + "; ".join(verdicts[sc.scene_number]["issues"])} for sc in weak]
            try:
                new = cls._redesign_beats(storyboard.topic_title, jobs, look, layout, header, tier, provider, (storyboard.route or {}).get("pack"))
                all_designs = {s.scene_number: s.scene3d for s in storyboard.scenes}; all_designs.update(new)
                lint = cls._lint_beats(all_designs, [{"beat": s.scene_number, "text": s.spoken_line, "seconds": round(s.end_sec - s.start_sec, 1)} for s in storyboard.scenes], look, layout, header)
                changed = []
                for sc in weak:
                    if any(not cls._is_soft(m) for m in lint.get(sc.scene_number, [])):
                        remaining.append(f"beat {sc.scene_number}: retry rejected (renderer errors), kept original; issues: {'; '.join(verdicts[sc.scene_number]['issues'])}")
                        continue
                    resolve_images(new[sc.scene_number]["objects"], assets_dir, narration=sc.spoken_line)
                    idx = storyboard.scenes.index(sc)
                    storyboard.scenes[idx] = sc.model_copy(update={"scene3d": new[sc.scene_number]})
                    changed.append(storyboard.scenes[idx])
                if changed:
                    paths.update(render(changed))
                    again = judge(items(changed, paths), note)
                    for sc in changed:
                        v2, v1 = again[sc.scene_number], verdicts[sc.scene_number]
                        if v2["score"] < qa["pass_score"]:
                            remaining.append(f"beat {sc.scene_number}: still {v2['score']}/10 after one retry: {'; '.join(v2['issues'])}")
                        elif v2["score"] < v1["score"]:
                            remaining.append(f"beat {sc.scene_number}: retry scored lower ({v2['score']} vs {v1['score']})")
            except Exception as e:
                remaining.append(f"retry failed ({e}); weak beats: {[sc.scene_number for sc in weak]}")
        for sc in storyboard.scenes:
            sc.image_path = paths[sc.scene_number]
        return remaining

    @classmethod
    def redesign_scene(
        cls,
        topic_title: str,
        scene: SceneBeat,
        instruction: str,
        look: str,
        assets_dir: str,
        tier: ReelGenerationTier = ReelGenerationTier.FREE,
        provider: str = "AUTO",
        layout: str = "full",
        header: Optional[List[str]] = None,
        pack: Optional[str] = None,
    ) -> SceneBeat:
        """Re-designs one scene from a creator's instruction (Gate 1 re-roll). Narration and timing stay fixed."""
        beat = {"beat": scene.scene_number, "text": scene.spoken_line, "seconds": round(max(2.0, scene.end_sec - scene.start_sec), 1)}
        design = cls._redesign_beat(topic_title, beat, scene.scene3d, look, layout, header, instruction, tier, provider, pack)
        lint = cls._lint_beats({scene.scene_number: design}, [beat], look, layout, header)
        hard = [m for msgs in lint.values() for m in msgs if not cls._is_soft(m)]
        if hard:
            raise Scene3DPlanError("Re-designed scene failed validation:\n- " + "\n- ".join(hard[:10]))
        resolve_images(design["objects"], assets_dir, narration=scene.spoken_line)
        return scene.model_copy(update={"scene3d": design, "visual_prompt": instruction})

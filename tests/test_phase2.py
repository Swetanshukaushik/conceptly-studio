import os
import sys
import json

sys.path.insert(0, os.path.abspath("."))

def test_phase2_intelligence():
    print("🧠 Running Phase 2 Multi-Agent Intelligence & HITL Gating Tests...")

    # 1. Test Curriculum Resolver
    from src.services.curriculum_resolver import curriculum_resolver
    resolved_seed = curriculum_resolver.resolve_topic(
        topic_title="Newton's Third Law",
        exam_type="SCHOOL",
        class_level=9,
        subject="Physics"
    )
    assert resolved_seed["topic_id"] == "topic-phys-9-newton-3"
    assert resolved_seed["is_resolved"] is True
    print(f"  [1/6] Curriculum Resolver (Seed Match): {resolved_seed['canonical_title']} -> ID: {resolved_seed['topic_id']}")

    resolved_custom = curriculum_resolver.resolve_topic(
        topic_title="Quantum Tunneling in Semiconductor Diodes",
        exam_type="IIT_JEE",
        class_level=12,
        subject="Physics"
    )
    assert resolved_custom["topic_id"] is not None
    assert resolved_custom["is_resolved"] is False
    print(f"  [2/6] Curriculum Resolver (Custom Deterministic UUID): ID: {resolved_custom['topic_id']}")

    # 2. Test CurriculumAgent
    from src.agents.curriculum_agent import CurriculumAgent
    from src.models.schemas import ReelGenerationTier
    concept = CurriculumAgent.extract_concept(
        topic_title="Newton's Third Law",
        exam_type="SCHOOL",
        class_level=9,
        subject="Physics",
        tier=ReelGenerationTier.DEFAULT
    )
    assert len(concept.target_misconception) > 10
    assert len(concept.counter_intuitive_hook) > 10
    assert len(concept.single_takeaway) > 10
    print(f"  [3/6] CurriculumAgent extraction verified: Hook: '{concept.counter_intuitive_hook[:50]}...'")

    # 3. Test ScriptAgent & FactCheckAgent
    from src.agents.script_agent import ScriptAgent
    from src.agents.factcheck_agent import FactCheckAgent
    script = ScriptAgent.generate_script(concept=concept, tier=ReelGenerationTier.DEFAULT)
    assert len(script.acts) == 4
    assert script.acts[0].act_number == 1
    assert script.acts[3].act_number == 4
    
    is_valid, report, cleaned_script = FactCheckAgent.verify_and_clean_script(script)
    assert is_valid is True, f"FactCheck failed: {report}"
    assert 90 <= cleaned_script.total_word_count <= 145
    print(f"  [4/6] ScriptAgent & FactCheck verified: {cleaned_script.total_word_count} spoken words across 4 acts. ({report})")

    # 4. Test QuizAgent
    from src.agents.quiz_agent import QuizAgent
    quiz = QuizAgent.generate_quiz(
        script=cleaned_script,
        topic_id=resolved_seed["topic_id"],
        tier=ReelGenerationTier.DEFAULT
    )
    assert len(quiz.questions) >= 2
    for q in quiz.questions:
        assert len(q.options) == 4
        assert q.correctOptionId in ["a", "b", "c", "d"]
        assert len(q.explanation) > 10
    print(f"  [5/6] QuizAgent verified: Generated {len(quiz.questions)} MCQs matching CONTRACT.md schema.")

    # 5. Test Full Orchestrator State Machine (Stage 1 -> Gate 1 -> Stage 2 -> Gate 2)
    from src.database.session import SessionLocal, Base, engine
    from src.models.entities import ReelJob, User
    from src.models.schemas import JobStatus
    from src.pipeline.orchestrator import PipelineOrchestrator

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    admin_user = db.query(User).first()
    
    test_job = ReelJob(
        user_id=admin_user.id if admin_user else None,
        generation_tier="DEFAULT",
        exam_type="SCHOOL",
        class_level=9,
        subject="Physics",
        topic_title="Newton's Third Law: The Wall Dilemma",
        status=JobStatus.PENDING.value
    )
    db.add(test_job)
    db.commit()
    db.refresh(test_job)

    # Initialize stages
    initial_stages = ["CURRICULUM_DISCOVERY", "CONCEPT_EXTRACTION", "SCRIPTWRITING", "GATE_1_REVIEW", "QUIZ_GENERATION", "GATE_2_REVIEW"]
    for s_name in initial_stages:
        from src.models.entities import JobStage
        db.add(JobStage(job_id=test_job.id, stage_name=s_name, status="PENDING"))
    db.commit()

    # Run Stage 1 (Automated)
    PipelineOrchestrator.run_stage1_blueprint(test_job.id)
    db.refresh(test_job)
    assert test_job.status == JobStatus.GATE_1_READY.value
    assert test_job.script_data is not None
    saved_script = json.loads(test_job.script_data)
    assert len(saved_script["acts"]) == 4

    # Creator approves Gate 1 (triggers Stage 2)
    PipelineOrchestrator.run_stage2_quiz(test_job.id)
    db.refresh(test_job)
    assert test_job.status == JobStatus.GATE_2_READY.value
    assert test_job.quiz_data is not None
    saved_quiz = json.loads(test_job.quiz_data)
    assert len(saved_quiz["questions"]) >= 2
    
    print(f"  [6/6] Pipeline Orchestrator State Machine verified:")
    print(f"       • Job transitioned to GATE_1_READY with 4-act script")
    print(f"       • Creator approved Gate 1 -> Job transitioned to GATE_2_READY with {len(saved_quiz['questions'])} MCQs")
    
    db.close()
    print("\n🎉 Phase 2 Dual-Tier Intelligence & State Machine Tests PASSED 100%!")

if __name__ == "__main__":
    test_phase2_intelligence()

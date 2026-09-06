"""Sanity tests for the new pyq_explanations schema (src/schema/models.py) — proves the
discriminated union actually enforces the right shape per format, not just that valid input
passes (same standard Phase 0 already held MCQQuestion/DescriptiveQuestion to)."""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pydantic import ValidationError

from src.schema.models import PYQExplanation, StandaloneExplanation, StatementBasedExplanation


def test_standalone_explanation_valid():
    detail = StandaloneExplanation(
        options=[
            {"option_label": "A", "option_text": "Life", "is_correct": True, "rationale": "Article 21 explicitly protects this."},
            {"option_label": "B", "option_text": "Property", "is_correct": False, "rationale": "Removed as a fundamental right by the 44th Amendment."},
        ]
    )
    assert detail.option_format == "standalone"
    assert len(detail.options) == 2


def test_statement_based_explanation_valid():
    detail = StatementBasedExplanation(
        statements=[
            {"statement_number": 1, "statement_text": "The Speaker is elected by Lok Sabha members.", "is_correct": True, "rationale": "Correct per Article 93."},
            {"statement_number": 2, "statement_text": "The Rajya Sabha cannot be dissolved.", "is_correct": True, "rationale": "Correct — it's a permanent house."},
        ],
        combination_rationale="Both statements are correct, so the answer is 'Only two'.",
    )
    assert detail.option_format == "statement_based"
    assert len(detail.statements) == 2


def test_standalone_missing_rationale_rejected():
    try:
        StandaloneExplanation(options=[{"option_label": "A", "option_text": "Life", "is_correct": True}])
        assert False, "should have raised — rationale is required"
    except ValidationError:
        pass


def test_statement_based_missing_combination_rationale_rejected():
    try:
        StatementBasedExplanation(
            statements=[{"statement_number": 1, "statement_text": "x", "is_correct": True, "rationale": "y"}]
        )
        assert False, "should have raised — combination_rationale is required"
    except ValidationError:
        pass


def test_full_pyq_explanation_standalone():
    explanation = PYQExplanation(
        question_id="upsc_cse_paper_1_1_pyq",
        concept_summary="Article 21 covers the right to life and personal liberty.",
        detail={
            "option_format": "standalone",
            "options": [
                {"option_label": "A", "option_text": "Life", "is_correct": True, "rationale": "Directly protected."},
                {"option_label": "B", "option_text": "Property", "is_correct": False, "rationale": "Not a fundamental right since the 44th Amendment."},
            ],
        },
        elimination_strategy="Property can be eliminated immediately — it's a well-known post-1978 removal from Part III.",
        grounding_chunk_ids=["upsc_cse_constitution_1_0"],
        model_version="claude-haiku-4-5-20251001",
        generated_at=datetime(2026, 9, 6),
    )
    assert explanation.detail.option_format == "standalone"
    assert explanation.elimination_strategy is not None


def test_full_pyq_explanation_statement_based():
    explanation = PYQExplanation(
        question_id="upsc_cse_paper_1_2_pyq",
        concept_summary="Tests knowledge of parliamentary procedure.",
        detail={
            "option_format": "statement_based",
            "statements": [
                {"statement_number": 1, "statement_text": "x", "is_correct": True, "rationale": "y"},
                {"statement_number": 2, "statement_text": "x2", "is_correct": False, "rationale": "y2"},
            ],
            "combination_rationale": "Only statement 1 is correct, so the answer is 'Only one'.",
        },
        model_version="claude-haiku-4-5-20251001",
        generated_at=datetime(2026, 9, 6),
    )
    assert explanation.detail.option_format == "statement_based"
    assert explanation.detail.statements[0].is_correct is True


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS: {name}")

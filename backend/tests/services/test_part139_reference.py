"""The Part 139 title table and its presence in every system prompt."""

from app.services.prompts import (
    GENERAL_PROMPT,
    PHL_PROMPT,
    RISK_REGISTER_PROMPT,
    SRA_PROMPT,
    SYSTEM_ANALYSIS_PROMPT,
)
from app.utils.part139 import PART_139_SECTIONS, render_part139_reference


def test_the_two_sections_the_model_confused_are_distinct() -> None:
    assert PART_139_SECTIONS["139.329"] == "Pedestrians and ground vehicles"
    assert PART_139_SECTIONS["139.323"] == "Traffic and wind direction indicators"


def test_subpart_d_is_complete() -> None:
    operations = [s for s in PART_139_SECTIONS if 300 < int(s.split(".")[1]) < 400]

    assert operations == [f"139.{n}" for n in range(301, 345, 2)]


def test_every_prompt_carries_the_reference_block() -> None:
    reference = render_part139_reference()

    assert "PART 139 CITATION REFERENCE" in reference
    assert "§139.329 Pedestrians and ground vehicles" in reference
    for prompt in (
        GENERAL_PROMPT,
        PHL_PROMPT,
        SRA_PROMPT,
        SYSTEM_ANALYSIS_PROMPT,
        RISK_REGISTER_PROMPT,
    ):
        assert reference in prompt

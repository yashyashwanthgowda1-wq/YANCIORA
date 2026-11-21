"""The evaluation's synthetic noise must be lossless: the noisy prompt has exactly the clean
prompt's words plus the repeated instruction (research/scripts/run_optimizer_eval.py)."""
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "research" / "scripts"
if not (SCRIPTS / "run_optimizer_eval.py").exists():
    pytest.skip("research scripts not present", allow_module_level=True)
sys.path.insert(0, str(SCRIPTS))
import run_optimizer_eval as E  # noqa: E402

from app.services.meaning import word_content  # noqa: E402

SAMPLES = ["Do not send the report before 5 pm.", "ವರದಿಯನ್ನು 5 ಗಂಟೆಗೆ ಮೊದಲು ಕಳುಹಿಸಬೇಡಿ.",
           "रिपोर्ट 5 बजे से पहले मत भेजो।", "one", "a b c d e f g"]


@pytest.mark.parametrize("text", SAMPLES)
def test_noise_is_lossless_and_deterministic(text):
    clean, noisy = E.prompt_clean(text), E.prompt_noisy(text)
    assert E.prompt_noisy(text) == noisy                                   # deterministic
    assert word_content(noisy) == word_content(clean) + word_content(E.INSTRUCTION)
    assert noisy.count("​") == 1 and noisy.count(E.INSTRUCTION) == 2 and "----------" in noisy
    assert E.detail_counts(noisy, "en") >= E.detail_counts(clean, "en")

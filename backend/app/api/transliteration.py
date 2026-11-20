from fastapi import APIRouter

from app.api.errors import ApiException
from app.schemas import ScriptVariantsRequest, ScriptVariantsResponse
from app.services import transliteration
from app.tokenizers import TokenizerUnavailable, available_tokenizers

router = APIRouter(prefix="/api", tags=["script"])


@router.post("/script-variants", response_model=ScriptVariantsResponse)
def script_variants(req: ScriptVariantsRequest) -> ScriptVariantsResponse:
    """Native ↔ Romanized script variants with token counts (translit_v1).

    Variants are never applied (`requires_review` is always true). Romanized → native needs a
    named `source_scheme`; `casual` returns status `unsupported`. Token counts are tokenizer
    counts, not provider billing, and say nothing about model understanding."""
    unknown = [n for n in req.tokenizers if n not in available_tokenizers()]
    if unknown:
        raise ApiException(400, "unknown_tokenizer",
                           f"Unknown tokenizer '{unknown[0]}'. Available: "
                           f"{', '.join(available_tokenizers())}.")
    try:
        return transliteration.script_variants(req)
    except transliteration.TransliterationUnavailable as exc:
        raise ApiException(503, "transliteration_unavailable", str(exc))
    except TokenizerUnavailable as exc:
        raise ApiException(503, "tokenizer_unavailable", str(exc))

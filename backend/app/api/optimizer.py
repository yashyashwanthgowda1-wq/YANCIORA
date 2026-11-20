from fastapi import APIRouter

from app.api.errors import ApiException
from app.schemas import OptimizeRequest, OptimizeResponse
from app.services import optimizer
from app.tokenizers import TokenizerUnavailable, UnknownTokenizer, available_tokenizers

router = APIRouter(prefix="/api", tags=["optimizer"])


@router.post("/optimize", response_model=OptimizeResponse)
def optimize(req: OptimizeRequest) -> OptimizeResponse:
    """Shorten a prompt with deterministic rules (opt_rules_v1).

    `accepted` edits are applied (meaning check `preserved`, fewer tokens, no tokenizer worse).
    `suggestions` are NOT applied and need the user's review (meaning check `at_risk`,
    duplicate sentences, script changes). `rejected` lists every other proposed edit with its
    reason. Savings are tokenizer counts, not provider billing."""
    unknown = [n for n in req.tokenizers if n not in available_tokenizers()]
    if unknown:
        raise ApiException(400, "unknown_tokenizer",
                           f"Unknown tokenizer '{unknown[0]}'. Available: "
                           f"{', '.join(available_tokenizers())}.")
    try:
        return optimizer.optimize(req)
    except UnknownTokenizer as exc:
        raise ApiException(400, "unknown_tokenizer", f"Unknown tokenizer '{exc.args[0]}'.")
    except TokenizerUnavailable as exc:
        raise ApiException(503, "tokenizer_unavailable", str(exc))

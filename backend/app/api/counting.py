from fastapi import APIRouter

from app.api.errors import ApiException
from app.schemas import CompareRequest, CompareResponse, TokenizeRequest, TokenizeResponse
from app.services import counting
from app.tokenizers import TokenizerUnavailable, UnknownTokenizer, available_tokenizers

router = APIRouter(prefix="/api", tags=["tokens"])


def _run(fn, req):
    try:
        return fn(req)
    except UnknownTokenizer:
        raise ApiException(
            400, "unknown_tokenizer",
            f"Unknown tokenizer '{req.tokenizer}'. Available: {', '.join(available_tokenizers())}.",
        )
    except TokenizerUnavailable as exc:
        raise ApiException(503, "tokenizer_unavailable", str(exc))
    except ValueError as exc:
        raise ApiException(422, "invalid_request", str(exc))


@router.get("/tokenizers")
def list_tokenizers() -> dict:
    return {"tokenizers": available_tokenizers()}


@router.post("/tokenize", response_model=TokenizeResponse)
def tokenize(req: TokenizeRequest) -> TokenizeResponse:
    return _run(counting.tokenize, req)


@router.post("/compare-languages", response_model=CompareResponse)
def compare_languages(req: CompareRequest) -> CompareResponse:
    return _run(counting.compare, req)

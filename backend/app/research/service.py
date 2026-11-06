import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlparse
from uuid import uuid4
import httpx
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.ai.errors import GenerationError
from app.core.config import Settings
from app.db.models import AutomatedReview
from app.schemas.chat import ReviewRequest, Plan, Source, ResearchJudgment
from app.research.providers import groq_json
from app.research.prompts import PLAN_SYSTEM, JUDGE_SYSTEM

WEIGHTS = {
    "authority": 30,
    "jurisdiction": 20,
    "interpretation": 25,
    "completeness": 15,
    "clarity": 10,
}
FOCUS = {
    "authority": "Existence, validity and actual support of cited statutes/cases.",
    "jurisdiction": "Controlling jurisdiction, applicability and effective law date.",
    "reasoning": "Application to facts, completeness, exceptions and legal conclusion.",
}
VERSION = "research-v4-portable-evidence"


def weighted_score(criteria: dict) -> int:
    total = (
        sum(Decimal(criteria[key]["score"]) * weight for key, weight in WEIGHTS.items())
        / 100
    )
    return int(total.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def aggregate(reports: list[dict]) -> dict:
    eligible = (
        len(reports) == 3
        and {r.get("id") for r in reports} == set(FOCUS)
        and all(
            r.get("status") == "complete"
            and type(r.get("score")) is int
            and 0 <= r["score"] <= 100
            for r in reports
        )
    )
    overall = (
        int(
            (sum(Decimal(r["score"]) for r in reports) / 3).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        if eligible
        else None
    )
    return {
        "overall_score": overall,
        "threshold": 80,
        "recommend_lawyer": None if overall is None else overall < 80,
        "lawyer_available": True,
        "expert_verified": False,
    }


def _public_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme in ("https", "http")
        and bool(parsed.hostname)
        and not parsed.username
    )


def search_evidence(
    settings: Settings, queries: list[str], prefix: str
) -> tuple[list[dict], list[str]]:
    if not settings.tavily_api_key.strip():
        raise GenerationError(
            "configuration", "Set TAVILY_API_KEY in backend/.env and restart.", 503
        )
    found = {}
    warnings = []
    try:
        with httpx.Client(timeout=45) as client:
            for query in queries:
                if not query.strip() or len(query) > 400:
                    raise GenerationError(
                        "invalid_output",
                        "Reviewer produced an invalid public search query.",
                    )
                response = client.post(
                    "https://api.tavily.com/search",
                    headers={"Authorization": f"Bearer {settings.tavily_api_key}"},
                    json={
                        "query": query,
                        "search_depth": "basic",
                        "max_results": settings.review_sources_per_query,
                        "include_raw_content": True,
                        "include_answer": False,
                        "auto_parameters": False,
                    },
                )
                if response.status_code == 429:
                    raise GenerationError(
                        "rate_limited",
                        "Tavily search quota/rate limit reached. Wait or check your free quota.",
                        429,
                    )
                if response.status_code in (401, 403, 432):
                    raise GenerationError(
                        "authentication",
                        "Tavily rejected the key or available credits. Check your free plan.",
                        503,
                    )
                response.raise_for_status()
                for item in response.json().get("results", []):
                    url = item.get("url", "")
                    if _public_url(url) and url not in found:
                        raw = item.get("raw_content") or ""
                        found[url] = {
                            "title": item.get("title") or url,
                            "url": url,
                            "text": raw or item.get("content") or "",
                            "evidence_type": (
                                "extracted_page" if raw else "search_excerpt"
                            ),
                            "published_date": item.get("published_date"),
                        }
            # One bounded extract request for sources where search returned snippets only.
            missing = [
                url
                for url, s in found.items()
                if s["evidence_type"] == "search_excerpt"
            ][: settings.review_sources_per_query]
            if missing:
                result = client.post(
                    "https://api.tavily.com/extract",
                    headers={"Authorization": f"Bearer {settings.tavily_api_key}"},
                    json={
                        "urls": missing,
                        "extract_depth": "basic",
                        "include_images": False,
                    },
                )
                if result.is_success:
                    for item in result.json().get("results", []):
                        url = item.get("url", "")
                        if url in found and item.get("raw_content"):
                            found[url]["text"] = item["raw_content"]
                            found[url]["evidence_type"] = "extracted_page"
                else:
                    warnings.append(
                        "Some page extraction failed; search snippets are marked and are not full legal text."
                    )
        now = datetime.now(timezone.utc).isoformat()
        sources = []
        for i, item in enumerate(found.values(), 1):
            if not isinstance(item["text"], str) or not item["text"].strip():
                continue
            text = item.pop("text")
            source = Source(
                id=f"{prefix}{i}",
                **item,
                text=text[: settings.review_source_chars],
                retrieved_at=now,
                truncated=len(text) > settings.review_source_chars,
            )
            sources.append(source.model_dump())
        return sources, warnings
    except GenerationError:
        raise
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise GenerationError(
            "search_unavailable",
            "Online research failed. Check Tavily key, free quota and connectivity; no legal score was substituted.",
            503,
        ) from None


def validate_evidence(judgment: ResearchJudgment, sources: list[dict]) -> None:
    by_id = {s["id"]: s for s in sources}
    quoted = 0
    normalize = lambda s: re.sub(r"\s+", " ", s).strip()
    for check in judgment.claim_checks:
        if check.verdict != "unresolved" and not check.evidence:
            raise GenerationError(
                "invalid_evidence",
                "A reviewer conclusion had no source quotation; no score was accepted.",
            )
        for evidence in check.evidence:
            source = by_id.get(evidence.source_id)
            if (
                not source
                or not normalize(evidence.quote)
                or normalize(evidence.quote) not in normalize(source["text"])
            ):
                raise GenerationError(
                    "invalid_evidence",
                    "A reviewer cited an unknown source or quotation not found in retrieved text. No score was accepted.",
                )
            quoted += 1
    if not judgment.abstain and (
        not quoted or not any(s["evidence_type"] == "extracted_page" for s in sources)
    ):
        raise GenerationError(
            "insufficient_evidence",
            "Scoring requires quoted evidence and at least one extracted page, not only snippets.",
        )
    if any(
        not dim["reason"].strip() for dim in judgment.criteria.model_dump().values()
    ):
        raise GenerationError(
            "invalid_output", "Reviewer did not explain all five criterion scores."
        )


def evidence_catalog(sources: list[dict]) -> dict:
    catalog = {}
    for source in sources:
        parts = re.split(r"(?<=[.;!?])\s+|\n+", source["text"])
        ranked = sorted(
            (part for part in parts if len(part.strip()) >= 25),
            key=lambda part: sum(
                word in part.lower()
                for word in (
                    "shall",
                    "must",
                    "may",
                    "unless",
                    "except",
                    "section",
                    "statute",
                    "court",
                    "rule",
                )
            ),
            reverse=True,
        )
        quotes = list(dict.fromkeys(part[:240] for part in ranked[:3])) or [
            source["text"][:240]
        ]
        for i, quote in enumerate(quotes, 1):
            catalog[f"{source['id']}-E{i}"] = {
                "source_id": source["id"],
                "quote": quote,
            }
    return catalog


def constrained_report_schema(sources: list[dict]) -> dict:
    schema = ResearchJudgment.model_json_schema()
    schema["$defs"]["Evidence"] = {
        "type": "object",
        "properties": {
            "evidence_id": {"type": "string", "enum": list(evidence_catalog(sources))}
        },
        "required": ["evidence_id"],
        "additionalProperties": False,
    }
    return schema


def attach_exact_evidence(result: dict, sources: list[dict]) -> dict:
    catalog = evidence_catalog(sources)
    for claim in result.get("claim_checks", []):
        for i, evidence in enumerate(claim.get("evidence", [])):
            if "evidence_id" in evidence:
                if evidence["evidence_id"] not in catalog:
                    raise GenerationError(
                        "invalid_evidence",
                        "Reviewer selected an unknown evidence reference; no score accepted.",
                    )
                claim["evidence"][i] = dict(catalog[evidence["evidence_id"]])
    return result


def model_for(settings: Settings, reviewer: str) -> str:
    models = {
        "authority": settings.review_model_authority,
        "jurisdiction": settings.review_model_jurisdiction,
        "reasoning": settings.review_model_reasoning,
    }
    if len(set(models.values())) != 3:
        raise GenerationError(
            "configuration", "Configure three distinct REVIEW_MODEL IDs.", 503
        )
    return models[reviewer]


def review(
    settings: Settings,
    db: Session,
    request: ReviewRequest,
    public: dict,
    provenance: str,
) -> dict:
    model = model_for(settings, request.reviewer)
    digest = hashlib.sha256(
        json.dumps(
            {
                "data": public,
                "generation": str(request.generation_id),
                "reviewer": request.reviewer,
                "mode": settings.review_mode,
                "model": model,
                "version": VERSION,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    if not request.force and settings.review_cache_seconds:
        threshold = datetime.now(timezone.utc) - timedelta(
            seconds=settings.review_cache_seconds
        )
        cached = db.scalar(
            select(AutomatedReview)
            .where(
                AutomatedReview.request_hash == digest,
                AutomatedReview.created_at >= threshold,
            )
            .order_by(AutomatedReview.created_at.desc())
            .limit(1)
        )
        if cached is not None:
            return {**cached.report, "cached": True}
    if settings.review_mode == "mock":
        n = {"authority": 58, "jurisdiction": 72, "reasoning": 64}[request.reviewer]
        report = ResearchJudgment.model_validate(
            {
                "criteria": {
                    k: {
                        "score": n,
                        "reason": "Offline fixture; no real model or web research was used.",
                    }
                    for k in WEIGHTS
                },
                "research_summary": "MOCK assessment for interface and integration testing only.",
                "jurisdiction_analysis": "No jurisdiction verified in mock mode.",
                "date_analysis": "No law date verified in mock mode.",
                "claim_checks": [
                    {
                        "claim": public["answer"][:300],
                        "verdict": "unresolved",
                        "explanation": "Mock fixture, not a real legal finding.",
                        "evidence": [],
                    }
                ],
                "limitations": ["No real research was performed."],
                "suggested_correction": "Obtain live evidence and independent legal review.",
                "conclusion": "Illustrative score only.",
                "abstain": False,
                "abstention_reason": "",
            }
        )
        queries = []
        sources = []
        warnings = []
    else:
        plan_data = groq_json(
            settings,
            model,
            PLAN_SYSTEM,
            {
                k: v
                for k, v in {
                    **public,
                    "reviewer_focus": FOCUS[request.reviewer],
                }.items()
                if k != "conversation_context"
            },
        )
        try:
            # Accept harmless planner representation differences; never invent queries.
            def strings(value, key):
                if isinstance(value, str):
                    value = [value]
                if not isinstance(value, list):
                    return []
                output = []
                for item in value:
                    if isinstance(item, dict):
                        item = item.get(key) or item.get("text")
                    if isinstance(item, str) and item.strip():
                        output.append(item.strip())
                return list(dict.fromkeys(output))

            plan_data = {
                "queries": strings(plan_data.get("queries"), "query")[:2],
                "claims_to_check": strings(plan_data.get("claims_to_check"), "claim")[
                    :8
                ],
            }
            plan = Plan.model_validate(plan_data)
        except ValidationError as error:
            fields = ", ".join(
                ".".join(map(str, e["loc"]))
                for e in error.errors(include_input=False)[:5]
            )
            raise GenerationError(
                "invalid_output",
                f"Research plan still had missing/invalid fields: {fields}; types: {', '.join(e['type'] for e in error.errors(include_input=False)[:5])}. No search query or score was invented.",
            ) from None
        queries = plan.queries[: settings.review_search_queries]
        sources, warnings = search_evidence(
            settings, queries, request.reviewer[0].upper()
        )
        if not sources:
            raise GenerationError(
                "insufficient_evidence",
                "Search found no usable sources. No score was generated; try a more specific legal question.",
                422,
            )
        payload = {
            **public,
            "reviewer_focus": FOCUS[request.reviewer],
            "claims_to_check": plan.claims_to_check,
            "sources": sources,
            "output_schema": constrained_report_schema(sources),
            "evidence_catalog": evidence_catalog(sources),
        }
        result = groq_json(
            settings,
            model,
            JUDGE_SYSTEM
            + "\nIn each claim evidence list, return only {evidence_id: ID} using an exact ID from evidence_catalog. Do not generate or rewrite quotations. The server attaches the original quote and source ID. All other fields must match the schema.",
            payload,
        )
        result = attach_exact_evidence(result, sources)
        try:
            report = ResearchJudgment.model_validate(result)
        except ValidationError as error:
            fields = ", ".join(
                ".".join(map(str, e["loc"]))
                for e in error.errors(include_input=False)[:5]
            )
            raise GenerationError(
                "invalid_output",
                f"Assessment schema mismatch at: {fields}. No score accepted.",
            ) from None
        validate_evidence(report, sources)
    criteria = report.criteria.model_dump()
    points = None if report.abstain else weighted_score(criteria)
    report_id = uuid4()
    response = {
        "id": request.reviewer,
        "reportId": str(report_id),
        "model": model,
        "mode": settings.review_mode,
        "status": "abstained" if report.abstain else "complete",
        "score": points,
        "explanation": report.conclusion,
        "findings": [c.explanation for c in report.claim_checks],
        "sources": sources,
        "research": report.model_dump(),
        "queries": queries,
        "weights": WEIGHTS,
        "formula": "round-half-up((30*authority + 20*jurisdiction + 25*interpretation + 15*completeness + 10*clarity)/100)",
        "researchWarnings": warnings,
        "provenance": provenance,
        "generationId": str(request.generation_id) if request.generation_id else None,
        "answerHash": hashlib.sha256(public["answer"].encode()).hexdigest(),
        "cached": False,
        "expertVerified": False,
        "promptVersion": VERSION,
    }
    db.add(
        AutomatedReview(
            id=report_id,
            generation_id=request.generation_id,
            request_hash=digest,
            report=response,
        )
    )
    db.commit()
    return response

"""
Keyword Engine for ATS v2
-------------------------

Responsibilities:
- Extract candidate keywords/phrases from a Job Description (JD) and classify them into tiers:
  required, preferred, bonus.
- Match these keywords against a resume text using fuzzy matching (RapidFuzz).
- Produce an explainable breakdown: matched, partial, missing, and a normalized keyword score (0-100).
- Respect configuration thresholds from ats_config.py.

Notes:
- Keep the module deterministic and explainable.
- Designed to be role-agnostic and work across many job types.
"""

from typing import List, Dict, Tuple
import re
from rapidfuzz import fuzz
from collections import defaultdict
import itertools

# Local config import (relative)
from .ats_config import ATS_CONFIG

# Simple phrase cleaning
_NON_WORD_RE = re.compile(r'[^\w\s\+\#\-\.]')  # allow tech chars like + # - .
_SPLIT_TOK_RE = re.compile(r'[\s,/;|]+')

# Heuristics for tier detection
_REQUIRED_HINTS = re.compile(r'\b(must have|required|required:|required skills|must be|must know|essential)\b', flags=re.IGNORECASE)
_PREFERRED_HINTS = re.compile(r'\b(preferred|nice to have|desirable|would be good|preferably)\b', flags=re.IGNORECASE)

# A small curated tech term lexicon to improve phrase extraction (can be extended)
COMMON_TECH_TERMS = set([
    "html5","html","css3","css","bootstrap","javascript","jquery","react","vue","angular",
    "nodejs","node","python","django","flask","java","spring","sql","postgresql","mysql",
    "aws","azure","gcp","docker","kubernetes","rest","graphql","typescript","sass","less",
    "photoshop","figma","sketch","responsive","accessibility","seo","json","xml"
])

def _clean_phrase(phrase: str) -> str:
    p = phrase.strip().lower()
    p = re.sub(_NON_WORD_RE, ' ', p)
    p = re.sub(r'\s+', ' ', p)
    return p.strip()

def _extract_candidate_phrases(text: str, max_phrases: int = 120) -> List[str]:
    """
    Naive phrase extractor:
    - Prefer multi-word phrases from comma/line separated lists (e.g. Skills:)
    - Fall back to individual tokens
    - Prioritize terms that appear in COMMON_TECH_TERMS
    """
    candidates = []
    # 1) Look for lines with 'skills' or 'requirements' and split them
    for line in text.splitlines():
        low = line.lower()
        if 'skill' in low or 'require' in low or 'experience' in low or 'knowledge' in low:
            # split by common separators
            parts = re.split(r'[,:;\|\-]', line)
            for part in parts:
                part = _clean_phrase(part)
                # split further on slashes/commas
                subparts = re.split(_SPLIT_TOK_RE, part)
                # if multi token phrase exists, prefer it
                if len(part.split()) > 1 and len(part) > 2:
                    candidates.append(part)
                else:
                    for sp in subparts:
                        if sp:
                            candidates.append(sp)
    # 2) Greedy extract of common tech terms appearing anywhere
    words = re.findall(r'[\w\+\#\-\.]+', text.lower())
    for w in words:
        if w in COMMON_TECH_TERMS:
            candidates.append(w)
    # 3) fallback: top frequent nouns/words (simple frequency heuristic)
    freq = defaultdict(int)
    for w in words:
        if len(w) > 2:
            freq[w] += 1
    sorted_tokens = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
    for tok, _ in sorted_tokens[:50]:
        candidates.append(tok)
    # clean and dedupe preserving order
    cleaned = []
    for c in candidates:
        p = _clean_phrase(c)
        if p and p not in cleaned:
            cleaned.append(p)
        if len(cleaned) >= max_phrases:
            break
    return cleaned

def _detect_tiers_from_jd(jd_text: str, candidate_phrases: List[str]) -> Dict[str, List[str]]:
    """
    Assign initial tiers based on heuristic hints in the JD.
    Returns dict: { "required": [...], "preferred": [...], "bonus": [...] }
    """
    required = []
    preferred = []
    bonus = []

    # Block detection: try to isolate a 'requirements' block and mark those as required
    # Very naive: split by headings
    sections = re.split(r'\n{2,}', jd_text)
    for sec in sections:
        sec_low = sec.lower()
        if _REQUIRED_HINTS.search(sec_low):
            # everything in this section becomes required candidates
            for phrase in candidate_phrases:
                if phrase in sec_low:
                    required.append(phrase)
        elif _PREFERRED_HINTS.search(sec_low):
            for phrase in candidate_phrases:
                if phrase in sec_low:
                    preferred.append(phrase)

    # Next pass: heuristics based on top lines or bullets
    # If a phrase appears within the first 8 lines of JD, bias it to preferred/required
    top_lines = '\n'.join(jd_text.splitlines()[:12]).lower()
    for phrase in candidate_phrases:
        if phrase in top_lines and phrase not in required and phrase not in preferred:
            preferred.append(phrase)

    # Finally, any common tech terms that remained unassigned go to bonus
    for phrase in candidate_phrases:
        if phrase not in required and phrase not in preferred and phrase not in bonus:
            # a simple heuristic: if it's a long phrase or contains tech chars, prefer it
            if any(ch in phrase for ch in ['+', '#', '.']) or len(phrase.split()) > 1:
                bonus.append(phrase)
            else:
                # tokens that are very common get bonus
                bonus.append(phrase)

    # Deduplicate lists while preserving order
    def _uniq(seq):
        seen = set()
        out = []
        for s in seq:
            if s and s not in seen:
                seen.add(s)
                out.append(s)
        return out

    return {
        "required": _uniq(required),
        "preferred": _uniq(preferred),
        "bonus": _uniq(bonus)
    }

def _fuzzy_match_phrase(phrase: str, resume_text: str, strong_threshold: int, partial_threshold: int) -> Tuple[str, int, float]:
    """
    Return (status, best_score, best_ratio)
    status in {"strong", "partial", "none"}
    best_score: the integer fuzzy ratio
    best_ratio: normalized 0..1 (ratio/100)
    """
    if not phrase:
        return ("none", 0, 0.0)
    best = 0
    # Check exact substring first (fast)
    if phrase in resume_text.lower():
        return ("strong", 100, 1.0)
    # Try whole-phrase fuzzy matching against resume tokens and n-grams
    # Create a sliding window of tokens from resume and compute fuzzy.ratio
    tokens = re.findall(r'[\w\+\#\-\.]+', resume_text.lower())
    # check n-grams up to len(phrase_tokens)+1 to capture variations
    p_tokens = phrase.split()
    max_n = min(len(tokens), max(1, len(p_tokens) + 2))
    for n in range(1, max_n+1):
        # iterate over windows
        for i in range(0, len(tokens)-n+1):
            window = ' '.join(tokens[i:i+n])
            # compute ratio
            r = fuzz.ratio(phrase, window)
            if r > best:
                best = int(r)
                # early exit on perfect match
                if best >= 98:
                    break
        if best >= 98:
            break

    if best >= strong_threshold:
        return ("strong", best, best / 100.0)
    if best >= partial_threshold:
        return ("partial", best, best / 100.0)
    return ("none", best, best / 100.0)


def score_keywords(jd_text: str, resume_text: str, max_keywords: int = None) -> Dict:
    """
    Main entrypoint.

    Returns dict with:
    - total_keyword_score: 0-100 (normalized)
    - breakdown: { 'required': {matched:[], partial:[], missing:[]}, 'preferred': ..., 'bonus': ... }
    - raw_counts: per-keyword match strengths
    """
    if not jd_text or not resume_text:
        return {
            "total_keyword_score": 0,
            "breakdown": {},
            "raw_counts": {}
        }

    cfg = ATS_CONFIG.get("keyword", {})
    strong_thr = cfg.get("fuzzy_threshold_strong", 85)
    partial_thr = cfg.get("fuzzy_threshold_partial", 70)
    max_considered = cfg.get("max_keywords_considered", 80)
    if max_keywords is None:
        max_keywords = max_considered

    # 1) Extract candidate phrases from JD
    candidates = _extract_candidate_phrases(jd_text, max_phrases=max_considered)

    # 2) Detect tiers heuristically
    tiers = _detect_tiers_from_jd(jd_text, candidates)

    # optional trimming
    for k in tiers:
        if len(tiers[k]) > max_keywords:
            tiers[k] = tiers[k][:max_keywords]

    # 3) Score each tier
    weight_map = {
        "required": cfg.get("required_weight", 2.0),
        "preferred": cfg.get("preferred_weight", 1.0),
        "bonus": cfg.get("bonus_weight", 0.5)
    }

    raw_counts = {}
    tier_results = {}
    weighted_sum = 0.0
    weight_total_possible = 0.0

    # flatten all keywords to compute normalization denominator
    all_keywords = list(itertools.chain.from_iterable([tiers.get(t, []) for t in ["required", "preferred", "bonus"]]))
    # avoid empty
    if not all_keywords:
        return {
            "total_keyword_score": 0,
            "breakdown": {},
            "raw_counts": {}
        }

    for tier in ["required", "preferred", "bonus"]:
        items = tiers.get(tier, [])
        tier_results[tier] = {"matched": [], "partial": [], "missing": []}
        tier_weight = weight_map.get(tier, 1.0)
        for phrase in items:
            status, best_score, ratio = _fuzzy_match_phrase(phrase, resume_text, strong_thr, partial_thr)
            raw_counts[phrase] = {"status": status, "score": best_score, "ratio": ratio, "tier": tier}
            if status == "strong":
                tier_results[tier]["matched"].append({"phrase": phrase, "score": best_score})
                weighted_sum += tier_weight * 1.0  # full credit
            elif status == "partial":
                tier_results[tier]["partial"].append({"phrase": phrase, "score": best_score, "ratio": ratio})
                weighted_sum += tier_weight * 0.6  # partial credit factor
            else:
                tier_results[tier]["missing"].append({"phrase": phrase})
            weight_total_possible += tier_weight

    # Normalize to 0-100
    if weight_total_possible <= 0:
        total_score = 0
    else:
        normalized = (weighted_sum / (weight_total_possible))  # in [0..1*possible_factor]
        # Map to 0-100 scale (we allow >1 if weights and matches cause >1; cap at 1.0)
        normalized = max(0.0, min(1.0, normalized))
        total_score = int(round(normalized * 100))

    return {
        "total_keyword_score": total_score,
        "breakdown": tier_results,
        "raw_counts": raw_counts,
        "tiers_detected": tiers
    }

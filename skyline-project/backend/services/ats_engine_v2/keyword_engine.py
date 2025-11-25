"""
Keyword Engine for ATS v2
-------------------------
Extracts keywords from JD, assigns tiers (required, preferred, bonus),
and matches them against resume text.
"""

from typing import List, Dict, Tuple
import re
from rapidfuzz import fuzz
from collections import defaultdict
import itertools

# Local config import (relative)
try:
    from .ats_config import ATS_CONFIG
except ImportError:
    ATS_CONFIG = {
        "keyword": {
            "fuzzy_threshold_strong": 85,
            "fuzzy_threshold_partial": 70,
            "max_keywords_considered": 80,
            "required_weight": 2.0,
            "preferred_weight": 1.0,
            "bonus_weight": 0.5
        }
    }

# ----- Cleaning -----
_NON_WORD_RE = re.compile(r'[^\w\s\+\#\-\.]')
_SPLIT_TOK_RE = re.compile(r'[\s,/;|]+')

def _clean_phrase(phrase: str) -> str:
    p = phrase.strip().lower()
    p = re.sub(_NON_WORD_RE, ' ', p)
    p = re.sub(r'\s+', ' ', p)
    return p.strip()

# ----- Known tech lexicon -----
COMMON_TECH_TERMS = set([
    "html5","html","css3","css","bootstrap","javascript","jquery","react","vue","angular",
    "nodejs","node","python","django","flask","java","spring","sql","postgresql","mysql",
    "aws","azure","gcp","docker","kubernetes","rest","graphql","typescript","sass","less",
    "photoshop","figma","sketch","responsive","accessibility","seo","json","xml"
])


# =====================================================================
# 1. CANDIDATE PHRASE EXTRACTION
# =====================================================================
def _extract_candidate_phrases(text: str, max_phrases: int = 120) -> List[str]:
    candidates = []

    # 1) Extract from skill/requirement lines
    for line in text.splitlines():
        low = line.lower()
        if any(key in low for key in ["skill", "require", "experience", "knowledge"]):
            parts = re.split(r'[,:;\|\-]', line)
            for part in parts:
                part = _clean_phrase(part)
                subparts = re.split(_SPLIT_TOK_RE, part)

                if len(part.split()) > 1 and len(part) > 2:
                    candidates.append(part)
                else:
                    for sp in subparts:
                        if sp:
                            candidates.append(sp)

    # 2) Add known tech terms from JD
    words = re.findall(r'[\w\+\#\-\.]+', text.lower())
    for w in words:
        if w in COMMON_TECH_TERMS:
            candidates.append(w)

    # 3) Fallback: top frequent nouns
    freq = defaultdict(int)
    for w in words:
        if len(w) > 2:
            freq[w] += 1

    for tok, _ in sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:50]:
        candidates.append(tok)

    # Dedupe
    cleaned = []
    for c in candidates:
        p = _clean_phrase(c)
        if p and p not in cleaned:
            cleaned.append(p)
        if len(cleaned) >= max_phrases:
            break

    return cleaned


# =====================================================================
# 2. EXTRACT EXPLICIT JD BLOCKS (MUST HAVE, NICE TO HAVE)
# =====================================================================
def _extract_block_items_direct(jd_text: str) -> Dict[str, List[str]]:
    lines = jd_text.splitlines()
    n = len(lines)
    i = 0

    REQ_HEAD = re.compile(r'(must[\s\-]*have|required|requirements|essential)\s*:?', flags=re.IGNORECASE)
    PREF_HEAD = re.compile(r'(nice[\s\-]*to[\s\-]*have|preferred|desirable|preferably)\s*:?', flags=re.IGNORECASE)
    HEADING_LIKE = re.compile(r'^[A-Z0-9\s\-\(\)\/]{1,60}\s*:?\s*$')

    blocks = {"required": [], "preferred": []}

    while i < n:
        line = lines[i].strip()

        # Inline: "MUST HAVE: JavaScript, HTML"
        m_req_inline = re.search(r'(must[\s\-]*have|required|requirements)\s*:\s*(.+)$', line, flags=re.IGNORECASE)
        if m_req_inline:
            for item in re.split(r'[,\|;/]+', m_req_inline.group(2)):
                blocks["required"].append(_clean_phrase(item))
            i += 1
            continue

        m_pref_inline = re.search(r'(nice[\s\-]*to[\s\-]*have|preferred|desirable)\s*:\s*(.+)$', line, flags=re.IGNORECASE)
        if m_pref_inline:
            for item in re.split(r'[,\|;/]+', m_pref_inline.group(2)):
                blocks["preferred"].append(_clean_phrase(item))
            i += 1
            continue

        # Block bullets under heading
        if REQ_HEAD.search(line):
            j = i + 1
            while j < n:
                l = lines[j].strip()
                if not l or (HEADING_LIKE.match(l) and l.endswith(':')):
                    break
                m = re.match(r'^[\-\u2022\*\d\.\)]\s*(.+)$', l)
                if m:
                    blocks["required"].append(_clean_phrase(m.group(1)))
                else:
                    if 1 <= len(l.split()) <= 6:
                        blocks["required"].append(_clean_phrase(l))
                j += 1
            i = j
            continue

        if PREF_HEAD.search(line):
            j = i + 1
            while j < n:
                l = lines[j].strip()
                if not l or (HEADING_LIKE.match(l) and l.endswith(':')):
                    break
                m = re.match(r'^[\-\u2022\*\d\.\)]\s*(.+)$', l)
                if m:
                    blocks["preferred"].append(_clean_phrase(m.group(1)))
                else:
                    if 1 <= len(l.split()) <= 6:
                        blocks["preferred"].append(_clean_phrase(l))
                j += 1
            i = j
            continue

        i += 1

    # dedupe
    def uniq(seq):
        seen = set()
        out = []
        for s in seq:
            if s and s not in seen:
                seen.add(s)
                out.append(s)
        return out

    return {"required": uniq(blocks["required"]), "preferred": uniq(blocks["preferred"])}


# =====================================================================
# 3. TIER DETECTION
# =====================================================================
def _detect_tiers_from_jd(jd_text: str, candidate_phrases: List[str]) -> Dict[str, List[str]]:
    block_items = _extract_block_items_direct(jd_text)

    # If explicit MUST HAVE / NICE TO HAVE found → trust them
    if block_items["required"] or block_items["preferred"]:
        required = []
        preferred = []
        bonus = []

        def match_block_items(block_list):
            mapped = []
            for bi in block_list:
                for cand in candidate_phrases:
                    cand_norm = _clean_phrase(cand)
                    cand_tokens = set(re.findall(r'[\w\+\#\-\.]+', cand_norm))
                    bi_tokens = set(re.findall(r'[\w\+\#\-\.]+', bi))

                    if bi == cand_norm:
                        mapped.append(cand)
                    elif bi_tokens.issubset(cand_tokens):
                        mapped.append(cand)
                    elif cand_tokens.issubset(bi_tokens):
                        mapped.append(cand)

                # fallback: ensure the normalized item exists even if no candidate matched
                if not any(_clean_phrase(m) == bi for m in mapped):
                    mapped.append(bi)
            return mapped

        required = match_block_items(block_items["required"])
        preferred = match_block_items(block_items["preferred"])

        # Remaining unassigned → bonus
        bonus = [c for c in candidate_phrases if c not in required and c not in preferred]

        def uniq(seq):
            seen = set()
            out = []
            for s in seq:
                if s and s not in seen:
                    seen.add(s)
                    out.append(s)
            return out

        return {
            "required": uniq(required),
            "preferred": uniq(preferred),
            "bonus": uniq(bonus),
        }

    # Fallback heuristic tiers
    required = []
    preferred = []
    bonus = []

    sections = re.split(r'\n{2,}', jd_text.lower())
    for sec in sections:
        if "must have" in sec or "required" in sec:
            for c in candidate_phrases:
                if c in sec:
                    required.append(c)
        elif "preferred" in sec or "nice to have" in sec:
            for c in candidate_phrases:
                if c in sec:
                    preferred.append(c)

    top = "\n".join(jd_text.lower().splitlines()[:12])
    for c in candidate_phrases:
        if c in top and c not in required and c not in preferred:
            preferred.append(c)

    for c in candidate_phrases:
        if c not in required and c not in preferred:
            bonus.append(c)

    return {"required": required, "preferred": preferred, "bonus": bonus}


# =====================================================================
# 4. FUZZY MATCHER
# =====================================================================
def _fuzzy_match_phrase(phrase: str, resume_text: str, strong_thr: int, partial_thr: int):
    resume_text = resume_text.lower()
    phrase = phrase.lower()

    if phrase in resume_text:
        return ("strong", 100, 1.0)

    best = 0
    tokens = re.findall(r'[\w\+\#\-\.]+', resume_text)
    p_tokens = phrase.split()
    max_n = min(len(tokens), max(1, len(p_tokens) + 2))

    for n in range(1, max_n + 1):
        for i in range(len(tokens) - n + 1):
            window = " ".join(tokens[i:i+n])
            score = fuzz.ratio(phrase, window)
            if score > best:
                best = score
            if best >= 98:
                break

    if best >= strong_thr:
        return ("strong", best, best/100)
    if best >= partial_thr:
        return ("partial", best, best/100)
    return ("none", best, best/100)


# =====================================================================
# 5. MAIN ENTRYPOINT
# =====================================================================
def analyze_keywords(jd_text: str, resume_text: str, max_keywords: int = None) -> Dict:
    if not jd_text or not resume_text:
        return {"total_keyword_score": 0, "breakdown": {}, "raw_counts": {}}

    cfg = ATS_CONFIG.get("keyword", {})
    strong_thr = cfg.get("fuzzy_threshold_strong", 85)
    partial_thr = cfg.get("fuzzy_threshold_partial", 70)
    max_considered = cfg.get("max_keywords_considered", 80)
    max_keywords = max_keywords or max_considered

    candidates = _extract_candidate_phrases(jd_text)
    tiers = _detect_tiers_from_jd(jd_text, candidates)

    # trim
    for k in tiers:
        tiers[k] = tiers[k][:max_keywords]

    weight_map = {
        "required": cfg.get("required_weight", 2.0),
        "preferred": cfg.get("preferred_weight", 1.0),
        "bonus": cfg.get("bonus_weight", 0.5),
    }

    raw_counts = {}
    results = {t: {"matched": [], "partial": [], "missing": []} for t in tiers}
    weighted_sum = 0.0
    weight_total = 0.0

    for tier in ["required", "preferred", "bonus"]:
        tier_weight = weight_map[tier]
        for phrase in tiers[tier]:
            status, score, ratio = _fuzzy_match_phrase(phrase, resume_text, strong_thr, partial_thr)
            raw_counts[phrase] = {"status": status, "score": score, "ratio": ratio, "tier": tier}

            if status == "strong":
                results[tier]["matched"].append({"phrase": phrase, "score": score})
                weighted_sum += tier_weight
            elif status == "partial":
                results[tier]["partial"].append({"phrase": phrase, "score": score})
                weighted_sum += tier_weight * 0.6
            else:
                results[tier]["missing"].append({"phrase": phrase})

            weight_total += tier_weight

    score = 0
    if weight_total > 0:
        score = int(round(min(1.0, weighted_sum / weight_total) * 100))

    return {
        "total_keyword_score": score,
        "breakdown": results,
        "raw_counts": raw_counts,
        "tiers_detected": tiers
    }

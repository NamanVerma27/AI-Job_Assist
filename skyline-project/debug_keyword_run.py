# debug_keyword_run.py
from backend.services.ats_engine_v2 import keyword_engine as ke
import json

resume_text = (
    "JACKSON MACARTHUR\n"
    "Web Developer\n"
    "SKILLS: JavaScript, HTML, CSS, React.js, Node.js, AWS\n"
    "EXPERIENCE: Web Developer at Squarespace"
)

jd_text = (
    "We are looking for a Senior Web Developer.\n\n"
    "MUST HAVE:\n"
    "- JavaScript\n"
    "- HTML\n"
    "- CSS\n"
    "- React.js\n"
    "- Node.js\n\n"
    "NICE TO HAVE:\n"
    "- Angular.js\n"
    "- AWS"
)

cands = ke._extract_candidate_phrases(jd_text)
print("CANDIDATES:", cands[:60])

blocks = ke._extract_block_items_direct(jd_text)
print("BLOCKS (direct):", json.dumps(blocks, indent=2))

tiers = ke._detect_tiers_from_jd(jd_text, cands)
print("TIERS:", json.dumps(tiers, indent=2))

report = ke.analyze_keywords(jd_text, resume_text)
print("\nREPORT TIERS_DETECTED:", json.dumps(report.get("tiers_detected", {}), indent=2))
print("\nREPORT BREAKDOWN (summary):")
for t in ["required", "preferred", "bonus"]:
    print(f" {t}: matched={len(report['breakdown'][t]['matched'])}, partial={len(report['breakdown'][t]['partial'])}, missing={len(report['breakdown'][t]['missing'])}")

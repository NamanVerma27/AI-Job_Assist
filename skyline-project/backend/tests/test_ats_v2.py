from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_ats_v2_scoring():
    """
    Tests the ATS V2 endpoint.
    Uses explicit \\n characters to guarantee section splitting.
    """
    # 1. Define Payload
    # A simple resume with the right keywords
    resume_text = (
        "JACKSON MACARTHUR\n"
        "Web Developer\n"
        "SKILLS: JavaScript, HTML, CSS, React.js, Node.js, AWS\n"
        "EXPERIENCE: Web Developer at Squarespace"
    )
    
    # 2. Define JD with EXPLICIT double newlines
    # The engine needs \n\n to know where 'Required' starts.
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

    payload = {
        "resume_text": resume_text,
        "jd_text": jd_text
    }

    # 3. Send Request
    response = client.post("/resume/ats-score-v2", json=payload)

    # 4. Assertions
    assert response.status_code == 200, f"Request failed: {response.text}"
    
    data = response.json()
    report = data["data"]
    import json
    print("\n>>> FULL KEYWORD BLOCKS:\n", json.dumps(report["raw"]["keywords"]["tiers_detected"], indent=2))
    print("\n>>> FULL KEYWORD RAW COUNTS:\n", json.dumps(report["raw"]["keywords"]["raw_counts"], indent=2))

    keyword_data = report["raw"]["keywords"]
    
    # 5. Debugging Outputs
    print(f"\n✅ Keyword Score: {keyword_data['total_keyword_score']}")
    
    matched_required = keyword_data["breakdown"]["required"]["matched"]
    matched_preferred = keyword_data["breakdown"]["preferred"]["matched"]
    
    # Get just the phrases for easy reading
    req_phrases = [m['phrase'] for m in matched_required]
    pref_phrases = [m['phrase'] for m in matched_preferred]
    
    print(f"✅ Required Matches: {req_phrases}")
    print(f"✅ Preferred Matches: {pref_phrases}")

    # 6. Final Check
    # We expect 'javascript' to be in REQUIRED because it is under 'MUST HAVE:'
    assert "javascript" in req_phrases, f"Expected 'javascript' in required, found in: {pref_phrases}"
    assert len(matched_required) >= 3, "Should have matched at least 3 required skills"
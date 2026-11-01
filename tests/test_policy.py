from phase2 import eligibility_gate
from submission_adapters import ReviewOnlyAdapter, SubmissionRequest

CONFIG = {'min_score': 80}
BASE = {'score': 95, 'eligibility': 'eligible', 'sponsorship': 'not_required', 'questions_for_review': []}

def test_unknown_eligibility_blocks():
    assert eligibility_gate({}, {**BASE, 'eligibility': 'unknown'}, CONFIG)[0] == 'review'

def test_unknown_sponsorship_blocks():
    assert eligibility_gate({}, {**BASE, 'sponsorship': 'unknown'}, CONFIG)[0] == 'review'

def test_low_score_rejected():
    assert eligibility_gate({}, {**BASE, 'score': 70}, CONFIG)[0] == 'rejected'

def test_questions_require_review():
    assert eligibility_gate({}, {**BASE, 'questions_for_review': ['salary?']}, CONFIG)[0] == 'review'

def test_approval_not_submission():
    assert eligibility_gate({}, BASE, CONFIG)[0] == 'approved'

def test_default_adapter_never_submits():
    request = SubmissionRequest('1','https://example.com','cv.pdf','example@example.com',{},True)
    assert not ReviewOnlyAdapter().submit(request).success

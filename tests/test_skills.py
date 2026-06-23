from etl.skills import extract_skills_from_text, normalize_skill


def test_normalize_variants():
    assert normalize_skill('Amazon Web Services') == 'AWS'
    assert normalize_skill('aws') == 'AWS'
    assert normalize_skill('Microsoft Azure') == 'Azure'


def test_extract_from_text():
    txt = 'We are hiring a Python developer with experience in AWS, Docker and SQL.'
    skills = extract_skills_from_text(txt)
    assert 'Python' in skills
    assert 'AWS' in skills
    assert 'Docker' in skills
    assert 'SQL' in skills

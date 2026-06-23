from etl.transform import transform_jobs


def test_transform_basic():
    raw = [{'id': 1, 'company': 'Acme', 'position': 'Senior Python Engineer', 'tags': ['Python', 'AWS'], 'description': 'We use Python and AWS.'}]
    df = transform_jobs(raw, staging_dir='tests/tmp_staging')
    assert df.iloc[0]['job_title'] in ('Python Developer', 'Senior Python Engineer', 'Python Engineer', 'Unknown')
    assert 'Python' in df.iloc[0]['skills']
from etl.transform import transform_records


def test_transform_empty():
    out = transform_records([])
    assert out == []

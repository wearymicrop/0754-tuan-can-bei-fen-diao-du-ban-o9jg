def test_preview_paths_follow_real_modules(client):
    run=client.post('/api/runs',json={'sample':'dirty'}).json()
    for stage in ('orders','substitutions','windows','capacity','allocation','reconcile'):
        response=client.get(f'/api/{stage}/dirty')
        assert response.status_code==200 and response.json()==run['result'][stage]


def test_clean_preview_renders_board(client):
    page=client.get('/?sample=clean')
    assert page.status_code==200 and '发餐波次板' in page.text
    assert client.get('/api/previews/clean').json()['reconcile']['totals']['shipped']==222


def test_bad_sample_returns_404(client):
    response=client.get('/api/capacity/missing')
    assert response.status_code==404 and response.json()['code']=='UNKNOWN_SAMPLE'

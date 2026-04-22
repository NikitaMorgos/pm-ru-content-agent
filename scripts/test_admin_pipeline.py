import urllib.request, json, time

payload = {
    'category': 'table',
    'article': '184109',
    'variant': 'Белый глянец',
    'brand': 'БЕННИ',
    'product_name': 'Стол обеденный раскладной',
    'width_cm': 75.0,
    'depth_cm': 90.0,
    'height_cm': 66.0,
    'tabletop_material': 'ЛДСП 22 мм',
    'tabletop_finish': 'Белый глянец',
    'legs_material': 'Металл, порошковая окраска',
    'utp_1': 'Раздвижной механизм',
    'utp_2': 'Влагостойкая столешница',
    'utp_3': 'Регулируемые ножки',
    'photo_url_1': ''
}

req = urllib.request.Request(
    'http://localhost:8001/admin/api/jobs',
    data=json.dumps(payload).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(req) as r:
    job = json.loads(r.read())

job_id = job['id']
print('Created job:', job_id, '  state:', job['state'])

for _ in range(30):
    time.sleep(3)
    with urllib.request.urlopen('http://localhost:8001/admin/api/jobs/' + job_id) as r:
        j = json.loads(r.read())
    step = j.get('current_step', '')
    state = j.get('state', '')
    print('  step=' + step + '  state=' + state)
    if state in ('done', 'error'):
        print('FINAL state=' + state)
        err = j.get('error_message', '')
        if err:
            print('Error:', err)
        urls = j.get('result_urls', [])
        if urls:
            print('Results:', urls)
        break

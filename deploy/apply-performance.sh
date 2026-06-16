#!/bin/bash
# 로딩 개선: nginx 봇 차단 + Gunicorn 워커 증가
# 실행: sudo bash /srv/excavator/deploy/apply-performance.sh
set -euo pipefail

cp /srv/excavator/deploy/nginx-bot-block-map.conf /etc/nginx/conf.d/bot-block-map.conf

EXCAVATOR=/etc/nginx/sites-available/excavator
if ! grep -q 'block_aggressive_bot' "$EXCAVATOR"; then
  python3 - <<'PY'
from pathlib import Path
src = Path("/etc/nginx/sites-available/excavator")
text = src.read_text()
needle = "    location = /viewsale/viewsale_010100.html { return 301 /; }\n\n    location / {"
insert = (
    "    location = /viewsale/viewsale_010100.html { return 301 /; }\n\n"
    "    if ($block_aggressive_bot) {\n"
    "        return 403;\n"
    "    }\n\n"
    "    location / {"
)
if needle not in text:
    raise SystemExit("excavator nginx 패턴을 찾지 못했습니다. 수동 확인 필요.")
src.write_text(text.replace(needle, insert))
print("nginx excavator: bot block 추가")
PY
fi

sed -i 's/--workers 3/--workers 5/' /etc/systemd/system/gunicorn-excavator.service

nginx -t
systemctl reload nginx
systemctl daemon-reload
systemctl restart gunicorn-excavator.service
echo "완료: nginx 봇 차단 + gunicorn workers=5"

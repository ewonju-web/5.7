#!/usr/bin/env bash
# direct-nara.co.kr SSL 설정 (DNS가 이 서버를 가리킬 때 certbot 실행)
set -euo pipefail

TARGET_IP="61.111.38.50"
DOMAINS=("direct-nara.co.kr" "www.direct-nara.co.kr")
DEPLOY_DIR="/srv/excavator/deploy"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "root 권한이 필요합니다: sudo bash $0"
  exit 1
fi

echo "=== 1. nginx server_name 적용 ==="
cp "${DEPLOY_DIR}/nginx-excavator.conf" /etc/nginx/sites-available/excavator
nginx -t
systemctl reload nginx
echo "nginx 적용 완료"

echo ""
echo "=== 2. certbot 설치 확인 ==="
if ! command -v certbot >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y certbot python3-certbot-nginx
fi
certbot --version

echo ""
echo "=== 3. DNS 확인 ==="
dns_ok=true
for domain in "${DOMAINS[@]}"; do
  resolved="$(dig +short "$domain" | tail -1)"
  echo "${domain} -> ${resolved:-없음}"
  if [[ "$resolved" != "$TARGET_IP" ]]; then
    dns_ok=false
  fi
done

if [[ "$dns_ok" != true ]]; then
  echo ""
  echo "DNS가 아직 ${TARGET_IP}를 가리키지 않습니다."
  echo "nginx 설정만 적용했습니다. DNS 전환 후 아래 명령으로 인증서를 발급하세요:"
  echo "  sudo certbot --nginx -d direct-nara.co.kr -d www.direct-nara.co.kr"
  exit 0
fi

echo ""
echo "=== 4. Let's Encrypt 인증서 발급 ==="
# 자체서명 443 리다이렉트가 있으면 certbot과 충돌할 수 있어 비활성화
if [[ -L /etc/nginx/sites-enabled/excavator-ssl ]]; then
  rm -f /etc/nginx/sites-enabled/excavator-ssl
  nginx -t
  systemctl reload nginx
  echo "excavator-ssl(자체서명) 비활성화"
fi

certbot --nginx -d direct-nara.co.kr -d www.direct-nara.co.kr --non-interactive --agree-tos --register-unsafely-without-email || {
  echo "certbot 대화형 실행이 필요할 수 있습니다:"
  echo "  sudo certbot --nginx -d direct-nara.co.kr -d www.direct-nara.co.kr"
  exit 1
}

nginx -t
systemctl reload nginx
echo ""
echo "SSL 설정 완료. https://direct-nara.co.kr 로 확인하세요."

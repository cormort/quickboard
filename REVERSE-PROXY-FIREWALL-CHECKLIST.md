# 反向代理與防火牆檢查清單

## DNS 與連線
- [ ] `DOMAIN` 的 A/AAAA 記錄指向正確主機。
- [ ] 僅公開 TCP 80、443；若使用 HTTP/3，再開放 UDP 443。
- [ ] FastAPI 8000 僅在 Docker network `quickboard` 中 expose，未綁定主機公開介面。
- [ ] Caddy 可解析 `quickboard:8000`，且健康檢查通過後才轉送流量。

## TLS 與標頭
- [ ] HTTPS 憑證有效且自動更新。
- [ ] HTTP 自動轉向 HTTPS。
- [ ] HSTS、nosniff、DENY frame、no-referrer 與 Permissions-Policy 已存在。
- [ ] `/api/*` 回應設定 `Cache-Control: no-store`。
- [ ] 反向代理正確傳遞 `X-Forwarded-For` 與 `X-Forwarded-Proto`。
- [ ] 若前方還有 CDN／負載平衡器，只信任已知代理 IP，避免偽造來源位址。

## 主機防火牆
### UFW 範例
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from <管理IP或VPN網段> to any port 22 proto tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw enable
sudo ufw status verbose
```

### firewalld 範例
```bash
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-port=443/udp
sudo firewall-cmd --reload
sudo firewall-cmd --list-all
```

## 驗證
```bash
docker compose ps
curl -fsS https://$DOMAIN/api/health
curl -I https://$DOMAIN/
ss -lntup
```
- [ ] `ss` 不應看到 8000 對外監聽。
- [ ] 從外部掃描只看到預期的 80／443 與受限 SSH。
- [ ] Caddy logs 沒有循環代理、TLS 或 upstream timeout 錯誤。

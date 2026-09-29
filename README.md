# QuickBoard 自架安全版

## 快速部署
```bash
cp .env.example .env
chmod +x scripts/*.sh
./scripts/generate-secret.sh
# 將輸出填入 .env 的 APP_SECRET，並設定 DOMAIN
docker compose up -d --build
docker compose logs -f
```

DNS 需先指向主機，並開放 TCP 80、443。正式環境保持 `COOKIE_SECURE=true`。

## 安全機制
- Argon2 密碼雜湊，密碼最低 12 字元。
- HttpOnly、Secure、SameSite=Strict JWT Cookie。
- 房間會員授權，非會員不能讀寫訊息。
- 只有房主能產生邀請碼及管理房內訊息。
- 邀請碼只顯示一次，資料庫只存加鹽雜湊，預設 24 小時、10 次使用上限。
- 登入、註冊、邀請與發文速率限制。
- 固定訊息 UUID，支援離線重送去重。
- Caddy 自動 HTTPS 與安全標頭。

## 備份
```bash
./scripts/backup.sh
```
備份預設保留 30 天。仍建議同步到另一個加密儲存位置。

## 本機測試
把 `.env` 的 `COOKIE_SECURE=false`，並暫時在 quickboard service 加上 `ports: ["8000:8000"]`，由 http://localhost:8000 測試。


## 管理員後台與清理
- 將 `.env` 的 `BOOTSTRAP_ADMIN_USERNAME` 設為第一位管理員帳號。既有資料庫啟動時會自動補上 `is_admin`、`is_active` 欄位，並將該帳號升級為管理員。
- 管理員登入後可開啟後台，查看統計、停用帳號、刪除房間、依房間與保留天數清理訊息，以及清理失效邀請。
- `AUTO_CLEANUP_ENABLED=true` 時，每次容器啟動會依 `MESSAGE_RETENTION_DAYS` 清理逾期訊息。清理前請執行 `./scripts/backup.sh`。

## 本次部署修正
- 增加既有 SQLite schema 的啟動遷移，避免 `create_all` 無法新增欄位。
- 管理員可以跨房間刪除訊息，停用帳號會立即阻止後續 API 存取。
- 移除前端 QR Code CDN 依賴，邀請視窗改顯示可複製的同源邀請網址，避免外部 CDN 被阻擋導致部署失敗。

- 公開註冊已關閉：新帳號一定要使用尚未過期、未撤銷且未達使用上限的邀請碼；首位管理員由 `.env` 的 bootstrap 帳密建立。


## 自動備份與還原
- `backup` 容器依 `BACKUP_INTERVAL_SECONDS` 自動使用 SQLite Online Backup API 建立一致性備份，完成後執行 `PRAGMA integrity_check`。
- 備份位於 `./backups/`，依 `BACKUP_RETENTION_DAYS` 自動輪替。
- 立即備份：`./scripts/backup-now.sh`。
- 還原：`./scripts/restore.sh backups/quickboard-YYYYMMDD-HHMMSS.db`。還原前會驗證完整性、停止寫入服務、保存 pre-restore 副本、移除舊 WAL/SHM，再啟動並複驗。
- 防火牆及反向代理檢核詳見 `REVERSE-PROXY-FIREWALL-CHECKLIST.md`。
- 管理員後台顯示最近 200 筆審計紀錄，並可匯出最多 10,000 筆 CSV。


## 備份告警、審計分頁、部署回滾
- 備份失敗可透過一般 JSON Webhook 和 SMTP 郵件通知；狀態寫入 `backups/backup-status.json`。
- 審計頁支援操作類型、起迄日期、每頁 50 筆、上一頁／下一頁，以及帶相同條件的 CSV 匯出。
- 完整部署及回滾請參閱 `DEPLOYMENT-ROLLBACK.md`，指令為 `scripts/deploy.sh`、`rollback.sh`、`full-rollback.sh`。

- 通知設定完成後可執行 `./scripts/test-notification.sh`，測試 Webhook／SMTP，不需故意破壞備份。

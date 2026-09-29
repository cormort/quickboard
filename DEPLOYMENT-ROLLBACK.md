# 完整部署與回滾流程

## 正式部署
1. 解壓新版本至專案外部，例如 `/tmp/quickboard-release`。
2. 確認目前服務正常並備妥 `.env`。
3. 執行：
```bash
./scripts/deploy.sh /tmp/quickboard-release
```
流程會先建立 SQLite 一致性備份、保存目前程式快照、驗證 Compose、重建映像、啟動服務並檢查 `/api/health`。健康檢查失敗會自動執行程式回滾。

## 僅回滾程式
```bash
./scripts/rollback.sh releases/pre-deploy-YYYYMMDD-HHMMSS
```
省略參數時，會使用 `releases/LAST_ROLLBACK_TARGET`。程式回滾不會回退資料庫，避免錯誤覆蓋部署後新資料。

## 程式與資料庫完整回滾
只有資料庫結構或資料已遭破壞時使用：
```bash
./scripts/full-rollback.sh releases/pre-deploy-YYYYMMDD-HHMMSS backups/quickboard-YYYYMMDD-HHMMSS.db
```
完整回滾會先退回程式，再透過 `restore.sh` 停止寫入並還原資料庫。部署後新增的資料會遺失，執行前必須取得業務確認。

## 回滾後驗證
```bash
docker compose ps
curl -fsS https://$DOMAIN/api/health
docker compose logs --tail=100 quickboard caddy backup
```
並人工驗證登入、房間、訊息、管理員後台、審計日誌及備份狀態。

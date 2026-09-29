import json, os, socket, sqlite3, sys, time, traceback
from pathlib import Path
from notify import notify
SRC=Path(os.getenv("DATABASE_PATH","/data/quickboard.db")); DST=Path(os.getenv("BACKUP_DIR","/backups")); KEEP=int(os.getenv("BACKUP_RETENTION_DAYS","30")); STATUS=DST/"backup-status.json"
START=time.time(); stamp=time.strftime("%Y%m%d-%H%M%S"); tmp=DST/f".quickboard-{stamp}.tmp"; out=DST/f"quickboard-{stamp}.db"
def status(ok, detail, output=None):
    DST.mkdir(parents=True,exist_ok=True); payload={"ok":ok,"time":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"detail":detail,"output":str(output) if output else None,"duration_seconds":round(time.time()-START,2)}
    t=STATUS.with_suffix(".tmp"); t.write_text(json.dumps(payload,ensure_ascii=False,indent=2)); t.replace(STATUS)
try:
    DST.mkdir(parents=True,exist_ok=True)
    if not SRC.exists(): raise FileNotFoundError(f"database not found: {SRC}")
    source=sqlite3.connect(f"file:{SRC}?mode=ro",uri=True,timeout=30); target=sqlite3.connect(tmp)
    with target: source.backup(target)
    source.close(); result=target.execute("PRAGMA integrity_check").fetchone()[0]; target.close()
    if result!="ok": raise RuntimeError(f"integrity_check={result}")
    tmp.replace(out); cutoff=time.time()-KEEP*86400
    for p in DST.glob("quickboard-*.db"):
        if p.stat().st_mtime<cutoff:p.unlink()
    status(True,"backup completed",out); print(out)
except Exception as e:
    tmp.unlink(missing_ok=True); detail=f"Host: {socket.gethostname()}\nDatabase: {SRC}\nError: {e}\n{traceback.format_exc()}"; status(False,str(e)); notify("QuickBoard backup failed",detail,"error"); print(detail,file=sys.stderr); raise

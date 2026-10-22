#!/usr/bin/env bash
# SQLite 온라인 백업. 앱을 멈추지 않고 컨테이너 안의 python sqlite3로 일관된 사본을 만든다.
# 사용: ./deploy/backup.sh  → db/backup/fridge-YYYYmmdd-HHMM.db
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p db/backup
stamp=$(date +%Y%m%d-%H%M)
docker exec fridge-dict python - "$stamp" <<'PY'
import sqlite3, sys, os
os.makedirs("/data/backup", exist_ok=True)
dst_path = f"/data/backup/fridge-{sys.argv[1]}.db"
src = sqlite3.connect("/data/fridge.db")
dst = sqlite3.connect(dst_path)
with dst:
    src.backup(dst)
dst.close(); src.close()
print(dst_path)
PY
echo "backup ok: db/backup/fridge-$stamp.db"

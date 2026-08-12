#!/bin/sh
# Sao lưu database VietReader.
#
# Dùng lệnh .backup của SQLite chứ KHÔNG copy file: copy trong lúc app đang ghi có thể ra bản
# hỏng, vì WAL còn dữ liệu chưa dồn vào file chính. .backup xử lý đúng chuyện đó.
#
#   ./scripts/backup_db.sh /data/vietreader.db /data/backups
#   crontab:  0 3 * * *  /app/scripts/backup_db.sh /data/vietreader.db /data/backups
set -eu

DB="${1:-/data/vietreader.db}"
DEST="${2:-/data/backups}"
KEEP="${KEEP:-14}"

[ -f "$DB" ] || { echo "khong thay database: $DB" >&2; exit 1; }
mkdir -p "$DEST"

STAMP=$(date +%Y%m%d-%H%M%S)
OUT="$DEST/vietreader-$STAMP.db"

sqlite3 "$DB" ".backup '$OUT'"
gzip -f "$OUT"
echo "da sao luu: $OUT.gz"

# Giữ lại KEEP bản gần nhất, xoá phần cũ hơn.
ls -1t "$DEST"/vietreader-*.db.gz 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
  rm -f "$old"
  echo "da xoa ban cu: $old"
done

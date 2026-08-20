# TODO

> Ghi chú: phần Phase 11 bên dưới là biên bản lịch sử tại thời điểm triển khai. Trạng thái và
> số lượng test hiện tại phải lấy từ lần chạy CI gần nhất, không từ các con số snapshot cũ.

## Phase 11 — Trải nghiệm đọc, bộ truyện, ghi chú, giao diện (2026-08-12)

**Trạng thái: XONG, tất cả xanh, NHƯNG CHƯA COMMIT** — 44 file thay đổi trong working tree.

```
make lint · make typecheck    sạch
make test                     178 passed, coverage 96%
make eval                     5/5 ngưỡng PASS (I1 và I6 vẫn 1.0000)
migration                     upgrade -> downgrade -> upgrade sạch, kể cả trên DB có dữ liệu
```

Toàn bộ quyết định và các lỗi đã sửa: xem `DECISIONS.md` mục Phase 11.
Giới hạn còn lại: xem `KNOWN_LIMITATIONS.md`.

### Đã làm trong phase này

- Vòng lặp đọc: URL thật cho mỗi chương, khôi phục vị trí đọc, thư viện, "Tiếp tục đọc",
  phím tắt, chỉnh cỡ chữ.
- Bộ truyện: tự gom chương theo URL, trang danh sách chương, đổi tên, theo dõi.
- Ghi chú khi đọc, gắn với chương + đoạn, trang `/feedback`.
- Chuyển chương trước/sau: tự dò trên mọi site + sửa tay khi dò trượt.
- Tên chương lấy từ trong trang (giữ dấu tiếng Việt), chương cũ tự cập nhật khi mở lại.
- Giao diện "Mây hồng" + linh vật Mây (SVG tự vẽ), bản sáng và bản tối.
- Cá nhân hoá theo `VIETREADER_READER_NAME` (mặc định `Ngân Giang`).

### Lỗi đã phát hiện và sửa (đều có test khoá lại)

Đáng chú ý: phần lớn chỉ lộ ra khi **chạy thật và nhìn màn hình**, không test nào bắt được.

1. `/api/position/{series_key}` luôn 404 với khoá URL — vị trí đọc chưa bao giờ chạy với chương
   đọc bằng URL, lỗi có từ Phase 7.
2. `GenericExtractor` dồn cả chương thành MỘT đoạn — mọi site chưa có adapter, lỗi từ Phase 4.
3. Gán bộ truyện ghi đè chương của bộ khác khi hai URL trùng nội dung.
4. Regex số chương đọc `%C3` trong URL percent-encode thành "chương 3".
5. `ChapterCacheEntry` thiếu `series_id`.
6. `.position-note[hidden]` bị `display:flex` ghi đè — hộp rỗng trên mọi chương.
7. Georgia thiếu ký tự tiếng Việt — chữ có dấu lệch nét so với chữ không dấu.

### Việc còn để ngỏ (không có gì đang hỏng)

- [ ] **Commit** — chưa commit gì cả.
- [ ] Bảng màu bản tối bị lặp 2 lần trong `style.css` (một cho `prefers-color-scheme`, một cho
      `data-theme`). CSS thuần không gộp được; muốn gộp thì cho JS luôn gắn `data-theme` ngay
      từ đầu. Rủi ro hiện tại: đổi màu tối mà quên một chỗ thì lệch.
- [ ] Viết adapter YAML cho `truyendichwiki.net` (`config/sites/`) để tên chương và link chuyển
      chương chính xác tuyệt đối thay vì phỏng đoán.
- [ ] Chưa ai xác nhận bằng mắt trong trình duyệt thật: popup quick-add khi bôi đen bằng chuột,
      tấm ghi chú kéo lên từ đáy trên điện thoại, cảm giác các hiệu ứng chuyển động.

### Dữ liệu demo

`demo.db` trong thư mục `vietreader/` là DB demo (đã `.gitignore`), chứa từ điển mẫu + vài
chương thật. Xoá lúc nào cũng được.

---

# Việc còn lại sau Phase 9

Tất cả 10 phase (0–9) đã hoàn thành và commit. Các mục dưới đây là phần **NOT RUN** trung thực,
không bịa kết quả — cần input bên ngoài (API key hoặc Docker daemon) mà agent không tự có.

## 1. Chạy với LLM thật (cần `ANTHROPIC_API_KEY`)

- [ ] `pytest -m live -v` → chạy `tests/integration/test_anthropic_live.py` thật
- [ ] `python evals/run_eval.py --live` → đo `ambiguity_accuracy` với LLM thật thay vì
      `FakeProvider` (hiện tại số liệu 1.00 chỉ phản ánh hành vi mặc định của FakeProvider,
      xem DECISIONS.md mục Phase 8)

Cách chạy khi có key:
```bash
export VIETREADER_LLM_API_KEY=sk-ant-...     # hoặc set trong .env
cd vietreader
.venv/Scripts/python.exe -m pytest -m live -v
.venv/Scripts/python.exe evals/run_eval.py --live
```

## 2. Xác minh `docker-compose.dev.yml`

- [x] **DONE** — đã khởi động Docker Desktop, chạy `docker compose -f docker-compose.dev.yml up
      --detach` thật, container `pip install` xong, server `Uvicorn running on
      http://0.0.0.0:8000`, xác nhận `curl http://localhost:8000/api/health` từ host trả
      `{"status":"ok"}` và `/docs` trả 200. Đã `docker compose down` dọn dẹp. Xem
      PHASE_REPORTS.md Phase 9 cho log đầy đủ.

## Trạng thái các phase (tham khảo, xem PHASE_REPORTS.md để đầy đủ)

| Phase | Trạng thái |
|---|---|
| 0 — Scaffolding | ✅ DONE |
| 1 — Core Domain | ✅ DONE |
| 2 — Resolver/Applier/Validator | ✅ DONE |
| 3 — LLM Disambiguator | ✅ DONE (live smoke test NOT RUN) |
| 4 — Extraction | ✅ DONE |
| 5 — Persistence/Pipeline | ✅ DONE |
| 6 — HTTP API | ✅ DONE |
| 7 — Reader UI | ✅ DONE |
| 8 — Eval Harness | ✅ DONE (--live NOT RUN) |
| 9 — Hardening/Handover | ✅ DONE (docker-compose up đã xác minh thật) |

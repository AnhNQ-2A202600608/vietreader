# TODO — việc còn lại sau Phase 9

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

# Completion TODO — When All Phases Are Done

> This is my personal checklist. Run through every item top to bottom once  
> Phase 6 (API Polish) and Phase 7 (E2E Tests) are both complete.

---

## 1. Verify the Standalone Demo Still Works

Run the original demo that tests Phase 1–3 **without a server** (direct Python, no HTTP):

```bash
cd backend
source .venv/bin/activate
python demo_complete.py
```

**Expected output:**
- ✓ Script: 5 beats
- ✓ Storyboard: 8 shots  
- ✓ Audio generated
- ✓ Chat routing: 3 intents parsed correctly
- ✓ Compliance: GREEN/YELLOW correctly returned
- ✓ IMPLEMENTATION COMPLETE

If any step fails → fix before moving forward.

---

## 2. Run the Full API End-to-End Demo

This demo exercises every HTTP endpoint through the actual server (the real integration path the frontend will use):

```bash
# Terminal 1 — start the server
source .venv/bin/activate
python -m uvicorn app.main:app --port 8000

# Terminal 2 — run the API demo
source .venv/bin/activate
python scripts/api_demo.py
```

**What `api_demo.py` should verify:**
- [ ] `POST /projects` → project created with ready_stages
- [ ] `POST /projects/{id}/stages/SCRIPT` → job queued
- [ ] `GET /projects/{id}/jobs/{job_id}` → polls until `completed`
- [ ] `GET /projects/{id}` → `script` field is populated (not null)
- [ ] `POST /projects/{id}/stages/STORYBOARD` → queued + completed
- [ ] `GET /projects/{id}` → `storyboard` field is populated
- [ ] `POST /projects/{id}/stages/AUDIO_AI` → queued + completed
- [ ] `GET /projects/{id}` → `audio` field is populated
- [ ] `POST /projects/{id}/chat` → returns intent + response
- [ ] `GET /projects/{id}/compliance/pending` → returns [] after GREEN stage
- [ ] `GET /projects/{id}/compliance/history` → shows all checkpoints
- [ ] `GET /projects/{id}/dag` → shows correct node statuses
- [ ] `GET /projects` → lists all projects (Phase 6 endpoint)

**Create this script at:** `backend/scripts/api_demo.py`

---

## 3. Run All Existing Unit Tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v --tb=short 2>&1 | tail -40
```

**Expected:** All 60+ tests pass. No regressions from our changes.  
If any fail → fix them before declaring done.

---

## 4. Run E2E API Tests (Phase 7)

```bash
pytest tests/e2e/ -v --tb=short
```

These should cover:
- [ ] AI voice full workflow
- [ ] YELLOW block + approval + unblock
- [ ] Chat routing for all 3 intents
- [ ] Job recovery after simulated crash

---

## 5. Check for Remaining Print Statements

Replace `print()` with `logging.info()` across worker and main:

```bash
grep -rn "^    print(" app/worker.py app/main.py app/orchestration/
```

Fix any `print()` that should be structured logs.

---

## 6. Verify No Hardcoded Paths

```bash
grep -rn "C:\\\\" backend/app/ backend/*.py
grep -rn "/Users/atharva" backend/app/ backend/*.py
grep -rn "/home/" backend/app/ backend/*.py
```

All should return zero results.

---

## 7. Clean the Database Before Handover

```bash
cd backend
source .venv/bin/activate
python -c "
import sqlite3
db = sqlite3.connect('cinema.db')
db.execute('DELETE FROM jobs')
db.execute('DELETE FROM compliance_checkpoints')
db.execute('DELETE FROM projects')
db.commit()
db.close()
print('cinema.db wiped — fresh start for frontend team')
"
```

---

## 8. Check the FastAPI Auto-Docs

Start the server and open: **http://localhost:8000/docs**

Verify:
- [ ] All endpoints are visible
- [ ] Request/response schemas are documented
- [ ] No endpoints are missing (cross-reference the table in AGENT_HANDOVER.md)

---

## 9. Update AGENT_HANDOVER.md One Final Time

- Mark Phase 6 and Phase 7 as ✅ done
- Update the "What Remains" section to reflect only Phase 8+ (WebSocket, Logging, Auth)
- Add the final commit hash

---

## 10. Commit Everything and Tag the Release

```bash
cd /Users/mayankchauhan/Documents/AgenticCinema
git add -A
git commit -m "Backend MVP: Phases 1-7 complete — production-ready for frontend integration"
git tag -a v0.1.0-mvp -m "Backend MVP complete"
git push origin integration --tags
```

---

## Summary — What "Done" Means

The backend is complete when:
- ✅ `demo_complete.py` runs without errors
- ✅ `scripts/api_demo.py` runs without errors through all 13 endpoint checks
- ✅ All 60+ unit tests pass
- ✅ All E2E tests pass
- ✅ `/docs` shows a clean API surface
- ✅ `cinema.db` is clean (no test data)
- ✅ Final commit is tagged

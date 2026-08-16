# SDD progress

Task 1: complete (commits 8a7ff73..fd326d8, review clean). Minor: dual conftest path setup; timeline_view.py main() not hooked (out of scope).
Task 2: complete (commits fd326d8..10c4165, review clean). Minor: unused Path/_which_missing in tests.
Task 3: complete (commits 10c4165..65c9254, review clean). Minor: mid-file import in render.py; unused validate_edl in pipeline (later tasks).
Task 4: complete (commits 65c9254..2043bca, review clean). Minor: non-atomic save_session; reclaim mutates in place.
Task 5: complete (commits 2043bca..7a166ce, review clean). Minor: run_helper untested; transcribe_batch still case-exact.
Task 6: complete (commits 7a166ce..d8b6502, review clean). Minor: no rendering/mtime-stale tests.
Task 7: complete (commits d8b6502..b286695, review clean). Minor: CORS only localhost:5173; state polls live doctor+ffprobe.
Task 8: complete (commits b286695..c399bc1, review clean). Minor: pid==1 test sentinel in production; live doctor on transcribe route.
Task 9: complete (commits c399bc1..4a67f4d, review clean). Minor: sync SSE can stall API; reject mid-stream can lose note; SKILL.md not also in The process.
Task 10: complete (commits 4a67f4d..7ad05b4, review clean after fix). Minor: leftover staging file; os.replace if player locks preview.mp4.
Task 11: complete (commits 7ad05b4..a811e0d, review clean). Minor: preview URL cache; action buttons re-enable after POST; Vite leftovers.
Task 12: complete (commits a811e0d..a148d3a, review clean after fix). Minor: no SSE unit test; duplicated reader.
Task 13: complete (commits a148d3a..4c9fe4c, review clean). Minor: uvicorn may outlive the shell.
Task 14: complete (commits 4c9fe4c..3b48794, smoke partial). Doctor+pytest+vitest+UI empty state green. ExecutionPolicy Bypass documented. Remaining: user footage → Transcribe → chat → Approve → revision → final.
Final-review fixes: 50628f7 (retry error event, preview cache-bust, acceptEdits)
All tasks complete. Tests: 45 pytest + 4 vitest passed.
Task 9: complete (commits c399bc1..4a67f4d). Minor: live doctor on chat enable; route/stream untested in-repo; pid=1 busy guard.
Final-review fixes: 50628f7 (retry error event, preview cache-bust, acceptEdits)



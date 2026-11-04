import pytest
from app import audio, jobs, tasks
from app.engine import MockEngine
from app.service import transcribe_file, plan_chunks, to_srt, to_vtt

PAT = [("tone", 3), ("sil", 1), ("tone", 2), ("sil", 1), ("tone", 4)]

@pytest.mark.parametrize("name,codec", [("a.wav", ()), ("a.mp3", ()), ("a.flac", ()),
                                        ("a.ogg", ("-c:a", "libvorbis")), ("a.m4a", ())])
def test_formats(mk, name, codec):
    r = transcribe_file(mk(name, PAT, codec), MockEngine())
    assert [(round(s["start"]), round(s["end"])) for s in r["segments"]] == [(0, 3), (4, 6), (7, 11)]
    assert r["language"] == "en" and r["stats"]["segments"] == 3

def test_long_file_offsets_no_dupes(mk):
    pat = []
    for _ in range(12): pat += [("tone", 9), ("sil", 1)]            # 120 s
    r = transcribe_file(mk("long.wav", pat), MockEngine(), min_len=20, max_len=40, overlap=2)
    assert r["chunks"] >= 3
    assert [round(s["start"]) for s in r["segments"]] == [i * 10 for i in range(12)]

def test_hard_cut_no_overlap_in_output(mk):
    r = transcribe_file(mk("t.wav", [("tone", 50)]), MockEngine(), min_len=10, max_len=20, overlap=1)
    assert r["chunks"] == 3
    segs = r["segments"]
    assert segs[0]["start"] == 0 and all(a["end"] <= b["start"] + .01 for a, b in zip(segs, segs[1:]))

def test_plan_chunks_prefers_silence():
    plan = plan_chunks(1300, [(590, 592), (880, 882)], 300, 600, 2)
    assert plan[0][1] == 591 and plan[0][3] == 593              # cut mid-silence, window +2 s overlap
    assert all(b - a <= 600 for a, b, *_ in plan)

def test_invalid_inputs(tmp_path):
    bad = tmp_path / "bad.mp3"; bad.write_bytes(b"not audio at all")
    with pytest.raises(audio.InvalidAudio): audio.inspect(bad)
    empty = tmp_path / "e.wav"; empty.write_bytes(b"")
    with pytest.raises(audio.InvalidAudio): audio.inspect(empty)

def test_srt_vtt(mk):
    r = transcribe_file(mk("a.wav", PAT), MockEngine())
    assert "00:00:04,000 --> 00:00:06,000" in to_srt(r) and to_vtt(r).startswith("WEBVTT")

def test_job_lifecycle_success(mk):
    p = mk("a.mp3", PAT)
    jid = jobs.create("a.mp3", p); tasks.run_job(jid)
    j = jobs.get(jid)
    assert j["status"] == "done" and j["progress"] == 1.0 and len(j["result"]["segments"]) == 3

def test_job_lifecycle_invalid_marks_failed(tmp_path):
    bad = tmp_path / "bad.wav"; bad.write_bytes(b"junk")
    jid = jobs.create("bad.wav", bad); tasks.run_job(jid)
    assert jobs.get(jid)["status"] == "failed"

def test_job_id_path_traversal_blocked():
    with pytest.raises(KeyError): jobs.get("../../etc/passwd")

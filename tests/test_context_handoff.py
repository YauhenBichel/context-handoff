import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from context_handoff import config, meter, prices, report, resume, transcript  # noqa: E402
from context_handoff.__main__ import main  # noqa: E402


def reply(msg_id, model="claude-opus-5-5", inp=10, w5=0, w1=0, read=0, out=100, sidechain=False):
    return {
        "type": "assistant",
        "isSidechain": sidechain,
        "message": {
            "id": msg_id,
            "model": model,
            "usage": {
                "input_tokens": inp,
                "cache_creation_input_tokens": w5 + w1,
                "cache_creation": {"ephemeral_5m_input_tokens": w5, "ephemeral_1h_input_tokens": w1},
                "cache_read_input_tokens": read,
                "output_tokens": out,
            },
        },
    }


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.cfg = config.Config(handoff_dir=str(self.dir / "notes"), state_dir=str(self.dir / "state"))
        self.cfg.notes.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def transcript(self, *records, name="t.jsonl"):
        p = self.dir / name
        with open(p, "w") as f:
            f.write(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")
            for r in records:
                f.write(json.dumps(r) + "\n")
        return str(p)

    def event(self, path, prompt="hello", session="s1"):
        return {"transcript_path": path, "session_id": session, "cwd": str(self.dir / "proj"), "prompt": prompt}


class Prices(unittest.TestCase):
    def test_longest_prefix_wins(self):
        self.assertEqual(prices.lookup("claude-opus-5-5").input, 4.0)
        self.assertEqual(prices.lookup("claude-opus-5").input, 5.0)
        self.assertEqual(prices.lookup("claude-sonnet-5-5[1m]").cache_read, 0.10)

    def test_unknown_model_falls_back(self):
        self.assertEqual(prices.lookup("something-else").model, "claude-opus-5-5")

    def test_write_multipliers(self):
        p = prices.lookup("claude-fable-5-2")
        self.assertAlmostEqual(p.write_5m, 10.0)
        self.assertAlmostEqual(p.write_1h, 16.0)


class Transcript(Base):
    def test_counts_each_reply_once_and_skips_subagents(self):
        path = self.transcript(
            reply("a", read=1000), reply("a", read=1000), reply("b", read=5000), reply("c", read=9, sidechain=True)
        )
        s = transcript.read(path)
        self.assertEqual(len(s.turns), 2)
        self.assertEqual(s.last.context, 5010)

    def test_cost(self):
        t = transcript.Turn("claude-opus-5-5", input=1_000_000, cache_write_1h=1_000_000,
                            cache_read=1_000_000, output=1_000_000)
        self.assertAlmostEqual(t.cost(prices.lookup(t.model)), 4 + 8 + 0.2 + 20)

    def test_no_ttl_breakdown_priced_as_1h(self):
        r = reply("a")
        r["message"]["usage"] = {"input_tokens": 0, "cache_creation_input_tokens": 1000, "output_tokens": 0}
        s = transcript.read(self.transcript(r))
        self.assertEqual(s.last.cache_write_1h, 1000)

    def test_missing_file(self):
        self.assertEqual(transcript.read(self.dir / "nope").turns, [])


class Meter(Base):
    def test_small_cheap_session_is_silent(self):
        path = self.transcript(reply("a", read=50_000))
        self.assertIsNone(meter.run(self.event(path), self.cfg))

    def test_big_context_asks_for_handoff_once(self):
        path = self.transcript(reply("a", read=160_000))
        out = meter.run(self.event(path), self.cfg)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertRegex(ctx, r"handoff note to .*proj-\d{8}-\d{4}\.md")
        self.assertIn("Open items and next steps", ctx)  # format taken from commands/handoff.md
        again = meter.run(self.event(path, "next"), self.cfg)
        self.assertNotIn("hookSpecificOutput", again)
        self.assertIn("160K", again["systemMessage"])

    def test_expensive_turn_triggers_even_with_small_context(self):
        # 100K tokens written to the 1-hour cache on Fable 5.2: 0.1M * $16 = $1.60
        path = self.transcript(reply("a", model="claude-fable-5-2", w1=100_000))
        out = meter.run(self.event(path), self.cfg)
        self.assertIn("last turn $1.6", out["hookSpecificOutput"]["additionalContext"])

    def test_session_total_triggers(self):
        recs = [reply(str(i), w1=50_000, out=0) for i in range(60)]  # 60 x $0.40 = $24
        self.cfg.warn_turn_usd = 0
        out = meter.run(self.event(self.transcript(*recs)), self.cfg)
        self.assertIn("session $24", out["hookSpecificOutput"]["additionalContext"])

    def test_auto_off_only_warns(self):
        self.cfg.auto_handoff = False
        out = meter.run(self.event(self.transcript(reply("a", read=160_000))), self.cfg)
        self.assertNotIn("hookSpecificOutput", out)

    def test_block(self):
        path = self.transcript(reply("a", read=410_000))
        self.assertEqual(meter.run(self.event(path), self.cfg)["decision"], "block")

    def test_block_on_turn_cost(self):
        path = self.transcript(reply("a", model="claude-fable-5-2", w1=200_000))  # $3.20
        self.assertEqual(meter.run(self.event(path), self.cfg)["decision"], "block")

    def test_bypass(self):
        path = self.transcript(reply("a", read=410_000))
        for prompt in ("handoff please", "/handoff", "/context-handoff:handoff", "go on #override"):
            out = meter.run(self.event(path, prompt), self.cfg)
            self.assertNotIn("decision", out, prompt)

    def test_zero_turns_limit_off(self):
        self.cfg.block_k = 0
        path = self.transcript(reply("a", read=410_000))
        self.assertNotIn("decision", meter.run(self.event(path), self.cfg))

    def test_cold_turn_projection(self):
        r = meter.measure(self.transcript(reply("a", read=400_000, inp=0)), self.cfg)
        self.assertAlmostEqual(r.cold_turn_usd, 3.20)

    def test_log_written(self):
        meter.run(self.event(self.transcript(reply("a", read=1000))), self.cfg)
        self.assertTrue((self.cfg.state / "meter.jsonl").read_text().strip())

    def test_missing_transcript(self):
        self.assertIsNone(meter.run({"transcript_path": "/nonexistent"}, self.cfg))


class Resume(Base):
    def note(self, name, age_s=0, text="# note\n"):
        p = self.cfg.notes / name
        p.write_text(text)
        t = time.time() - age_s
        os.utime(p, (t, t))
        return p

    def ev(self):
        return {"cwd": str(self.dir / "proj"), "source": "clear"}

    def test_nothing(self):
        self.assertIsNone(resume.run(self.ev(), self.cfg))

    def test_stale_and_other_projects_ignored(self):
        self.note("proj-20200101-0000.md", age_s=10 * 3600)
        self.note("proj-extra-20990101-0000.md")
        self.note("projx-20990101-0000.md")
        self.assertIsNone(resume.run(self.ev(), self.cfg))

    def test_newest_loaded_once(self):
        self.note("proj-20990101-0000.md", age_s=60, text="# older\n")
        self.note("proj-20990101-0100.md", text="# fresh\n")
        out = resume.run(self.ev(), self.cfg)
        self.assertIn("# fresh", out["hookSpecificOutput"]["additionalContext"])
        out = resume.run(self.ev(), self.cfg)
        self.assertIn("# older", out["hookSpecificOutput"]["additionalContext"])
        self.assertIsNone(resume.run(self.ev(), self.cfg))


class Config(unittest.TestCase):
    def test_file_and_env(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.json"
            p.write_text(json.dumps({"warn_k": 100, "auto_handoff": False,
                                     "prices": {"claude-opus-5-5": [1, 2, 0.1]}}))
            os.environ["CONTEXT_HANDOFF_WARN_TURN_USD"] = "0.75"
            try:
                cfg = config.load(p)
            finally:
                del os.environ["CONTEXT_HANDOFF_WARN_TURN_USD"]
        self.assertEqual(cfg.warn_k, 100)
        self.assertFalse(cfg.auto_handoff)
        self.assertEqual(cfg.warn_turn_usd, 0.75)
        self.assertEqual(prices.lookup("claude-opus-5-5", cfg.prices).input, 1.0)


class Cli(Base):
    def test_hook_never_fails_on_bad_input(self):
        sys.stdin = io.StringIO("not json")
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(main(["meter"]), 0)
            self.assertEqual(buf.getvalue(), "")
        finally:
            sys.stdin = sys.__stdin__

    def test_report(self):
        proj = self.dir / "projects" / "-x-proj"
        proj.mkdir(parents=True)
        (proj / "abc.jsonl").write_text(json.dumps(reply("a", w1=100_000)) + "\n")
        text = report.render(self.cfg, 7, self.dir / "projects")
        self.assertIn("1 sessions", text)
        self.assertIn("-x-proj", text)


if __name__ == "__main__":
    unittest.main()

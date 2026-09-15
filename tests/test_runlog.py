from pathlib import Path

from magnet_embed.runlog import new_run_log
from magnet_embed.state import PrinterState


def test_runlog_roundtrip_and_close(tmp_path):
    rl = new_run_log(tmp_path, "my job!!")
    rl.write("log", "hello")
    rl.write("state", None)
    rl.close()
    rl.write("after-close", "ignored")  # must not raise, must not append

    files = list(Path(tmp_path).glob("*.log"))
    assert len(files) == 1
    assert files[0].name.endswith("-myjob.log")   # name sanitised
    text = files[0].read_text()
    lines = text.splitlines()
    assert any("log hello" in line for line in lines)
    assert any(line.endswith("close") for line in lines)
    assert lines[-1] == "=== END SUMMARY ==="   # summary block is the file's tail
    assert not any("after-close" in line for line in lines)


# --- run summary -----------------------------------------------------

def test_summary_reports_completion_and_no_errors(tmp_path):
    rl = new_run_log(tmp_path, "job")
    rl.write("done", {"sent": 10, "total": 10, "sentinels": 1})
    rl.close()
    assert "lines sent: 10/10" in rl.summary_text
    assert "magnet inserts (sentinels) seen: 1" in rl.summary_text
    assert "errors: none" in rl.summary_text


def test_summary_reports_incomplete_run_when_no_done_event(tmp_path):
    rl = new_run_log(tmp_path, "job")
    rl.write("log", "cancelling")
    rl.close()
    assert "did not reach completion" in rl.summary_text


def test_summary_lists_errors(tmp_path):
    rl = new_run_log(tmp_path, "job")
    rl.write("error", "AckTimeout: no ok within 30s")
    rl.write("error", "PrinterError: MAXTEMP triggered")
    rl.close()
    assert "errors (2):" in rl.summary_text
    assert "AckTimeout: no ok within 30s" in rl.summary_text
    assert "PrinterError: MAXTEMP triggered" in rl.summary_text


def test_summary_includes_final_position_and_temps(tmp_path):
    rl = new_run_log(tmp_path, "job")
    st = PrinterState(x=60.0, y=60.0, z=6.2, nozzle_temp=219.0, nozzle_target=220.0,
                       bed_temp=69.0, bed_target=70.0)
    rl.write("state", st)
    rl.close()
    assert "final position: X60.0 Y60.0 Z6.20" in rl.summary_text
    assert "final temps: nozzle 219/220" in rl.summary_text
    assert "bed 69/70" in rl.summary_text


def test_close_is_idempotent_with_summary(tmp_path):
    rl = new_run_log(tmp_path, "job")
    rl.close()
    first = rl.summary_text
    rl.close()  # must not raise or overwrite
    assert rl.summary_text == first

from pathlib import Path

from magnet_embed.runlog import new_run_log


def test_runlog_roundtrip_and_close(tmp_path):
    rl = new_run_log(tmp_path, "my job!!")
    rl.write("log", "hello")
    rl.write("state", None)
    rl.close()
    rl.write("after-close", "ignored")  # must not raise, must not append

    files = list(Path(tmp_path).glob("*.log"))
    assert len(files) == 1
    assert files[0].name.endswith("-myjob.log")   # name sanitised
    lines = files[0].read_text().splitlines()
    assert any("log hello" in line for line in lines)
    assert lines[-1].endswith("close")
    assert not any("after-close" in line for line in lines)

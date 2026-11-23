import json, os, subprocess, sys
from pathlib import Path

BRIDGE = Path(__file__).resolve().parents[1] / "crewlink/crew_session_bridge.py"


def run(env_config, *args):
    env = dict(os.environ, CREWLINK_CONFIG=str(env_config))
    return subprocess.run([sys.executable, str(BRIDGE), *args], env=env, capture_output=True, text=True)


def test_roster_comes_from_config(tmp_path):
    cfg = tmp_path / "crew.json"
    cfg.write_text(json.dumps({"claude": ["Lead"], "gpt": ["Builder"], "command": "mycrew"}))
    help_text = run(cfg, "send", "--help").stdout
    assert "Lead" in help_text and "Builder" in help_text and "Alpha" not in help_text
    bad = run(cfg, "--state-dir", str(tmp_path / "s"), "read", "--to", "Alpha")
    assert bad.returncode == 2 and "invalid choice" in bad.stderr


def test_missing_config_refuses(tmp_path):
    result = run(tmp_path / "absent.json", "read", "--to", "x")
    assert result.returncode == 2


def test_duplicate_role_rejected(tmp_path):
    cfg = tmp_path / "crew.json"
    cfg.write_text(json.dumps({"claude": ["Ann"], "gpt": ["ann"]}))
    assert "invalid crew config" in run(cfg, "read", "--to", "Ann").stderr

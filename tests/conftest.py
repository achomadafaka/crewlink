import os
from pathlib import Path

# Tests run against a fixed eight-role roster; set before any crew module is imported.
os.environ["CREWLINK_CONFIG"] = str(Path(__file__).with_name("crew.json"))

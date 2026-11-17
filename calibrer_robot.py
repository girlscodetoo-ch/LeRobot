#!/usr/bin/env python3
"""
Calibrate a new pair of arms and save the calibration in the repo (calibration/).

The GUI (lerobot_teleop_gui_v2.py) reads the calibration files from the repo's calibration/ folder,
so a `git pull` is enough to use the same arms on another computer. A plain `lerobot-calibrate` in a
terminal writes to LeRobot's cache (~/.cache/huggingface/lerobot/calibration) instead, where the GUI
doesn't look. This script runs `lerobot-calibrate` with the repo folder as destination.

By default it uses the model, USB ports and IDs set in the GUI's settings (⚙️):
    python calibrer_robot.py                         # follower, then leader
    python calibrer_robot.py --bras follower         # only the follower
    python calibrer_robot.py --nom Chantal           # IDs Chantal_follower / Chantal_leader
    python calibrer_robot.py --follower-port COM10 --leader-port COM26 --nom Chantal

Calibrations already done in the cache are copied into the repo too (existing repo files are never
overwritten). Don't forget to commit + push the new files in calibration/ afterwards.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from test_lerobot_teleop_gui import load_config

REPO_CALIBRATION = Path(__file__).resolve().with_name("calibration")


def cache_calibration_dir():
    """LeRobot's default calibration folder (same rule as lerobot.utils.constants, minus our override)."""
    from huggingface_hub.constants import HF_HOME

    home = Path(os.getenv("HF_LEROBOT_HOME", Path(HF_HOME) / "lerobot")).expanduser()
    return home / "calibration"


def import_cache_calibrations():
    """Copy into the repo the calibration files that only exist in LeRobot's cache.

    Returns the list of copied files (relative to calibration/). The repo is the reference: a file
    already in the repo is never overwritten.
    """
    cache = cache_calibration_dir()
    if not cache.is_dir() or cache.resolve() == REPO_CALIBRATION.resolve():
        return []
    copied = []
    for src in cache.rglob("*.json"):
        rel = src.relative_to(cache)
        dst = REPO_CALIBRATION / rel
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(rel)
    return copied


def calibrate(kind, model, port, arm_id):
    """Run lerobot-calibrate for one arm ("follower" or "leader"), saving into the repo."""
    prefix = "so101" if model == "SO-101" else "so100"
    device = "robot" if kind == "follower" else "teleop"
    cmd = [
        sys.executable, "-m", "lerobot.scripts.lerobot_calibrate",
        f"--{device}.type={prefix}_{kind}",
        f"--{device}.port={port}",
        f"--{device}.id={arm_id}",
    ]
    print(f"\n=== Calibration du bras {kind} « {arm_id} » (port {port}) ===")
    print("$ " + " ".join(cmd))
    env = dict(os.environ, HF_LEROBOT_CALIBRATION=str(REPO_CALIBRATION))
    return subprocess.call(cmd, env=env)


def main():
    cfg = load_config()
    parser = argparse.ArgumentParser(description="Calibre de nouveaux bras et enregistre la calibration dans le repo.")
    parser.add_argument("--bras", choices=["both", "follower", "leader"], default="both",
                        help="bras à calibrer (défaut : les deux)")
    parser.add_argument("--nom", help="nom du robot : IDs <nom>_follower et <nom>_leader")
    parser.add_argument("--modele", choices=["SO-100", "SO-101"], default=cfg.get("robot_model", "SO-101"))
    parser.add_argument("--follower-port", default=cfg["follower_port"])
    parser.add_argument("--leader-port", default=cfg["leader_port"])
    parser.add_argument("--follower-id", default=cfg["follower_id"])
    parser.add_argument("--leader-id", default=cfg["leader_id"])
    args = parser.parse_args()

    if args.nom:
        args.follower_id = f"{args.nom}_follower"
        args.leader_id = f"{args.nom}_leader"

    copied = import_cache_calibrations()
    if copied:
        print("Calibrations copiées du cache LeRobot vers calibration/ :")
        for rel in copied:
            print(f"  {rel}")

    arms = []
    if args.bras in ("both", "follower"):
        arms.append(("follower", args.follower_port, args.follower_id))
    if args.bras in ("both", "leader"):
        arms.append(("leader", args.leader_port, args.leader_id))

    for kind, port, arm_id in arms:
        code = calibrate(kind, args.modele, port, arm_id)
        if code != 0:
            print(f"\nLa calibration du bras {kind} a échoué (code {code}). Vérifie le port USB et l'alimentation.")
            return code

    print(f"\nCalibration enregistrée dans {REPO_CALIBRATION}")
    print("Pense à faire un commit + push des nouveaux fichiers pour les autres ordinateurs.")
    if (args.follower_id, args.leader_id) != (cfg["follower_id"], cfg["leader_id"]):
        print(f"Dans l'interface (⚙️), mets les IDs : follower = {args.follower_id}, leader = {args.leader_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

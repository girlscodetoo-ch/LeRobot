#!/usr/bin/env python3
"""
Compare teleoperation vs replay

1. TELEOP : you move the leader arm, the follower copies it. For each step we save
   the action sent (leader angles) and the angles really measured on the follower.
2. REPLAY : the follower goes back to the start position, then the saved actions are
   sent again at the same FPS. We save again the angles measured on the follower.
3. PLOT   : one subplot per motor, teleop vs replay on the same graph, with the RMSE.

The data are saved in CSV files (outputs/teleop_vs_replay/) so you can re-plot later.
At the end, the graphs (all the motors + one graph per motor) are saved in output/<date_heure>/.

ToDo before  : pip install -e ".[matplotlib-dep]"
Launch :
    python compare_teleop_replay.py            # teleop + replay + plot
    python compare_teleop_replay.py teleop     # only record the teleop
    python compare_teleop_replay.py replay     # only replay the last teleop recorded
    python compare_teleop_replay.py plot       # only plot the saved CSV
"""

import argparse
import csv
import time
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig

# --- ADAPT ---
FOLLOWER_PORT = "COM3"
FOLLOWER_ID = "Carol_follower_first_lerobot"
LEADER_PORT = "COM4"
LEADER_ID = "Carol_leader_first_lerobot"

FPS = 30
DURATION_S = 15.0  # duration of the teleop sequence (Ctrl+C to stop before)
GO_TO_START_S = 3.0  # time to go smoothly back to the start position before the replay

OUTPUT_DIR = Path("outputs/teleop_vs_replay")
TELEOP_CSV = OUTPUT_DIR / "teleop.csv"
REPLAY_CSV = OUTPUT_DIR / "replay.csv"
GRAPH_DIR = Path("output")  # the graphs are saved in output/<date_heure>/

MOTOR_COLORS = {
    "shoulder_pan": "#2a78d6",  # bleu
    "shoulder_lift": "#eb6834",  # orange
    "elbow_flex": "#1baf7a",  # aqua
    "wrist_flex": "#eda100",  # jaune
    "wrist_roll": "#e87ba4",  # magenta
    "gripper": "#008300",  # vert
}


def wait_next_step(loop_start):
    time.sleep(max(1.0 / FPS - (time.perf_counter() - loop_start), 0.0))


def save_csv(path, rows, motor_names):
    """rows = list of (t, action_dict, obs_dict)"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["t"] + [f"action.{m}" for m in motor_names] + [f"obs.{m}" for m in motor_names]
        )
        for t, action, obs in rows:
            writer.writerow(
                [f"{t:.4f}"]
                + [f"{action[f'{m}.pos']:.4f}" for m in motor_names]
                + [f"{obs[f'{m}.pos']:.4f}" for m in motor_names]
            )
    print(f"Saved {len(rows)} steps in {path}")


def load_csv(path):
    """Return (t, actions, obs, motor_names) with actions/obs = {motor: np.array}"""
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        data = list(reader)
    motor_names = [c.removeprefix("obs.") for c in reader.fieldnames if c.startswith("obs.")]
    t = np.array([float(r["t"]) for r in data])
    actions = {m: np.array([float(r[f"action.{m}"]) for r in data]) for m in motor_names}
    obs = {m: np.array([float(r[f"obs.{m}"]) for r in data]) for m in motor_names}
    return t, actions, obs, motor_names


def connect_follower():
    follower = SO101Follower(SO101FollowerConfig(port=FOLLOWER_PORT, id=FOLLOWER_ID))
    follower.connect()
    return follower


# ---------------------------------------------------------------- TELEOP
def record_teleop(follower):
    leader = SO101Leader(SO101LeaderConfig(port=LEADER_PORT, id=LEADER_ID))
    leader.connect()
    motor_names = list(follower.bus.motors.keys())

    input("\n[TELEOP] Press Enter to start the recording, then move the leader arm...")
    print(f"Recording for {DURATION_S:.0f} s (Ctrl+C to stop before)")

    rows = []
    t_start = time.perf_counter()
    try:
        while time.perf_counter() - t_start < DURATION_S:
            loop_start = time.perf_counter()
            action = leader.get_action()
            sent_action = follower.send_action(action)
            obs = follower.get_observation()
            rows.append((time.perf_counter() - t_start, sent_action, obs))
            wait_next_step(loop_start)
    except KeyboardInterrupt:
        print("\nRecording stopped by the user.")
    finally:
        leader.disconnect()

    save_csv(TELEOP_CSV, rows, motor_names)


# ---------------------------------------------------------------- REPLAY
def go_to_start(follower, start_action, motor_names):
    """Go smoothly (linear interpolation) from the current position to the start position."""
    obs = follower.get_observation()
    current = {m: obs[f"{m}.pos"] for m in motor_names}
    n_steps = max(int(GO_TO_START_S * FPS), 1)
    for i in range(1, n_steps + 1):
        loop_start = time.perf_counter()
        alpha = i / n_steps
        action = {
            f"{m}.pos": (1 - alpha) * current[m] + alpha * start_action[f"{m}.pos"] for m in motor_names
        }
        follower.send_action(action)
        wait_next_step(loop_start)
    time.sleep(0.5)  # let the motors stabilise


def replay(follower):
    t_rec, actions, _, motor_names = load_csv(TELEOP_CSV)
    n = len(t_rec)
    recorded_actions = [{f"{m}.pos": float(actions[m][i]) for m in motor_names} for i in range(n)]

    input("\n[REPLAY] Put the leader arm away. Press Enter to go to the start position...")
    go_to_start(follower, recorded_actions[0], motor_names)

    print(f"Replaying {n} steps...")
    rows = []
    t_start = time.perf_counter()
    try:
        for i, action in enumerate(recorded_actions):
            # wait until the same time as during the teleop, to keep the same timing
            while time.perf_counter() - t_start < t_rec[i]:
                time.sleep(0.001)
            sent_action = follower.send_action(action)
            obs = follower.get_observation()
            rows.append((time.perf_counter() - t_start, sent_action, obs))
    except KeyboardInterrupt:
        print("\nReplay stopped by the user.")

    save_csv(REPLAY_CSV, rows, motor_names)


# ---------------------------------------------------------------- PLOT
def plot_motor(ax, m, t_tel, act_tel, obs_tel, t_rep, obs_rep):
    """Draw the 3 curves of one motor on ax and return the RMSE teleop vs replay."""
    color = MOTOR_COLORS.get(m, "#444444")
    ax.set_facecolor("#fcfcfb")
    ax.plot(t_tel, act_tel[m], color="#9a9a9a", linewidth=1, linestyle=":", label="commande (leader)")
    ax.plot(t_tel, obs_tel[m], color=color, linewidth=2, label="teleop (follower)")
    ax.plot(t_rep, obs_rep[m], color="#222222", linewidth=1.3, linestyle="--", label="replay (follower)")

    # RMSE on the same time base (interpolate the replay on the teleop times)
    rep_on_tel = np.interp(t_tel, t_rep, obs_rep[m])
    rmse = float(np.sqrt(np.mean((rep_on_tel - obs_tel[m]) ** 2)))

    unit = "%" if m == "gripper" else "deg"
    ax.set_title(f"{m}  (RMSE = {rmse:.2f} {unit})", fontsize=10)
    ax.set_ylabel(unit)
    ax.grid(True, color="#e1e0d9", linewidth=0.5)
    return rmse


def plot():
    t_tel, act_tel, obs_tel, motor_names = load_csv(TELEOP_CSV)
    t_rep, _, obs_rep, _ = load_csv(REPLAY_CSV)
    curves = (t_tel, act_tel, obs_tel, t_rep, obs_rep)

    # --- figure with all the motors
    n_cols = 2
    n_rows = int(np.ceil(len(motor_names) / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(14, 3.2 * n_rows), sharex=True)
    fig.patch.set_facecolor("#fcfcfb")
    axes = np.array(axes).reshape(-1)

    print("\nRMSE teleop vs replay (follower angles) :")
    for ax, m in zip(axes, motor_names, strict=False):
        rmse = plot_motor(ax, m, *curves)
        print(f"  {m:15s} {rmse:6.2f}")

    for ax in axes[len(motor_names) :]:
        ax.set_visible(False)
    for ax in axes[-n_cols:]:
        ax.set_xlabel("temps (s)")

    axes[0].legend(loc="upper right", fontsize=8)
    fig.suptitle("Angles des moteurs : teleoperation vs replay")
    fig.tight_layout()

    # --- save the graphs in output/<date_heure>/
    graph_dir = GRAPH_DIR / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    graph_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(graph_dir / "all_motors.png", dpi=150)

    for m in motor_names:
        fig_m, ax_m = plt.subplots(figsize=(10, 4))
        fig_m.patch.set_facecolor("#fcfcfb")
        plot_motor(ax_m, m, *curves)
        ax_m.set_xlabel("temps (s)")
        ax_m.legend(loc="upper right", fontsize=8)
        fig_m.tight_layout()
        fig_m.savefig(graph_dir / f"{m}.png", dpi=150)
        plt.close(fig_m)

    print(f"Graphs saved in {graph_dir.resolve()}")
    plt.show()


# ---------------------------------------------------------------- MAIN
def main():
    parser = argparse.ArgumentParser(description="Compare the motor angles in teleop and in replay.")
    parser.add_argument("mode", nargs="?", default="all", choices=["all", "teleop", "replay", "plot"])
    mode = parser.parse_args().mode

    if mode in ("all", "teleop", "replay"):
        follower = connect_follower()
        try:
            if mode in ("all", "teleop"):
                record_teleop(follower)
            if mode in ("all", "replay"):
                replay(follower)
        finally:
            follower.disconnect()

    if mode in ("all", "plot"):
        plot()


if __name__ == "__main__":
    main()

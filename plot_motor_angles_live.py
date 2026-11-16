#!/usr/bin/env python3
"""
Plot 2D 

This script do the teleoperation of the S0-101 arm and print in real time the angle of each motor.

ToDo before  : pip install -e ".[matplotlib-dep]"
Launch :  python plot_motor_angles_live.py
"""

import time
from collections import deque

import matplotlib.pyplot as plt

from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig

# --- ADAPT ---
FOLLOWER_PORT = "COM3"
FOLLOWER_ID = "Carol_follower_first_lerobot"
LEADER_PORT = "COM4"
LEADER_ID = "Carol_leader_first_lerobot"

FPS = 30
WINDOW_S = 20.0  # how long the window stay 

MOTOR_COLORS = {
    "shoulder_lift": "#eb6834",  # orange
    "elbow_flex": "#1baf7a",  # aqua
    "wrist_flex": "#eda100",  # jaune
    "wrist_roll": "#e87ba4",  # magenta
    "gripper": "#008300",  # vert
}


def main():
    follower = SO101Follower(SO101FollowerConfig(port=FOLLOWER_PORT, id=FOLLOWER_ID))
    leader = SO101Leader(SO101LeaderConfig(port=LEADER_PORT, id=LEADER_ID))
    follower.connect()
    leader.connect()

    motor_names = list(follower.bus.motors.keys())
    max_points = int(WINDOW_S * FPS)
    times = deque(maxlen=max_points)
    angles = {name: deque(maxlen=max_points) for name in motor_names}

    plt.ion()
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    lines = {
        name: ax.plot([], [], label=name, color=MOTOR_COLORS.get(name, MOTOR_COLORS.get(f"{name}.pos")), linewidth=2)[0]
        for name in motor_names
    }
    ax.set_xlabel("temps (s)")
    ax.set_ylabel("angle (deg) / ouverture gripper (%)")
    ax.set_title("Angles des moteurs en temps reel")
    ax.legend(loc="upper left", ncol=3, fontsize=9)
    ax.grid(True, color="#e1e0d9", linewidth=0.5)

    t_start = time.perf_counter()
    print("Teleoperation running : you can move the leader arm")
    print("Close the window to stop the script")

    try:
        while plt.fignum_exists(fig.number):
            loop_start = time.perf_counter()

            action = leader.get_action()
            follower.send_action(action)
            obs = follower.get_observation()

            t = time.perf_counter() - t_start
            times.append(t)
            for name in motor_names:
                angles[name].append(obs[f"{name}.pos"])

            if len(times) >= 2:
                for name in motor_names:
                    lines[name].set_data(times, angles[name])
                ax.set_xlim(times[0], times[-1])
                ax.relim()
                ax.autoscale_view(scalex=False, scaley=True)

            fig.canvas.draw_idle()
            fig.canvas.flush_events()

            time.sleep(max(1.0 / FPS - (time.perf_counter() - loop_start), 0.0))
    except KeyboardInterrupt:
        pass
    finally:
        follower.disconnect()
        leader.disconnect()
        print("\nTeleoperation stopped.")


if __name__ == "__main__":
    main()

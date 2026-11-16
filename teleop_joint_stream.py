#!/usr/bin/env python3
"""
Runs `lerobot-teleoperate` unchanged, and also prints the follower arm's joint
positions on stdout, about 15 times per second, as lines like:

    JOINTS {"shoulder_pan": 12.3, "shoulder_lift": -45.0, ..., "gripper": 31.2}

Angles are in degrees, the gripper opening in % (0-100). `lerobot_teleop_gui_v2.py`
launches teleoperation through this script to show the joint angles live: the USB
ports are owned by the teleoperation process, so the GUI can't read the motors itself.

Takes exactly the same arguments as `lerobot-teleoperate`:
    python teleop_joint_stream.py --robot.type=so101_follower --robot.port=COM3 ...
"""

import json
import time

from lerobot.scripts import lerobot_teleoperate

STREAM_HZ = 15

_make_robot_from_config = lerobot_teleoperate.make_robot_from_config


def _make_streaming_robot(config):
    """Same robot, but each observation also prints its joint positions (rate-limited)."""
    robot = _make_robot_from_config(config)
    get_observation = robot.get_observation
    last_print = 0.0

    def get_observation_and_stream():
        nonlocal last_print
        obs = get_observation()
        now = time.perf_counter()
        if now - last_print >= 1 / STREAM_HZ:
            last_print = now
            joints = {
                key.removesuffix(".pos"): round(float(value), 2)
                for key, value in obs.items()
                if key.endswith(".pos")
            }
            # Leading newline: the teleop loop moves the cursor without ending its line
            print("\nJOINTS " + json.dumps(joints), flush=True)
        return obs

    robot.get_observation = get_observation_and_stream
    return robot


lerobot_teleoperate.make_robot_from_config = _make_streaming_robot

if __name__ == "__main__":
    lerobot_teleoperate.main()

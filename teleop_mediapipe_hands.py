#!/usr/bin/env python3
"""
Control the SO-100 / SO-101 follower arm with your hand, seen by a webcam (MediaPipe Hands).

    Move the hand left / right        -> shoulder_pan   (the arm turns)
    Move the hand up / down           -> shoulder_lift  (the arm rises / lowers)
    Move the hand closer / farther    -> elbow_flex     (the arm reaches out / folds)
    Tilt the fingers toward the camera-> wrist_flex
    Turn the hand like a steering wheel -> wrist_roll
    Pinch thumb and index together    -> gripper closes (open them to open it)

Works like a clutch, so the arm never jumps: press SPACE to take control. The hand position at
that moment becomes the reference, and the arm follows the hand's *movements* from where it is.
Press SPACE again to pause (then move your hand back to a comfortable spot and press SPACE again).
If the hand leaves the camera view, the arm stays still.

Keys (in the camera window):  SPACE = take control / pause    Q or Esc = quit
On quit, the arm slowly goes back to its starting position before disconnecting
(hold it: the motors are released when the program ends).

The USB port, arm id and model come from the teleoperation GUI settings (~/.lerobot_teleop_gui.json).
Close the GUI (or stop its teleoperation) first: only one program can use the arm at a time.

Install once (in the LeRobot environment):
    uv pip install --no-deps mediapipe absl-py flatbuffers cffi pycparser sounddevice
    (--no-deps keeps your current OpenCV: mediapipe would otherwise add a second, conflicting one)

Launch:
    python teleop_mediapipe_hands.py              # control the robot
    python teleop_mediapipe_hands.py --dry-run    # no robot: just see the hand tracking and targets
    python teleop_mediapipe_hands.py --camera 1   # another webcam (default: the one chosen in the GUI settings)

It can also be started from the teleoperation GUI (hand control button). The GUI then stops it by
writing "quit" on its standard input, so the arm still goes back to its starting position.
"""

import argparse
import json
import math
import os
import sys
import threading
import time
import tkinter as tk
import traceback
import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision
from PIL import Image, ImageTk

from test_lerobot_teleop_gui import load_config

# Same calibration files as the GUI: the ones in the repo (calibration/)
os.environ.setdefault("HF_LEROBOT_CALIBRATION", str(Path(__file__).with_name("calibration")))

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/"
    "hand_landmarker.task"
)
MODEL_PATH = Path(__file__).with_name("hand_landmarker.task")

JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]

# How each joint follows the hand: (hand feature, degrees per unit of that feature).
# Flip the sign of a gain if a joint moves the wrong way on your arm.
#   x, y   : hand position in the image, 0..1 (x to the right, y downward)
#   depth  : log of the hand's apparent size ratio (+0.3 ~ hand 35% closer to the camera)
#   pitch, roll : hand angles in degrees
GAINS = {
    "shoulder_pan": ("x", -120.0),
    "shoulder_lift": ("y", 110.0),
    "elbow_flex": ("depth", -120.0),
    "wrist_flex": ("pitch", 1.0),
    "wrist_roll": ("roll", 1.0),
}
# Gripper: absolute, from the thumb-index distance (relative to the palm size)
PINCH_CLOSED, PINCH_OPEN = 0.25, 1.1  # pinch ratio for "fully closed" / "fully open"
GRIPPER_CLOSED, GRIPPER_OPEN = 0.0, 60.0  # gripper opening in %, swap them if it's reversed

SAFE_RANGE = 0.85  # fraction of each joint's calibrated half-range the arm is allowed to use
MAX_STEP_DEG = 4.0  # max movement per frame and per joint (~120 deg/s at 30 fps)
SMOOTHING = 0.35  # 0..1, lower = smoother but slower to react

# MediaPipe hand landmark indices
WRIST, THUMB_TIP, INDEX_MCP, INDEX_TIP, MIDDLE_MCP, PINKY_MCP = 0, 4, 5, 8, 9, 17


def ensure_model():
    if not MODEL_PATH.exists():
        print(f"Downloading the MediaPipe hand model to {MODEL_PATH} ...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    return MODEL_PATH


def wrap_deg(angle):
    return (angle + 180.0) % 360.0 - 180.0


def hand_features(landmarks, world_landmarks, aspect):
    """Hand position / size / angles from MediaPipe landmarks (image already mirrored)."""
    pts = np.array([[p.x * aspect, p.y] for p in landmarks])  # aspect-corrected image coordinates
    palm = pts[[WRIST, INDEX_MCP, MIDDLE_MCP, PINKY_MCP]].mean(axis=0)
    palm_length = np.linalg.norm(pts[MIDDLE_MCP] - pts[WRIST])
    palm_width = np.linalg.norm(pts[PINKY_MCP] - pts[INDEX_MCP])
    size = palm_length + palm_width

    across = pts[PINKY_MCP] - pts[INDEX_MCP]
    roll = math.degrees(math.atan2(across[1], across[0]))

    w = np.array([[p.x, p.y, p.z] for p in world_landmarks])  # metric, centered on the hand
    up = w[MIDDLE_MCP] - w[WRIST]
    pitch = math.degrees(math.atan2(-up[2], -up[1]))  # 0 = fingers up, + = fingers toward the camera

    pinch = np.linalg.norm(pts[THUMB_TIP] - pts[INDEX_TIP]) / max(palm_length, 1e-6)
    return {"x": palm[0] / aspect, "y": palm[1], "size": size, "pitch": pitch, "roll": roll, "pinch": pinch}


class HandMapper:
    """Turns hand features into joint targets, relative to the pose captured when control starts."""

    def __init__(self, limits):
        self.limits = limits  # joint -> (low, high) in degrees (gripper in %)
        self.ref = None
        self.base = None
        self.filtered = None

    def engage(self, features, robot_pose):
        self.ref = dict(features)
        self.base = dict(robot_pose)
        self.filtered = {"x": 0.0, "y": 0.0, "depth": 0.0, "pitch": 0.0, "roll": 0.0, "pinch": features["pinch"]}

    def targets(self, features):
        deltas = {
            "x": features["x"] - self.ref["x"],
            "y": features["y"] - self.ref["y"],
            "depth": math.log(features["size"] / self.ref["size"]),
            "pitch": wrap_deg(features["pitch"] - self.ref["pitch"]),
            "roll": wrap_deg(features["roll"] - self.ref["roll"]),
            "pinch": features["pinch"],
        }
        for key, value in deltas.items():  # exponential smoothing against hand-tracking jitter
            self.filtered[key] += SMOOTHING * (value - self.filtered[key])

        out = {}
        for joint, (feature, gain) in GAINS.items():
            out[joint] = self.base[joint] + gain * self.filtered[feature]
        t = (self.filtered["pinch"] - PINCH_CLOSED) / (PINCH_OPEN - PINCH_CLOSED)
        out["gripper"] = GRIPPER_CLOSED + min(1.0, max(0.0, t)) * (GRIPPER_OPEN - GRIPPER_CLOSED)
        return {j: float(min(self.limits[j][1], max(self.limits[j][0], v))) for j, v in out.items()}


def step_towards(current, target, max_step):
    return {j: current[j] + max(-max_step, min(max_step, target[j] - current[j])) for j in current}


def joint_limits(robot):
    """Allowed range of each joint, from the arm's calibration (positions are centered on 0 deg)."""
    limits = {}
    for joint in JOINTS:
        cal = robot.bus.calibration[joint]
        if joint == "gripper":
            limits[joint] = (0.0, 100.0)
        else:
            half = (cal.range_max - cal.range_min) / 2 * 360 / 4095
            limits[joint] = (-half * SAFE_RANGE, half * SAFE_RANGE)
    return limits


def connect_robot(cfg):
    from lerobot.robots.so_follower import SO100Follower, SO101Follower, SO101FollowerConfig

    robot_cls = SO100Follower if cfg.get("robot_model") == "SO-100" else SO101Follower
    robot = robot_cls(SO101FollowerConfig(
        port=cfg["follower_port"], id=cfg["follower_id"],
        max_relative_target=MAX_STEP_DEG * 2,  # extra safety net inside LeRobot itself
    ))
    robot.connect()
    return robot


def read_pose(robot):
    obs = robot.get_observation()
    return {j: float(obs[f"{j}.pos"]) for j in JOINTS}


def draw(frame, landmarks, status, color, pose):
    h, w = frame.shape[:2]
    if landmarks:
        pts = [(int(p.x * w), int(p.y * h)) for p in landmarks]
        for c in vision.HandLandmarksConnections.HAND_CONNECTIONS:
            cv2.line(frame, pts[c.start], pts[c.end], (255, 255, 255), 2, cv2.LINE_AA)
        for p in pts:
            cv2.circle(frame, p, 4, (122, 69, 232), -1, cv2.LINE_AA)
        cv2.line(frame, pts[THUMB_TIP], pts[INDEX_TIP], (0, 200, 255), 2, cv2.LINE_AA)

    cv2.rectangle(frame, (0, 0), (w, 44), (40, 30, 45), -1)
    cv2.putText(frame, status, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2, cv2.LINE_AA)
    cv2.putText(frame, "SPACE: control / pause   Q: quit", (12, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (255, 255, 255), 1, cv2.LINE_AA)
    if pose:
        for i, joint in enumerate(JOINTS):
            unit = "%" if joint == "gripper" else "deg"
            cv2.putText(frame, f"{joint:13s} {pose[joint]:7.1f} {unit}", (w - 250, 70 + 22 * i),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--camera", type=int, default=None,
                        help="webcam index (default: the one chosen in the GUI settings, else 0)")
    parser.add_argument("--dry-run", action="store_true", help="no robot: only show the tracking and targets")
    parser.add_argument("--stream-joints", action="store_true",
                        help="print the joint targets as 'JOINTS {...}' lines (used by the GUI's joint window)")
    args = parser.parse_args()
    cfg = load_config()
    camera = args.camera if args.camera is not None else int(cfg.get("hand_camera", 0))

    # Started from the GUI: a "quit" line on stdin asks for a clean stop (arm back home, then disconnect)
    quit_requested = threading.Event()
    if sys.stdin is not None and not sys.stdin.isatty():
        def listen_stdin():
            for line in sys.stdin:
                if line.strip().lower() == "quit":
                    quit_requested.set()
                    return

        threading.Thread(target=listen_stdin, daemon=True).start()

    landmarker = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(ensure_model())),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.6,
        min_tracking_confidence=0.5,
    ))

    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    cap = cv2.VideoCapture(camera, backend)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        sys.exit(f"Could not open webcam {camera}. Choose another one in the GUI settings, or use --camera.")

    robot = None
    if args.dry_run:
        limits = {j: (-90.0, 90.0) for j in JOINTS} | {"gripper": (0.0, 100.0)}
        pose = {j: 0.0 for j in JOINTS}
    else:
        print(f"Connecting to the follower arm on {cfg['follower_port']} ...")
        robot = connect_robot(cfg)
        limits = joint_limits(robot)
        pose = read_pose(robot)
    start_pose = dict(pose)
    mapper = HandMapper(limits)
    engaged = False
    start = time.perf_counter()

    # LeRobot uses the "headless" build of OpenCV, which can't open windows (no cv2.imshow):
    # the frames are shown in a Tk window instead (cv2 still draws the overlay on them).
    root = tk.Tk()
    root.title("LeRobot - hand control")
    root.configure(bg="black")
    view = tk.Label(root, bg="black")
    view.pack()
    space_pressed = []
    root.bind("<KeyPress-space>", lambda e: space_pressed.append(True))
    for key in ("q", "Q", "Escape"):
        root.bind(f"<KeyPress-{key}>", lambda e: root.quit())
    root.protocol("WM_DELETE_WINDOW", root.quit)

    ready_announced = False
    last_stream = 0.0

    def tick():
        nonlocal pose, engaged, ready_announced, last_stream
        try:
            if quit_requested.is_set():
                root.quit()
                return
            ok, frame = cap.read()
            if not ok:
                print("Webcam frame not received, stopping.")
                root.quit()
                return
            frame = cv2.flip(frame, 1)  # mirror: moving your hand right moves it right on screen
            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb),
                                                 int((time.perf_counter() - start) * 1000))
            hand = result.hand_landmarks[0] if result.hand_landmarks else None
            features = hand_features(hand, result.hand_world_landmarks[0], w / h) if hand else None

            if space_pressed:
                space_pressed.clear()
                if engaged:
                    engaged = False
                elif features:
                    if robot:
                        pose = read_pose(robot)  # start from where the arm really is
                    mapper.engage(features, pose)
                    engaged = True

            if not engaged:
                status, color = ("Hand found - press SPACE to take control", (0, 220, 255)) if features else \
                    ("Show your hand to the camera", (200, 200, 200))
            elif not features:
                status, color = "Hand lost - the arm waits", (0, 165, 255)
            else:
                status, color = "CONTROL ON - move your hand", (80, 220, 80)
                pose = step_towards(pose, mapper.targets(features), MAX_STEP_DEG)
                if robot:
                    robot.send_action({f"{j}.pos": v for j, v in pose.items()})

            draw(frame, hand, status, color, pose)
            photo = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
            view.configure(image=photo)
            view.image = photo  # keep a reference, or Tk drops the image
            if not ready_announced:  # the GUI waits for this line before saying "hand control on"
                print("HAND_CONTROL_READY", flush=True)
                ready_announced = True
            if args.stream_joints and time.perf_counter() - last_stream >= 1 / 15:
                last_stream = time.perf_counter()
                print("JOINTS " + json.dumps({j: round(v, 2) for j, v in pose.items()}), flush=True)
            root.after(1, tick)
        except Exception:
            traceback.print_exc()
            root.quit()  # stop cleanly: the arm still goes back and disconnects below

    try:
        root.after(0, tick)
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
        cap.release()
        landmarker.close()
        if robot:
            print("Going back to the starting position ...")
            try:
                for _ in range(150):  # at most ~5 s
                    pose = step_towards(pose, start_pose, MAX_STEP_DEG / 2)
                    robot.send_action({f"{j}.pos": v for j, v in pose.items()})
                    if all(abs(pose[j] - start_pose[j]) < 0.5 for j in JOINTS):
                        break
                    time.sleep(1 / 30)
            finally:
                robot.disconnect()
                print("Arm disconnected.")


if __name__ == "__main__":
    main()

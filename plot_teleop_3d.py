#!/usr/bin/env python3
"""
Plot 3D - Trajectoire du gripper pendant une teleoperation (SO-101)
=====================================================================

Ce script teleoperate le bras SO-101 (leader -> follower) exactement comme
`test_move.py`, mais en plus il enregistre la position (x, y, z) du gripper
a chaque instant (calculee par cinematique directe a partir des angles des
moteurs) et affiche, une fois la teleoperation arretee (Ctrl+C), un graphique
3D du chemin parcouru.

Prerequis (une seule fois) :
    pip install -e ".[kinematics]"     # installe placo, utilise pour la cinematique
    pip install -e ".[matplotlib-dep]" # installe matplotlib, utilise pour le graphique

Le modele 3D du bras (fichier URDF) est telecharge automatiquement depuis
Hugging Face au premier lancement et mis en cache.

Lancement :
    python plot_teleop_3d.py
"""

import time

import numpy as np

from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig
from lerobot.utils.constants import HF_LEROBOT_HOME

# --- A adapter a ton installation (memes valeurs que dans test_move.py) ---
FOLLOWER_PORT = "COM3"
FOLLOWER_ID = "Carol_follower_first_lerobot"
LEADER_PORT = "COM4"
LEADER_ID = "Carol_leader_first_lerobot"

FPS = 30
TARGET_FRAME_NAME = "gripper_frame_link"

# Rampe sequentielle "bleu" (une seule teinte, du clair au fonce) utilisee
# pour colorer la trajectoire en fonction du temps ecoule.
TIME_COLOR_RAMP = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]


def ensure_so101_urdf() -> str:
    """Renvoie le chemin du fichier URDF du SO-101 (le telecharge au premier appel)."""
    dest_dir = HF_LEROBOT_HOME / "robot-urdfs" / "so101"
    urdf_path = dest_dir / "so101_new_calib.urdf"
    marker = dest_dir / ".sync_complete"
    if not marker.exists():
        from huggingface_hub import sync_bucket

        print("Telechargement du modele 3D (URDF) du SO-101 (une seule fois)...")
        sync_bucket("hf://buckets/lerobot/robot-urdfs/so101", str(dest_dir), quiet=True)
        marker.touch()
    return str(urdf_path)


def main():
    try:
        from lerobot.model.kinematics import RobotKinematics
    except ImportError as e:
        raise ImportError(
            "La cinematique directe necessite 'placo'. Installe-le avec :\n"
            '    pip install -e ".[kinematics]"'
        ) from e

    follower = SO101Follower(SO101FollowerConfig(port=FOLLOWER_PORT, id=FOLLOWER_ID))
    leader = SO101Leader(SO101LeaderConfig(port=LEADER_PORT, id=LEADER_ID))
    follower.connect()
    leader.connect()

    motor_names = list(follower.bus.motors.keys())
    kinematics = RobotKinematics(
        urdf_path=ensure_so101_urdf(),
        target_frame_name=TARGET_FRAME_NAME,
        joint_names=motor_names,
    )

    positions = []  # (x, y, z) en metres, un point par frame
    timestamps = []  # secondes depuis le debut de l'enregistrement
    t_start = time.perf_counter()

    print("Teleoperation en cours : bouge le bras leader.")
    print("Appuie sur Ctrl+C pour arreter et afficher le graphique 3D.")
    try:
        while True:
            loop_start = time.perf_counter()

            action = leader.get_action()
            follower.send_action(action)

            obs = follower.get_observation()
            joint_pos = np.array([obs[f"{name}.pos"] for name in motor_names], dtype=float)
            ee_pose = kinematics.forward_kinematics(joint_pos)
            positions.append(ee_pose[:3, 3].copy())
            timestamps.append(time.perf_counter() - t_start)

            time.sleep(max(1.0 / FPS - (time.perf_counter() - loop_start), 0.0))
    except KeyboardInterrupt:
        print("\nTeleoperation arretee.")
    finally:
        follower.disconnect()
        leader.disconnect()

    if len(positions) < 2:
        print("Pas assez de mouvement enregistre pour tracer un graphique.")
        return

    plot_trajectory_3d(np.array(positions), np.array(timestamps))


def plot_trajectory_3d(positions: np.ndarray, timestamps: np.ndarray) -> None:
    try:
        import matplotlib.pyplot as plt
        from matplotlib.colors import LinearSegmentedColormap
        from mpl_toolkits.mplot3d.art3d import Line3DCollection
    except ImportError as e:
        raise ImportError(
            'matplotlib est requis pour le graphique. Installe-le avec :\n    pip install -e ".[matplotlib-dep]"'
        ) from e

    x, y, z = positions[:, 0], positions[:, 1], positions[:, 2]
    cmap = LinearSegmentedColormap.from_list("time_blue", TIME_COLOR_RAMP)

    fig = plt.figure(figsize=(9, 7))
    fig.patch.set_facecolor("#fcfcfb")
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("#fcfcfb")

    # Segments de la trajectoire, colores du plus clair (debut) au plus fonce (fin).
    points = np.stack([x, y, z], axis=1)
    segments = np.stack([points[:-1], points[1:]], axis=1)
    line_collection = Line3DCollection(segments, cmap=cmap, linewidths=2)
    line_collection.set_array(timestamps[:-1])
    ax.add_collection3d(line_collection)

    ax.text(x[0], y[0], z[0], "Depart", color="#52514e", fontsize=9)
    ax.text(x[-1], y[-1], z[-1], "Fin", color="#52514e", fontsize=9)
    ax.scatter([x[0], x[-1]], [y[0], y[-1]], [z[0], z[-1]], color="#0d366b", s=25)

    ax.set_xlim(x.min(), x.max())
    ax.set_ylim(y.min(), y.max())
    ax.set_zlim(z.min(), z.max())
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_zlabel("z (m)")
    ax.set_title("Trajectoire du gripper pendant la teleoperation")

    mappable = plt.cm.ScalarMappable(cmap=cmap)
    mappable.set_array(timestamps)
    cbar = fig.colorbar(mappable, ax=ax, shrink=0.6, pad=0.1)
    cbar.set_label("temps (s)")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()

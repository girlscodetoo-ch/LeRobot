"""
Plot 3D - Trajectoire du gripper pendant une teleoperation (SO-101)
=====================================================================

Ce script teleoperate le bras SO-101 (leader -> follower) exactement comme
`test_move.py`, mais en plus il enregistre la position (x, y, z) du gripper
a chaque instant (calculee par cinematique directe a partir des angles des
moteurs) et affiche, une fois la teleoperation arretee (Ctrl+C), un graphique
3D du chemin parcouru.

Version compatible Windows : la cinematique directe est calculee directement
a partir du fichier URDF, en Python pur (numpy + bibliotheque standard).
Plus besoin de 'placo', qui ne s'installe pas sous Windows.

Prerequis (une seule fois) :
    pip install -e ".[matplotlib-dep]" # installe matplotlib, utilise pour le graphique

Le modele 3D du bras (fichier URDF) est telecharge automatiquement depuis
Hugging Face au premier lancement et mis en cache.

Lancement :
    python plot_teleop_3d.py
"""

import time
import xml.etree.ElementTree as ET

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



def _parse_floats(text: str | None, default: tuple[float, float, float]) -> np.ndarray:
    if text is None:
        return np.array(default, dtype=float)
    return np.array([float(v) for v in text.split()], dtype=float)


def _rpy_to_matrix(rpy: np.ndarray) -> np.ndarray:
    """Convention URDF : R = Rz(yaw) @ Ry(pitch) @ Rx(roll)."""
    r, p, y = rpy
    cr, sr = np.cos(r), np.sin(r)
    cp, sp = np.cos(p), np.sin(p)
    cy, sy = np.cos(y), np.sin(y)
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return rz @ ry @ rx


def _axis_angle_to_matrix(axis: np.ndarray, angle: float) -> np.ndarray:
    """Rotation d'un angle (radians) autour d'un axe (formule de Rodrigues)."""
    axis = axis / np.linalg.norm(axis)
    k = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + np.sin(angle) * k + (1 - np.cos(angle)) * (k @ k)


class UrdfForwardKinematics:
    """Cinematique directe minimale lue depuis un fichier URDF.

    Meme utilisation que RobotKinematics de LeRobot :
    forward_kinematics(angles_en_degres) -> matrice 4x4 de la pose du repere cible.
    """

    def __init__(self, urdf_path: str, target_frame_name: str, joint_names: list[str]):
        root = ET.parse(urdf_path).getroot()

        # Pour chaque maillon, on retient l'articulation qui le relie a son parent.
        joints_by_child = {}
        for joint in root.findall("joint"):
            origin = joint.find("origin")
            xyz = _parse_floats(origin.get("xyz") if origin is not None else None, (0, 0, 0))
            rpy = _parse_floats(origin.get("rpy") if origin is not None else None, (0, 0, 0))
            t_origin = np.eye(4)
            t_origin[:3, :3] = _rpy_to_matrix(rpy)
            t_origin[:3, 3] = xyz

            axis_el = joint.find("axis")
            axis = _parse_floats(axis_el.get("xyz") if axis_el is not None else None, (1, 0, 0))

            joints_by_child[joint.find("child").get("link")] = {
                "name": joint.get("name"),
                "type": joint.get("type"),
                "parent": joint.find("parent").get("link"),
                "origin": t_origin,
                "axis": axis,
            }

        link_names = {link.get("name") for link in root.findall("link")}
        if target_frame_name not in link_names:
            raise ValueError(
                f"Le repere '{target_frame_name}' n'existe pas dans l'URDF. "
                f"Reperes disponibles : {sorted(link_names)}"
            )

        # On remonte du repere cible jusqu'a la base, puis on inverse l'ordre.
        chain = []
        link = target_frame_name
        while link in joints_by_child:
            joint = joints_by_child[link]
            chain.append(joint)
            link = joint["parent"]
        self.chain = list(reversed(chain))

        self.joint_index = {name: i for i, name in enumerate(joint_names)}
        missing = [
            j["name"]
            for j in self.chain
            if j["type"] in ("revolute", "continuous", "prismatic") and j["name"] not in self.joint_index
        ]
        if missing:
            print(f"Attention : articulations de l'URDF absentes des moteurs (fixees a 0) : {missing}")

    def forward_kinematics(self, joint_pos_deg: np.ndarray) -> np.ndarray:
        q = np.deg2rad(np.asarray(joint_pos_deg, dtype=float))
        pose = np.eye(4)
        for joint in self.chain:
            pose = pose @ joint["origin"]
            value = q[self.joint_index[joint["name"]]] if joint["name"] in self.joint_index else 0.0
            motion = np.eye(4)
            if joint["type"] in ("revolute", "continuous"):
                motion[:3, :3] = _axis_angle_to_matrix(joint["axis"], value)
            elif joint["type"] == "prismatic":
                motion[:3, 3] = joint["axis"] * value
            pose = pose @ motion
        return pose


# ---------------------------------------------------------------------------


def main():
    follower = SO101Follower(SO101FollowerConfig(port=FOLLOWER_PORT, id=FOLLOWER_ID))
    leader = SO101Leader(SO101LeaderConfig(port=LEADER_PORT, id=LEADER_ID))
    follower.connect()
    leader.connect()

    motor_names = list(follower.bus.motors.keys())
    kinematics = UrdfForwardKinematics(
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

    # Petite marge pour eviter une erreur si le bras n'a pas bouge sur un axe.
    margin = 0.01
    ax.set_xlim(x.min() - margin, x.max() + margin)
    ax.set_ylim(y.min() - margin, y.max() + margin)
    ax.set_zlim(z.min() - margin, z.max() + margin)
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
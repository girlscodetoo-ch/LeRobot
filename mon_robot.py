import time
from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

# On se connecte au robot
robot = SO101Follower(SO101FollowerConfig(port="COM3", id="Carol_follower_first_lerobot"))
robot.connect()
depart = robot.get_observation()
position = dict(depart)


# Cette fonction fait bouger une partie du robot, tout doucement
def bouge(partie, angle):
    angle = max(-45, min(45, angle))  # pas plus de 45 degrés, pour ne pas abîmer le robot
    cible = depart[partie] + angle
    while abs(cible - position[partie]) > 1:
        position[partie] += 1 if cible > position[partie] else -1
        robot.send_action(position)
        time.sleep(0.03)


base = "shoulder_pan.pos"
epaule = "shoulder_lift.pos"
coude = "elbow_flex.pos"
poignet = "wrist_flex.pos"
rotation = "wrist_roll.pos"
pince = "gripper.pos"


# ==========================================================
#   ÉCRIS TON CODE ICI
#
#   Les parties : base  epaule  coude  poignet  rotation  pince
#
#   Exemples :  bouge(coude, 20)
#               bouge(base, -30)
#               time.sleep(1)
# ==========================================================




# ==========================================================


# À la fin, le robot revient à sa place
for partie in [base, epaule, coude, poignet, rotation, pince]:
    bouge(partie, 0)
robot.disconnect()

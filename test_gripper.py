"""
Faire bouger la pince du robot : elle s'ouvre et se ferme 3 fois.

Pour lancer :  python test_gripper.py
"""

import time

from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

PORT = "COM3"                          # port USB du bras robot
ROBOT_ID = "Carol_follower_first_lerobot"

OUVERTE = 60.0     # position pince ouverte (0 = fermée, 100 = grande ouverte)
FERMEE = 5.0       # position pince fermée
VITESSE = 1.5      # degrés par petit pas (plus petit = plus doux)
FREQUENCE = 30     # petits pas par seconde


def aller_doucement(robot, actuelle, cible):
    """Amène la pince de 'actuelle' à 'cible' petit pas par petit pas."""
    while abs(cible - actuelle) > 0.01:
        actuelle += max(-VITESSE, min(VITESSE, cible - actuelle))
        robot.send_action({"gripper.pos": actuelle})
        time.sleep(1 / FREQUENCE)
    return actuelle


def main():
    robot = SO101Follower(SO101FollowerConfig(port=PORT, id=ROBOT_ID))
    robot.connect()

    depart = robot.get_observation()["gripper.pos"]
    position = depart

    try:
        for _ in range(3):
            print("Ouvre la pince")
            position = aller_doucement(robot, position, OUVERTE)
            time.sleep(0.5)
            print("Ferme la pince")
            position = aller_doucement(robot, position, FERMEE)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nOn arrête !")
    finally:
        aller_doucement(robot, position, depart)
        robot.disconnect()


if __name__ == "__main__":
    main()

import time
from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig

follower_config = SO101FollowerConfig(port="COM3", id="Carol_follower_first_lerobot")
leader_config = SO101LeaderConfig(port="COM4", id="Carol_leader_first_lerobot")

follower = SO101Follower(follower_config)
leader = SO101Leader(leader_config)
follower.connect()
leader.connect()

MAX_STEP_DEG = 2.0    # plus lent = moins de risque de forcer
SAFE_MIN = -145.0     # marge de sécurité nettement plus large
SAFE_MAX = 142.0
STUCK_TIMEOUT = 0.3   # réagit beaucoup plus vite

obs = follower.get_observation()
current_wrist_roll = obs["wrist_roll.pos"]

at_limit_since = None
torque_released = False

try:
    while True:
        action = leader.get_action()
        target = action["wrist_roll.pos"]

        delta = (target - current_wrist_roll + 180) % 360 - 180
        delta = max(-MAX_STEP_DEG, min(MAX_STEP_DEG, delta))
        current_wrist_roll += delta
        current_wrist_roll = ((current_wrist_roll + 180) % 360) - 180

        at_limit = current_wrist_roll <= SAFE_MIN or current_wrist_roll >= SAFE_MAX
        current_wrist_roll = max(SAFE_MIN, min(SAFE_MAX, current_wrist_roll))

        if at_limit:
            if at_limit_since is None:
                at_limit_since = time.time()
            elif time.time() - at_limit_since > STUCK_TIMEOUT and not torque_released:
                try:
                    print(">>> Relâchement du couple wrist_roll <<<")
                    follower.bus.disable_torque("wrist_roll")
                    torque_released = True
                except RuntimeError as e:
                    print(f">>> Échec du relâchement (moteur déjà en surcharge ?) : {e}")
        else:
            if torque_released:
                try:
                    print(">>> Réactivation du couple <<<")
                    follower.bus.enable_torque("wrist_roll")
                    torque_released = False
                except RuntimeError as e:
                    print(f">>> Échec de la réactivation : {e}")
            at_limit_since = None

        action["wrist_roll.pos"] = current_wrist_roll
        try:
            follower.send_action(action)
        except RuntimeError as e:
            print(f">>> Erreur d'envoi (ignorée) : {e}")

        time.sleep(1 / 30)
except KeyboardInterrupt:
    pass

follower.disconnect()
leader.disconnect()
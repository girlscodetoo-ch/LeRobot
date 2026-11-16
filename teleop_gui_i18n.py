"""
Translations for lerobot_teleop_gui_v2.py.

To add a language: add its code to LANGUAGES, then a translation for that code in every
entry of STRINGS. A missing translation falls back to English.
"""

LANGUAGES = {"en": "English", "fr": "Français", "de": "Deutsch", "it": "Italiano"}

_language = "en"


def set_language(code):
    global _language
    _language = code if code in LANGUAGES else "en"


def get_language():
    return _language


def tr(key, **kwargs):
    """Text for `key` in the current language, with {placeholders} filled from kwargs."""
    entry = STRINGS[key]
    text = entry.get(_language) or entry["en"]
    return text.format(**kwargs) if kwargs else text


STRINGS = {
    # ----- Main window ---------------------------------------------------------------
    "app_title": {
        "en": "LeRobot Workshop",
        "fr": "Atelier LeRobot",
        "de": "LeRobot Workshop",
        "it": "Laboratorio LeRobot",
    },
    "subtitle": {
        "en": "{model}   ·   follower {follower}   ·   leader {leader}",
        "fr": "{model}   ·   suiveur {follower}   ·   leader {leader}",
        "de": "{model}   ·   Follower {follower}   ·   Leader {leader}",
        "it": "{model}   ·   follower {follower}   ·   leader {leader}",
    },
    "btn_settings": {
        "en": "⚙  Settings",
        "fr": "⚙  Réglages",
        "de": "⚙  Einstellungen",
        "it": "⚙  Impostazioni",
    },
    "btn_joints": {
        "en": "∿  Joint angles",
        "fr": "∿  Angles des joints",
        "de": "∿  Gelenkwinkel",
        "it": "∿  Angoli dei giunti",
    },
    "show_log": {
        "en": "Show technical details  ▸",
        "fr": "Afficher les détails techniques  ▸",
        "de": "Technische Details anzeigen  ▸",
        "it": "Mostra dettagli tecnici  ▸",
    },
    "hide_log": {
        "en": "Hide technical details  ▴",
        "fr": "Masquer les détails techniques  ▴",
        "de": "Technische Details ausblenden  ▴",
        "it": "Nascondi dettagli tecnici  ▴",
    },
    "esc_hint": {
        "en": "Esc  =  emergency stop",
        "fr": "Échap  =  arrêt d'urgence",
        "de": "Esc  =  Not-Aus",
        "it": "Esc  =  arresto di emergenza",
    },
    "log_title": {
        "en": "Technical details",
        "fr": "Détails techniques",
        "de": "Technische Details",
        "it": "Dettagli tecnici",
    },
    # ----- Big round button ----------------------------------------------------------
    "big_start": {"en": "START", "fr": "DÉMARRER", "de": "START", "it": "AVVIA"},
    "big_start_sub": {
        "en": "Take control",
        "fr": "Prendre le contrôle",
        "de": "Steuerung übernehmen",
        "it": "Prendi il controllo",
    },
    "big_stop": {"en": "STOP", "fr": "STOP", "de": "STOPP", "it": "STOP"},
    "big_stop_sub": {
        "en": "Release control",
        "fr": "Rendre le contrôle",
        "de": "Steuerung abgeben",
        "it": "Rilascia il controllo",
    },
    "big_wait": {"en": "WAIT", "fr": "ATTENTE", "de": "WARTEN", "it": "ATTESA"},
    "big_wait_sub": {
        "en": "Click to cancel",
        "fr": "Clique pour annuler",
        "de": "Klicken zum Abbrechen",
        "it": "Clicca per annullare",
    },
    "big_busy": {"en": "BUSY", "fr": "OCCUPÉ", "de": "BELEGT", "it": "OCCUPATO"},
    "big_busy_sub": {
        "en": "Robot in use",
        "fr": "Robot occupé",
        "de": "Roboter in Betrieb",
        "it": "Robot in uso",
    },
    # ----- Status pill -----------------------------------------------------------------
    "status_stopped": {
        "en": "Robot stopped",
        "fr": "Robot arrêté",
        "de": "Roboter gestoppt",
        "it": "Robot fermo",
    },
    "status_connecting": {
        "en": "Connecting to the robot…",
        "fr": "Connexion au robot…",
        "de": "Verbindung zum Roboter…",
        "it": "Connessione al robot…",
    },
    "status_running": {
        "en": "Robot running — move the leader arm!",
        "fr": "Robot en marche — bouge le bras leader !",
        "de": "Roboter läuft — bewege den Leader-Arm!",
        "it": "Robot in funzione — muovi il braccio leader!",
    },
    "status_recording": {
        "en": "Recording episode {n}",
        "fr": "Enregistrement de l'épisode {n}",
        "de": "Episode {n} wird aufgenommen",
        "it": "Registrazione episodio {n}",
    },
    "status_record_preparing": {
        "en": "Getting ready to record…",
        "fr": "Préparation de l'enregistrement…",
        "de": "Aufnahme wird vorbereitet…",
        "it": "Preparazione della registrazione…",
    },
    "status_replaying": {
        "en": "Replaying episode {n}",
        "fr": "Rejeu de l'épisode {n}",
        "de": "Episode {n} wird abgespielt",
        "it": "Riproduzione episodio {n}",
    },
    "status_stopping": {
        "en": "Stopping…",
        "fr": "Arrêt…",
        "de": "Wird gestoppt…",
        "it": "Arresto…",
    },
    "status_recorded": {
        "en": "Episode {n} recorded",
        "fr": "Épisode {n} enregistré",
        "de": "Episode {n} aufgenommen",
        "it": "Episodio {n} registrato",
    },
    "status_replay_done": {
        "en": "Replay finished",
        "fr": "Rejeu terminé",
        "de": "Wiedergabe beendet",
        "it": "Riproduzione terminata",
    },
    "status_error": {
        "en": "Something went wrong",
        "fr": "Un problème est survenu",
        "de": "Etwas ist schiefgelaufen",
        "it": "Qualcosa è andato storto",
    },
    # ----- Hints under the big button ------------------------------------------------
    "hint_idle": {
        "en": "Click the button to take control of the arm!",
        "fr": "Clique sur le bouton pour prendre le contrôle du bras !",
        "de": "Klicke auf den Knopf, um den Arm zu steuern!",
        "it": "Clicca sul pulsante per controllare il braccio!",
    },
    "hint_connecting": {
        "en": "Hold on, the robot is waking up…",
        "fr": "Patience, le robot se réveille…",
        "de": "Einen Moment, der Roboter wacht auf…",
        "it": "Un attimo, il robot si sta svegliando…",
    },
    "hint_slow": {
        "en": "Still waiting for the robot… Check that both arms are plugged in and powered on.",
        "fr": "On attend toujours le robot… Vérifie que les deux bras sont branchés et allumés.",
        "de": "Warte immer noch auf den Roboter… Prüfe, ob beide Arme eingesteckt und eingeschaltet sind.",
        "it": "Ancora in attesa del robot… Controlla che entrambi i bracci siano collegati e accesi.",
    },
    "hint_running": {
        "en": "The robot copies every move of the leader arm.",
        "fr": "Le robot copie chaque mouvement du bras leader.",
        "de": "Der Roboter macht jede Bewegung des Leader-Arms nach.",
        "it": "Il robot copia ogni movimento del braccio leader.",
    },
    "hint_record_preparing": {
        "en": "Don't move yet! The recording starts in a few seconds: wait for “Go!”.",
        "fr": "Ne bouge pas encore ! L'enregistrement démarre dans quelques secondes : attends le « C'est parti ! ».",
        "de": "Noch nicht bewegen! Die Aufnahme startet in ein paar Sekunden: warte auf „Los!“.",
        "it": "Non muoverti ancora! La registrazione parte tra qualche secondo: aspetta il “Via!”.",
    },
    "hint_recording": {
        "en": "Go! Move the leader arm now. Stopping early may make this episode unusable — "
              "let it finish on its own.",
        "fr": "C'est parti ! Bouge le bras leader maintenant. Arrêter avant la fin peut rendre l'épisode "
              "inutilisable — laisse-le se terminer tout seul.",
        "de": "Los! Bewege jetzt den Leader-Arm. Wenn du zu früh stoppst, ist die Episode vielleicht "
              "unbrauchbar — lass sie von selbst enden.",
        "it": "Via! Muovi ora il braccio leader. Fermarsi prima può rendere l'episodio inutilizzabile — "
              "lascialo finire da solo.",
    },
    "hint_replaying": {
        "en": "Hands off: the robot is moving on its own.",
        "fr": "Pas touche : le robot bouge tout seul.",
        "de": "Hände weg: Der Roboter bewegt sich von allein.",
        "it": "Giù le mani: il robot si muove da solo.",
    },
    "hint_recorded": {
        "en": "Great job! Record another one, or watch the robot replay it.",
        "fr": "Bravo ! Enregistres-en un autre, ou regarde le robot le rejouer.",
        "de": "Super! Nimm noch eine auf oder schau zu, wie der Roboter sie abspielt.",
        "it": "Ottimo lavoro! Registrane un altro o guarda il robot che lo ripete.",
    },
    "hint_replay_done": {
        "en": "Want to see it again? Click Replay.",
        "fr": "Tu veux le revoir ? Clique sur Rejouer.",
        "de": "Nochmal sehen? Klicke auf Abspielen.",
        "it": "Vuoi rivederlo? Clicca su Riproduci.",
    },
    "hint_record_early": {
        "en": "Recording stopped early: this episode was not counted.",
        "fr": "Enregistrement arrêté avant la fin : cet épisode n'a pas été compté.",
        "de": "Aufnahme zu früh gestoppt: Diese Episode wurde nicht gezählt.",
        "it": "Registrazione interrotta prima della fine: questo episodio non è stato contato.",
    },
    "hint_error": {
        "en": "The robot stopped because of a problem. Check the USB cables and the power, then try again. "
              "(Ask the teacher for help or look at the technical details.)",
        "fr": "Le robot s'est arrêté à cause d'un problème. Vérifie les câbles USB et l'alimentation, "
              "puis réessaie. (Demande de l'aide à l'enseignant·e ou regarde les détails techniques.)",
        "de": "Der Roboter wurde wegen eines Problems gestoppt. Prüfe die USB-Kabel und den Strom und "
              "versuche es erneut. (Frag die Lehrperson oder schau in die technischen Details.)",
        "it": "Il robot si è fermato per un problema. Controlla i cavi USB e l'alimentazione, poi riprova. "
              "(Chiedi aiuto all'insegnante o guarda i dettagli tecnici.)",
    },
    "hint_settings_saved": {
        "en": "Settings saved. Click {start} to take control of the arm!",
        "fr": "Réglages enregistrés. Clique sur {start} pour prendre le contrôle du bras !",
        "de": "Einstellungen gespeichert. Klicke auf {start}, um den Arm zu steuern!",
        "it": "Impostazioni salvate. Clicca su {start} per controllare il braccio!",
    },
    # ----- Record / replay cards -----------------------------------------------------
    "rec_title": {"en": "●  Record", "fr": "●  Enregistrer", "de": "●  Aufnehmen", "it": "●  Registra"},
    "rec_desc": {
        "en": "Move the leader arm: the robot remembers what you do.",
        "fr": "Bouge le bras leader : le robot retient ce que tu fais.",
        "de": "Bewege den Leader-Arm: Der Roboter merkt sich, was du tust.",
        "it": "Muovi il braccio leader: il robot ricorda cosa fai.",
    },
    "rec_counter": {
        "en": "episodes\nrecorded",
        "fr": "épisodes\nenregistrés",
        "de": "Episoden\naufgenommen",
        "it": "episodi\nregistrati",
    },
    "rec_btn": {
        "en": "●  Record an episode",
        "fr": "●  Enregistrer un épisode",
        "de": "●  Episode aufnehmen",
        "it": "●  Registra un episodio",
    },
    "rec_stop": {
        "en": "■  Stop recording",
        "fr": "■  Arrêter l'enregistrement",
        "de": "■  Aufnahme stoppen",
        "it": "■  Ferma la registrazione",
    },
    "rec_progress": {
        "en": "Recording…  {elapsed} s / {total} s",
        "fr": "Enregistrement…  {elapsed} s / {total} s",
        "de": "Aufnahme…  {elapsed} s / {total} s",
        "it": "Registrazione…  {elapsed} s / {total} s",
    },
    "rec_preparing": {
        "en": "Getting ready…",
        "fr": "Préparation…",
        "de": "Vorbereitung…",
        "it": "Preparazione…",
    },
    "rec_saving": {
        "en": "Finishing and saving…",
        "fr": "Fin et sauvegarde…",
        "de": "Wird beendet und gespeichert…",
        "it": "Chiusura e salvataggio…",
    },
    "rep_title": {"en": "▶  Replay", "fr": "▶  Rejouer", "de": "▶  Abspielen", "it": "▶  Riproduci"},
    "rep_desc": {
        "en": "The robot repeats a recorded episode all by itself.",
        "fr": "Le robot refait tout seul un épisode enregistré.",
        "de": "Der Roboter wiederholt eine aufgenommene Episode ganz allein.",
        "it": "Il robot ripete da solo un episodio registrato.",
    },
    "rep_btn": {
        "en": "▶  Replay episode",
        "fr": "▶  Rejouer l'épisode",
        "de": "▶  Episode abspielen",
        "it": "▶  Riproduci episodio",
    },
    "rep_stop": {
        "en": "■  Stop replay",
        "fr": "■  Arrêter le rejeu",
        "de": "■  Wiedergabe stoppen",
        "it": "■  Ferma la riproduzione",
    },
    # ----- Hand control (webcam) -----------------------------------------------------
    "hand_btn": {
        "en": "☝  Hand control (camera)",
        "fr": "☝  Contrôle à la main (caméra)",
        "de": "☝  Handsteuerung (Kamera)",
        "it": "☝  Controllo con la mano (camera)",
    },
    "hand_stop": {
        "en": "■  Stop hand control",
        "fr": "■  Arrêter le contrôle à la main",
        "de": "■  Handsteuerung stoppen",
        "it": "■  Ferma il controllo con la mano",
    },
    "status_hand_starting": {
        "en": "Starting the camera…",
        "fr": "Démarrage de la caméra…",
        "de": "Kamera wird gestartet…",
        "it": "Avvio della camera…",
    },
    "status_hand_running": {
        "en": "Hand control on",
        "fr": "Contrôle à la main actif",
        "de": "Handsteuerung aktiv",
        "it": "Controllo con la mano attivo",
    },
    "hint_hand_starting": {
        "en": "The camera window opens in a few seconds…",
        "fr": "La fenêtre de la caméra s'ouvre dans quelques secondes…",
        "de": "Das Kamerafenster öffnet sich in ein paar Sekunden…",
        "it": "La finestra della camera si apre tra qualche secondo…",
    },
    "hint_hand_running": {
        "en": "In the camera window: SPACE to take control or pause, Q to quit.",
        "fr": "Dans la fenêtre de la caméra : ESPACE pour prendre le contrôle ou faire une pause, Q pour quitter.",
        "de": "Im Kamerafenster: LEERTASTE zum Steuern oder Pausieren, Q zum Beenden.",
        "it": "Nella finestra della camera: SPAZIO per prendere il controllo o mettere in pausa, Q per uscire.",
    },
    # ----- Joint angles window -------------------------------------------------------
    "joints_window": {
        "en": "Joint angles (live)",
        "fr": "Angles des joints (en direct)",
        "de": "Gelenkwinkel (live)",
        "it": "Angoli dei giunti (dal vivo)",
    },
    "joints_title": {
        "en": "Joint angles",
        "fr": "Angles des joints",
        "de": "Gelenkwinkel",
        "it": "Angoli dei giunti",
    },
    "joints_waiting": {
        "en": "Waiting for data…",
        "fr": "En attente des données…",
        "de": "Warte auf Daten…",
        "it": "In attesa dei dati…",
    },
    "joints_idle": {
        "en": "Click {start} to see the joints move.",
        "fr": "Clique sur {start} pour voir bouger les joints.",
        "de": "Klicke auf {start}, um die Gelenke in Bewegung zu sehen.",
        "it": "Clicca su {start} per vedere muoversi i giunti.",
    },
    "joints_live": {
        "en": "●  Live — follower arm",
        "fr": "●  En direct — bras suiveur",
        "de": "●  Live — Follower-Arm",
        "it": "●  Dal vivo — braccio follower",
    },
    "joints_stopped": {
        "en": "Teleoperation stopped — last values received.",
        "fr": "Téléopération arrêtée — dernières valeurs reçues.",
        "de": "Teleoperation gestoppt — zuletzt empfangene Werte.",
        "it": "Teleoperazione fermata — ultimi valori ricevuti.",
    },
    "joints_note": {
        "en": "Angles in degrees, gripper opening in %.\nCharts show the last {seconds} seconds.",
        "fr": "Angles en degrés, ouverture de la pince en %.\nLes courbes montrent les {seconds} dernières secondes.",
        "de": "Winkel in Grad, Greiferöffnung in %.\nDie Kurven zeigen die letzten {seconds} Sekunden.",
        "it": "Angoli in gradi, apertura della pinza in %.\nI grafici mostrano gli ultimi {seconds} secondi.",
    },
    "joint_shoulder_pan": {
        "en": "Shoulder pan",
        "fr": "Rotation épaule",
        "de": "Schulter drehen",
        "it": "Rotazione spalla",
    },
    "joint_shoulder_lift": {
        "en": "Shoulder lift",
        "fr": "Lever épaule",
        "de": "Schulter heben",
        "it": "Sollevamento spalla",
    },
    "joint_elbow_flex": {
        "en": "Elbow flex",
        "fr": "Flexion coude",
        "de": "Ellbogen beugen",
        "it": "Flessione gomito",
    },
    "joint_wrist_flex": {
        "en": "Wrist flex",
        "fr": "Flexion poignet",
        "de": "Handgelenk beugen",
        "it": "Flessione polso",
    },
    "joint_wrist_roll": {
        "en": "Wrist roll",
        "fr": "Rotation poignet",
        "de": "Handgelenk drehen",
        "it": "Rotazione polso",
    },
    "joint_gripper": {"en": "Gripper", "fr": "Pince", "de": "Greifer", "it": "Pinza"},
    # ----- Settings window (for the teacher) -----------------------------------------
    "settings_window": {
        "en": "Settings (teacher)",
        "fr": "Réglages (enseignant·e)",
        "de": "Einstellungen (Lehrperson)",
        "it": "Impostazioni (insegnante)",
    },
    "settings_title": {
        "en": "Robot settings",
        "fr": "Réglages du robot",
        "de": "Robotereinstellungen",
        "it": "Impostazioni del robot",
    },
    "settings_help": {
        "en": "Set once. Run 'lerobot-find-port' in a terminal to find the USB ports.",
        "fr": "À régler une seule fois. Lancez 'lerobot-find-port' dans un terminal pour trouver les ports USB.",
        "de": "Nur einmal einstellen. Führe 'lerobot-find-port' in einem Terminal aus, um die USB-Ports zu finden.",
        "it": "Da impostare una sola volta. Esegui 'lerobot-find-port' in un terminale per trovare le porte USB.",
    },
    "language": {"en": "LANGUAGE", "fr": "LANGUE", "de": "SPRACHE", "it": "LINGUA"},
    "find_port": {"en": "Find the port", "fr": "Trouver le port", "de": "Port finden", "it": "Trova la porta"},
    "find_port_unplug": {
        "en": "Unplug the USB cable of the {arm} (leave the other arm plugged in), then click OK.",
        "fr": "Débranchez le câble USB du {arm} (laissez l'autre bras branché), puis cliquez sur OK.",
        "de": "Ziehe das USB-Kabel vom {arm} ab (der andere Arm bleibt eingesteckt) und klicke dann auf OK.",
        "it": "Scollega il cavo USB del {arm} (lascia collegato l'altro braccio), poi clicca su OK.",
    },
    "find_port_found": {
        "en": "{arm}: port {port} found.\n\nYou can plug the cable back in.",
        "fr": "{arm} : port {port} trouvé.\n\nVous pouvez rebrancher le câble.",
        "de": "{arm}: Port {port} gefunden.\n\nDu kannst das Kabel wieder einstecken.",
        "it": "{arm}: porta {port} trovata.\n\nPuoi ricollegare il cavo.",
    },
    "find_port_fail": {
        "en": "No port found. Plug the cable back in and try again, unplugging only one arm.",
        "fr": "Aucun port trouvé. Rebranchez le câble et réessayez en ne débranchant qu'un seul bras.",
        "de": "Kein Port gefunden. Stecke das Kabel wieder ein und versuche es erneut, nur einen Arm abziehen.",
        "it": "Nessuna porta trovata. Ricollega il cavo e riprova, scollegando un solo braccio.",
    },
    "hand_control": {
        "en": "HAND CONTROL (CAMERA)",
        "fr": "CONTRÔLE À LA MAIN (CAMÉRA)",
        "de": "HANDSTEUERUNG (KAMERA)",
        "it": "CONTROLLO CON LA MANO (CAMERA)",
    },
    "enabled": {"en": "On", "fr": "Activé", "de": "An", "it": "Attivo"},
    "disabled": {"en": "Off", "fr": "Désactivé", "de": "Aus", "it": "Disattivo"},
    "hand_camera": {
        "en": "CAMERA (HAND CONTROL)",
        "fr": "CAMÉRA (CONTRÔLE À LA MAIN)",
        "de": "KAMERA (HANDSTEUERUNG)",
        "it": "CAMERA (CONTROLLO CON LA MANO)",
    },
    "camera_searching": {
        "en": "Looking for cameras…",
        "fr": "Recherche des caméras…",
        "de": "Kameras werden gesucht…",
        "it": "Ricerca delle camere…",
    },
    "camera_none": {
        "en": "No camera found",
        "fr": "Aucune caméra trouvée",
        "de": "Keine Kamera gefunden",
        "it": "Nessuna camera trovata",
    },
    "camera_n": {"en": "Camera {n}", "fr": "Caméra {n}", "de": "Kamera {n}", "it": "Camera {n}"},
    "robot_model": {"en": "ROBOT MODEL", "fr": "MODÈLE DE ROBOT", "de": "ROBOTERMODELL", "it": "MODELLO DI ROBOT"},
    "follower_arm": {"en": "Follower arm", "fr": "Bras suiveur", "de": "Follower-Arm", "it": "Braccio follower"},
    "leader_arm": {"en": "Leader arm", "fr": "Bras leader", "de": "Leader-Arm", "it": "Braccio leader"},
    "usb_port": {"en": "USB PORT", "fr": "PORT USB", "de": "USB-PORT", "it": "PORTA USB"},
    "arm_id": {"en": "ARM ID", "fr": "ID DU BRAS", "de": "ARM-ID", "it": "ID BRACCIO"},
    "recording": {"en": "Recording", "fr": "Enregistrement", "de": "Aufnahme", "it": "Registrazione"},
    "dataset_name": {
        "en": "DATASET NAME",
        "fr": "NOM DU DATASET",
        "de": "DATENSATZNAME",
        "it": "NOME DEL DATASET",
    },
    "task_description": {
        "en": "TASK DESCRIPTION",
        "fr": "DESCRIPTION DE LA TÂCHE",
        "de": "AUFGABENBESCHREIBUNG",
        "it": "DESCRIZIONE DEL COMPITO",
    },
    "episode_duration": {
        "en": "EPISODE DURATION (S)",
        "fr": "DURÉE D'UN ÉPISODE (S)",
        "de": "EPISODENDAUER (S)",
        "it": "DURATA EPISODIO (S)",
    },
    "save": {"en": "Save", "fr": "Enregistrer", "de": "Speichern", "it": "Salva"},
    "cancel": {"en": "Cancel", "fr": "Annuler", "de": "Abbrechen", "it": "Annulla"},
    # ----- Pop-ups -------------------------------------------------------------------
    "busy_title": {
        "en": "Robot running",
        "fr": "Robot en marche",
        "de": "Roboter läuft",
        "it": "Robot in funzione",
    },
    "busy_msg": {
        "en": "Stop the robot first before changing the settings.",
        "fr": "Arrêtez d'abord le robot avant de modifier les réglages.",
        "de": "Stoppe zuerst den Roboter, bevor du die Einstellungen änderst.",
        "it": "Ferma il robot prima di cambiare le impostazioni.",
    },
    "notfound_title": {
        "en": "Command not found",
        "fr": "Commande introuvable",
        "de": "Befehl nicht gefunden",
        "it": "Comando non trovato",
    },
    "notfound_msg": {
        "en": "The '{cmd}' command was not found.\n\n"
              "Check that LeRobot is properly installed and that this\n"
              "application is launched from the same environment\n"
              "(e.g. the same conda/virtualenv environment).",
        "fr": "La commande '{cmd}' est introuvable.\n\n"
              "Vérifiez que LeRobot est bien installé et que cette\n"
              "application est lancée depuis le même environnement\n"
              "(par ex. le même environnement conda/virtualenv).",
        "de": "Der Befehl '{cmd}' wurde nicht gefunden.\n\n"
              "Prüfe, ob LeRobot richtig installiert ist und ob diese\n"
              "Anwendung aus derselben Umgebung gestartet wird\n"
              "(z. B. derselben conda/virtualenv-Umgebung).",
        "it": "Il comando '{cmd}' non è stato trovato.\n\n"
              "Verifica che LeRobot sia installato correttamente e che questa\n"
              "applicazione sia avviata dallo stesso ambiente\n"
              "(ad es. lo stesso ambiente conda/virtualenv).",
    },
}

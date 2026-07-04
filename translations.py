TRANSLATIONS = {
    "de": {
        "ui": {
            "title": "Selve2MQTT Dashboard",
            "btn_learn_actor": "Aktor Lernmodus (60s)",
            "btn_learn_sensor": "Sensor Lernmodus (60s)",
            "btn_reset_gw": "Gateway Reset",
            "btn_led_on": "LED An",
            "btn_led_off": "LED Aus",
            "btn_new_group": "Neue Gruppe",
            "btn_rename_gw": "Gateway benennen",
            "gw_status": "Gateway Status",
            "duty_cycle": "Duty Cycle",
            "hw_ver": "HW",
            "fw_ver": "FW",
            "latest_ver": "Aktuell",
            "header_groups": "Gruppen",
            "header_devices": "Geräte",
            "header_sensors": "Sensoren",
            "status": "Status",
            "pos": "Position",
            "btn_open": "Öffnen",
            "btn_stop": "Stop",
            "btn_close": "Schließen",
            "btn_rename": "Umbenennen",
            "btn_pair": "FB Koppeln",
            "btn_show_senders": "Sender anzeigen",
            "btn_delete": "Löschen",
            "btn_edit": "Bearbeiten",
            "connectivity": "Erreichbarkeit",
            "gw_led": "Gateway LED",
            "gw_forwarding": "Commeo Weiterleitung",
            "gw_duty_cycle": "Gateway Auslastung",
            "gw_duty_blocked": "Gateway Auslastung Blockiert",
            "group_tag": "Gruppe",
            "members": "Mitglieder IDs",
            "loading": "Lade...",
            "coupled_senders": "Gekoppelte Sender",
            "no_senders": "Keine Fremdsender gefunden",
            "confirm_reset": "Möchten Sie das Gateway wirklich neu starten?",
            "confirm_del_group": "Gruppe wirklich löschen?",
            "confirm_del_device": "Aktor wirklich löschen?",
            "confirm_del_sensor": "Sensor wirklich löschen?",
            "prompt_new_name": "Neuer Name",
            "learning_active": "Lernmodus aktiv...",
            "learning_sensor_active": (
                "Sensor-Lernmodus aktiv... PROG-Taste am "
                "Sensor drücken."
            ),
            "btn_sender_teach_start": "Sender anlernen starten",
            "btn_sender_teach_stop": "Sender anlernen stoppen",
            "learning_sender_active": "Sender-Lernmodus aktiv...",
            "result_prefix": "Ergebnis: ",
            "error_start_sender": "Fehler beim Starten des Sender-Anlernens",
            "error_stop_sender": "Fehler beim Stoppen des Sender-Anlernens",
            "sender_teach_stopped": "Sender-Anlernen gestoppt",
            "learning_finished": "Beendet.",
            "alert_id_name_required": "ID und Name erforderlich!",
            "lbl_group_id": "ID (0-63):",
            "status_ok": "OK",
            "status_blocked": "BLOCKIERT"
        },
        "sensors": {
            "wind": "Wind",
            "rain": "Regen",
            "light": "Sonne",
            "temp": "Temperatur",
            "generic": "Sensor"
        },
        "logs": {
            "gw_init": "Selve Gateway initialisiert (Port: {port})",
            "discovery_start": "Bestandsaufnahme der gespeicherten Geräte wird gestartet...",
            "scan_start": "Suche nach neuen Geräten gestartet (Lernmodus)...",
            "discovery_done": (
                "Suche abgeschlossen: {devices} Geräte, {groups} "
                "Gruppen, {sensors} Sensoren und {senders} Fernbedienungen gefunden."
            ),
            "duty_cycle_event": (
                "GATEWAY EVENT - Duty Cycle: {duty}% "
                "[Status: {status}]"
            ),
            "status_ok": "OK",
            "status_blocked": "BLOCKIERT",
            "device_unreachable": "Gerät {name} (ID: {id}) ist NICHT ERREICHBAR",
            "device_online": "Gerät {name} (ID: {id}) ist wieder ONLINE",
            "update_received": "Update für {id}: {pos}% (moving={moving}, raw={raw})",
            "cmd_sent": "Befehl '{cmd}' an {type} {id} gesendet{val}",
            "type_device": "Gerät",
            "type_group": "Gruppe",
            "pairing_start": "Pairing-Modus gestartet (Commeo)...",
            "scan_progress": "Scan läuft... {count} potenzielle Geräte gefunden.",
            "scan_finished": "Scan beendet. {count} neue Geräte gefunden.",
            "save_dev": "Speichere Gerät {id} dauerhaft...",
            "sensor_teach_start": "Sensor-Anlernmodus gestartet (Commeo)...",
            "sensor_teach_progress": "Sensor-Anlernen aktiv... {time}s verbleibend.",
            "sensor_teach_success": (
                "Sensor erfolgreich angelernt! Zugewiesene "
                "ID: {id}"
            ),
            "del_dev": "Lösche Gerät {id}...",
            "del_sens": "Lösche Sensor {id}...",
            "set_learn_mode": "Lernmodus für Gerät {id} auf {mode} gesetzt",
            "get_senders": "Senderliste für Gerät {id} wird abgerufen...",
            "del_sender": "Sender {index} von Gerät {id} wird gelöscht...",
            "save_group": "Speichere Gruppe {id} mit Name '{name}'...",
            "del_group": "Lösche Gruppe {id}...",
            "rename_dev": "Benenne Gerät {id} in '{name}' um...",
            "rename_sens": "Benenne Sensor {id} in '{name}' um...",
            "reset_gw": "Reset-Befehl an Gateway gesendet...",
            "gw_id": "Gateway Identifikation - Hardware: {hw}, Firmware: {fw}",
            "fw_ok": "Gateway Firmware ist aktuell.",
            "fw_warn": "Firmware-Update empfohlen! Aktuell: {fw}, Benötigt: {min}",
            "fw_online": (
                "Neue Firmware online verfügbar: {latest} "
                "(Aktuell: {fw})"
            ),
            "err_name_too_long": "Name ist zu lang (max 23 Bytes).",
            "err_pos_range": (
                "Positions-Wert {pos} für {id} liegt außerhalb "
                "des Bereichs (0-100)."
            ),
            "err_scan_failed": "Gerätescan auf Gateway-Ebene fehlgeschlagen.",
            "err_fw_fetch": "Firmware-Version konnte nicht abgerufen werden: {e}",
            "err_gw_setup": "Fehler beim Initialisieren des Gateways: {e}"
        },
        "api": {
            "learn_success": "Geräte gefunden und gespeichert",
            "learn_timeout": "Keine neuen Geräte gefunden",
            "sensor_success": "Sensor gelernt und registriert",
            "sensor_timeout": "Kein Sensor gelernt",
            "gw_reset_success": "Gateway Reset-Befehl erfolgreich gesendet.",
            "gw_reset_failed": "Gateway Reset-Befehl fehlgeschlagen.",
            "err_unknown_setting": "Unbekannte Einstellung",
            "err_generic_fail": "Aktion fehlgeschlagen",
            "not_found": "Nicht gefunden"
        }
    },
    "en": {
        "ui": {
            "title": "Selve2MQTT Dashboard",
            "btn_learn_actor": "Actor Learning (60s)",
            "btn_learn_sensor": "Sensor Learning (60s)",
            "btn_reset_gw": "Gateway Reset",
            "btn_led_on": "LED On",
            "btn_led_off": "LED Off",
            "btn_new_group": "New Group",
            "btn_rename_gw": "Rename Gateway",
            "gw_status": "Gateway Status",
            "duty_cycle": "Duty Cycle",
            "hw_ver": "HW",
            "fw_ver": "FW",
            "latest_ver": "Latest",
            "header_groups": "Groups",
            "header_devices": "Devices",
            "header_sensors": "Sensors",
            "status": "Status",
            "pos": "Position",
            "btn_open": "Open",
            "btn_stop": "Stop",
            "btn_close": "Close",
            "btn_rename": "Rename",
            "btn_pair": "Pair Remote",
            "btn_show_senders": "Show Senders",
            "btn_delete": "Delete",
            "btn_edit": "Edit",
            "connectivity": "Connectivity",
            "gw_led": "Gateway LED",
            "gw_forwarding": "Commeo Forwarding",
            "gw_duty_cycle": "Gateway Duty Cycle",
            "gw_duty_blocked": "Gateway Duty Cycle Blocked",
            "group_tag": "Group",
            "members": "Member IDs",
            "loading": "Loading...",
            "coupled_senders": "Coupled Senders",
            "no_senders": "No foreign senders found",
            "confirm_reset": "Do you really want to restart the gateway?",
            "confirm_del_group": "Delete group?",
            "confirm_del_device": "Delete device?",
            "confirm_del_sensor": "Delete sensor?",
            "prompt_new_name": "New name",
            "learning_active": "Learning mode active...",
            "learning_sensor_active": (
                "Sensor learning active... Press PROG "
                "button on sensor."
            ),
            "btn_sender_teach_start": "Start sender teach",
            "btn_sender_teach_stop": "Stop sender teach",
            "learning_sender_active": "Sender learning active...",
            "result_prefix": "Result: ",
            "error_start_sender": "Error starting sender teach",
            "error_stop_sender": "Error stopping sender teach",
            "sender_teach_stopped": "Sender teach stopped",
            "learning_finished": "Done.",
            "alert_id_name_required": "ID and name required!",
            "lbl_group_id": "ID (0-63):",
            "status_ok": "OK",
            "status_blocked": "BLOCKED"
        },
        "sensors": {
            "wind": "Wind",
            "rain": "Rain",
            "light": "Light",
            "temp": "Temperature",
            "generic": "Generic"
        },
        "logs": {
            "gw_init": "Selve Gateway initialized (Port: {port})",
            "discovery_start": "Starting discovery of stored devices...",
            "scan_start": "Starting scan for new devices (Learning mode)...",
            "discovery_done": (
                "Discovery finished: {devices} devices, {groups} "
                "groups, {sensors} sensors and {senders} remotes found."
            ),"duty_cycle_event": (
                "GATEWAY EVENT - Duty Cycle: {duty}% "
                "[Status: {status}]"
            ),
            "status_ok": "OK",
            "status_blocked": "BLOCKED",
            "device_unreachable": "Device {name} (ID: {id}) became UNREACHABLE",
            "device_online": "Device {name} (ID: {id}) is back ONLINE",
            "update_received": "Update for {id}: {pos}% (moving={moving}, raw={raw})",
            "cmd_sent": "Command '{cmd}' sent to {type} {id}{val}",
            "type_device": "device",
            "type_group": "group",
            "pairing_start": "Starting pairing mode (Commeo)...",
            "scan_progress": "Scan in progress... found {count} potential devices.",
            "scan_finished": "Scan finished. Found {count} new devices.",
            "save_dev": "Saving device {id} permanently...",
            "sensor_teach_start": "Starting sensor teach-in mode (Commeo)...",
            "sensor_teach_progress": "Sensor teach-in active... {time}s remaining.",
            "sensor_teach_success": (
                "Sensor successfully learned! Assigned "
                "ID: {id}"
            ),
            "del_dev": "Deleting device {id}...",
            "del_sens": "Deleting sensor {id}...",
            "set_learn_mode": "Setting learning mode for device {id} to {mode}",
            "get_senders": "Retrieving sender list for device {id}...",
            "del_sender": "Deleting sender {index} from device {id}...",
            "save_group": "Saving group {id} with name '{name}'...",
            "del_group": "Deleting group {id}...",
            "rename_dev": "Renaming device {id} to '{name}'...",
            "rename_sens": "Renaming sensor {id} to '{name}'...",
            "reset_gw": "Sending reset command to gateway...",
            "gw_id": "Gateway Identification - Hardware: {hw}, Firmware: {fw}",
            "fw_ok": "Gateway firmware is up to date.",
            "fw_warn": "Firmware update recommended! Current: {fw}, Required: {min}",
            "fw_online": (
                "New firmware available online: {latest} "
                "(Current: {fw})"
            ),
            "err_name_too_long": "Name is too long (max 23 bytes).",
            "err_pos_range": (
                "Position value {pos} for {id} is out of "
                "range (0-100)."
            ),
            "err_scan_failed": "Scan failed on gateway level.",
            "err_fw_fetch": "Could not retrieve firmware version: {e}",
            "err_gw_setup": "Error initializing the gateway: {e}"
        },
        "api": {
            "learn_success": "Devices found and saved",
            "learn_timeout": "No new devices found",
            "sensor_success": "Sensor learned and registered",
            "sensor_timeout": "No sensor learned",
            "gw_reset_success": "Gateway reset command sent successfully.",
            "gw_reset_failed": "Gateway reset command failed.",
            "err_unknown_setting": "Unknown setting",
            "err_generic_fail": "Action failed",
            "not_found": "Not found"
        }
    },
    "es": {
        "ui": {
            "title": "Panel Selve2MQTT",
            "btn_learn_actor": "Aprendizaje de Actores (60s)",
            "btn_learn_sensor": "Aprendizaje de Sensores (60s)",
            "btn_reset_gw": "Reiniciar Gateway",
            "btn_led_on": "LED Encendido",
            "btn_led_off": "LED Apagado",
            "btn_new_group": "Nuevo Grupo",
            "btn_rename_gw": "Renombrar Gateway",
            "gw_status": "Estado del Gateway",
            "duty_cycle": "Ciclo de Trabajo",
            "hw_ver": "HW",
            "fw_ver": "FW",
            "latest_ver": "Última",
            "header_groups": "Grupos",
            "header_devices": "Dispositivos",
            "header_sensors": "Sensores",
            "status": "Estado",
            "pos": "Posición",
            "btn_open": "Abrir",
            "btn_stop": "Parar",
            "btn_close": "Cerrar",
            "btn_rename": "Renombrar",
            "btn_pair": "Emparejar Mando",
            "btn_show_senders": "Mostrar Mandos",
            "btn_delete": "Eliminar",
            "btn_edit": "Editar",
            "connectivity": "Conectividad",
            "gw_led": "LED del Gateway",
            "gw_forwarding": "Reenvío Commeo",
            "gw_duty_cycle": "Ciclo de Trabajo del Gateway",
            "gw_duty_blocked": "Ciclo de Trabajo Bloqueado",
            "group_tag": "Grupo",
            "members": "IDs de Miembros",
            "loading": "Cargando...",
            "coupled_senders": "Mandos Acoplados",
            "no_senders": "No se encontraron mandos externos",
            "confirm_reset": "¿Realmente desea reiniciar el gateway?",
            "confirm_del_group": "¿Eliminar grupo?",
            "confirm_del_device": "¿Eliminar dispositivo?",
            "confirm_del_sensor": "¿Eliminar sensor?",
            "prompt_new_name": "Nuevo nombre",
            "learning_active": "Modo aprendizaje activo...",
            "learning_sensor_active": (
                "Aprendizaje de sensor activo... Pulse el "
                "botón PROG en el sensor."
            ),
            "btn_sender_teach_start": "Iniciar aprendizaje de mando",
            "btn_sender_teach_stop": "Detener aprendizaje de mando",
            "learning_sender_active": "Aprendizaje de mando activo...",
            "result_prefix": "Resultado: ",
            "error_start_sender": "Error al iniciar el aprendizaje del mando",
            "error_stop_sender": "Error al detener el aprendizaje del mando",
            "sender_teach_stopped": "Aprendizaje de mando detenido",
            "learning_finished": "Hecho.",
            "alert_id_name_required": "¡ID y nombre requeridos!",
            "lbl_group_id": "ID (0-63):",
            "status_ok": "OK",
            "status_blocked": "BLOQUEADO"
        },
        "sensors": {
            "wind": "Viento",
            "rain": "Lluvia",
            "light": "Luz",
            "temp": "Temperatura",
            "generic": "Sensor"
        },
        "logs": {
            "gw_init": "Gateway Selve inicializado (Puerto: {port})",
            "discovery_start": "Iniciando descubrimiento de dispositivos almacenados...",
            "scan_start": "Iniciando escaneo de nuevos dispositivos (modo aprendizaje)...",
            "discovery_done": (
                "Descubrimiento finalizado: {devices} dispositivos, "
                "{groups} grupos, {sensors} sensores y {senders} mandos encontrados."
            ),
            "duty_cycle_event": (
                "EVENTO DEL GATEWAY - Ciclo de Trabajo: {duty}% "
                "[Estado: {status}]"
            ),
            "status_ok": "OK",
            "status_blocked": "BLOQUEADO",
            "device_unreachable": "Dispositivo {name} (ID: {id}) se volvió INALCANZABLE",
            "device_online": "Dispositivo {name} (ID: {id}) está de nuevo EN LÍNEA",
            "update_received": "Actualización para {id}: {pos}% (moviendo={moving}, raw={raw})",
            "cmd_sent": "Comando '{cmd}' enviado a {type} {id}{val}",
            "type_device": "dispositivo",
            "type_group": "grupo",
            "pairing_start": "Iniciando modo de emparejamiento (Commeo)...",
            "scan_progress": "Escaneo en progreso... {count} dispositivos potenciales encontrados.",
            "scan_finished": "Escaneo finalizado. {count} nuevos dispositivos encontrados.",
            "save_dev": "Guardando dispositivo {id} permanentemente...",
            "sensor_teach_start": "Iniciando modo de aprendizaje de sensor (Commeo)...",
            "sensor_teach_progress": "Aprendizaje de sensor activo... {time}s restantes.",
            "sensor_teach_success": (
                "¡Sensor aprendido exitosamente! ID "
                "asignada: {id}"
            ),
            "del_dev": "Eliminando dispositivo {id}...",
            "del_sens": "Eliminando sensor {id}...",
            "set_learn_mode": "Configurando modo aprendizaje para dispositivo {id} a {mode}",
            "get_senders": "Obteniendo lista de mandos para dispositivo {id}...",
            "del_sender": "Eliminando mando {index} del dispositivo {id}...",
            "save_group": "Guardando grupo {id} con nombre '{name}'...",
            "del_group": "Eliminando grupo {id}...",
            "rename_dev": "Renombrando dispositivo {id} a '{name}'...",
            "rename_sens": "Renombrando sensor {id} a '{name}'...",
            "reset_gw": "Enviando comando de reinicio al gateway...",
            "gw_id": "Identificación del Gateway - Hardware: {hw}, Firmware: {fw}",
            "fw_ok": "El firmware del gateway está actualizado.",
            "fw_warn": "¡Actualización de firmware recomendada! Actual: {fw}, Requerido: {min}",
            "fw_online": (
                "Nuevo firmware disponible en línea: {latest} "
                "(Actual: {fw})"
            ),
            "err_name_too_long": "El nombre es demasiado largo (máx. 23 bytes).",
            "err_pos_range": (
                "El valor de posición {pos} para {id} está fuera "
                "del rango (0-100)."
            ),
            "err_scan_failed": "Escaneo falló a nivel del gateway.",
            "err_fw_fetch": "No se pudo obtener la versión del firmware: {e}",
            "err_gw_setup": "Error al inicializar el gateway: {e}"
        },
        "api": {
            "learn_success": "Dispositivos encontrados y guardados",
            "learn_timeout": "No se encontraron nuevos dispositivos",
            "sensor_success": "Sensor aprendido y registrado",
            "sensor_timeout": "Ningún sensor aprendido",
            "gw_reset_success": "Comando de reinicio del gateway enviado exitosamente.",
            "gw_reset_failed": "Comando de reinicio del gateway falló.",
            "err_unknown_setting": "Configuración desconocida",
            "err_generic_fail": "Acción fallida",
            "not_found": "No encontrado"
        }
    },
    "fr": {
        "ui": {
            "title": "Tableau de Bord Selve2MQTT",
            "btn_learn_actor": "Apprentissage Actionneurs (60s)",
            "btn_learn_sensor": "Apprentissage Capteurs (60s)",
            "btn_reset_gw": "Réinitialiser Gateway",
            "btn_led_on": "LED Allumé",
            "btn_led_off": "LED Éteint",
            "btn_new_group": "Nouveau Groupe",
            "btn_rename_gw": "Renommer Gateway",
            "gw_status": "État du Gateway",
            "duty_cycle": "Cycle d'Utilisation",
            "hw_ver": "HW",
            "fw_ver": "FW",
            "latest_ver": "Dernière",
            "header_groups": "Groupes",
            "header_devices": "Appareils",
            "header_sensors": "Capteurs",
            "status": "État",
            "pos": "Position",
            "btn_open": "Ouvrir",
            "btn_stop": "Arrêter",
            "btn_close": "Fermer",
            "btn_rename": "Renommer",
            "btn_pair": "Appairer Télécommande",
            "btn_show_senders": "Afficher Télécommandes",
            "btn_delete": "Supprimer",
            "btn_edit": "Modifier",
            "connectivity": "Connectivité",
            "gw_led": "LED du Gateway",
            "gw_forwarding": "Transmission Commeo",
            "gw_duty_cycle": "Cycle d'Utilisation du Gateway",
            "gw_duty_blocked": "Cycle d'Utilisation Bloqué",
            "group_tag": "Groupe",
            "members": "IDs des Membres",
            "loading": "Chargement...",
            "coupled_senders": "Télécommandes Couplées",
            "no_senders": "Aucune télécommande externe trouvée",
            "confirm_reset": "Voulez-vous vraiment redémarrer le gateway ?",
            "confirm_del_group": "Supprimer le groupe ?",
            "confirm_del_device": "Supprimer l'appareil ?",
            "confirm_del_sensor": "Supprimer le capteur ?",
            "prompt_new_name": "Nouveau nom",
            "learning_active": "Mode apprentissage actif...",
            "learning_sensor_active": (
                "Apprentissage capteur actif... Appuyez sur "
                "le bouton PROG du capteur."
            ),
            "btn_sender_teach_start": "Démarrer apprentissage télécommande",
            "btn_sender_teach_stop": "Arrêter apprentissage télécommande",
            "learning_sender_active": "Apprentissage télécommande actif...",
            "result_prefix": "Résultat : ",
            "error_start_sender": "Erreur au démarrage de l'apprentissage télécommande",
            "error_stop_sender": "Erreur à l'arrêt de l'apprentissage télécommande",
            "sender_teach_stopped": "Apprentissage télécommande arrêté",
            "learning_finished": "Terminé.",
            "alert_id_name_required": "ID et nom requis !",
            "lbl_group_id": "ID (0-63) :",
            "status_ok": "OK",
            "status_blocked": "BLOQUÉ"
        },
        "sensors": {
            "wind": "Vent",
            "rain": "Pluie",
            "light": "Lumière",
            "temp": "Température",
            "generic": "Capteur"
        },
        "logs": {
            "gw_init": "Gateway Selve initialisé (Port : {port})",
            "discovery_start": "Lancement de la découverte des appareils enregistrés...",
            "scan_start": "Lancement de l'analyse des nouveaux appareils (mode apprentissage)...",
            "discovery_done": (
                "Découverte terminée : {devices} appareils, "
                "{groups} groupes, {sensors} capteurs et {senders} télécommandes trouvés."
            ),
            "duty_cycle_event": (
                "ÉVÉNEMENT GATEWAY - Cycle d'Utilisation : {duty}% "
                "[Statut : {status}]"
            ),
            "status_ok": "OK",
            "status_blocked": "BLOQUÉ",
            "device_unreachable": "Appareil {name} (ID : {id}) est devenu INJOIGNABLE",
            "device_online": "Appareil {name} (ID : {id}) est de retour EN LIGNE",
            "update_received": "Mise à jour pour {id} : {pos}% (en mouvement={moving}, raw={raw})",
            "cmd_sent": "Commande '{cmd}' envoyée à {type} {id}{val}",
            "type_device": "appareil",
            "type_group": "groupe",
            "pairing_start": "Lancement du mode d'appairage (Commeo)...",
            "scan_progress": "Analyse en cours... {count} appareils potentiels trouvés.",
            "scan_finished": "Analyse terminée. {count} nouveaux appareils trouvés.",
            "save_dev": "Enregistrement permanent de l'appareil {id}...",
            "sensor_teach_start": "Lancement du mode d'apprentissage capteur (Commeo)...",
            "sensor_teach_progress": "Apprentissage capteur actif... {time}s restantes.",
            "sensor_teach_success": (
                "Capteur appris avec succès ! ID "
                "attribuée : {id}"
            ),
            "del_dev": "Suppression de l'appareil {id}...",
            "del_sens": "Suppression du capteur {id}...",
            "set_learn_mode": "Configuration du mode apprentissage pour l'appareil {id} à {mode}",
            "get_senders": "Récupération de la liste des télécommandes pour l'appareil {id}...",
            "del_sender": "Suppression de la télécommande {index} de l'appareil {id}...",
            "save_group": "Enregistrement du groupe {id} avec le nom '{name}'...",
            "del_group": "Suppression du groupe {id}...",
            "rename_dev": "Renommage de l'appareil {id} en '{name}'...",
            "rename_sens": "Renommage du capteur {id} en '{name}'...",
            "reset_gw": "Envoi de la commande de réinitialisation au gateway...",
            "gw_id": "Identification du Gateway - Matériel : {hw}, Firmware : {fw}",
            "fw_ok": "Le firmware du gateway est à jour.",
            "fw_warn": "Mise à jour du firmware recommandée ! Actuel : {fw}, Requis : {min}",
            "fw_online": (
                "Nouveau firmware disponible en ligne : {latest} "
                "(Actuel : {fw})"
            ),
            "err_name_too_long": "Le nom est trop long (max 23 octets).",
            "err_pos_range": (
                "La valeur de position {pos} pour {id} est hors "
                "de la plage (0-100)."
            ),
            "err_scan_failed": "L'analyse a échoué au niveau du gateway.",
            "err_fw_fetch": "Impossible de récupérer la version du firmware : {e}",
            "err_gw_setup": "Erreur lors de l'initialisation du gateway : {e}"
        },
        "api": {
            "learn_success": "Appareils trouvés et enregistrés",
            "learn_timeout": "Aucun nouvel appareil trouvé",
            "sensor_success": "Capteur appris et enregistré",
            "sensor_timeout": "Aucun capteur appris",
            "gw_reset_success": "Commande de réinitialisation du gateway envoyée avec succès.",
            "gw_reset_failed": "La commande de réinitialisation du gateway a échoué.",
            "err_unknown_setting": "Paramètre inconnu",
            "err_generic_fail": "Action échouée",
            "not_found": "Non trouvé"
        }
    },
    "nl": {
        "ui": {
            "title": "Selve2MQTT Dashboard",
            "btn_learn_actor": "Actor Leren (60s)",
            "btn_learn_sensor": "Sensor Leren (60s)",
            "btn_reset_gw": "Gateway Resetten",
            "btn_led_on": "LED Aan",
            "btn_led_off": "LED Uit",
            "btn_new_group": "Nieuwe Groep",
            "btn_rename_gw": "Gateway Hernoemen",
            "gw_status": "Gateway Status",
            "duty_cycle": "Duty Cycle",
            "hw_ver": "HW",
            "fw_ver": "FW",
            "latest_ver": "Nieuwste",
            "header_groups": "Groepen",
            "header_devices": "Apparaten",
            "header_sensors": "Sensoren",
            "status": "Status",
            "pos": "Positie",
            "btn_open": "Openen",
            "btn_stop": "Stoppen",
            "btn_close": "Sluiten",
            "btn_rename": "Hernoemen",
            "btn_pair": "Afstandsbediening Koppelen",
            "btn_show_senders": "Zenders Weergeven",
            "btn_delete": "Verwijderen",
            "btn_edit": "Bewerken",
            "connectivity": "Connectiviteit",
            "gw_led": "Gateway LED",
            "gw_forwarding": "Commeo Doorsturen",
            "gw_duty_cycle": "Gateway Duty Cycle",
            "gw_duty_blocked": "Gateway Duty Cycle Geblokkeerd",
            "group_tag": "Groep",
            "members": "Lid IDs",
            "loading": "Laden...",
            "coupled_senders": "Gekoppelde Zenders",
            "no_senders": "Geen externe zenders gevonden",
            "confirm_reset": "Wilt u de gateway echt opnieuw opstarten?",
            "confirm_del_group": "Groep verwijderen?",
            "confirm_del_device": "Apparaat verwijderen?",
            "confirm_del_sensor": "Sensor verwijderen?",
            "prompt_new_name": "Nieuwe naam",
            "learning_active": "Leermodus actief...",
            "learning_sensor_active": (
                "Sensor leren actief... Druk op de "
                "PROG-knop op de sensor."
            ),
            "btn_sender_teach_start": "Zender leren starten",
            "btn_sender_teach_stop": "Zender leren stoppen",
            "learning_sender_active": "Zender leren actief...",
            "result_prefix": "Resultaat: ",
            "error_start_sender": "Fout bij starten van zender leren",
            "error_stop_sender": "Fout bij stoppen van zender leren",
            "sender_teach_stopped": "Zender leren gestopt",
            "learning_finished": "Klaar.",
            "alert_id_name_required": "ID en naam vereist!",
            "lbl_group_id": "ID (0-63):",
            "status_ok": "OK",
            "status_blocked": "GEBLOKKEERD"
        },
        "sensors": {
            "wind": "Wind",
            "rain": "Regen",
            "light": "Licht",
            "temp": "Temperatuur",
            "generic": "Sensor"
        },
        "logs": {
            "gw_init": "Selve Gateway geïnitialiseerd (Poort: {port})",
            "discovery_start": "Starten met ontdekken van opgeslagen apparaten...",
            "scan_start": "Starten met scannen naar nieuwe apparaten (leermodus)...",
            "discovery_done": (
                "Ontdekking voltooid: {devices} apparaten, "
                "{groups} groepen, {sensors} sensoren en {senders} afstandsbedieningen gevonden."
            ),
            "duty_cycle_event": (
                "GATEWAY GEBEURTENIS - Duty Cycle: {duty}% "
                "[Status: {status}]"
            ),
            "status_ok": "OK",
            "status_blocked": "GEBLOKKEERD",
            "device_unreachable": "Apparaat {name} (ID: {id}) is ONBEREIKBAAR geworden",
            "device_online": "Apparaat {name} (ID: {id}) is weer ONLINE",
            "update_received": "Update voor {id}: {pos}% (bewegend={moving}, raw={raw})",
            "cmd_sent": "Commando '{cmd}' verzonden naar {type} {id}{val}",
            "type_device": "apparaat",
            "type_group": "groep",
            "pairing_start": "Starten van koppelmodus (Commeo)...",
            "scan_progress": "Scannen bezig... {count} potentiële apparaten gevonden.",
            "scan_finished": "Scan voltooid. {count} nieuwe apparaten gevonden.",
            "save_dev": "Apparaat {id} permanent opslaan...",
            "sensor_teach_start": "Starten van sensor leermodus (Commeo)...",
            "sensor_teach_progress": "Sensor leren actief... {time}s resterend.",
            "sensor_teach_success": (
                "Sensor succesvol geleerd! Toegewezen "
                "ID: {id}"
            ),
            "del_dev": "Verwijderen apparaat {id}...",
            "del_sens": "Verwijderen sensor {id}...",
            "set_learn_mode": "Leermodus instellen voor apparaat {id} op {mode}",
            "get_senders": "Ophalen zenderlijst voor apparaat {id}...",
            "del_sender": "Verwijderen zender {index} van apparaat {id}...",
            "save_group": "Opslaan groep {id} met naam '{name}'...",
            "del_group": "Verwijderen groep {id}...",
            "rename_dev": "Hernoemen apparaat {id} naar '{name}'...",
            "rename_sens": "Hernoemen sensor {id} naar '{name}'...",
            "reset_gw": "Resetcommando naar gateway verzenden...",
            "gw_id": "Gateway Identificatie - Hardware: {hw}, Firmware: {fw}",
            "fw_ok": "Gateway firmware is up-to-date.",
            "fw_warn": "Firmware-update aanbevolen! Huidig: {fw}, Vereist: {min}",
            "fw_online": (
                "Nieuwe firmware online beschikbaar: {latest} "
                "(Huidig: {fw})"
            ),
            "err_name_too_long": "Naam is te lang (max 23 bytes).",
            "err_pos_range": (
                "Positiewaarde {pos} voor {id} valt buiten "
                "het bereik (0-100)."
            ),
            "err_scan_failed": "Scan mislukt op gateway-niveau.",
            "err_fw_fetch": "Kon firmwareversie niet ophalen: {e}",
            "err_gw_setup": "Fout bij initialiseren van de gateway: {e}"
        },
        "api": {
            "learn_success": "Apparaten gevonden en opgeslagen",
            "learn_timeout": "Geen nieuwe apparaten gevonden",
            "sensor_success": "Sensor geleerd en geregistreerd",
            "sensor_timeout": "Geen sensor geleerd",
            "gw_reset_success": "Gateway resetcommando succesvol verzonden.",
            "gw_reset_failed": "Gateway resetcommando mislukt.",
            "err_unknown_setting": "Onbekende instelling",
            "err_generic_fail": "Actie mislukt",
            "not_found": "Niet gevonden"
        }
    },
    "pt": {
        "ui": {
            "title": "Painel Selve2MQTT",
            "btn_learn_actor": "Aprendizagem de Atuadores (60s)",
            "btn_learn_sensor": "Aprendizagem de Sensores (60s)",
            "btn_reset_gw": "Reiniciar Gateway",
            "btn_led_on": "LED Ligado",
            "btn_led_off": "LED Desligado",
            "btn_new_group": "Novo Grupo",
            "btn_rename_gw": "Renomear Gateway",
            "gw_status": "Estado do Gateway",
            "duty_cycle": "Ciclo de Trabalho",
            "hw_ver": "HW",
            "fw_ver": "FW",
            "latest_ver": "Mais Recente",
            "header_groups": "Grupos",
            "header_devices": "Dispositivos",
            "header_sensors": "Sensores",
            "status": "Estado",
            "pos": "Posição",
            "btn_open": "Abrir",
            "btn_stop": "Parar",
            "btn_close": "Fechar",
            "btn_rename": "Renomear",
            "btn_pair": "Emparelhar Controlo",
            "btn_show_senders": "Mostrar Controlos",
            "btn_delete": "Eliminar",
            "btn_edit": "Editar",
            "connectivity": "Conectividade",
            "gw_led": "LED do Gateway",
            "gw_forwarding": "Encaminhamento Commeo",
            "gw_duty_cycle": "Ciclo de Trabalho do Gateway",
            "gw_duty_blocked": "Ciclo de Trabalho Bloqueado",
            "group_tag": "Grupo",
            "members": "IDs dos Membros",
            "loading": "A carregar...",
            "coupled_senders": "Controlos Acoplados",
            "no_senders": "Nenhum controlo externo encontrado",
            "confirm_reset": "Deseja realmente reiniciar o gateway?",
            "confirm_del_group": "Eliminar grupo?",
            "confirm_del_device": "Eliminar dispositivo?",
            "confirm_del_sensor": "Eliminar sensor?",
            "prompt_new_name": "Novo nome",
            "learning_active": "Modo de aprendizagem ativo...",
            "learning_sensor_active": (
                "Aprendizagem de sensor ativa... Prima o "
                "botão PROG no sensor."
            ),
            "btn_sender_teach_start": "Iniciar aprendizagem de controlo",
            "btn_sender_teach_stop": "Parar aprendizagem de controlo",
            "learning_sender_active": "Aprendizagem de controlo ativa...",
            "result_prefix": "Resultado: ",
            "error_start_sender": "Erro ao iniciar a aprendizagem do controlo",
            "error_stop_sender": "Erro ao parar a aprendizagem do controlo",
            "sender_teach_stopped": "Aprendizagem de controlo parada",
            "learning_finished": "Concluído.",
            "alert_id_name_required": "ID e nome obrigatórios!",
            "lbl_group_id": "ID (0-63):",
            "status_ok": "OK",
            "status_blocked": "BLOQUEADO"
        },
        "sensors": {
            "wind": "Vento",
            "rain": "Chuva",
            "light": "Luz",
            "temp": "Temperatura",
            "generic": "Sensor"
        },
        "logs": {
            "gw_init": "Gateway Selve inicializado (Porta: {port})",
            "discovery_start": "A iniciar descoberta de dispositivos armazenados...",
            "scan_start": "A iniciar pesquisa de novos dispositivos (modo aprendizagem)...",
            "discovery_done": (
                "Descoberta concluída: {devices} dispositivos, "
                "{groups} grupos, {sensors} sensores e {senders} controlos remotos encontrados."
            ),
            "duty_cycle_event": (
                "EVENTO DO GATEWAY - Ciclo de Trabalho: {duty}% "
                "[Estado: {status}]"
            ),
            "status_ok": "OK",
            "status_blocked": "BLOQUEADO",
            "device_unreachable": "Dispositivo {name} (ID: {id}) tornou-se INALCANÇÁVEL",
            "device_online": "Dispositivo {name} (ID: {id}) está de volta ONLINE",
            "update_received": "Atualização para {id}: {pos}% (movendo={moving}, raw={raw})",
            "cmd_sent": "Comando '{cmd}' enviado para {type} {id}{val}",
            "type_device": "dispositivo",
            "type_group": "grupo",
            "pairing_start": "A iniciar modo de emparelhamento (Commeo)...",
            "scan_progress": "Pesquisa em progresso... {count} dispositivos potenciais encontrados.",
            "scan_finished": "Pesquisa concluída. {count} novos dispositivos encontrados.",
            "save_dev": "A guardar dispositivo {id} permanentemente...",
            "sensor_teach_start": "A iniciar modo de aprendizagem de sensor (Commeo)...",
            "sensor_teach_progress": "Aprendizagem de sensor ativa... {time}s restantes.",
            "sensor_teach_success": (
                "Sensor aprendido com sucesso! ID "
                "atribuída: {id}"
            ),
            "del_dev": "A eliminar dispositivo {id}...",
            "del_sens": "A eliminar sensor {id}...",
            "set_learn_mode": "A definir modo de aprendizagem para dispositivo {id} para {mode}",
            "get_senders": "A obter lista de controlos para dispositivo {id}...",
            "del_sender": "A eliminar controlo {index} do dispositivo {id}...",
            "save_group": "A guardar grupo {id} com nome '{name}'...",
            "del_group": "A eliminar grupo {id}...",
            "rename_dev": "A renomear dispositivo {id} para '{name}'...",
            "rename_sens": "A renomear sensor {id} para '{name}'...",
            "reset_gw": "A enviar comando de reinício para o gateway...",
            "gw_id": "Identificação do Gateway - Hardware: {hw}, Firmware: {fw}",
            "fw_ok": "O firmware do gateway está atualizado.",
            "fw_warn": "Atualização de firmware recomendada! Atual: {fw}, Requerido: {min}",
            "fw_online": (
                "Novo firmware disponível online: {latest} "
                "(Atual: {fw})"
            ),
            "err_name_too_long": "O nome é demasiado longo (máx. 23 bytes).",
            "err_pos_range": (
                "O valor de posição {pos} para {id} está fora "
                "do intervalo (0-100)."
            ),
            "err_scan_failed": "Pesquisa falhou ao nível do gateway.",
            "err_fw_fetch": "Não foi possível obter a versão do firmware: {e}",
            "err_gw_setup": "Erro ao inicializar o gateway: {e}"
        },
        "api": {
            "learn_success": "Dispositivos encontrados e guardados",
            "learn_timeout": "Nenhum novo dispositivo encontrado",
            "sensor_success": "Sensor aprendido e registado",
            "sensor_timeout": "Nenhum sensor aprendido",
            "gw_reset_success": "Comando de reinício do gateway enviado com sucesso.",
            "gw_reset_failed": "Comando de reinício do gateway falhou.",
            "err_unknown_setting": "Configuração desconhecida",
            "err_generic_fail": "Ação falhou",
            "not_found": "Não encontrado"
        }
    },
    "it": {
        "ui": {
            "title": "Dashboard Selve2MQTT",
            "btn_learn_actor": "Apprendimento Attuatori (60s)",
            "btn_learn_sensor": "Apprendimento Sensori (60s)",
            "btn_reset_gw": "Riavvio Gateway",
            "btn_led_on": "LED Acceso",
            "btn_led_off": "LED Spento",
            "btn_new_group": "Nuovo Gruppo",
            "btn_rename_gw": "Rinomina Gateway",
            "gw_status": "Stato Gateway",
            "duty_cycle": "Ciclo di Lavoro",
            "hw_ver": "HW",
            "fw_ver": "FW",
            "latest_ver": "Ultima",
            "header_groups": "Gruppi",
            "header_devices": "Dispositivi",
            "header_sensors": "Sensori",
            "status": "Stato",
            "pos": "Posizione",
            "btn_open": "Apri",
            "btn_stop": "Ferma",
            "btn_close": "Chiudi",
            "btn_rename": "Rinomina",
            "btn_pair": "Abbina Telecomando",
            "btn_show_senders": "Mostra Telecomandi",
            "btn_delete": "Elimina",
            "btn_edit": "Modifica",
            "connectivity": "Connettività",
            "gw_led": "LED Gateway",
            "gw_forwarding": "Inoltro Commeo",
            "gw_duty_cycle": "Ciclo di Lavoro Gateway",
            "gw_duty_blocked": "Ciclo di Lavoro Bloccato",
            "group_tag": "Gruppo",
            "members": "ID Membri",
            "loading": "Caricamento...",
            "coupled_senders": "Telecomandi Accoppiati",
            "no_senders": "Nessun telecomando esterno trovato",
            "confirm_reset": "Riavviare realmente il gateway?",
            "confirm_del_group": "Eliminare il gruppo?",
            "confirm_del_device": "Eliminare il dispositivo?",
            "confirm_del_sensor": "Eliminare il sensore?",
            "prompt_new_name": "Nuovo nome",
            "learning_active": "Modalità apprendimento attiva...",
            "learning_sensor_active": (
                "Apprendimento sensore attivo... Premere il "
                "pulsante PROG sul sensore."
            ),
            "btn_sender_teach_start": "Avvia apprendimento telecomando",
            "btn_sender_teach_stop": "Ferma apprendimento telecomando",
            "learning_sender_active": "Apprendimento telecomando attivo...",
            "result_prefix": "Risultato: ",
            "error_start_sender": "Errore nell'avvio dell'apprendimento telecomando",
            "error_stop_sender": "Errore nell'arresto dell'apprendimento telecomando",
            "sender_teach_stopped": "Apprendimento telecomando fermato",
            "learning_finished": "Fatto.",
            "alert_id_name_required": "ID e nome richiesti!",
            "lbl_group_id": "ID (0-63):",
            "status_ok": "OK",
            "status_blocked": "BLOCCATO"
        },
        "sensors": {
            "wind": "Vento",
            "rain": "Pioggia",
            "light": "Luce",
            "temp": "Temperatura",
            "generic": "Sensore"
        },
        "logs": {
            "gw_init": "Gateway Selve inizializzato (Porta: {port})",
            "discovery_start": "Avvio scoperta dispositivi memorizzati...",
            "scan_start": "Avvio scansione nuovi dispositivi (modalità apprendimento)...",
            "discovery_done": (
                "Scoperta completata: {devices} dispositivi, "
                "{groups} gruppi, {sensors} sensori e {senders} telecomandi trovati."
            ),
            "duty_cycle_event": (
                "EVENTO GATEWAY - Ciclo di Lavoro: {duty}% "
                "[Stato: {status}]"
            ),
            "status_ok": "OK",
            "status_blocked": "BLOCCATO",
            "device_unreachable": "Dispositivo {name} (ID: {id}) è diventato IRRAGGIUNGIBILE",
            "device_online": "Dispositivo {name} (ID: {id}) è di nuovo ONLINE",
            "update_received": "Aggiornamento per {id}: {pos}% (in movimento={moving}, raw={raw})",
            "cmd_sent": "Comando '{cmd}' inviato a {type} {id}{val}",
            "type_device": "dispositivo",
            "type_group": "gruppo",
            "pairing_start": "Avvio modalità associazione (Commeo)...",
            "scan_progress": "Scansione in corso... {count} dispositivi potenziali trovati.",
            "scan_finished": "Scansione completata. {count} nuovi dispositivi trovati.",
            "save_dev": "Salvataggio permanente dispositivo {id}...",
            "sensor_teach_start": "Avvio modalità apprendimento sensore (Commeo)...",
            "sensor_teach_progress": "Apprendimento sensore attivo... {time}s rimanenti.",
            "sensor_teach_success": (
                "Sensore appreso con successo! ID "
                "assegnato: {id}"
            ),
            "del_dev": "Eliminazione dispositivo {id}...",
            "del_sens": "Eliminazione sensore {id}...",
            "set_learn_mode": "Impostazione modalità apprendimento per dispositivo {id} a {mode}",
            "get_senders": "Recupero elenco telecomandi per dispositivo {id}...",
            "del_sender": "Eliminazione telecomando {index} dal dispositivo {id}...",
            "save_group": "Salvataggio gruppo {id} con nome '{name}'...",
            "del_group": "Eliminazione gruppo {id}...",
            "rename_dev": "Rinomina dispositivo {id} in '{name}'...",
            "rename_sens": "Rinomina sensore {id} in '{name}'...",
            "reset_gw": "Invio comando di riavvio al gateway...",
            "gw_id": "Identificazione Gateway - Hardware: {hw}, Firmware: {fw}",
            "fw_ok": "Il firmware del gateway è aggiornato.",
            "fw_warn": "Aggiornamento firmware consigliato! Attuale: {fw}, Richiesto: {min}",
            "fw_online": (
                "Nuovo firmware disponibile online: {latest} "
                "(Attuale: {fw})"
            ),
            "err_name_too_long": "Il nome è troppo lungo (max 23 byte).",
            "err_pos_range": (
                "Il valore di posizione {pos} per {id} è fuori "
                "dall'intervallo (0-100)."
            ),
            "err_scan_failed": "Scansione fallita a livello di gateway.",
            "err_fw_fetch": "Impossibile recuperare la versione del firmware: {e}",
            "err_gw_setup": "Errore durante l'inizializzazione del gateway: {e}"
        },
        "api": {
            "learn_success": "Dispositivi trovati e salvati",
            "learn_timeout": "Nessun nuovo dispositivo trovato",
            "sensor_success": "Sensore appreso e registrato",
            "sensor_timeout": "Nessun sensore appreso",
            "gw_reset_success": "Comando di riavvio del gateway inviato con successo.",
            "gw_reset_failed": "Comando di riavvio del gateway fallito.",
            "err_unknown_setting": "Impostazione sconosciuta",
            "err_generic_fail": "Azione fallita",
            "not_found": "Non trovato"
        }
    }
}

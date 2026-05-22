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
            "rssi": "RSSI",
            "btn_open": "Öffnen",
            "btn_stop": "Stop",
            "btn_close": "Schließen",
            "btn_rename": "Umbenennen",
            "btn_pair": "FB Koppeln",
            "btn_show_senders": "Sender anzeigen",
            "btn_delete": "Löschen",
            "btn_edit": "Bearbeiten",
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
            "unit_dbm": "dBm",
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
            "update_received": "Update für {id}: {pos}%",
            "cmd_sent": "Befehl '{cmd}' an {type} {id} gesendet.",
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
            "rssi": "RSSI",
            "btn_open": "Open",
            "btn_stop": "Stop",
            "btn_close": "Close",
            "btn_rename": "Rename",
            "btn_pair": "Pair Remote",
            "btn_show_senders": "Show Senders",
            "btn_delete": "Delete",
            "btn_edit": "Edit",
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
            "unit_dbm": "dBm",
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
            "update_received": "Update for {id}: {pos}%",
            "cmd_sent": "Command '{cmd}' sent to {type} {id}.",
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
    }
}

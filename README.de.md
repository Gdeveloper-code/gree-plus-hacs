# Gree Plus für Home Assistant

[English](README.md) | [Deutsch](README.de.md) | [Español](README.es.md) | [Français](README.fr.md) | [Português (Brasil)](README.pt-BR.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [简体中文](README.zh-Hans.md) | [繁體中文](README.zh-Hant.md)

Gree Plus ist eine inoffizielle, von der Community gepflegte Home-Assistant-Integration für technikaffine Anwender. Sie verbindet unterstützte GREE+-Klimageräte über das GREE+-Cloudkonto des Benutzers mit Home Assistant.

## Funktionen

- Steuerung von Ein/Aus, Betriebsart, Solltemperatur und Lüfterstufe.
- Unterstützung für Celsius, Fahrenheit und modellabhängige Temperaturschritte.
- Statusaktualisierung nach der Einrichtung und nach Steuerbefehlen.
- Manuelle Aktualisierung ohne dauerhafte Abfrage im Hintergrund.

## Voraussetzungen

- Home Assistant 2026.9.1 oder neuer.
- Ein GREE+-Konto mit mindestens einem unterstützten Klimagerät.
- Internetzugriff von Home Assistant auf den Cloud-Dienst.

## Installation

1. Öffnen Sie HACS in Home Assistant.
2. Fügen Sie dieses Repository als benutzerdefiniertes Repository der Kategorie **Integration** hinzu.
3. Laden Sie **Gree Plus** herunter und starten Sie Home Assistant neu.
4. Öffnen Sie **Einstellungen > Geräte & Dienste > Integration hinzufügen** und wählen Sie **Gree Plus**.

## Konfiguration

Wählen Sie die Region des Kontos und melden Sie sich mit dem GREE+-Konto an, dem die Geräte zugeordnet sind. Home Assistant speichert die Authentifizierungsdaten, damit die Integration die Verbindung wiederherstellen kann.

Wenn eine zusätzliche Überprüfung erforderlich ist, öffnen Sie den von Home Assistant angezeigten Anmeldelink, schließen Sie die Prüfung im Browser ab und fügen Sie anschließend die vollständige Adresse `http://localhost/...` aus der Adressleiste ein. Senden Sie das Anmeldeformular nicht wiederholt ab.

## Aktualisierungsverhalten

Die Integration fragt den Status nicht dauerhaft ab. Sie aktualisiert ihn bei der Einrichtung, nach Steuerbefehlen und bei einer manuellen Entitätsaktualisierung. Änderungen außerhalb von Home Assistant werden möglicherweise erst nach der nächsten Aktualisierung angezeigt.

## Einschränkungen

- Unterstützt werden nur Ein/Aus, Betriebsart, Solltemperatur und Lüfterstufe.
- Verfügbare Betriebsarten und Temperaturschritte hängen vom jeweiligen Gerät ab.
- Der Betrieb ist von Verfügbarkeit und Kompatibilität des Cloud-Dienstes abhängig.

## Support und Datenschutz

Melden Sie Fehler über den Issue Tracker des Repositorys. Entfernen Sie vor dem Anhängen von Diagnosedaten oder Protokollen Kontokennungen, Authentifizierungsdaten, Gerätekennungen, Namen und Standortinformationen.

## Haftungsausschluss

Dieses Projekt wird ausschließlich als Home-Assistant-Integration entwickelt und unterstützt. Die Maintainer unterstützen oder befürworten keine Verwendung in davon unabhängigen kommerziellen Produkten oder Diensten.

Dieses Projekt ist nicht mit Gree Electric Appliances, Inc. verbunden und wird von diesem Unternehmen weder empfohlen noch unterstützt. GREE und zugehörige Marken gehören ihren jeweiligen Eigentümern. Der Cloud-Dienst kann sich ohne Vorankündigung ändern oder nicht mehr verfügbar sein. Die Nutzung erfolgt auf eigenes Risiko. Prüfen Sie Automatisierungen vor der Aktivierung und behalten Sie eine offizielle Steuerungsmöglichkeit. Die Maintainer haften nicht für Dienstunterbrechungen, unbeabsichtigte Gerätefunktionen, Datenverlust oder daraus entstehende Schäden.

## Lizenz

MIT

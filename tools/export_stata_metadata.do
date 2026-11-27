* SLC-Datenbank: Export der Stata-Metadaten
* Der zu prüfende Datensatz muss bereits geladen sein.

* Originalzustand sichern
preserve

* Sämtliche Beobachtungen entfernen
keep if 0

* Sicherheitsprüfung
assert _N == 0

* Metadatendatei speichern
save "metadata.dta", replace

* Originalzustand wiederherstellen
restore

display "Metadatenexport erfolgreich abgeschlossen."
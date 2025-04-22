import sys  # Zugriff auf Systemfunktionen (z.B. sys.exit)
from load_data import load_existing_data  # lädt das lokale Experiment-DataFrame
from configuration_functions import load_parameter_and_objective_config  # lädt Parameter- und Objective-Definitionen
from ax_functions import (generate_new_trial, generate_batch_trials, ensure_client, add_outputs_flow, prompt_float)  # Ax-Helpers importieren
from save_data import save_data  # speichert DataFrame in Excel

def main():  # Hauptfunktion
    print("BO-Wasserkefir")  # Programmüberschrift anzeigen
    df, info_cols, fixed_cols = load_existing_data()  # initial Daten laden
    client = None  # AxClient-Handle initialisieren

    while True:  # Menü-Schleife starten
        print("\nMenu:")  # Menü anzeigen
        print("1) Show Data")  # Option 1
        print("2) Generate new trial")  # Option 2
        print("3) Add output values")  # Option 3
        print("0) Exit")  # Option 0
        choice = input("Wahl: ").strip()  # Auswahl einlesen und trimmen

        if choice == "1":  # wenn Show Data gewählt
            df, info_cols, fixed_cols = load_existing_data()  # Daten neu laden
            print("Aktuelle DataFrame:")  # lokale Tabelle ausgeben
            print(df)  # DataFrame drucken

            client = ensure_client(client, df)  # Client initialisieren bzw. laden
            data = client.experiment.fetch_data()  # Ax-Experiment-Daten abrufen
            print("\nDaten im Ax Experiment:")  # Ax-Daten-Überschrift
            print(data.df)  # Ax-DataFrame ausgeben

        elif choice == "2":  # wenn Trial-Generierung gewählt
            has_trials = df["trial_index"].notna().any()  # prüfen, ob schon Trials existieren
            if not has_trials:  # falls keine Trials vorhanden
                cnt = int(input("Sobol‑Anzahl: ").strip())  # Sobol-Anzahl abfragen
                seed_in = input("Seed (Enter none): ").strip()  # optionalen Seed abfragen
                seed = int(seed_in) if seed_in else None  # Seed konvertieren oder None
                client = ensure_client(None, df, sobol_args=(seed, cnt))  # Client mit Sobol-Init.
                df = generate_batch_trials(client, df, cnt)  # Sobol-Trials generieren
                print(f"{cnt} SOBOL‑Trials generiert.")  # Rückmeldung
                model = "Sobol"  # Modellname setzen
            else:  # falls bereits Trials existieren
                cnt = int(input("Anzahl Trials: ").strip())  # Anzahl neuer Trials abfragen
                client = ensure_client(client, df)  # bestehenden Client verwenden
                if cnt == 1:  # wenn genau 1 Trial
                    trial, df = generate_new_trial(client, df)  # neuen Trial generieren
                    if trial:
                        print("Neuer Trial:", trial)  # Trial-Daten anzeigen- kann raus
                else:  # wenn mehrere Trials
                    df = generate_batch_trials(client, df, cnt)  # mehrere Trials generieren
                    print(f"{cnt} neue Trials generiert.")  # Rückmeldung
                model = "BoTorch"  # Modellname setzen
            print(f"Verwendetes Modell: {model}")  # Modell ausgeben
            save_data(df)  # DataFrame speichern

        elif choice == "3":  # wenn Add Outputs gewählt
            client = ensure_client(client, df)  # Client initialisieren/laden
            df = add_outputs_flow(df, client, prompt_float, load_parameter_and_objective_config)  # Outputs abfragen

        elif choice == "0":  # wenn Exit gewählt
            print("Beende.")  # Beenden-Meldung
            save_data(df)  # DataFrame speichern
            break  # Schleife verlassen

        else:  # ungültige Eingabe
            print("Ungültig, bitte 0–3 wählen.")  # Fehlermeldung

        ddf, info_cols, fixed_cols = load_existing_data()  # Daten für nächsten Zyklus neu laden

    sys.exit(0)  # Programm beenden

if __name__ == "__main__":  # Skript-Einstiegspunkt
    main()  # Hauptfunktion aufrufen

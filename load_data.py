import os  # für Dateipfade und Existenzprüfungen
import pandas as pd  # DataFrame-Verarbeitung
from configuration_functions import (load_parameter_and_objective_config, load_feste_parameter_columns, load_column_type_order, CONFIG_PATH, EXPERIMENT_DATA_PATH)  # Config-Pfade und Funktionen

def load_existing_data():  # Hauptfunktion zum Laden der Daten
    parameters, objectives, _ = load_parameter_and_objective_config()  # lade Param-/Objective-Config

    config = pd.read_excel(CONFIG_PATH, sheet_name=None)  # gesamte Config-Datei einlesen
    info_cols = (  # Spalten unter „Informationspalten“
        config.get("Informationspalten", pd.DataFrame()).get("name", pd.Series()).dropna().tolist()
    )
    feste_param_cols = load_feste_parameter_columns()  # feste Parameter-Spalten einlesen

    required_columns = (  # alle notwendigen Spalten
        [p["name"] for p in parameters] + list(objectives.keys()) + ["trial_index"] + info_cols + feste_param_cols
    )

    if os.path.exists(EXPERIMENT_DATA_PATH):  # falls Datei existiert
        df = pd.read_excel(EXPERIMENT_DATA_PATH)  # lade Excel-Datei
    else:
        df = pd.DataFrame(columns=required_columns)  # sonst leeres DataFrame mit Spalten

    for col in required_columns:  # jede erforderliche Spalte prüfen
        if col not in df.columns:  
            df[col] = pd.NA  # fehlende Spalte als NA anlegen

    type_order = load_column_type_order()  # gewünscht Reihenfolge der Spaltentypen
    param_names = [p["name"] for p in parameters]  # Parameternamen-Liste
    type_by_col = {}
    for col in df.columns:  # jeden DataFrame-Spaltennamen klassifizieren
        if col == "trial_index":
            tp = "trial_index"
        elif col in feste_param_cols:
            tp = "feste_parameter"
        elif col in param_names:
            tp = "parameters"
        elif col in objectives:
            tp = "objectives"
        elif col in info_cols:
            tp = "info"
        else:
            tp = None
        type_by_col[col] = tp

    ordered = []
    for t in type_order:  # für jeden Typ in der Reihenfolge
        cols = sorted([c for c, tp in type_by_col.items() if tp == t])  # sortierte Liste
        ordered.extend(cols)  # anhängen
    rest = sorted([c for c in df.columns if type_by_col.get(c) not in type_order])  # übrige Spalten
    ordered.extend(rest)  # anhängen

    df = df[ordered]  # Spalten neu anordnen
    return df, info_cols, feste_param_cols  # Rückgabe: DataFrame und Metalisten

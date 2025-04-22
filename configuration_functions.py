import os  # Dateisystem-Zugriff
import pandas as pd  # DataFrame-Verarbeitung
from ax.service.ax_client import ObjectiveProperties  # für Objective-Definitionen

CONFIG_PATH = "config.xlsx"  # Pfad zur Config-Excel
EXPERIMENT_DATA_PATH = "experiment_data.xlsx"  # Pfad zur Experiment-Daten-Excel

## load_column_type_order - geht auch einfacher (nur Zeile 20)
def load_column_type_order():
    """
    Lädt aus dem Sheet 'ColumnTypeOrder' die gewünschte Reihenfolge der Spaltentypen.
    """
    config = pd.read_excel(CONFIG_PATH, sheet_name=None)  # Config-Datei lesen
    cols = (
        config.get("ColumnTypeOrder", pd.DataFrame(columns=["Spaltentyp"]))["Spaltentyp"]  # Spaltentypen-Liste
        .dropna()  # leere Einträge entfernen
        .tolist()  # als Liste zurückgeben
    )
    if not cols:  # wenn keine Einträge
        cols = ["trial_index", "feste_parameter", "parameters", "objectives", "info"]  # Default-Reihenfolge
    return cols  # Reihenfolge zurückgeben

## load_parameter_and_objective_config
def load_parameter_and_objective_config():
    """
    Liest aus dem Config-Excel:
      - parameters (+ bounds, digits)
      - objectives (mit minimize-Flag)
      - parameter_constraints (als Strings)
    """
    config = pd.read_excel(CONFIG_PATH, sheet_name=None)  # gesamte Config-Datei

    params_df = config.get("parameters", pd.DataFrame())  # Parameter-Sheet
    if {"min_bound", "max_bound"}.issubset(params_df.columns):  # wenn Bounds definiert
        params_df["bounds"] = params_df.apply(
            lambda r: [float(r["min_bound"]), float(r["max_bound"])], axis=1
        )  # bounds-Liste erzeugen
        params_df = params_df.drop(columns=["min_bound", "max_bound"])  # Spalten entfernen
    if "digits" in params_df.columns:  # falls Rundungsstellen definiert
        params_df["digits"] = params_df["digits"].astype("Int64")  # in Int64 umwandeln
    else:
        params_df["digits"] = None  # sonst None
    params_df["value_type"] = params_df["digits"].apply(lambda d: "int" if d == 0 else "float")  # Typ bestimmen
    parameters = params_df.to_dict("records")  # als Liste von Dicts

    objs_df = config.get("objectives", pd.DataFrame(columns=["name", "minimize"]))  # Objectives-Sheet
    objectives = {r["name"]: ObjectiveProperties(minimize=bool(r["minimize"])) for _, r in objs_df.iterrows()}  # Dict erzeugen

    constraint_df = config.get("parameter_constraints", pd.DataFrame())  # Constraints-Sheet
    parameter_constraints = constraint_df.get("constraint", pd.Series()).dropna().tolist()  # als Liste

    return parameters, objectives, parameter_constraints  # zurückgeben

## load_feste_parameter_columns
def load_feste_parameter_columns():
    """
    Liest aus dem Sheet 'Feste_Parameter' die Namen fester Parameter-Spalten.
    """
    if os.path.exists(CONFIG_PATH):  # wenn Config-Datei existiert
        conf = pd.read_excel(CONFIG_PATH, sheet_name=None)  # einlesen
        return conf.get("Feste_Parameter", pd.DataFrame(columns=["name"]))["name"].dropna().tolist()  # Liste zurückgeben
    return []  # sonst leere Liste

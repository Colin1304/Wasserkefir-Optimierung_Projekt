import pandas as pd  # DataFrame-Verarbeitung
from configuration_functions import EXPERIMENT_DATA_PATH  # Pfad zur Experiment-Daten-Excel

def save_data(df, path=None):
    """
    Speichert das gegebene DataFrame in eine Excel-Datei.
    """
    if path is None:  # falls kein Pfad übergeben
        path = EXPERIMENT_DATA_PATH  # Standardpfad verwenden
    df.to_excel(path, index=False)  # DataFrame ohne Index speichern

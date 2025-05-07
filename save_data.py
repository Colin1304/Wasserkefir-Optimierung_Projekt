import pandas as pd
from configuration_functions import EXPERIMENT_DATA_PATH

def save_data(df, path=None):
    """Speichert das DataFrame in eine Excel-Datei."""
    if path is None:
        path = EXPERIMENT_DATA_PATH
    df.to_excel(path, index=False)

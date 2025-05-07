import os
import pandas as pd
from configuration_functions import (
    load_parameter_and_objective_config,
    load_feste_parameter_columns,
    load_column_type_order,
    CONFIG_PATH,
    EXPERIMENT_DATA_PATH,
)

def load_existing_data():
    """
    Lädt vorhandene Experimentdaten, stellt sicher,
    dass alle benötigten Spalten existieren und sortiert sie.
    """
    parameters, objectives, _ = load_parameter_and_objective_config()

    config = pd.read_excel(CONFIG_PATH, sheet_name=None)
    info_cols = (
        config
        .get("Informationspalten", pd.DataFrame())
        .get("name", pd.Series())
        .dropna()
        .tolist()
    )
    feste_param_cols = load_feste_parameter_columns()

    required_columns = (
        [p["name"] for p in parameters]
        + list(objectives.keys())
        + ["trial_index"]
        + info_cols
        + feste_param_cols
    )

    if os.path.exists(EXPERIMENT_DATA_PATH):
        df = pd.read_excel(EXPERIMENT_DATA_PATH)
    else:
        df = pd.DataFrame(columns=required_columns)

    for col in required_columns:
        if col not in df.columns:
            df[col] = pd.NA

    # Spalten nach Typen sortieren
    type_order = load_column_type_order()
    param_names = [p["name"] for p in parameters]
    type_by_col = {}
    for col in df.columns:
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
    for t in type_order:
        cols = sorted([c for c, tp in type_by_col.items() if tp == t])
        ordered.extend(cols)
    rest = sorted([c for c in df.columns if type_by_col.get(c) not in type_order])
    ordered.extend(rest)

    df = df[ordered]
    return df, info_cols, feste_param_cols

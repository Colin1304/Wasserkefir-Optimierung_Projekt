import os
import pandas as pd
from ax.service.ax_client import ObjectiveProperties

CONFIG_PATH = "config.xlsx"
EXPERIMENT_DATA_PATH = "experiment_data.xlsx"

def load_column_type_order():
    """
    Lädt die Spaltentyp-Reihenfolge aus dem Sheet 'ColumnTypeOrder'.
    """
    config = pd.read_excel(CONFIG_PATH, sheet_name=None)
    cols = (
        config
        .get("ColumnTypeOrder", pd.DataFrame(columns=["Spaltentyp"]))
        ["Spaltentyp"]
        .dropna()
        .tolist()
    )
    if not cols:
        cols = ["trial_index", "feste_parameter", "parameters", "objectives", "info"]
    return cols

def load_parameter_and_objective_config():
    """
    Liest Parameter-/Objective-Config aus Excel.
    """
    config = pd.read_excel(CONFIG_PATH, sheet_name=None)
    # Parameter
    params_df = config.get("parameters", pd.DataFrame())
    if {"min_bound", "max_bound"}.issubset(params_df.columns):
        params_df["bounds"] = params_df.apply(
            lambda r: [float(r["min_bound"]), float(r["max_bound"])],
            axis=1,
        )
        params_df = params_df.drop(columns=["min_bound", "max_bound"])
    if "digits" in params_df.columns:
        params_df["digits"] = params_df["digits"].astype("Int64")
    else:
        params_df["digits"] = None
    params_df["value_type"] = params_df["digits"].apply(
        lambda d: "int" if d == 0 else "float"
    )
    parameters = params_df.to_dict("records")

    # Objectives
    objs_df = config.get("objectives", pd.DataFrame(columns=["name", "minimize"]))
    objectives = {
        r["name"]: ObjectiveProperties(minimize=bool(r["minimize"]))
        for _, r in objs_df.iterrows()
    }

    # Parameter-Constraints
    constraint_df = config.get("parameter_constraints", pd.DataFrame())
    parameter_constraints = (
        constraint_df.get("constraint", pd.Series())
        .dropna()
        .tolist()
    )

    return parameters, objectives, parameter_constraints

def load_feste_parameter_columns():
    """
    Liest feste Parameter-Spalten aus Excel.
    """
    if os.path.exists(CONFIG_PATH):
        conf = pd.read_excel(CONFIG_PATH, sheet_name=None)
        return (
            conf
            .get("Feste_Parameter", pd.DataFrame(columns=["name"]))
            ["name"]
            .dropna()
            .tolist()
        )
    return []

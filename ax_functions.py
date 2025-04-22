import warnings  # für Warnungssteuerung
warnings.filterwarnings("ignore", category=FutureWarning)  # Future-Warnings unterdrücken
warnings.filterwarnings("ignore", category=UserWarning, message="Encountered exception in computing model fit quality") #kein Vorhersage‑API implementiert, und daher schlägt dieser Evaluations‑Schritt fehl.
import logging 
logging.getLogger("ax").setLevel(logging.WARNING) # Alle INFO‑Meldungen von Ax komplett ausblenden - zum Debuggen auskommentieren
import math  # für Abrund-Operationen
import pandas as pd  # DataFrame-Verarbeitung
from ax.exceptions.core import DataRequiredError  # Fehler falls Daten fehlen
from ax.service.ax_client import AxClient  # Hauptklasse für Ax
from ax.modelbridge.generation_strategy import GenerationStrategy, GenerationStep  # Strategiedefinition
from ax.modelbridge.registry import Models  # registrierte Modelle
from configuration_functions import load_parameter_and_objective_config  # Config-Funktion
from save_data import save_data  # speichert DataFrame in Excel

## create_ax_client (verwendet in ensure client)
def create_ax_client(sobol_seed=None, sobol_trials=0):
    parameters, objectives, parameter_constraints = load_parameter_and_objective_config()  # Config laden
    steps = []  # Liste der Generationsschritte
    if sobol_trials > 0:  # wenn Sobol-Anteil
        steps.append(GenerationStep(model=Models.SOBOL, num_trials=sobol_trials, model_kwargs={"seed": sobol_seed}))  # Sobol-Step
    steps.append(GenerationStep(model=Models.BOTORCH_MODULAR, num_trials=-1))  # BoTorch-Folge
    strat = GenerationStrategy(steps=steps)  # Strategie zusammenstellen

    client = AxClient(generation_strategy=strat, verbose_logging=False)  # AxClient erzeugen
    client.create_experiment(name="async_experiment", parameters=parameters, objectives=objectives, parameter_constraints=parameter_constraints)  # Experiment erstellen
    return client  # Client zurückgeben

## add_trials_to_ax
def add_trials_to_ax(client: AxClient, df: pd.DataFrame):
    parameters, objectives, _ = load_parameter_and_objective_config()  # Config laden
    pnames = [p["name"] for p in parameters]  # Parameternamen-Liste
    for _, row in df.iterrows():  # jede DataFrame-Zeile
        raw = {k: float(row[k]) for k in pnames if pd.notna(row[k])}  # vorhandene Parameterwerte
        if len(raw) != len(pnames):  # wenn unvollständig
            continue  # überspringen
        floored = {k: math.floor(v * 10) / 10 for k, v in raw.items()}  # abrunden auf 1 Dezim.
        _, trial_index = client.attach_trial(parameters=floored)  # Arm anlegen - Versuchssetup
        results = {o: float(row[o]) for o in objectives if pd.notna(row[o])}  # vorhandene Objectives - baut ein Python‑Dictionary namens results, in dem für jedes Objective (o) ein Eintrag angelegt wird, falls in der aktuellen DataFrame‑Zeile (row) für genau dieses Objective kein NaN (also ein gültiger Messwert) steht
        if results:  # falls Ergebnisse vorliegen
            client.complete_trial(trial_index=trial_index, raw_data=results)  # Trial abschließen

## ensure_client
def ensure_client(client, df, sobol_args=None):
    """
    Stellt sicher, dass ein AxClient existiert und lädt lokale Trials hoch.
    """
    if client is None:  # falls noch kein Client
        if sobol_args:  
            client = create_ax_client(*sobol_args)  # mit Sobol-Init.
        else:
            client = create_ax_client()  # ohne Sobol
        add_trials_to_ax(client, df)  # Trials nach Ax hochladen
    return client  # bestehenden oder neuen Client zurückgeben

## prompt_float
def prompt_float(prompt_text):
    """Fordert eine Fließkommazahl vom Nutzer an und validiert sie."""
    while True:  # Schleife bis gültige Eingabe
        val = input(prompt_text).strip()  # Eingabe abholen
        try:
            return float(val)  # in float umwandeln und zurückgeben
        except ValueError:
            print("Ungültig, bitte Fließzahl eingeben.")  # Fehlermeldung

## add_outputs_flow
def add_outputs_flow(df, client, prompt_fn, load_param_cfg):
    """
    Fragt alle fehlenden Objective-Werte ab, speichert lokal und schließt Trials in Ax ab.
    """
    parameters, objectives, _ = load_param_cfg()  # Config laden
    obj_names = list(objectives.keys())  # Liste der Objective-Namen
    missing_idx = df[df[obj_names].isnull().any(axis=1)].index.tolist()  # Indizes mit fehlenden Outputs
    for count, idx in enumerate(missing_idx, start=1):  # jeden fehlenden Trial
        trial_idx = int(df.at[idx, "trial_index"])  # Trial-Index holen
        print(f"\nTrial {count}/{len(missing_idx)} – Trial Index: {trial_idx}")  # Statusanzeige
        outputs = {}  # Ergebnisse sammeln
        for obj in obj_names:  # jedes Objective
            if pd.isna(df.at[idx, obj]):  # falls Wert fehlt
                val = prompt_fn(f"Wert für {obj}: ")  # abfragen
                df.at[idx, obj] = val  # DataFrame aktualisieren
                outputs[obj] = val  # sammeln
        save_data(df)  # lokal speichern
        client.complete_trial(trial_index=trial_idx, raw_data=outputs)  # Trial abschließen
    print("\nAlle Outputs eingetragen.")  # Abschlussmeldung
    return df  # aktualisiertes DataFrame zurückgeben

## append_trial
def append_trial(df, trial, idx):
    """
    Baut aus neuen Trial-Parametern + Index eine Zeile und hängt sie ans DataFrame.
    """
    row = {**trial, "trial_index": idx}  # Parameter und Index kombinieren
    df2 = pd.concat([df, pd.DataFrame([row])], ignore_index=True)  # Zeile anhängen
    return df2[df.columns]  # mit originaler Spaltenreihenfolge zurückgeben

## generate_new_trial
def generate_new_trial(client, df):
    """
    Generiert einen neuen Trial via AxClient und gibt (params, neues_df) zurück.
    """
    try:
        result = client.get_next_trials(1)  # fordere 1 Trial an
        trials = result[0] if isinstance(result, tuple) else result  # entpacke evtl. Tuple - 0 ist der Index des ersten Elements
    except DataRequiredError:
        print("Fehler: Keine abgeschlossenen Trials vorhanden.")  # Fehler, falls notwendig
        return None, df  # unverändert zurückgeben
    idx, params = next(iter(trials.items()))  #Extrahiere das erste trial_index/Parameter-Dict-Paar aus dem trials-Dictionary
    df2 = append_trial(df, params, idx)  # neuen Trial anhängen
    save_data(df2)  # speichern
    return params, df2  # Parameter und neues DataFrame zurückgeben

## generate_batch_trials
def generate_batch_trials(client, df, cnt):
    """
    Generiert mehrere (cnt) neue Trials und hängt sie ans DataFrame.
    """
    df2 = df.copy()  # Erstelle eine Kopie des DataFrames, um Änderungen daran vorzunehmen, ohne das Original zu verändern
    try:
        result = client.get_next_trials(cnt)  # fordere cnt Trials /cnt=count variable aus abfrage bo_process.py
        trials = result[0] if isinstance(result, tuple) else result #wenn tuple
    except DataRequiredError:
        print("Fehler: Keine abgeschlossenen Trials vorhanden.")  # Fehler
        return df2  # unverändert zurückgeben
    for idx, params in trials.items():  # jeden neuen Trial
        df2 = append_trial(df2, params, idx)  # anhängen
    save_data(df2)  # speichern
    return df2  # erweitertes DataFrame zurückgeben

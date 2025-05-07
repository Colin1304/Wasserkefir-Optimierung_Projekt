import os
import math
import pandas as pd
from ax.exceptions.core import DataRequiredError
from ax.service.ax_client import AxClient
from ax.modelbridge.generation_strategy import GenerationStrategy, GenerationStep
from ax.modelbridge.registry import Models
from configuration_functions import load_parameter_and_objective_config
from save_data import save_data

# Pfad zur Persistenz des AxClients
CLIENT_JSON_PATH = "ax_client.json"


def save_client(client: AxClient):
    """
    Speichert den aktuellen AxClient-Zustand in eine JSON-Datei.
    """
    client.save_to_json_file(CLIENT_JSON_PATH)


def load_client() -> AxClient:
    """
    Lädt den AxClient aus der JSON-Datei.
    """
    return AxClient.load_from_json_file(CLIENT_JSON_PATH)


def create_ax_client(sobol_seed=None, sobol_trials=0) -> AxClient:
    """
    Erzeugt einen neuen AxClient mit:
      - Sobol für `sobol_trials` Trials (falls >0),
      - anschließend unendlich BoTorch.
    """
    parameters, objectives, parameter_constraints = load_parameter_and_objective_config()
    steps = []
    if sobol_trials and sobol_trials > 0:
        steps.append(
            GenerationStep(
                model=Models.SOBOL,
                num_trials=sobol_trials,
                model_kwargs={"seed": sobol_seed},
            )
        )
    steps.append(GenerationStep(model=Models.BOTORCH_MODULAR, num_trials=-1))
    strat = GenerationStrategy(steps=steps)

    client = AxClient(
        generation_strategy=strat,
        verbose_logging=False,
        random_seed=sobol_seed,
    )
    client.create_experiment(
        name="async_experiment",
        parameters=parameters,
        objectives=objectives,
        parameter_constraints=parameter_constraints,
    )
    return client


def add_trials_to_ax(client: AxClient, df: pd.DataFrame) -> None:
    """
    Hängt alle Trials aus `df` (Parameter + Outputs) an den geladenen AxClient.
    Nur solche Zeilen, die bereits Outputs (Objective-Werte) haben, werden komplett angehängt.
    """
    parameters, objectives, _ = load_parameter_and_objective_config()
    pnames = [p["name"] for p in parameters]
    obj_names = [o.name if hasattr(o, "name") else o for o in objectives]

    # Temporär Parameter-Constraints ausschalten
    space = client.experiment.search_space
    old_constraints = space._parameter_constraints
    space._parameter_constraints = []

    for _, row in df.iterrows():
        # Nur Zeilen mit vollständigen Parametern
        if any(pd.isna(row[p]) for p in pnames):
            continue
        params = {p: float(row[p]) for p in pnames}
        # Floorden auf 0.1-Stufen
        params = {k: math.floor(v * 10) / 10 for k, v in params.items()}
        # Attach Trial
        trial, trial_index = client.attach_trial(parameters=params)
        # Wenn Outputs vorhanden, complete_trial
        if not any(pd.isna(row[obj]) for obj in obj_names):
            data = {obj: float(row[obj]) for obj in obj_names}
            client.complete_trial(trial_index=trial_index, raw_data=data)

    # Constraints wiederherstellen
    space._parameter_constraints = old_constraints


def ensure_client(client, df, sobol_args=None):
    """
    1) Wenn `client` schon im Speicher, return.
    2) Wenn `sobol_args=(seed,cnt)` gegeben (erstes Trial):
       - neuen Client mit Sobol(cnt)+BoTorch erzeugen und speichern.
    3) Sonst, wenn JSON existiert (Folgeaufrufe):
       - Client laden,
       - alle im df bereits eingetragenen Trials (inkl. Outputs) anhängen,
       - Strategy auf BoTorch-only setzen,
       - return.
    4) Sonst (erstmaliger Start ohne Sobol-Args):
       - reinen BoTorch-Client erzeugen,
       - vorhandene df-Trials anhängen,
       - speichern und return.
    """
    if client is not None:
        return client

    #  Erstes Trial: Sobol-Phase
    if sobol_args is not None:
        seed, cnt = sobol_args
        client = create_ax_client(sobol_seed=seed, sobol_trials=cnt)
        save_client(client)
        return client

    #  Folgeaufrufe: JSON laden, df-Trials anhängen, BoTorch-only setzen
    if os.path.exists(CLIENT_JSON_PATH):
        client = load_client()
        # Alte Trials + Outputs anhängen
        add_trials_to_ax(client, df)
        # Strategy auf BoTorch-only wechseln
        botorch_only = GenerationStrategy(
            steps=[GenerationStep(model=Models.BOTORCH_MODULAR, num_trials=-1)]
        )
        client._generation_strategy = botorch_only
        return client

    #  Erststart ohne Sobol-Args: BoTorch-Client + df-Trials
    client = create_ax_client()
    add_trials_to_ax(client, df)
    save_client(client)
    return client


def prompt_float(prompt_text):
    """
    Liest von der CLI eine gültige Fließzahl ein.
    """
    while True:
        val = input(prompt_text).strip()
        try:
            return float(val)
        except ValueError:
            print("Ungültig, bitte Fließzahl eingeben.")


def add_outputs_flow(df: pd.DataFrame, client: AxClient, prompt_fn, load_param_cfg):
    """
    Fragt fehlende Objective-Werte ab, schließt Trials ab und speichert.
    """
    parameters, objectives, _ = load_param_cfg()
    obj_names = [o.name if hasattr(o, "name") else o for o in objectives]
    missing_idx = df[df[obj_names].isnull().any(axis=1)].index.tolist()

    for count, idx in enumerate(missing_idx, start=1):
        trial_idx = int(df.at[idx, "trial_index"])
        print(f"\nTrial {count}/{len(missing_idx)} – Trial Index: {trial_idx}")
        outputs = {}
        for obj in obj_names:
            if pd.isna(df.at[idx, obj]):
                val = prompt_fn(f"Wert für {obj}: ")
                df.at[idx, obj] = val
                outputs[obj] = val
        save_data(df)
        client.complete_trial(trial_index=trial_idx, raw_data=outputs)

    print("\nAlle Outputs eingetragen.")
    save_client(client)
    return df


def append_trial(df, params: dict, trial_index: int):
    """
    Hängt eine neue Zeile mit Parametern + trial_index an `df` an.
    """
    floored = {}
    for k, v in params.items():
        try:
            fv = float(v)
            floored[k] = math.floor(fv * 10) / 10
        except (ValueError, TypeError):
            floored[k] = v
    new_row = {**floored, "trial_index": trial_index}
    df2 = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    return df2[df.columns]


def generate_new_trial(client: AxClient, df: pd.DataFrame):
    """
    Generiert einen einzelnen neuen Trial via BoTorch, hängt ihn an df und speichert.
    """
    try:
        result = client.get_next_trials(1)
    except DataRequiredError:
        print("Fehler: Keine abgeschlossenen Trials mit Outputs vorhanden. "
              "Bitte zuerst Option 3 ('Add Outputs') ausführen.")
        return None, df

    trials = result[0] if isinstance(result, tuple) else result
    idx, params = next(iter(trials.items()))
    df2 = append_trial(df, params, idx)
    save_data(df2)
    save_client(client)
    return params, df2


def generate_batch_trials(client: AxClient, df: pd.DataFrame, cnt: int):
    """
    Generiert `cnt` Arms per Batch:
      - Beim ersten Aufruf (Sobol-Phase) Sobol für `cnt` Trials.
      - Danach (BoTorch-only) BoTorch für je `cnt` Trials.
      - Fängt DataRequiredError ab, falls trotzdem keine Daten vorhanden.
    """
    try:
        gen_run = client.generation_strategy.gen(
            experiment=client.experiment,
            n=cnt,
        )
    except DataRequiredError:
        print("Fehler: Keine abgeschlossenen Trials mit Outputs vorhanden. "
              "Bitte zuerst Option 3 ('Add Outputs') ausführen.")
        return df

    batch = client.experiment.new_batch_trial(generator_run=gen_run)
    df2 = df.copy()
    # Verwende für trial_index den internen Arm-Namen (z.B. '0_0', '0_1', ...)
    for arm in batch.arms:
        arm_name = arm.name  # z.B. "0_0", "0_1"
        df2 = append_trial(df2, arm.parameters, arm_name)

    save_data(df2)
    save_client(client)
    return df2

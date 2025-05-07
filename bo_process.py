# bo_process.py
import sys
from load_data import load_existing_data
from ax_functions import (
    generate_new_trial,
    generate_batch_trials,
    ensure_client,
    add_outputs_flow,
    prompt_float,
)
from save_data import save_data

def main():
    print("BO-CLI für Wasserkefir (v23)")
    df, info_cols, fixed_cols = load_existing_data()
    client = None

    while True:
        print("\nMenü:")
        print("1) Show Data")
        print("2) Trial-Generierung")
        print("3) Add Outputs")
        print("0) Exit")
        choice = input("Wahl: ").strip()

        if choice == "1":
            # a) lokales Excel-DF
            df, info_cols, fixed_cols = load_existing_data()
            print("=== Lokales DataFrame ===")
            print(df)

            # b) Ax-Client und alle Arms
            client = ensure_client(client, df)
            print("\n=== Arms im Ax Experiment ===")
            for trial in client.experiment.trials.values():
                for arm in trial.arms:
                    status = trial.status.name
                    print(
                        f"Trial {trial.index} [{status}]: "
                        f"{arm.name} → {arm.parameters}"
                    )

        elif choice == "2":
            has_trials = df["trial_index"].notna().any()
            if not has_trials:
                cnt = int(input("Sobol-Anzahl: ").strip())
                seed_in = input("Seed (Enter none): ").strip()
                seed = int(seed_in) if seed_in else None
                client = ensure_client(client, df, sobol_args=(seed, cnt))
                df = generate_batch_trials(client, df, cnt)
                print(f"{cnt} initiale Sobol-Arms generiert.")
            else:
                cnt = int(input("Anzahl Arms: ").strip())
                client = ensure_client(client, df)
                if cnt == 1:
                    params, df = generate_new_trial(client, df)
                    print("Neuer Arm generiert.")
                else:
                    df = generate_batch_trials(client, df, cnt)
                    print(f"{cnt} neue Arms generiert und Duplikate vermieden.")

            save_data(df)

        elif choice == "3":
            client = ensure_client(client, df)
            df = add_outputs_flow(
                df,
                client,
                prompt_float,
                __import__('configuration_functions', fromlist=['load_parameter_and_objective_config']).load_parameter_and_objective_config
            )

        elif choice == "0":
            print("Beende.")
            save_data(df)
            break

        else:
            print("Ungültig, bitte 0–3 wählen.")

        # nach jeder Aktion Data neu laden
        df, info_cols, fixed_cols = load_existing_data()

    sys.exit(0)

if __name__ == "__main__":
    main()

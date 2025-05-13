#!/usr/bin/env python3
import os

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

mpl.rcParams["hatch.linewidth"] = 0.5


dir_out = "wyniki/wyniki_swiadomosc_topologii"


# Wczytaj dane z pliku Excel
def load_data():
    df = pd.read_excel(
        "wyniki_swiadomosc_topologii.xlsx", sheet_name="Świadomość topologii"
    )

    # Przetwarzamy dane - są one w dwóch blokach kolumn
    blocks = []

    # Pierwszy blok kolumn (Kueue)
    cols1 = [
        "Scenariusz",
        "System",
        "Metryka",
        "Powt. 1",
        "Powt. 2",
        "Powt. 3",
        "Powt. 4",
        "Powt. 5",
        "Średnia (Obliczona)",
        "Odch.Std (Obliczone)",
    ]
    block1 = df.iloc[:, 0:10].copy()
    block1.columns = cols1
    blocks.append(block1)

    # Drugi blok kolumn (Volcano)
    cols2 = [
        "Scenariusz",
        "System",
        "Metryka",
        "Powt. 1",
        "Powt. 2",
        "Powt. 3",
        "Powt. 4",
        "Powt. 5",
        "Średnia (Obliczona)",
        "Odch.Std (Obliczone)",
    ]
    block2 = df.iloc[:, 11:21].copy()
    block2.columns = cols2
    blocks.append(block2)

    # Połącz bloki w jeden DataFrame
    data = pd.concat(blocks, ignore_index=True)

    # Usuń wiersze nagłówkowe i puste
    data = data[data["Scenariusz"] != "Scenariusz"]
    data = data[~data["Scenariusz"].isna()]

    # Konwersja kolumn liczbowych
    data["Średnia (Obliczona)"] = pd.to_numeric(
        data["Średnia (Obliczona)"], errors="coerce"
    )
    data["Odch.Std (Obliczone)"] = pd.to_numeric(
        data["Odch.Std (Obliczone)"], errors="coerce"
    )

    return data


# Funkcja do tworzenia grupowanych wykresów słupkowych
def plot_grouped_bar(
    x_labels, mean_dict, std_dict, title, xlabel, ylabel, labels, outfile
):
    fig, ax = plt.subplots(figsize=(10, 5))
    N = len(x_labels)
    M = len(labels)
    width = 0.8 / M
    offsets = [(-0.4 + width / 2 + i * width) for i in range(M)]

    for i, (system, metric_type) in enumerate(labels):
        means = mean_dict[(system, metric_type)]
        stds = std_dict[(system, metric_type)]

        bars = ax.bar(
            np.arange(N) + offsets[i],
            means,
            width,
            label=f"{system} {metric_type}",
            facecolor=colors[system],
            alpha=0.8,
            edgecolor="black",
            linewidth=0.5,
            hatch=hatches.get(metric_type, ""),
            yerr=stds,
            capsize=3,
            error_kw={"ecolor": "black", "elinewidth": 1.5},
        )

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xticks(np.arange(N))
    ax.set_xticklabels(x_labels)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), borderaxespad=0)
    plt.tight_layout()
    plt.savefig(os.path.join(dir_out, outfile), bbox_inches="tight")
    plt.close()


# Przygotuj mapowanie metryki do klucza pliku i etykiety wyświetlania
file_key_map = {
    # Metryki poprawności rozmieszczenia
    "Poprawność Rozmieszcz. - Krok 1 (Twarde spine) [%]": "Correctness_Step1_Spine",
    "Poprawność Rozmieszcz. - Krok 2 (Miękkie spine) [%]": "Correctness_Step2_Spine",
    "Poprawność Rozmieszcz. - Krok 1 (Twarde block) [%]": "Correctness_Step1_Block",
    "Poprawność Rozmieszcz. - Krok 2 (Miękkie block) [%]": "Correctness_Step2_Block",
    "Poprawność Rozmieszcz. - Krok 1 (Twarde hostname) [%]": "Correctness_Step1_Hostname",
    "Poprawność Rozmieszcz. - Krok 2 (Miękkie hostname) [%]": "Correctness_Step2_Hostname",
    "Poprawność Rozmieszcz. - Krok 2 (Twarde spine) [%]": "Correctness_Step2_Spine_Hard",
    # Metryki odległości topologicznej - średnie
    "Śr. odl. top. - Krok 1 (Twarde spine) [skoki]": "Mean_Distance_Step1_Spine",
    "Śr. odl. top. - Krok 2 (Miękkie spine) [skoki]": "Mean_Distance_Step2_Spine",
    "Śr. odl. top. - Krok 1 (Twarde block) [skoki]": "Mean_Distance_Step1_Block",
    "Śr. odl. top. - Krok 2 (Miękkie block) [skoki]": "Mean_Distance_Step2_Block",
    "Śr. odl. top. - Krok 1 (Twarde hostname) [skoki]": "Mean_Distance_Step1_Hostname",
    "Śr. odl. top. - Krok 2 (Miękkie hostname) [skoki]": "Mean_Distance_Step2_Hostname",
    "Śr. odl. top. - Krok 2 (Twarde spine) [skoki]": "Mean_Distance_Step2_Spine_Hard",
    # Metryki odległości topologicznej - maksymalne
    "Maks. odl. top. - Krok 1 (Twarde spine) [skoki]": "Max_Distance_Step1_Spine",
    "Maks. odl. top. - Krok 2 (Miękkie spine) [skoki]": "Max_Distance_Step2_Spine",
    "Maks. odl. top. - Krok 1 (Twarde block) [skoki]": "Max_Distance_Step1_Block",
    "Maks. odl. top. - Krok 2 (Miękkie block) [skoki]": "Max_Distance_Step2_Block",
    "Maks. odl. top. - Krok 1 (Twarde hostname) [skoki]": "Max_Distance_Step1_Hostname",
    "Maks. odl. top. - Krok 2 (Miękkie hostname) [skoki]": "Max_Distance_Step2_Hostname",
    "Maks. odl. top. - Krok 2 (Twarde spine) [skoki]": "Max_Distance_Step2_Spine_Hard",
    # Metryki czasu oczekiwania (tylko dla T4)
    "Śr. czas oczekiwania - Krok 2 (A + B) [s]": "Mean_Wait_Time_Step2",
    "Maks. czas oczekiwania - Krok 2 (A + B) [s]": "Max_Wait_Time_Step2",
    # Makespan
    "Makespan [s]": "Makespan",
}

# Mapowanie etykiet wyświetlania
display_label_map = {
    # Poprawność rozmieszczenia
    "Correctness_Step1_Spine": "Poprawność rozmieszczenia [%]",
    "Correctness_Step2_Spine": "Poprawność rozmieszczenia [%]",
    "Correctness_Step1_Block": "Poprawność rozmieszczenia [%]",
    "Correctness_Step2_Block": "Poprawność rozmieszczenia [%]",
    "Correctness_Step1_Hostname": "Poprawność rozmieszczenia [%]",
    "Correctness_Step2_Hostname": "Poprawność rozmieszczenia [%]",
    "Correctness_Step2_Spine_Hard": "Poprawność rozmieszczenia [%]",
    # Odległości topologiczne
    "Mean_Distance_Step1_Spine": "Odległość topologiczna [skoki]",
    "Mean_Distance_Step2_Spine": "Odległość topologiczna [skoki]",
    "Mean_Distance_Step1_Block": "Odległość topologiczna [skoki]",
    "Mean_Distance_Step2_Block": "Odległość topologiczna [skoki]",
    "Mean_Distance_Step1_Hostname": "Odległość topologiczna [skoki]",
    "Mean_Distance_Step2_Hostname": "Odległość topologiczna [skoki]",
    "Mean_Distance_Step2_Spine_Hard": "Odległość topologiczna [skoki]",
    "Max_Distance_Step1_Spine": "Odległość topologiczna [skoki]",
    "Max_Distance_Step2_Spine": "Odległość topologiczna [skoki]",
    "Max_Distance_Step1_Block": "Odległość topologiczna [skoki]",
    "Max_Distance_Step2_Block": "Odległość topologiczna [skoki]",
    "Max_Distance_Step1_Hostname": "Odległość topologiczna [skoki]",
    "Max_Distance_Step2_Hostname": "Odległość topologiczna [skoki]",
    "Max_Distance_Step2_Spine_Hard": "Odległość topologiczna [skoki]",
    # Czas oczekiwania
    "Mean_Wait_Time_Step2": "Czas oczekiwania [s]",
    "Max_Wait_Time_Step2": "Czas oczekiwania [s]",
    # Makespan
    "Makespan": "Całkowity czas wykonania [s]",
}

# Mapowanie tytułów wykresów
title_label_map = {
    "Correctness": "Poprawność rozmieszczenia",
    "Distance": "Odległość topologiczna",
    "Wait_Time": "Czas oczekiwania",
    "Makespan": "Całkowity czas wykonania",
}

# Mapowanie typów metryk
metric_type_map = {
    # Poprawność
    "Poprawność Rozmieszcz. - Krok 1 (Twarde spine) [%]": "Krok 1",
    "Poprawność Rozmieszcz. - Krok 2 (Miękkie spine) [%]": "Krok 2",
    "Poprawność Rozmieszcz. - Krok 1 (Twarde block) [%]": "Krok 1",
    "Poprawność Rozmieszcz. - Krok 2 (Miękkie block) [%]": "Krok 2",
    "Poprawność Rozmieszcz. - Krok 1 (Twarde hostname) [%]": "Krok 1",
    "Poprawność Rozmieszcz. - Krok 2 (Miękkie hostname) [%]": "Krok 2",
    "Poprawność Rozmieszcz. - Krok 2 (Twarde spine) [%]": "Krok 2",
    # Średnie odległości
    "Śr. odl. top. - Krok 1 (Twarde spine) [skoki]": "Średnia",
    "Śr. odl. top. - Krok 2 (Miękkie spine) [skoki]": "Średnia",
    "Śr. odl. top. - Krok 1 (Twarde block) [skoki]": "Średnia",
    "Śr. odl. top. - Krok 2 (Miękkie block) [skoki]": "Średnia",
    "Śr. odl. top. - Krok 1 (Twarde hostname) [skoki]": "Średnia",
    "Śr. odl. top. - Krok 2 (Miękkie hostname) [skoki]": "Średnia",
    "Śr. odl. top. - Krok 2 (Twarde spine) [skoki]": "Średnia",
    # Maksymalne odległości
    "Maks. odl. top. - Krok 1 (Twarde spine) [skoki]": "Maksymalna",
    "Maks. odl. top. - Krok 2 (Miękkie spine) [skoki]": "Maksymalna",
    "Maks. odl. top. - Krok 1 (Twarde block) [skoki]": "Maksymalna",
    "Maks. odl. top. - Krok 2 (Miękkie block) [skoki]": "Maksymalna",
    "Maks. odl. top. - Krok 1 (Twarde hostname) [skoki]": "Maksymalna",
    "Maks. odl. top. - Krok 2 (Miękkie hostname) [skoki]": "Maksymalna",
    "Maks. odl. top. - Krok 2 (Twarde spine) [skoki]": "Maksymalna",
    # Czas oczekiwania
    "Śr. czas oczekiwania - Krok 2 (A + B) [s]": "Średni",
    "Maks. czas oczekiwania - Krok 2 (A + B) [s]": "Maksymalny",
    # Makespan
    "Makespan [s]": "",
}

# Grupowanie metryk według typu wykresu
metric_groups = {
    "T1": {
        "Correctness": [
            "Poprawność Rozmieszcz. - Krok 1 (Twarde spine) [%]",
            "Poprawność Rozmieszcz. - Krok 2 (Miękkie spine) [%]",
        ],
        "Distance": [
            "Śr. odl. top. - Krok 1 (Twarde spine) [skoki]",
            "Śr. odl. top. - Krok 2 (Miękkie spine) [skoki]",
            "Maks. odl. top. - Krok 1 (Twarde spine) [skoki]",
            "Maks. odl. top. - Krok 2 (Miękkie spine) [skoki]",
        ],
        "Makespan": ["Makespan [s]"],
    },
    "T2": {
        "Correctness": [
            "Poprawność Rozmieszcz. - Krok 1 (Twarde block) [%]",
            "Poprawność Rozmieszcz. - Krok 2 (Miękkie block) [%]",
        ],
        "Distance": [
            "Śr. odl. top. - Krok 1 (Twarde block) [skoki]",
            "Śr. odl. top. - Krok 2 (Miękkie block) [skoki]",
            "Maks. odl. top. - Krok 1 (Twarde block) [skoki]",
            "Maks. odl. top. - Krok 2 (Miękkie block) [skoki]",
        ],
        "Makespan": ["Makespan [s]"],
    },
    "T3": {
        "Correctness": [
            "Poprawność Rozmieszcz. - Krok 1 (Twarde hostname) [%]",
            "Poprawność Rozmieszcz. - Krok 2 (Miękkie hostname) [%]",
        ],
        "Distance": [
            "Śr. odl. top. - Krok 1 (Twarde hostname) [skoki]",
            "Śr. odl. top. - Krok 2 (Miękkie hostname) [skoki]",
            "Maks. odl. top. - Krok 1 (Twarde hostname) [skoki]",
            "Maks. odl. top. - Krok 2 (Miękkie hostname) [skoki]",
        ],
        "Makespan": ["Makespan [s]"],
    },
    "T4": {
        "Correctness": [
            "Poprawność Rozmieszcz. - Krok 2 (Twarde spine) [%]",
        ],
        "Distance": [
            "Śr. odl. top. - Krok 2 (Twarde spine) [skoki]",
            "Maks. odl. top. - Krok 2 (Twarde spine) [skoki]",
        ],
        "Wait_Time": [
            "Śr. czas oczekiwania - Krok 2 (A + B) [s]",
            "Maks. czas oczekiwania - Krok 2 (A + B) [s]",
        ],
        "Makespan": ["Makespan [s]"],
    },
}

# Systemy i ich kolory
systems = ["Kueue", "Volcano"]
colors = {"Kueue": "blue", "Volcano": "red"}

# Wzory wypełnienia dla różnych typów metryk
hatches = {
    "Krok 1": "////",
    "Krok 2": "",
    "Średnia": "////",
    "Maksymalna": "",
    "Średni": "////",
    "Maksymalny": "",
}


def main():
    # Utworzenie katalogu na wykresy
    os.makedirs(dir_out, exist_ok=True)

    # Wczytanie danych
    data = load_data()

    # Generowanie wykresów dla każdego scenariusza
    scenarios = ["T1", "T2", "T3", "T4"]
    for scenario in scenarios:
        df_scenario = data[data["Scenariusz"] == scenario]
        if df_scenario.empty:
            continue

        # Przetwarzanie każdej grupy metryk
        for group_name, metrics in metric_groups[scenario].items():
            if group_name == "Correctness":
                # Wykres poprawności rozmieszczenia
                labels = []
                mean_dict = {}
                std_dict = {}

                for system in systems:
                    for metric in metrics:
                        metric_type = metric_type_map[metric]
                        label = (system, metric_type)
                        labels.append(label)

                        df_filtered = df_scenario[
                            (df_scenario["System"] == system)
                            & (df_scenario["Metryka"] == metric)
                        ]

                        mean_value = (
                            df_filtered["Średnia (Obliczona)"].values[0]
                            if not df_filtered.empty
                            else 0
                        )
                        std_value = (
                            df_filtered["Odch.Std (Obliczone)"].values[0]
                            if not df_filtered.empty
                            else 0
                        )

                        mean_dict[label] = [mean_value]
                        std_dict[label] = [std_value]

                # Wygeneruj wykres dla poprawności rozmieszczenia
                title = f"Scenariusz {scenario} – {title_label_map[group_name]}"
                outfile = f"{scenario}_{group_name}.svg"
                xlabel = "Scenariusz"
                ylabel = display_label_map[file_key_map[metrics[0]]]

                plot_grouped_bar(
                    [scenario],  # Używamy scenariusza jako etykiety osi X
                    mean_dict,
                    std_dict,
                    title,
                    xlabel,
                    ylabel,
                    labels,
                    outfile,
                )

            elif group_name == "Distance":
                # Wykres odległości topologicznych (średnie i maksymalne)
                # Dzielimy metryki na 'Średnia' i 'Maksymalna'
                mean_metrics = [m for m in metrics if "Śr. odl. top." in m]
                max_metrics = [m for m in metrics if "Maks. odl. top." in m]

                # Przygotuj dane dla średnich odległości
                labels_mean = []
                mean_dict_mean = {}
                std_dict_mean = {}

                for system in systems:
                    for metric in mean_metrics:
                        step_info = "Krok 1" if "Krok 1" in metric else "Krok 2"
                        label = (system, step_info)
                        labels_mean.append(label)

                        df_filtered = df_scenario[
                            (df_scenario["System"] == system)
                            & (df_scenario["Metryka"] == metric)
                        ]

                        mean_value = (
                            df_filtered["Średnia (Obliczona)"].values[0]
                            if not df_filtered.empty
                            else 0
                        )
                        std_value = (
                            df_filtered["Odch.Std (Obliczone)"].values[0]
                            if not df_filtered.empty
                            else 0
                        )

                        mean_dict_mean[label] = [mean_value]
                        std_dict_mean[label] = [std_value]

                # Wygeneruj wykres dla średnich odległości
                title_mean = f"Scenariusz {scenario} – Średnie odległości topologiczne"
                outfile_mean = f"{scenario}_Mean_Distance.svg"
                xlabel = "Scenariusz"
                ylabel = "Średnia odległość topologiczna [skoki]"

                plot_grouped_bar(
                    [scenario],
                    mean_dict_mean,
                    std_dict_mean,
                    title_mean,
                    xlabel,
                    ylabel,
                    labels_mean,
                    outfile_mean,
                )

                # Przygotuj dane dla maksymalnych odległości
                labels_max = []
                mean_dict_max = {}
                std_dict_max = {}

                for system in systems:
                    for metric in max_metrics:
                        step_info = "Krok 1" if "Krok 1" in metric else "Krok 2"
                        label = (system, step_info)
                        labels_max.append(label)

                        df_filtered = df_scenario[
                            (df_scenario["System"] == system)
                            & (df_scenario["Metryka"] == metric)
                        ]

                        mean_value = (
                            df_filtered["Średnia (Obliczona)"].values[0]
                            if not df_filtered.empty
                            else 0
                        )
                        std_value = (
                            df_filtered["Odch.Std (Obliczone)"].values[0]
                            if not df_filtered.empty
                            else 0
                        )

                        mean_dict_max[label] = [mean_value]
                        std_dict_max[label] = [std_value]

                # Wygeneruj wykres dla maksymalnych odległości
                title_max = (
                    f"Scenariusz {scenario} – Maksymalne odległości topologiczne"
                )
                outfile_max = f"{scenario}_Max_Distance.svg"
                xlabel = "Scenariusz"
                ylabel = "Maksymalna odległość topologiczna [skoki]"

                plot_grouped_bar(
                    [scenario],
                    mean_dict_max,
                    std_dict_max,
                    title_max,
                    xlabel,
                    ylabel,
                    labels_max,
                    outfile_max,
                )

            elif group_name == "Wait_Time" and scenario == "T4":
                # Wykres czasów oczekiwania (tylko dla T4)
                labels = []
                mean_dict = {}
                std_dict = {}

                for system in systems:
                    for metric in metrics:
                        metric_type = metric_type_map[metric]
                        label = (system, metric_type)
                        labels.append(label)

                        df_filtered = df_scenario[
                            (df_scenario["System"] == system)
                            & (df_scenario["Metryka"] == metric)
                        ]

                        mean_value = (
                            df_filtered["Średnia (Obliczona)"].values[0]
                            if not df_filtered.empty
                            else 0
                        )
                        std_value = (
                            df_filtered["Odch.Std (Obliczone)"].values[0]
                            if not df_filtered.empty
                            else 0
                        )

                        mean_dict[label] = [mean_value]
                        std_dict[label] = [std_value]

                # Wygeneruj wykres dla czasów oczekiwania
                title = f"Scenariusz {scenario} – {title_label_map[group_name]}"
                outfile = f"{scenario}_{group_name}.svg"
                xlabel = "Scenariusz"
                ylabel = display_label_map[file_key_map[metrics[0]]]

                plot_grouped_bar(
                    [scenario],
                    mean_dict,
                    std_dict,
                    title,
                    xlabel,
                    ylabel,
                    labels,
                    outfile,
                )

            elif group_name == "Makespan":
                # Wykres makespan
                labels = []
                mean_dict = {}
                std_dict = {}

                for system in systems:
                    for metric in metrics:
                        label = (system, "")  # Puste oznaczenie typu metryki
                        labels.append(label)

                        df_filtered = df_scenario[
                            (df_scenario["System"] == system)
                            & (df_scenario["Metryka"] == metric)
                        ]

                        mean_value = (
                            df_filtered["Średnia (Obliczona)"].values[0]
                            if not df_filtered.empty
                            else 0
                        )
                        std_value = (
                            df_filtered["Odch.Std (Obliczone)"].values[0]
                            if not df_filtered.empty
                            else 0
                        )

                        mean_dict[label] = [mean_value]
                        std_dict[label] = [std_value]

                # Wygeneruj wykres dla makespan
                title = f"Scenariusz {scenario} – {title_label_map[group_name]}"
                outfile = f"{scenario}_{group_name}.svg"
                xlabel = "Scenariusz"
                ylabel = display_label_map[file_key_map[metrics[0]]]

                plot_grouped_bar(
                    [scenario],
                    mean_dict,
                    std_dict,
                    title,
                    xlabel,
                    ylabel,
                    labels,
                    outfile,
                )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Wczytanie danych z pliku Excel
df = pd.read_excel("Wyniki.xlsx", sheet_name="Wydajność i Skalowalność")

# Wyciągnięcie bloków danych dla trzech systemów (suffix: "", ".1", ".2")
blocks = []
for suffix in ["", ".1", ".2"]:
    cols = [
        f"Scenariusz{suffix}",
        f"Kombinacja{suffix}",
        f"System{suffix}",
        f"Metryka{suffix}",
        f"Średnia (Obliczona){suffix}",
        f"Odch.Std (Obliczone){suffix}",
    ]
    block = df[cols].copy()
    block.columns = ["Scenariusz", "Kombinacja", "System", "Metryka", "Mean", "Std"]
    blocks.append(block)

data = pd.concat(blocks, ignore_index=True)
# Usunięcie wierszy nagłówkowych i braków
data = data[data["Scenariusz"] != "Scenariusz"]
data = data[data["Metryka"] != "Metryka"]
data.dropna(subset=["Scenariusz", "Metryka"], inplace=True)
data["Mean"] = pd.to_numeric(data["Mean"], errors="coerce")
data["Std"] = pd.to_numeric(data["Std"], errors="coerce")

# Mapowania nazw metryk na klucze plików i etykiety w j. polskim
file_key_map = {
    "Makespan [s]": "Makespan",
    "Śr. Wykorz. CPU (w nasyceniu) [%]": "CPU_Utilization",
    "Śr. Wykorz. Pam. (w nasyceniu) [%]": "RAM_Utilization",
    "Śr. Wykorz. GPU (w nasyceniu) [%]": "GPU_Utilization",
    "Śr. StdDev CPU (w nasyceniu) [%]": "CPU_StdDev",
    "Śr. StdDev Pam. (w nasyceniu) [%]": "RAM_StdDev",
    "Śr. Narzut CPU Harmonogr. [cores]": "CPU_Overhead",
    "Śr. Narzut Pam. Harmonogr. [MB]": "RAM_Overhead",
}

display_label_map = {
    "Makespan": "Całkowity czas wykonania [s]",
    "CPU_Utilization": "Wykorzystanie zasobów (%)",
    "RAM_Utilization": "Wykorzystanie zasobów (%)",
    "GPU_Utilization": "Wykorzystanie zasobów (%)",
    "CPU_StdDev": "Równomierność rozłożenia zasobów (%)",
    "RAM_StdDev": "Równomierność rozłożenia zasobów (%)",
    "CPU_Overhead": "Narzut CPU harmonogramu [rdzenie]",
    "RAM_Overhead": "Narzut pamięci RAM harmonogramu [MB]",
}

# Zmapowanie surowych nazw metryk na klucze zasobów
type_map_util = {
    "Śr. Wykorz. CPU (w nasyceniu) [%]": "CPU",
    "Śr. Wykorz. Pam. (w nasyceniu) [%]": "RAM",
    "Śr. Wykorz. GPU (w nasyceniu) [%]": "GPU",
}
type_map_std = {
    "Śr. StdDev CPU (w nasyceniu) [%]": "CPU",
    "Śr. StdDev Pam. (w nasyceniu) [%]": "RAM",
}

tools = ["Kueue", "Volcano", "YuniKorn"]
colors = {"Kueue": "blue", "Volcano": "red", "YuniKorn": "green"}
hatches = {"CPU": "", "RAM": "//", "GPU": "xx"}


# Funkcja do sortowania kombinacji "WxH"
def sort_key(combo):
    if isinstance(combo, str) and "x" in combo:
        try:
            w, h = combo.split("x")
            return (int(w), int(h))
        except:
            return combo
    return combo


# Katalog na wykresy
dir_out = "wyniki_wydajnosc_i_skalowalnosc_"
os.makedirs(dir_out, exist_ok=True)


# Funkcja rysująca wykres słupkowy z odchyleniami i legendą na zewnątrz
def plot_grouped_bar(
    x_labels, mean_dict, std_dict, title, xlabel, ylabel, labels, outfile
):
    fig, ax = plt.subplots(figsize=(8, 4))
    N = len(x_labels)
    M = len(labels)
    width = 0.8 / M
    offsets = [(-0.4 + width / 2 + i * width) for i in range(M)]
    for i, (tool, resource) in enumerate(labels):
        means = mean_dict[(tool, resource)]
        stds = std_dict[(tool, resource)]
        ax.bar(
            np.arange(N) + offsets[i],
            means,
            width,
            label=f"{tool} {resource}",
            color=colors[tool],
            hatch=hatches.get(resource, ""),
            yerr=stds,
            capsize=3,
        )
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xticks(np.arange(N))
    ax.set_xticklabels(x_labels)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), borderaxespad=0)
    plt.tight_layout()
    plt.savefig(os.path.join(dir_out, outfile), bbox_inches="tight")
    plt.close()


# Generowanie wykresów dla każdego scenariusza
db_util = list(type_map_util.keys())
db_std = list(type_map_std.keys())
scenarios = ["V1", "V2", "V3"]
for scen in scenarios:
    df_s = data[data["Scenariusz"] == scen]
    if df_s.empty:
        continue
    combos = sorted(df_s["Kombinacja"].dropna().unique(), key=sort_key)
    # Wykres wykorzystania zasobów (CPU, RAM, GPU)
    labels_util = []
    mean_util = {}
    std_util = {}
    for tool in tools:
        for raw in db_util:
            resource = type_map_util[raw]
            label = (tool, resource)
            labels_util.append(label)
            df_m = df_s[df_s["Metryka"] == raw]
            piv_mean = df_m.pivot(
                index="Kombinacja", columns="System", values="Mean"
            ).reindex(combos)
            piv_std = df_m.pivot(
                index="Kombinacja", columns="System", values="Std"
            ).reindex(combos)
            mean_util[label] = piv_mean.get(tool, pd.Series([0] * len(combos))).tolist()
            std_util[label] = piv_std.get(tool, pd.Series([0] * len(combos))).tolist()
    plot_grouped_bar(
        combos,
        mean_util,
        std_util,
        f"Scenariusz {scen} – Wykorzystanie zasobów (%)",
        "Kombinacja zadań",
        "Wykorzystanie zasobów (%)",
        labels_util,
        f"{scen}_Wykorzystanie_zasobow.svg",
    )

    # Wykres równomierności rozłożenia zasobów (std CPU, std RAM)
    labels_std = []
    mean_std = {}
    std_std = {}
    for tool in tools:
        for raw in db_std:
            resource = type_map_std[raw]
            label = (tool, resource)
            labels_std.append(label)
            df_m = df_s[df_s["Metryka"] == raw]
            piv_mean = df_m.pivot(
                index="Kombinacja", columns="System", values="Mean"
            ).reindex(combos)
            piv_std = df_m.pivot(
                index="Kombinacja", columns="System", values="Std"
            ).reindex(combos)
            mean_std[label] = piv_mean.get(tool, pd.Series([0] * len(combos))).tolist()
            std_std[label] = piv_std.get(tool, pd.Series([0] * len(combos))).tolist()
    plot_grouped_bar(
        combos,
        mean_std,
        std_std,
        f"Scenariusz {scen} – Równomierność rozłożenia zasobów (%)",
        "Kombinacja zadań",
        "Równomierność rozłożenia zasobów (%)",
        labels_std,
        f"{scen}_Rownomiernosc_zasobow.svg",
    )

    # Pozostałe metryki (Makespan i narzuty)
    for raw_metric, file_key in file_key_map.items():
        if file_key in ["Makespan", "CPU_Overhead", "RAM_Overhead"]:
            df_m = df_s[df_s["Metryka"] == raw_metric]
            if df_m.empty:
                continue
            piv_mean = df_m.pivot(
                index="Kombinacja", columns="System", values="Mean"
            ).reindex(combos)
            piv_std = df_m.pivot(
                index="Kombinacja", columns="System", values="Std"
            ).reindex(combos)
            mean_vals = {
                tool: piv_mean.get(tool, pd.Series([0] * len(combos))).tolist()
                for tool in tools
            }
            std_vals = {
                tool: piv_std.get(tool, pd.Series([0] * len(combos))).tolist()
                for tool in tools
            }
            labels_single = [(tool, "") for tool in tools]
            plot_grouped_bar(
                combos,
                {(tool, ""): mean_vals[tool] for tool in tools},
                {(tool, ""): std_vals[tool] for tool in tools},
                f"Scenariusz {scen} – {display_label_map[file_key]}",
                "Kombinacja zadań",
                display_label_map[file_key],
                labels_single,
                f"{scen}_{file_key}.svg",
            )

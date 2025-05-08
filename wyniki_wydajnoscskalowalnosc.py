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
    "Śr. StdDev GPU (w nasyceniu) [%]": "GPU_StdDev",
    "Śr. Narzut CPU Harmonogr. [cores]": "CPU_Overhead",
    "Śr. Narzut Pam. Harmonogr. [MB]": "RAM_Overhead",
}

display_label_map = {
    "Makespan": "Całkowity czas wykonania [s]",
    "CPU_Utilization": "Wykorzystanie CPU (%)",
    "RAM_Utilization": "Wykorzystanie pamięci RAM (%)",
    "GPU_Utilization": "Wykorzystanie GPU (%)",
    "CPU_StdDev": "Odchylenie standardowe CPU (%)",
    "RAM_StdDev": "Odchylenie standardowe pamięci RAM (%)",
    "GPU_StdDev": "Odchylenie standardowe GPU (%)",
    "CPU_Overhead": "Narzut CPU harmonogramu [rdzenie]",
    "RAM_Overhead": "Narzut pamięci RAM harmonogramu [MB]",
}

tools = ["Kueue", "Volcano", "YuniKorn"]
colors = {"Kueue": "blue", "Volcano": "red", "YuniKorn": "green"}


# Funkcja do sortowania kombinacji "WxH"
def sort_key(combo):
    if isinstance(combo, str) and "x" in combo:
        w, h = combo.split("x")
        try:
            return (int(w), int(h))
        except:
            return combo
    return combo


# Utworzenie katalogu na wykresy
dir_out = "wyniki_wydajnosc_i_skalowalnosc_"
os.makedirs(dir_out, exist_ok=True)


# Funkcja rysująca wykres słupkowy z odchyleniami standardowymi i legendą spoza obszaru
def plot_grouped_bar(x_labels, mean_dict, std_dict, title, xlabel, ylabel, outfile):
    x = np.arange(len(x_labels))
    width = 0.2
    fig, ax = plt.subplots(figsize=(6, 4))
    offsets = [-width, 0, width]
    for i, tool in enumerate(tools):
        means = mean_dict.get(tool, [0] * len(x_labels))
        stds = std_dict.get(tool, [0] * len(x_labels))
        ax.bar(
            x + offsets[i],
            means,
            width,
            label=tool,
            color=colors[tool],
            yerr=stds,
            capsize=3,
        )
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels)
    # Legenda poza wykresem po prawej stronie
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), borderaxespad=0)
    plt.tight_layout()
    plt.savefig(os.path.join(dir_out, outfile), bbox_inches="tight")
    plt.close()


# Generowanie wykresów dla poszczególnych scenariuszy
tasks = ["V1", "V2", "V3"]
for scen in tasks:
    df_s = data[data["Scenariusz"] == scen]
    if df_s.empty:
        continue
    combos = sorted(df_s["Kombinacja"].dropna().unique(), key=sort_key)
    for raw_metric, file_key in file_key_map.items():
        df_m = df_s[df_s["Metryka"] == raw_metric]
        if df_m.empty:
            continue
        piv_mean = df_m.pivot(
            index="Kombinacja", columns="System", values="Mean"
        ).reindex(combos)
        piv_std = df_m.pivot(
            index="Kombinacja", columns="System", values="Std"
        ).reindex(combos)
        mean_vals = {tool: piv_mean[tool].fillna(0).tolist() for tool in tools}
        std_vals = {tool: piv_std[tool].fillna(0).tolist() for tool in tools}
        title = f"Scenariusz {scen} – {display_label_map[file_key]}"
        xlabel = "Kombinacja zadań"
        ylabel = display_label_map[file_key]
        outfile = f"{scen}_{file_key}.svg"
        plot_grouped_bar(combos, mean_vals, std_vals, title, xlabel, ylabel, outfile)

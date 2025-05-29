#!/usr/bin/env python3
import os

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

mpl.rcParams["hatch.linewidth"] = 0.5

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
    "Makespan": "Makespan [s]",
    "CPU_Utilization": "Resource utilization (%)",
    "RAM_Utilization": "Resource utilization (%)",
    "GPU_Utilization": "Resource utilization (%)",
    "CPU_StdDev": "Resource distribution evenness (%)",
    "RAM_StdDev": "Resource distribution evenness (%)",
    "CPU_Overhead": "CPU scheduler overhead [cores]",
    "RAM_Overhead": "Memory scheduler overhead [MB]",
}

title_label_map = {
    "Makespan": "Makespan",
    "CPU_Utilization": "Resource utilization",
    "RAM_Utilization": "Resource utilization",
    "GPU_Utilization": "Resource utilization",
    "CPU_StdDev": "Resource distribution evenness",
    "RAM_StdDev": "Resource distribution evenness",
    "CPU_Overhead": "CPU scheduler overhead",
    "RAM_Overhead": "Memory scheduler overhead",
}

type_map_util = {
    "Śr. Wykorz. CPU (w nasyceniu) [%]": "CPU",
    "Śr. Wykorz. Pam. (w nasyceniu) [%]": "Memory",
    "Śr. Wykorz. GPU (w nasyceniu) [%]": "GPU",
}

type_map_std = {
    "Śr. StdDev CPU (w nasyceniu) [%]": "CPU",
    "Śr. StdDev Pam. (w nasyceniu) [%]": "Memory",
    "Śr. StdDev GPU (w nasyceniu) [%]": "GPU",
}

tools = ["Kueue", "Volcano", "YuniKorn"]
colors = {"Kueue": "blue", "Volcano": "red", "YuniKorn": "green"}
hatches = {"CPU": "////", "Memory": "", "GPU": "xxx"}


def load_data(path, sheet):
    """
    Wczytuje dane z Excela i przygotowuje blokowe połączenie danych.
    """
    df = pd.read_excel(path, sheet_name=sheet)
    return prepare_blocks(df)


def prepare_blocks(df):
    """
    Łączy bloki danych z sufiksami '', '.1', '.2', filtruje nagłówki i konwertuje na odpowiednie typy.
    """
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
    data = data[data["Scenariusz"] != "Scenariusz"]
    data = data[data["Metryka"] != "Metryka"]
    data.dropna(subset=["Scenariusz", "Metryka"], inplace=True)
    data["Mean"] = pd.to_numeric(data["Mean"], errors="coerce")
    data["Std"] = pd.to_numeric(data["Std"], errors="coerce")
    return data


def sort_key(combo):
    """
    Klucz sortujący kombinacje w formacie 'WxH' według wartości liczbowych.
    """
    if isinstance(combo, str) and "x" in combo:
        try:
            w, h = combo.split("x")
            return (int(w), int(h))
        except Exception:
            return combo
    return combo


def plot_grouped_bar(
    x_labels, mean_dict, std_dict, title, xlabel, ylabel, labels, outfile, output_dir
):
    """
    Pomocnicza funkcja do rysowania grupowanych wykresów słupkowych z wartościami na słupkach.
    """
    fig, ax = plt.subplots(figsize=(10, 6))  # Zwiększone rozmiary dla czytelności
    N = len(x_labels)
    M = len(labels)
    width = 0.8 / M
    offsets = [(-0.4 + width / 2 + i * width) for i in range(M)]

    # Znajdź maksymalną wartość do ustalenia marginesu górnego
    max_val = 0
    for i, (tool, resource) in enumerate(labels):
        means = mean_dict[(tool, resource)]
        stds = std_dict[(tool, resource)]
        for j in range(len(means)):
            val_with_error = means[j] + stds[j]
            if val_with_error > max_val:
                max_val = val_with_error

    for i, (tool, resource) in enumerate(labels):
        means = mean_dict[(tool, resource)]
        stds = std_dict[(tool, resource)]

        bars = ax.bar(
            np.arange(N) + offsets[i],
            means,
            width,
            label=f"{tool} {resource}",
            facecolor=colors[tool],
            alpha=0.8,
            edgecolor="black",
            linewidth=0.5,
            hatch=hatches.get(resource, ""),
            yerr=stds,
            capsize=3,
            error_kw={"ecolor": "black", "elinewidth": 1.5},
        )

        # Dodaj wartości na słupkach
        for j, (bar, mean_val, std_val) in enumerate(zip(bars, means, stds)):
            # Pokaż wartość na każdym słupku, również gdy wynosi 0
            # Pozycja tekstu nad słupkiem (z uwzględnieniem error bar)
            y_pos = mean_val + std_val + (max_val * 0.02)  # 2% marginesu
            x_pos = bar.get_x() + bar.get_width() / 2

            # Formatowanie wartości - zawsze 2 miejsca po przecinku
            text_val = f"{mean_val:.2f}"

            # Dodaj tekst z wartością
            ax.text(
                x_pos,
                y_pos,
                text_val,
                ha="center",
                va="bottom",
                fontsize=8,  # Mały font dla czytelności
                fontweight="bold",
                color="black",
                bbox=dict(
                    boxstyle="round,pad=0.2",
                    facecolor="white",
                    alpha=0.8,
                    edgecolor="none",
                ),
            )

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xticks(np.arange(N))
    ax.set_xticklabels(
        x_labels, rotation=45, ha="right"
    )  # Obrót etykiet dla lepszej czytelności

    # Zwiększ margines górny o 15% dla zmieszczenia etykiet
    ax.set_ylim(0, max_val * 1.15)

    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), borderaxespad=0)
    ax.grid(True, alpha=0.3, axis="y")  # Delikatna siatka dla lepszej czytelności

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, outfile), bbox_inches="tight", dpi=300)
    plt.close()


def draw_resource_utilization(df, scenario, output_dir):
    """
    Rysuje wykres wykorzystania zasobów (CPU, RAM, GPU) dla danego scenariusza.
    """
    df_s = df[df["Scenariusz"] == scenario]
    combos = sorted(df_s["Kombinacja"].dropna().unique(), key=sort_key)
    db_util = list(type_map_util.keys())
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
        f"Scenario {scenario} – Resource utilization",
        "Node and task combinations",
        "Resource utilization (%)",
        labels_util,
        f"{scenario}_Wykorzystanie_zasobow.svg",
        output_dir,
    )


def draw_resource_distribution(df, scenario, output_dir):
    """
    Rysuje wykres równomierności rozłożenia zasobów (std CPU, std RAM, std GPU) dla danego scenariusza.
    """
    df_s = df[df["Scenariusz"] == scenario]
    combos = sorted(df_s["Kombinacja"].dropna().unique(), key=sort_key)
    db_std = list(type_map_std.keys())
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
        f"Scenario {scenario} – Resource distribution evenness",
        "Node and task combinations",
        "Resource distribution evenness (%)",
        labels_std,
        f"{scenario}_Rownomiernosc_zasobow.svg",
        output_dir,
    )


def draw_other_metrics(df, scenario, output_dir):
    """
    Rysuje wykresy dla pozostałych metryk: Makespan i narzutów zasobów.
    """
    df_s = df[df["Scenariusz"] == scenario]
    combos = sorted(
        df_s["Kombinacja"].dropna().unique(), key=sort_key
    )  # REFAKTOR: compute combos here
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
                f"Scenario {scenario} – {title_label_map[file_key]}",
                "Node and task combinations",
                display_label_map[file_key],
                labels_single,
                f"{scenario}_{file_key}.svg",
                output_dir,
            )


if __name__ == "__main__":
    input_file = "Wyniki.xlsx"
    sheet = "Wydajność i Skalowalność"
    output_base = "wyniki/wyniki_wydajnosc_i_skalowalnosc"
    os.makedirs(output_base, exist_ok=True)
    data = load_data(input_file, sheet)
    scenarios = ["V1", "V2", "V3"]
    for scen in scenarios:
        df_s = data[data["Scenariusz"] == scen]
        if df_s.empty:
            continue
        draw_resource_utilization(data, scen, output_base)
        draw_resource_distribution(data, scen, output_base)
        draw_other_metrics(data, scen, output_base)

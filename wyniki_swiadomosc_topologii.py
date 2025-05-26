#!/usr/bin/env python3
"""
Script do generowania wykresów świadomości topologii z pliku Excel.
"""

import os
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

# Kolory wykresów dla porównania systemów
colors = {"Kueue": "blue", "Volcano": "red"}
# Sposób rysowania hatch wzorem z wyniki_wydajnoscskalowalnosc.py
hatches_wait = {"Średni czas oczekiwania": "xxx", "Maksymalny czas oczekiwania": ""}
# Ustawienia globalne Matplotlib
plt.rcParams["hatch.linewidth"] = 0.5


def translate_step_label(label):
    """
    Tłumaczy polskie etykiety kroków na angielskie.
    """
    return (
        label.replace("Krok", "Step")
        .replace("Miękkie", "Soft")
        .replace("Twarde", "Hard")
    )


def load_data(path, sheet):
    """
    Wczytuje dane z Excela i przygotowuje blokowe połączenie danych.
    Zwraca DataFrame z kolumnami: Scenariusz, System, Metryka, Mean, Std.
    """
    raw = pd.read_excel(path, sheet_name=sheet)
    return prepare_blocks(raw)


def prepare_blocks(df):
    """
    Łączy bloki danych z sufiksami '', '.1', filtruje nagłówki i konwertuje na odpowiednie typy.
    """
    blocks = []
    for suffix in ["", ".1"]:
        cols = [
            f"Scenariusz{suffix}",
            f"System{suffix}",
            f"Metryka{suffix}",
            f"Średnia (Obliczona){suffix}",
            f"Odch.Std (Obliczone){suffix}",
        ]
        block = df[cols].copy()
        block.columns = ["Scenariusz", "System", "Metryka", "Mean", "Std"]
        blocks.append(block)
    data = pd.concat(blocks, ignore_index=True)
    data = data[(data["Scenariusz"] != "Scenariusz") & (data["Metryka"] != "Metryka")]
    data.dropna(subset=["Scenariusz", "Metryka"], inplace=True)
    data["Mean"] = pd.to_numeric(data["Mean"], errors="coerce")
    data["Std"] = pd.to_numeric(data["Std"], errors="coerce")
    return data


def add_value_labels(ax, bars, values, stds, max_val):
    """
    Pomocnicza funkcja dodająca etykiety z wartościami na słupkach.
    """
    for bar, val, std in zip(bars, values, stds):
        # Pokaż wartość na każdym słupku, również gdy wynosi 0
        # Pozycja tekstu nad słupkiem (z uwzględnieniem error bar)
        y_pos = val + std + (max_val * 0.02)  # 2% marginesu
        x_pos = bar.get_x() + bar.get_width() / 2

        # Formatowanie wartości - zawsze 2 miejsca po przecinku
        text_val = f"{val:.2f}"

        # Dodaj tekst z wartością
        ax.text(
            x_pos,
            y_pos,
            text_val,
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="bold",
            color="black",
            bbox=dict(
                boxstyle="round,pad=0.2", facecolor="white", alpha=0.8, edgecolor="none"
            ),
        )


def draw_correctness(df, scenario, output_dir):
    """
    Rysuje wykres poprawności rozmieszczenia dla scenariusza.
    Zapisuje 'T?_correctness.svg'.
    """
    df_s = df[df["Scenariusz"] == scenario]
    pattern = r"Poprawność Rozmieszcz\. - Krok \d"
    metrics = df_s[df_s["Metryka"].str.contains(pattern)]["Metryka"].unique().tolist()
    metrics.sort(key=lambda m: int(re.search(r"Krok (\d)", m).group(1)))
    x_labels = [translate_step_label(m.split(" - ")[1].split(" [")[0]) for m in metrics]

    systems = ["Kueue", "Volcano"]
    mean_vals, std_vals = {sys: [] for sys in systems}, {sys: [] for sys in systems}
    for m in metrics:
        for sys in systems:
            row = df_s[(df_s["Metryka"] == m) & (df_s["System"] == sys)]
            if not row.empty:
                mean_vals[sys].append(row["Mean"].iat[0])
                std_vals[sys].append(row["Std"].iat[0])
            else:
                mean_vals[sys].append(0)
                std_vals[sys].append(0)

    # Oblicz maksymalną wartość dla marginesu
    max_val = 0
    for sys in systems:
        for mean, std in zip(mean_vals[sys], std_vals[sys]):
            val_with_error = mean + std
            if val_with_error > max_val:
                max_val = val_with_error

    fig, ax = plt.subplots(figsize=(8, 5))  # Zwiększone rozmiary
    N, M = len(x_labels), len(systems)
    width = 0.8 / M
    offsets = [(-0.4 + width / 2 + i * width) for i in range(M)]

    for i, sys in enumerate(systems):
        bars = ax.bar(
            [j + offsets[i] for j in range(N)],
            mean_vals[sys],
            width,
            yerr=std_vals[sys],
            capsize=3,
            label=sys,
            facecolor=colors[sys],
            alpha=0.8,
            edgecolor="black",
            linewidth=0.5,
        )

        # Dodaj wartości na słupkach
        add_value_labels(ax, bars, mean_vals[sys], std_vals[sys], max_val)

    ax.set_xlabel("Step")
    ax.set_ylabel("Placement correctness [%]")
    ax.set_xticks(range(N))
    ax.set_xticklabels(x_labels)
    ax.set_ylim(0, max_val * 1.15)  # Margines górny
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1), frameon=False)
    ax.grid(True, alpha=0.3, axis="y")  # Siatka
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{scenario}_correctness.svg"), dpi=300)
    plt.close()


def draw_distances(df, scenario, output_dir):
    """
    Dwa wykresy odległości: avg i max per krok.
    Zapisuje 'T?_avg_distances.svg' i 'T?_max_distances.svg'.
    """
    df_s = df[df["Scenariusz"] == scenario]
    avg_metrics = sorted(
        {m for m in df_s["Metryka"] if m.startswith("Śr. odl.")},
        key=lambda m: int(re.search(r"Krok (\d)", m).group(1)),
    )
    max_metrics = sorted(
        {m for m in df_s["Metryka"] if m.startswith("Maks. odl.")},
        key=lambda m: int(re.search(r"Krok (\d)", m).group(1)),
    )

    def plot_metrics(metrics, title_label, filename):
        labels = [
            translate_step_label(m.split(" - ")[1].split(" [")[0]) for m in metrics
        ]
        systems = ["Kueue", "Volcano"]
        mean_vals, std_vals = {sys: [] for sys in systems}, {sys: [] for sys in systems}
        for m in metrics:
            for sys in systems:
                row = df_s[(df_s["Metryka"] == m) & (df_s["System"] == sys)]
                if not row.empty:
                    mean_vals[sys].append(row["Mean"].iat[0])
                    std_vals[sys].append(row["Std"].iat[0])
                else:
                    mean_vals[sys].append(0)
                    std_vals[sys].append(0)

        # Oblicz maksymalną wartość dla marginesu
        max_val = 0
        for sys in systems:
            for mean, std in zip(mean_vals[sys], std_vals[sys]):
                val_with_error = mean + std
                if val_with_error > max_val:
                    max_val = val_with_error

        fig, ax = plt.subplots(figsize=(8, 5))  # Zwiększone rozmiary
        N, M = len(labels), len(systems)
        width = 0.8 / M
        offsets = [(-0.4 + width / 2 + i * width) for i in range(M)]

        for i, sys in enumerate(systems):
            bars = ax.bar(
                [j + offsets[i] for j in range(N)],
                mean_vals[sys],
                width,
                yerr=std_vals[sys],
                capsize=3,
                label=sys,
                facecolor=colors[sys],
                alpha=0.8,
                edgecolor="black",
                linewidth=0.5,
            )

            # Dodaj wartości na słupkach
            add_value_labels(ax, bars, mean_vals[sys], std_vals[sys], max_val)

        ax.set_xlabel("Step")
        ax.set_ylabel("Distance [hops]")
        ax.set_xticks(range(N))
        ax.set_xticklabels(labels)
        ax.set_ylim(0, max_val * 1.15)  # Margines górny
        ax.legend(loc="upper left", bbox_to_anchor=(1, 1), frameon=False)
        ax.grid(True, alpha=0.3, axis="y")  # Siatka
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, filename), dpi=300)
        plt.close()

    plot_metrics(
        avg_metrics, "Average topological distance", f"{scenario}_avg_distances.svg"
    )
    plot_metrics(
        max_metrics,
        "Maximum topological distance",
        f"{scenario}_max_distances.svg",
    )


def draw_wait_times(df, scenario, output_dir):
    """
    Dodatkowy wykres dla T4: średni i maksymalny czas oczekiwania per system.
    Zapisuje 'T4_wait_times.svg'.
    """
    if scenario != "T4":
        return
    df_s = df[df["Scenariusz"] == scenario]
    # Filtracja unikalnych metryk oczekiwania tylko dla T4
    wait_metrics_set = {m for m in df_s["Metryka"] if "czas oczekiwania" in m}
    # Sortuj: średni (Śr.) przed maksymalny (Maks.)
    wait_metrics = sorted(wait_metrics_set, key=lambda m: m.startswith("Maks."))
    # Etykiety: pełne z nazwą metryki i krokiem, bez jednostek
    labels = [
        m.split(" [")[0].replace("Śr.", "Average").replace("Maks.", "Maximum")
        for m in wait_metrics
    ]

    systems = ["Kueue", "Volcano"]
    mean_vals = {lbl: [] for lbl in labels}
    std_vals = {lbl: [] for lbl in labels}
    for m, lbl in zip(wait_metrics, labels):
        for sys in systems:
            row = df_s[(df_s["Metryka"] == m) & (df_s["System"] == sys)]
            if not row.empty:
                mean_vals[lbl].append(row["Mean"].iat[0])
                std_vals[lbl].append(row["Std"].iat[0])
            else:
                mean_vals[lbl].append(0)
                std_vals[lbl].append(0)

    # Oblicz maksymalną wartość dla marginesu
    max_val = 0
    for lbl in labels:
        for mean, std in zip(mean_vals[lbl], std_vals[lbl]):
            val_with_error = mean + std
            if val_with_error > max_val:
                max_val = val_with_error

    fig, ax = plt.subplots(figsize=(8, 5))  # Zwiększone rozmiary
    N = len(systems)
    M = len(labels)
    width = 0.8 / M
    offsets = [(-0.4 + width / 2 + i * width) for i in range(M)]

    for i, lbl in enumerate(labels):
        # Wybierz hatch po typie metryki
        if lbl.startswith("Average czas oczekiwania"):
            hatch_style = hatches_wait["Średni czas oczekiwania"]
        else:
            hatch_style = hatches_wait["Maksymalny czas oczekiwania"]

        bars = ax.bar(
            [j + offsets[i] for j in range(N)],
            mean_vals[lbl],
            width,
            yerr=std_vals[lbl],
            capsize=3,
            facecolor=[colors[sys] for sys in systems],
            hatch=[hatch_style] * N,
            edgecolor="black",
            linewidth=0.5,
        )

        # Dodaj wartości na słupkach
        add_value_labels(ax, bars, mean_vals[lbl], std_vals[lbl], max_val)

    ax.set_xlabel("System")
    ax.set_ylabel("Time [s]")
    ax.set_xticks(range(N))
    ax.set_xticklabels(systems)
    ax.set_ylim(0, max_val * 1.15)  # Margines górny

    metric_handles = [
        Patch(
            facecolor="white",
            edgecolor="black",
            hatch=hatches_wait["Średni czas oczekiwania"],
            label="Average wait time",
        ),
        Patch(
            facecolor="white",
            edgecolor="black",
            hatch=hatches_wait["Maksymalny czas oczekiwania"],
            label="Maximum wait time",
        ),
    ]
    handles = metric_handles
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1, 1), frameon=False)
    ax.grid(True, alpha=0.3, axis="y")  # Siatka
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{scenario}_wait_times.svg"), dpi=300)
    plt.close()


def draw_makespan(df, scenario, output_dir):
    """
    Rysuje wykres makespanu (całkowitego czasu wykonania) dla scenariusza.
    Zapisuje 'T?_makespan.svg'.
    """
    df_s = df[df["Scenariusz"] == scenario]
    m_df = df_s[df_s["Metryka"] == "Makespan [s]"]
    systems = ["Kueue", "Volcano"]
    makespan_mean, makespan_std = [], []
    for sys in systems:
        row = m_df[m_df["System"] == sys]
        if not row.empty:
            makespan_mean.append(row["Mean"].iat[0])
            makespan_std.append(row["Std"].iat[0])
        else:
            makespan_mean.append(0)
            makespan_std.append(0)

    # Oblicz maksymalną wartość dla marginesu
    max_val = max(m + s for m, s in zip(makespan_mean, makespan_std))

    fig, ax = plt.subplots(figsize=(6, 5))  # Zwiększone rozmiary
    x = list(range(len(systems)))
    bars = ax.bar(
        x,
        makespan_mean,
        color=[colors[sys] for sys in systems],
        yerr=makespan_std,
        capsize=3,
        alpha=0.8,
        edgecolor="black",
        linewidth=0.5,
    )

    # Dodaj wartości na słupkach
    add_value_labels(ax, bars, makespan_mean, makespan_std, max_val)

    ax.set_xlabel("System")
    ax.set_ylabel("Makespan [s]")
    ax.set_xticks(x)
    ax.set_xticklabels(systems)
    ax.set_ylim(0, max_val * 1.15)  # Margines górny
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1), frameon=False)
    ax.grid(True, alpha=0.3, axis="y")  # Siatka
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{scenario}_makespan.svg"), dpi=300)
    plt.close()


if __name__ == "__main__":
    input_file = "Wyniki.xlsx"
    sheet = "Świadomość topologii"
    output_base = "wyniki/wyniki_swiadomosc_topologii"
    os.makedirs(output_base, exist_ok=True)
    data = load_data(input_file, sheet)
    scenarios = ["T1", "T2", "T3", "T4"]
    for scen in scenarios:
        df_s = data[data["Scenariusz"] == scen]
        if df_s.empty:
            continue
        draw_correctness(data, scen, output_base)
        draw_distances(data, scen, output_base)
        draw_wait_times(data, scen, output_base)
        draw_makespan(data, scen, output_base)

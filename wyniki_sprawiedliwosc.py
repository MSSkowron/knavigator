#!/usr/bin/env python3
"""
Script do generowania wykresów sprawiedliwości systemów szeregowania z pliku Excel.
"""

import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

# Kolory wykresów dla porównania systemów (zgodne z wyniki_wydajnoscskalowalnosc.py)
colors = {"Kueue": "blue", "Volcano": "red", "YuniKorn": "green"}

# Hatches dla różnych zasobów i wariantów (inspirowane poprzednimi skryptami)
hatches = {"CPU": "////", "RAM": "", "GPU": "xxx"}
hatches_variant = {
    "Z gwarancjami": "xxx",
    "Bez gwarancji": "",
    "Brak": "",  # Scenariusze F3 i F4
}

# Ustawienia globalne Matplotlib
plt.rcParams["hatch.linewidth"] = 0.5


def load_data(path, sheet):
    """
    Wczytuje dane z Excela i przygotowuje blokowe połączenie danych.
    Zwraca DataFrame z kolumnami: Scenariusz, System, Wariant, Metryka, Mean, Std.
    """
    raw = pd.read_excel(path, sheet_name=sheet)
    return prepare_blocks(raw)


def prepare_blocks(df):
    """
    Łączy bloki danych z sufiksami '', '.1', '.2', filtruje nagłówki i konwertuje na odpowiednie typy.
    """
    blocks = []
    for suffix in ["", ".1", ".2"]:
        cols = [
            f"Scenariusz{suffix}",
            f"System{suffix}",
            f"Wariant{suffix}",
            f"Metryka{suffix}",
            f"Średnia (Obliczona){suffix}",
            f"Odch.Std (Obliczone){suffix}",
        ]

        # Sprawdzamy, czy wszystkie kolumny istnieją w DataFrame
        if all(col in df.columns for col in cols):
            block = df[cols].copy()
            block.columns = [
                "Scenariusz",
                "System",
                "Wariant",
                "Metryka",
                "Mean",
                "Std",
            ]
            blocks.append(block)

    data = pd.concat(blocks, ignore_index=True)
    # Filtracja wierszy nagłówkowych
    data = data[(data["Scenariusz"] != "Scenariusz") & (data["Metryka"] != "Metryka")]
    data.dropna(subset=["Scenariusz", "Metryka"], inplace=True)
    # Konwersja na typy numeryczne
    data["Mean"] = pd.to_numeric(data["Mean"], errors="coerce")
    data["Std"] = pd.to_numeric(data["Std"], errors="coerce")
    data["Wariant"] = data["Wariant"].fillna("Brak")
    return data


def draw_wait_times(df, scenario, output_dir):
    """
    Rysuje wykres średniego czasu oczekiwania dla danego scenariusza,
    ze słupkami ułożonymi w grupach po systemach.
    """
    # Filtrowanie danych po scenariuszu
    df_s = df[df["Scenariusz"] == scenario]

    # Szukamy metryk zawierających "czas oczekiwania"
    wait_metrics = [
        m for m in df_s["Metryka"].unique() if "czas oczekiwania" in m.lower()
    ]
    if not wait_metrics:
        return

    # Rozróżniamy średnie i maksymalne metryki
    wait_types = {}
    for metric in wait_metrics:
        low = metric.lower()
        if "śr." in low or "średni" in low:
            wait_types[metric] = "Średni czas oczekiwania"
        elif "maks." in low or "maksymalny" in low:
            wait_types[metric] = "Maksymalny czas oczekiwania"

    # Lista systemów i wariantów
    systems = df_s["System"].unique().tolist()
    variants = df_s["Wariant"].unique().tolist()

    # Grupujemy dane (sys, var) -> {typ: {mean, std}}
    grouped = {}
    for sys in systems:
        for var in variants:
            for metric, wtype in wait_types.items():
                rows = df_s[
                    (df_s["System"] == sys)
                    & (df_s["Wariant"] == var)
                    & (df_s["Metryka"] == metric)
                ]
                if not rows.empty:
                    grouped.setdefault((sys, var), {})[wtype] = {
                        "mean": rows["Mean"].iloc[0],
                        "std": rows["Std"].iloc[0],
                    }

    # Rysujemy tylko średni czas oczekiwania
    target = "Średni czas oczekiwania"
    fig, ax = plt.subplots(figsize=(10, 6))
    width = 0.35
    scale = width * 1.1 if len(variants) == 1 else 1
    x = np.arange(len(systems)) * scale

    # Dla każdego wariantu rysujemy słupki z offsetem
    for i, var in enumerate(variants):
        heights, errs, pos, cols, hatches_list = [], [], [], [], []
        offset = (i - (len(variants) - 1) / 2) * width

        for j, sys in enumerate(systems):
            data = grouped.get((sys, var), {}).get(target)
            if data:
                heights.append(data["mean"])
                errs.append(data["std"])
                pos.append(j * scale + offset)
                cols.append(colors[sys])
                hatches_list.append(hatches_variant.get(var, ""))

        ax.bar(
            pos,
            heights,
            width=width,
            yerr=errs,
            capsize=3,
            color=cols,
            hatch=hatches_list,
            alpha=0.8,
            edgecolor="black",
            linewidth=0.5,
            label=var,
        )

    # Oznaczenia osi
    ax.set_xlabel("System")
    ax.set_ylabel("Średni czas oczekiwania [s]")
    ax.set_xticks(x)
    ax.set_xticklabels(systems, rotation=45, ha="right")

    # Legenda wariantów, jeśli ma sens
    if not (len(variants) == 1 and variants[0] == "Brak"):
        handles = [
            Patch(
                facecolor="white",
                edgecolor="black",
                hatch=hatches_variant.get(var, ""),
                label=var,
            )
            for var in variants
        ]
        ax.legend(
            handles=handles, loc="upper left", bbox_to_anchor=(1, 1), frameon=False
        )

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{scenario}_czasy_oczekiwania.svg"))
    plt.close()


def draw_jfi(df, scenario, output_dir):
    """
    Rysuje wykres JFI (Jain's Fairness Index) dla danego scenariusza.
    """
    df_s = df[df["Scenariusz"] == scenario]

    # Filtrujemy metryki JFI
    jfi_metrics = [m for m in df_s["Metryka"].unique() if "JFI" in m]
    if not jfi_metrics:
        return

    # Określamy typy zasobów z metryk JFI
    resource_types = {}
    for metric in jfi_metrics:
        if "CPU" in metric:
            resource_types[metric] = "CPU"
        elif "RAM" in metric or "Pamięć" in metric:
            resource_types[metric] = "RAM"
        elif "GPU" in metric:
            resource_types[metric] = "GPU"

    systems = df_s["System"].unique().tolist()
    variants = df_s["Wariant"].unique().tolist()

    # Przygotowujemy dane
    labels = []
    mean_vals = {}
    std_vals = {}

    for sys in systems:
        for metric in jfi_metrics:
            resource = resource_types[metric]
            for variant in variants:
                rows = df_s[
                    (df_s["System"] == sys)
                    & (df_s["Metryka"] == metric)
                    & (df_s["Wariant"] == variant)
                ]

                if not rows.empty:
                    label = (sys, resource, variant)
                    labels.append(label)
                    mean_vals[label] = rows["Mean"].values[0]
                    std_vals[label] = rows["Std"].values[0]

    # Grupujemy etykiety dla osi X
    grouped_labels = {}
    for sys, res, var in labels:
        key = f"{sys}-{res}"
        if key not in grouped_labels:
            grouped_labels[key] = []
        grouped_labels[key].append((sys, res, var))

    x_labels = sorted(grouped_labels.keys())

    fig, ax = plt.subplots(figsize=(10, 6))

    width = 0.35
    scale = width * 1.1 if len(variants) == 1 else 1
    x_ticks = np.arange(len(x_labels)) * scale

    for i, var in enumerate(variants):
        heights = []
        errs = []
        positions = []
        colors_list = []
        hatches_list = []

        for j, key in enumerate(x_labels):
            sys, res = key.split("-")
            label = next((l for l in grouped_labels[key] if l[2] == var), None)
            offset = (i - 0.5 * (len(variants) - 1)) * width

            if label:
                heights.append(mean_vals[label])
                errs.append(std_vals[label])
                positions.append(j * scale + offset)
                colors_list.append(colors[sys])
                hatches_list.append(hatches_variant.get(var, ""))

        ax.bar(
            positions,
            heights,
            width=width,
            yerr=errs,
            capsize=3,
            color=colors_list,
            hatch=hatches_list[0] if hatches_list else "",
            alpha=0.8,
            edgecolor="black",
            linewidth=0.5,
            label=var,
        )

    ax.set_xlabel("System-Zasób")
    ax.set_ylabel("JFI")
    ax.set_xticks(x_ticks)
    ax.set_xticklabels(x_labels, rotation=45, ha="right")
    ax.set_ylim(0, 1.1)

    if not (len(variants) == 1 and variants[0] == "Brak"):
        leg = ax.legend(loc="upper left", bbox_to_anchor=(1, 1), frameon=False)
        for handle in leg.legend_handles:
            handle.set_facecolor("white")
            handle.set_edgecolor("black")
            handle.set_alpha(1)

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{scenario}_jfi.svg"))
    plt.close()


def draw_running_pods(df, scenario, output_dir):
    """
    Rysuje wykres liczby uruchomionych podów dla danego scenariusza,
    ze słupkami ułożonymi w grupach po systemach.
    """
    df_s = df[df["Scenariusz"] == scenario]

    # Filtrujemy metryki liczby podów
    pod_metrics = [
        m for m in df_s["Metryka"].unique() if "Liczba Uruchomionych Podów" in m
    ]
    if not pod_metrics:
        return

    systems = df_s["System"].unique().tolist()
    variants = df_s["Wariant"].unique().tolist()

    grouped_data = {}
    for sys in systems:
        for metric in pod_metrics:
            for var in variants:
                rows = df_s[
                    (df_s["System"] == sys)
                    & (df_s["Metryka"] == metric)
                    & (df_s["Wariant"] == var)
                ]
                if not rows.empty:
                    grouped_data[(sys, var)] = {
                        "mean": rows["Mean"].values[0],
                        "std": rows["Std"].values[0],
                    }

    fig, ax = plt.subplots(figsize=(10, 6))
    width = 0.35
    scale = width * 1.1 if len(variants) == 1 else 1
    x = np.arange(len(systems)) * scale

    for i, var in enumerate(variants):
        heights, errs, pos, cols, hatches_list = [], [], [], [], []
        offset = (i - (len(variants) - 1) / 2) * width

        for j, sys in enumerate(systems):
            key = (sys, var)
            if key in grouped_data:
                heights.append(grouped_data[key]["mean"])
                errs.append(grouped_data[key]["std"])
                pos.append(j * scale + offset)
                cols.append(colors[sys])
                hatches_list.append(hatches_variant.get(var, ""))
        ax.bar(
            pos,
            heights,
            width=width,
            yerr=errs,
            capsize=3,
            color=cols,
            hatch=hatches_list,
            alpha=0.8,
            edgecolor="black",
            linewidth=0.5,
            label=var,
        )

    ax.set_xlabel("System")
    ax.set_ylabel("Liczba podów")
    ax.set_xticks(x)
    ax.set_xticklabels(systems, rotation=45, ha="right")

    if not (len(variants) == 1 and variants[0] == "Brak"):
        leg_handles = [
            Patch(
                facecolor="white",
                edgecolor="black",
                hatch=hatches_variant.get(var, ""),
                label=var,
            )
            for var in variants
        ]
        ax.legend(
            handles=leg_handles, loc="upper left", bbox_to_anchor=(1, 1), frameon=False
        )

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{scenario}_liczba_podow.svg"))
    plt.close()


def draw_makespan(df, scenario, output_dir):
    """
    Rysuje wykres makespanu (całkowitego czasu wykonania) dla danego scenariusza,
    ze słupkami ułożonymi w grupach po systemach, z hatchami dla wariantów.
    """
    df_s = df[df["Scenariusz"] == scenario]

    # Filtrujemy metryki makespanu
    makespan_metrics = [m for m in df_s["Metryka"].unique() if "Makespan" in m]
    if not makespan_metrics:
        return

    # Lista systemów i wariantów (w ustalonej kolejności)
    systems = df_s["System"].unique().tolist()
    variants = df_s["Wariant"].unique().tolist()

    # Grupujemy dane: (system, wariant) -> {mean, std}
    grouped = {}
    for sys in systems:
        for var in variants:
            for metric in makespan_metrics:
                rows = df_s[
                    (df_s["System"] == sys)
                    & (df_s["Wariant"] == var)
                    & (df_s["Metryka"] == metric)
                ]
                if not rows.empty:
                    grouped[(sys, var)] = {
                        "mean": rows["Mean"].iloc[0],
                        "std": rows["Std"].iloc[0],
                    }

    # Rysowanie
    fig, ax = plt.subplots(figsize=(10, 6))
    width = 0.35
    scale = width * 1.1 if len(variants) == 1 else 1
    x = np.arange(len(systems)) * scale

    # Dla każdego wariantu – budujemy listy wysokości, błędów, pozycji, kolorów i hatchy
    for i, var in enumerate(variants):
        heights, errs, pos, cols, hatches_list = [], [], [], [], []
        offset = (i - (len(variants) - 1) / 2) * width

        for j, sys in enumerate(systems):
            data = grouped.get((sys, var))
            if data:
                heights.append(data["mean"])
                errs.append(data["std"])
                pos.append(j * scale + offset)
                cols.append(colors[sys])
                hatches_list.append(hatches_variant.get(var, ""))

        ax.bar(
            pos,
            heights,
            width=width,
            yerr=errs,
            capsize=3,
            color=cols,
            hatch=hatches_list,
            alpha=0.8,
            edgecolor="black",
            linewidth=0.5,
            label=var,
        )

    # Oś X – tylko nazwy systemów
    ax.set_xlabel("System")
    ax.set_ylabel("Makespan [s]")
    ax.set_xticks(x)
    ax.set_xticklabels(systems, rotation=45, ha="right")

    # Legenda wariantów (jeśli są istotne)
    if not (len(variants) == 1 and variants[0] == "Brak"):
        legend_handles = [
            Patch(
                facecolor="white",
                edgecolor="black",
                hatch=hatches_variant.get(v, ""),
                label=v,
            )
            for v in variants
        ]
        ax.legend(
            handles=legend_handles,
            loc="upper left",
            bbox_to_anchor=(1, 1),
            frameon=False,
        )

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{scenario}_makespan.svg"))
    plt.close()


def draw_resource_shares(df, scenario, output_dir):
    """
    Rysuje wykres udziałów zasobów (CPU, RAM, GPU) dla danego scenariusza.
    """
    df_s = df[df["Scenariusz"] == scenario]

    resource_metrics = [m for m in df_s["Metryka"].unique() if "Udział" in m]
    if not resource_metrics:
        return

    resource_types = {}
    for metric in resource_metrics:
        if "CPU" in metric:
            resource_types[metric] = "CPU"
        elif "RAM" in metric or "Pamięć" in metric:
            resource_types[metric] = "RAM"
        elif "GPU" in metric:
            resource_types[metric] = "GPU"

    systems = df_s["System"].unique().tolist()
    variants = df_s["Wariant"].unique().tolist()

    labels = []
    mean_vals = {}
    std_vals = {}

    for sys in systems:
        for metric in resource_metrics:
            resource = resource_types[metric]
            for variant in variants:
                rows = df_s[
                    (df_s["System"] == sys)
                    & (df_s["Metryka"] == metric)
                    & (df_s["Wariant"] == variant)
                ]

                if not rows.empty:
                    label = (sys, resource, variant)
                    labels.append(label)
                    mean_vals[label] = rows["Mean"].values[0]
                    std_vals[label] = rows["Std"].values[0]

    fig, ax = plt.subplots(figsize=(10, 6))

    grouped_labels = {}
    for sys, res, var in labels:
        key = f"{sys}-{res}"
        if key not in grouped_labels:
            grouped_labels[key] = []
        grouped_labels[key].append((sys, res, var))

    x_labels = sorted(grouped_labels.keys())
    width = 0.35
    scale = width * 1.1 if len(variants) == 1 else 1
    x_ticks = np.arange(len(x_labels)) * scale

    for i, var in enumerate(variants):
        heights = []
        errs = []
        positions = []
        colors_list = []
        hatches_list = []

        for j, key in enumerate(x_labels):
            sys, res = key.split("-")
            label = next((l for l in grouped_labels[key] if l[2] == var), None)
            offset = (i - 0.5 * (len(variants) - 1)) * width

            if label:
                heights.append(mean_vals[label])
                errs.append(std_vals[label])
                positions.append(j * scale + offset)
                colors_list.append(colors[sys])
                hatches_list.append(hatches_variant.get(var, ""))

        ax.bar(
            positions,
            heights,
            width=width,
            yerr=errs,
            capsize=3,
            color=colors_list,
            hatch=hatches_list[0] if hatches_list else "",
            alpha=0.8,
            edgecolor="black",
            linewidth=0.5,
            label=var,
        )

    ax.set_xlabel("System-Zasób")
    ax.set_ylabel("Udział zasobów [%]")
    ax.set_xticks(x_ticks)
    ax.set_xticklabels(x_labels, rotation=45, ha="right")

    if not (len(variants) == 1 and variants[0] == "Brak"):
        handles = [
            Patch(
                facecolor="white",
                edgecolor="black",
                hatch=hatches_variant.get(var, ""),
                label=var,
            )
            for var in variants
        ]
        ax.legend(
            handles=handles, loc="upper left", bbox_to_anchor=(1, 1), frameon=False
        )

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{scenario}_udzialy_zasobow.svg"))
    plt.close()


def draw_metrics_comparison(df, scenario, output_dir):
    """
    Rysuje wykresy porównujące różne metryki dla scenariusza, które nie zostały obsłużone
    przez inne funkcje (np. sprawiedliwość, efektywność).
    """
    df_s = df[df["Scenariusz"] == scenario]

    excluded_keywords = [
        "Udział",
        "JFI",
        "czas oczekiwania",
        "Makespan",
        "Liczba Uruchomionych Podów",
    ]
    other_metrics = [
        m
        for m in df_s["Metryka"].unique()
        if not any(kw.lower() in str(m).lower() for kw in excluded_keywords)
    ]

    for metric in other_metrics:
        metric_df = df_s[df_s["Metryka"] == metric]
        systems = metric_df["System"].unique().tolist()
        variants = metric_df["Wariant"].unique().tolist()

        if not systems or not variants:
            continue

        grouped_data = {}
        for sys in systems:
            for variant in variants:
                rows = metric_df[
                    (metric_df["System"] == sys) & (metric_df["Wariant"] == variant)
                ]
                if not rows.empty:
                    key = (sys, variant)
                    grouped_data[key] = {
                        "mean": rows["Mean"].values[0],
                        "std": rows["Std"].values[0],
                    }

        system_variant_keys = sorted(grouped_data.keys())
        width = 0.35
        variants_in_metric = list(set([v for _, v in system_variant_keys]))

        # Jeśli tylko jeden wariant ("Brak"), ustaw niewielki odstęp między słupkami
        if len(variants_in_metric) == 1 and variants_in_metric[0] == "Brak":
            scale = width * 1.1
        else:
            scale = 1

        fig, ax = plt.subplots(figsize=(10, 6))

        x_ticks = np.arange(len(system_variant_keys)) * scale
        positions = [i * scale for i in range(len(system_variant_keys))]
        heights = [grouped_data[key]["mean"] for key in system_variant_keys]
        errs = [grouped_data[key]["std"] for key in system_variant_keys]
        colors_list = [colors[sys] for sys, _ in system_variant_keys]
        hatches_list = [hatches_variant.get(var, "") for _, var in system_variant_keys]

        ax.bar(
            positions,
            heights,
            yerr=errs,
            capsize=3,
            color=colors_list,
            hatch=hatches_list,
            alpha=0.8,
            edgecolor="black",
            linewidth=0.5,
        )

        ax.set_xlabel("System-Wariant")
        ax.set_ylabel(metric)
        metric_name = metric.split(" [")[0] if " [" in metric else metric
        ax.set_title(f"Scenariusz {scenario} - {metric_name}")
        ax.set_xticks(x_ticks)
        ax.set_xticklabels([f"{sys}-{var}" for sys, var in system_variant_keys])

        # Legendy: warianty i systemy (jeśli jest sens)
        handles = []

        if not (len(variants_in_metric) == 1 and variants_in_metric[0] == "Brak"):
            for var in variants_in_metric:
                handles.append(
                    Patch(
                        facecolor="white",
                        edgecolor="black",
                        hatch=hatches_variant.get(var, ""),
                        label=var,
                    )
                )

        for sys in set(sys for sys, _ in system_variant_keys):
            handles.append(Patch(facecolor=colors[sys], edgecolor="black", label=sys))

        if handles:
            ax.legend(
                handles=handles, loc="upper left", bbox_to_anchor=(1, 1), frameon=False
            )

        safe_metric_name = metric_name.replace(" ", "_").replace("/", "_na_")

        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, f"{scenario}_{safe_metric_name}.svg"))
        plt.close()


if __name__ == "__main__":
    input_file = "wyniki_sprawiedliwosc.xlsx"
    sheet = "Sprawiedliwość"
    output_base = "wyniki/wyniki_sprawiedliwosc"
    os.makedirs(output_base, exist_ok=True)

    data = load_data(input_file, sheet)
    scenarios = ["F1", "F2", "F3", "F4"]

    for scen in scenarios:
        df_s = data[data["Scenariusz"] == scen]
        if df_s.empty:
            continue

        print(f"Generowanie wykresów dla scenariusza {scen}...")

        # Generowanie wykresów dla różnych typów danych
        draw_resource_shares(data, scen, output_base)
        draw_jfi(data, scen, output_base)
        draw_wait_times(data, scen, output_base)
        draw_makespan(data, scen, output_base)
        draw_running_pods(data, scen, output_base)
        draw_metrics_comparison(data, scen, output_base)

        print(f"Zakończono generowanie wykresów dla scenariusza {scen}")

    print("Zakończono generowanie wszystkich wykresów sprawiedliwości!")

#!/usr/bin/env python3
"""
Script do generowania wykresów sprawiedliwości systemów szeregowania z pliku Excel Wyniki.xlsx.
"""

import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

# Kolory wykresów dla porównania systemów (zgodne z projektem)
colors = {"Kueue": "blue", "Volcano": "red", "YuniKorn": "green"}

# Hatch dla wariantów
hatches_variant = {"Z gwarancjami": "xxx", "Bez gwarancji": "", "Brak": ""}

# Ustawienia globalne Matplotlib
plt.rcParams["hatch.linewidth"] = 0.5


def load_data(path, sheet):
    """
    Wczytuje dane z Excela i przygotowuje blokowe połączenie danych.
    Zwraca DataFrame z kolumnami: Scenariusz, Wariant, System, Metryka, Tenant, Mean, Std.
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
            f"Wariant{suffix}",
            f"System{suffix}",
            f"Metryka{suffix}",
            f"Tenant{suffix}",
            f"Średnia (Obliczona){suffix}",
            f"Odch.Std (Obliczone){suffix}",
        ]
        if all(col in df.columns for col in cols):
            block = df[cols].copy()
            block.columns = [
                "Scenariusz",
                "Wariant",
                "System",
                "Metryka",
                "Tenant",
                "Mean",
                "Std",
            ]
            blocks.append(block)
    data = pd.concat(blocks, ignore_index=True)
    # Filtrujemy wiersze nagłówkowe
    data = data[(data["Scenariusz"] != "Scenariusz") & (data["Metryka"] != "Metryka")]
    data.dropna(subset=["Scenariusz", "Metryka"], inplace=True)
    data["Mean"] = pd.to_numeric(data["Mean"], errors="coerce")
    data["Std"] = pd.to_numeric(data["Std"], errors="coerce")
    data["Wariant"] = data["Wariant"].fillna("Brak")
    data["Tenant"] = data["Tenant"].fillna("Brak")
    return data


def draw_general_metric(df, scenario, output_dir, metric_name, ylabel, filename):
    """
    Rysuje wykres słupkowy dla ogólnego metryki (np. makespan, JFI).
    """
    df_s = df[df["Scenariusz"] == scenario]
    metric_df = df_s[df_s["Metryka"] == metric_name]
    if metric_df.empty:
        return
    # Kolejność systemów i wariantów
    systems = sorted(
        metric_df["System"].unique(),
        key=lambda x: ["Kueue", "Volcano", "YuniKorn"].index(x)
        if x in ["Kueue", "Volcano", "YuniKorn"]
        else x,
    )
    variants = sorted(
        metric_df["Wariant"].unique(),
        key=lambda x: ["Z gwarancjami", "Bez gwarancji", "Brak"].index(x)
        if x in ["Z gwarancjami", "Bez gwarancji", "Brak"]
        else x,
    )
    width = 0.35
    scale = width * 1.1 if len(variants) == 1 else 1
    x = np.arange(len(systems)) * scale

    fig, ax = plt.subplots(figsize=(6, 4))
    for i, var in enumerate(variants):
        heights, errs, positions, cols, hatches_list = [], [], [], [], []
        offset = (i - (len(variants) - 1) / 2) * width
        for j, sys in enumerate(systems):
            row = metric_df[
                (metric_df["System"] == sys) & (metric_df["Wariant"] == var)
            ]
            if not row.empty:
                heights.append(row["Mean"].iloc[0])
                errs.append(row["Std"].iloc[0])
            else:
                heights.append(0)
                errs.append(0)
            cols.append(colors.get(sys, "black"))
            hatches_list.append(hatches_variant.get(var, ""))
            positions.append(j * scale + offset)
        ax.bar(
            positions,
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
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(systems)
    if not (len(variants) == 1 and variants[0] == "Brak"):
        handles = [
            Patch(
                facecolor="white",
                edgecolor="black",
                hatch=hatches_variant[var],
                label=var,
            )
            for var in variants
        ]
        ax.legend(
            handles=handles, loc="upper left", bbox_to_anchor=(1, 1), frameon=False
        )

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, filename))
    plt.close()


def draw_per_tenant_metric(df, scenario, output_dir, metric_name, ylabel, filename):
    """
    Rysuje wykres słupkowy dla metryki per-tenant, grupując dane według systemu i tenantów.
    """
    df_s = df[df["Scenariusz"] == scenario]
    metric_df = df_s[df_s["Metryka"] == metric_name]
    if metric_df.empty:
        return
    systems = sorted(
        metric_df["System"].unique(),
        key=lambda x: ["Kueue", "Volcano", "YuniKorn"].index(x)
        if x in ["Kueue", "Volcano", "YuniKorn"]
        else x,
    )
    tenants_order = {"A": 0, "B": 1, "C": 2}
    tenants = sorted(
        metric_df["Tenant"].unique(), key=lambda x: tenants_order.get(x, x)
    )
    variants = sorted(
        metric_df["Wariant"].unique(),
        key=lambda x: ["Z gwarancjami", "Bez gwarancji", "Brak"].index(x)
        if x in ["Z gwarancjami", "Bez gwarancji", "Brak"]
        else x,
    )
    width = 0.35
    scale = width * 1.1 if len(variants) == 1 else 1
    combos = [(sys, ten) for sys in systems for ten in tenants]
    x = np.arange(len(combos)) * scale

    fig, ax = plt.subplots(figsize=(10, 6))
    for i, var in enumerate(variants):
        heights, errs, positions, cols, hatches_list = [], [], [], [], []
        offset = (i - (len(variants) - 1) / 2) * width
        for idx, (sys, ten) in enumerate(combos):
            row = metric_df[
                (metric_df["System"] == sys)
                & (metric_df["Tenant"] == ten)
                & (metric_df["Wariant"] == var)
            ]
            if not row.empty:
                heights.append(row["Mean"].iloc[0])
                errs.append(row["Std"].iloc[0])
            else:
                heights.append(0)
                errs.append(0)
            cols.append(colors.get(sys, "black"))
            hatches_list.append(hatches_variant.get(var, ""))
            positions.append(idx * scale + offset)
        ax.bar(
            positions,
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

    labels = [f"{sys}-{ten}" for sys, ten in combos]
    ax.set_xlabel("System-Tenant")
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    if not (len(variants) == 1 and variants[0] == "Brak"):
        handles = [
            Patch(
                facecolor="white",
                edgecolor="black",
                hatch=hatches_variant[var],
                label=var,
            )
            for var in variants
        ]
        ax.legend(
            handles=handles, loc="upper left", bbox_to_anchor=(1, 1), frameon=False
        )

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, filename))
    plt.close()


if __name__ == "__main__":
    input_file = "Wyniki.xlsx"
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

        # Metryki ogólne
        general_metrics = [
            (
                "Makespan (Faza 2) [s]",
                f"{scen}_makespan_phase2.svg",
                "Całkowity zakres czasowy (Faza 2) [s]",
            ),
            ("Makespan [s]", f"{scen}_makespan.svg", "Całkowity zakres czasowy [s]"),
            (
                "Śr. JFI CPU (w nasyceniu)",
                f"{scen}_jfi_cpu.svg",
                "Śr. JFI CPU (w nasyceniu)",
            ),
            (
                "Śr. JFI GPU (w nasyceniu)",
                f"{scen}_jfi_gpu.svg",
                "Śr. JFI GPU (w nasyceniu)",
            ),
            (
                "Śr. JFI Pamięć (w nasyceniu)",
                f"{scen}_jfi_ram.svg",
                "Śr. JFI Pamięć (w nasyceniu)",
            ),
        ]
        for metric, filename, ylabel in general_metrics:
            draw_general_metric(data, scen, output_base, metric, ylabel, filename)

        # Metryki per-tenant
        tenant_metrics = [
            (
                "Śr. Czas Oczekiwania (Faza 2 do momentu nasycenia klastra) [s]",
                f"{scen}_wait_time_phase2.svg",
                "Śr. czas oczekiwania (Faza 2 do momentu nasycenia klastra) [s]",
            ),
            (
                "Śr. Czas Oczekiwania (wszystkie zadadania) [s]",
                f"{scen}_wait_time.svg",
                "Śr. czas oczekiwania [s]",
            ),
            (
                "Śr. Liczba Uruchomionych Podów (w nasyceniu)",
                f"{scen}_no_pods.svg",
                "Śr. liczba Podów (w nasyceniu)",
            ),
            (
                "Śr. Udział CPU (w nasyceniu) [%]",
                f"{scen}_cpu_share.svg",
                "Śr. udział CPU (w nasyceniu) [%]",
            ),
            (
                "Śr. Udział GPU (w nasyceniu) [%]",
                f"{scen}_gpu_share.svg",
                "Śr. udział GPU (w nasyceniu) [%]",
            ),
            (
                "Śr. Udział Pamięć (w nasyceniu) [%]",
                f"{scen}_ram_share.svg",
                "Śr. udział pamięci (w nasyceniu) [%]",
            ),
        ]
        for metric, filename, ylabel in tenant_metrics:
            draw_per_tenant_metric(data, scen, output_base, metric, ylabel, filename)

        print(f"Zakończono generowanie wykresów dla scenariusza {scen}")

    print("Zakończono generowanie wszystkich wykresów sprawiedliwości!")

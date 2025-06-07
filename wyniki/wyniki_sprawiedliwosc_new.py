#!/usr/bin/env python3
"""
Script do generowania wykresów sprawiedliwości systemów szeregowania z pliku Excel Wyniki.xlsx.
"""

import os
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

# Kolory wykresów dla porównania systemów (zgodne z projektem)
colors = {"Kueue": "blue", "Volcano": "red", "YuniKorn": "green"}

# Odcienie kolorów dla wariantów (ciemniejszy = z gwarancjami, jaśniejszy = bez gwarancji)
color_variants = {
    "Kueue": {
        "Z gwarancjami": "#000080",
        "Bez gwarancji": "#4169E1",
        "Brak": "#0000FF",
    },
    "Volcano": {
        "Z gwarancjami": "#8B0000",
        "Bez gwarancji": "#FF4500",
        "Brak": "#FF0000",
    },
    "YuniKorn": {
        "Z gwarancjami": "#006400",
        "Bez gwarancji": "#32CD32",
        "Brak": "#008000",
    },
}

# Hatch dla wariantów (zachowuję oryginalną logikę dla kompatybilności)
hatches_variant = {"Z gwarancjami": "xxx", "Bez gwarancji": "", "Brak": ""}

# Hatch dla zasobów w wykresach łączonych
hatches_resource = {"CPU": "///", "Memory": "\\\\\\", "GPU": "+++"}

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
    # UWAGA: Nie używamy fillna dla Wariant i Tenant - pozostawiamy NaN dla pustych wartości
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
            fontsize=7,  # Nieco mniejszy font dla gęstszych wykresów
            fontweight="bold",
            color="black",
            bbox=dict(
                boxstyle="round,pad=0.15",
                facecolor="white",
                alpha=0.8,
                edgecolor="none",
            ),
        )


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
        else 999,
    )
    # Filtruj NaN z wariantów
    variants = [v for v in variants if pd.notna(v)]
    if len(variants) == 0:
        variants = ["Brak"]  # Fallback dla scenariuszy bez wariantów
    width = 0.35
    scale = width * 1.1 if len(variants) == 1 else 1
    x = np.arange(len(systems)) * scale

    # Oblicz maksymalną wartość dla marginesu
    max_val = 0
    for var in variants:
        for sys in systems:
            if variants == ["Brak"]:
                row = metric_df[
                    (metric_df["System"] == sys) & (metric_df["Wariant"].isna())
                ]
            else:
                row = metric_df[
                    (metric_df["System"] == sys) & (metric_df["Wariant"] == var)
                ]
            if not row.empty:
                val_with_error = row["Mean"].iloc[0] + row["Std"].iloc[0]
                if val_with_error > max_val:
                    max_val = val_with_error

    fig, ax = plt.subplots(figsize=(8, 5))  # Zwiększone rozmiary
    for i, var in enumerate(variants):
        heights, errs, positions, cols = [], [], [], []
        offset = (i - (len(variants) - 1) / 2) * width
        current_pos = 0
        for j, sys in enumerate(systems):
            # Dla scenariuszy F1 i F2, pomiń YuniKorn w wariancie "Bez gwarancji"
            if (
                scenario in ["F1", "F2"]
                and sys == "YuniKorn"
                and var == "Bez gwarancji"
            ):
                continue

            if variants == ["Brak"]:
                # Dla scenariuszy bez wariantów szukaj wierszy z NaN w Wariant
                row = metric_df[
                    (metric_df["System"] == sys) & (metric_df["Wariant"].isna())
                ]
            else:
                # Dla scenariuszy z wariantami filtruj normalnie
                row = metric_df[
                    (metric_df["System"] == sys) & (metric_df["Wariant"] == var)
                ]
            if not row.empty:
                heights.append(row["Mean"].iloc[0])
                errs.append(row["Std"].iloc[0])
            else:
                heights.append(0)
                errs.append(0)
            # ZMIANA: Użyj odcienia koloru odpowiedniego dla systemu i wariantu
            cols.append(
                color_variants[sys][var]
                if sys in color_variants and var in color_variants[sys]
                else colors.get(sys, "black")
            )
            positions.append(current_pos * scale + offset)
            current_pos += 1

        bars = ax.bar(
            positions,
            heights,
            width=width,
            yerr=errs,
            capsize=3,
            color=cols,
            alpha=0.8,
            edgecolor="black",
            linewidth=0.5,
            label=var,
        )

        # Dodaj wartości na słupkach
        add_value_labels(ax, bars, heights, errs, max_val)

    # Utwórz etykiety tylko dla systemów, które rzeczywiście są wyświetlane
    labels = []
    x_positions = []
    current_pos = 0
    for sys in systems:
        # Sprawdź czy ten system jest pomijany dla któregokolwiek wariantu
        should_include = False
        for var in variants:
            if not (
                scenario in ["F1", "F2"]
                and sys == "YuniKorn"
                and var == "Bez gwarancji"
            ):
                should_include = True
                break
        if should_include:
            labels.append(sys)
            x_positions.append(current_pos * scale)
            current_pos += 1

    ax.set_xlabel("System")
    ax.set_ylabel(ylabel)
    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, max_val * 1.15)  # Margines górny
    ax.grid(True, alpha=0.3, axis="y")  # Siatka

    # Legenda dla systemów
    system_handles = [
        Patch(facecolor=colors[sys], edgecolor="black", label=sys) for sys in systems
    ]
    system_legend = ax.legend(
        handles=system_handles,
        title="Systems",
        loc="upper left",
        bbox_to_anchor=(1.02, 1),
        borderaxespad=0,
    )
    ax.add_artist(system_legend)

    # Legenda dla wariantów - tylko jeśli mamy więcej niż jeden wariant i nie jest "Brak"
    if not (len(variants) == 1 and variants[0] == "Brak"):
        # ZMIANA: Użyj neutralnych odcieni szarości dla legendy wariantów (jak w jfi_combined)
        variant_colors = {"Z gwarancjami": "#404040", "Bez gwarancji": "#808080"}
        variant_handles = []
        for var in variants:
            # Translate variant names for display
            display_var = {
                "Z gwarancjami": "With guarantees",
                "Bez gwarancji": "Without guarantees",
            }.get(var, var)
            variant_handles.append(
                Patch(
                    facecolor=variant_colors.get(var, "#606060"),
                    edgecolor="black",
                    label=display_var,
                )
            )
        ax.legend(
            handles=variant_handles,
            title="Variants",
            loc="upper left",
            bbox_to_anchor=(1.02, 0.7),
            borderaxespad=0,
        )

    left, right = 0.09, 0.74
    if len(variants) == 1:
        left, right = 0.09, 0.85
    plt.subplots_adjust(left=left, right=right, top=0.98, bottom=0.1)
    plt.savefig(os.path.join(output_dir, filename), dpi=300)
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
    # ZMIANA: Rozszerzono słownik tenants_order dla większej liczby tenantów
    tenants_order = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6, "H": 7}
    tenants = sorted(
        metric_df["Tenant"].unique(), key=lambda x: tenants_order.get(x, 999)
    )
    variants = sorted(
        metric_df["Wariant"].unique(),
        key=lambda x: ["Z gwarancjami", "Bez gwarancji", "Brak"].index(x)
        if x in ["Z gwarancjami", "Bez gwarancji", "Brak"]
        else 999,
    )
    # Filtruj NaN z wariantów
    variants = [v for v in variants if pd.notna(v)]
    if len(variants) == 0:
        variants = ["Brak"]  # Fallback dla scenariuszy bez wariantów
    width = 0.35
    scale = width * 1.1 if len(variants) == 1 else 1
    combos = [(sys, ten) for sys in systems for ten in tenants]
    x = np.arange(len(combos)) * scale

    # Oblicz maksymalną wartość dla marginesu
    max_val = 0
    for var in variants:
        for sys, ten in combos:
            if variants == ["Brak"]:
                row = metric_df[
                    (metric_df["System"] == sys)
                    & (metric_df["Tenant"] == ten)
                    & (metric_df["Wariant"].isna())
                ]
            else:
                row = metric_df[
                    (metric_df["System"] == sys)
                    & (metric_df["Tenant"] == ten)
                    & (metric_df["Wariant"] == var)
                ]
            if not row.empty:
                val_with_error = row["Mean"].iloc[0] + row["Std"].iloc[0]
                if val_with_error > max_val:
                    max_val = val_with_error

    # ZMIANA: Dostosuj rozmiar figury w zależności od liczby tenantów
    num_tenants = len(tenants)
    if num_tenants <= 3:
        figsize = (12, 6)  # Oryginalna wielkość dla 3 tenantów
    elif num_tenants <= 6:
        figsize = (16, 6)  # Większa szerokość dla 6 tenantów
    else:
        figsize = (20, 6)  # Jeszcze większa szerokość dla 8 tenantów

    fig, ax = plt.subplots(figsize=figsize)
    for i, var in enumerate(variants):
        heights, errs, positions, cols = [], [], [], []
        offset = (i - (len(variants) - 1) / 2) * width
        current_pos = 0
        for idx, (sys, ten) in enumerate(combos):
            # Dla scenariuszy F1 i F2, pomiń YuniKorn w wariancie "Bez gwarancji"
            if (
                scenario in ["F1", "F2"]
                and sys == "YuniKorn"
                and var == "Bez gwarancji"
            ):
                continue

            if variants == ["Brak"]:
                # Dla scenariuszy bez wariantów szukaj wierszy z NaN w Wariant
                row = metric_df[
                    (metric_df["System"] == sys)
                    & (metric_df["Tenant"] == ten)
                    & (metric_df["Wariant"].isna())
                ]
            else:
                # Dla scenariuszy z wariantami filtruj normalnie
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
            # ZMIANA: Użyj odcienia koloru odpowiedniego dla systemu i wariantu
            cols.append(
                color_variants[sys][var]
                if sys in color_variants and var in color_variants[sys]
                else colors.get(sys, "black")
            )
            positions.append(current_pos * scale + offset)
            current_pos += 1

        bars = ax.bar(
            positions,
            heights,
            width=width,
            yerr=errs,
            capsize=3,
            color=cols,
            alpha=0.8,
            edgecolor="black",
            linewidth=0.5,
            label=var,
        )

        # Dodaj wartości na słupkach
        add_value_labels(ax, bars, heights, errs, max_val)

    # Utwórz etykiety tylko dla kombinacji, które rzeczywiście są wyświetlane
    labels = []
    x_positions = []
    current_pos = 0
    for sys, ten in combos:
        # Sprawdź czy ta kombinacja jest pomijana dla któregokolwiek wariantu
        should_include = False
        for var in variants:
            if not (
                scenario in ["F1", "F2"]
                and sys == "YuniKorn"
                and var == "Bez gwarancji"
            ):
                should_include = True
                break
        if should_include:
            labels.append(f"{sys}-{ten}")
            x_positions.append(current_pos * scale)
            current_pos += 1

    ax.set_xlabel("System-Tenant")
    ax.set_ylabel(ylabel)
    ax.set_xticks(x_positions)
    # ZMIANA: Dostosuj rotację etykiet w zależności od liczby tenantów
    rotation_angle = 45 if num_tenants <= 6 else 60
    fontsize = 8 if num_tenants <= 6 else 6
    ax.set_xticklabels(labels, rotation=rotation_angle, ha="right", fontsize=fontsize)
    ax.set_ylim(0, max_val * 1.15)  # Margines górny
    ax.grid(True, alpha=0.3, axis="y")  # Siatka

    # Legenda dla systemów
    system_handles = [
        Patch(facecolor=colors[sys], edgecolor="black", label=sys) for sys in systems
    ]
    system_legend = ax.legend(
        handles=system_handles,
        title="Systems",
        loc="upper left",
        bbox_to_anchor=(1.02, 1),
        borderaxespad=0,
    )
    ax.add_artist(system_legend)

    # Legenda dla wariantów - tylko jeśli mamy więcej niż jeden wariant i nie jest "Brak"
    if not (len(variants) == 1 and variants[0] == "Brak"):
        # ZMIANA: Użyj neutralnych odcieni szarości dla legendy wariantów (jak w jfi_combined)
        variant_colors = {"Z gwarancjami": "#404040", "Bez gwarancji": "#808080"}
        variant_handles = []
        for var in variants:
            # Translate variant names for display
            display_var = {
                "Z gwarancjami": "With guarantees",
                "Bez gwarancji": "Without guarantees",
            }.get(var, var)
            variant_handles.append(
                Patch(
                    facecolor=variant_colors.get(var, "#606060"),
                    edgecolor="black",
                    label=display_var,
                )
            )
        ax.legend(
            handles=variant_handles,
            title="Variants",
            loc="upper left",
            bbox_to_anchor=(1.02, 0.8),
            borderaxespad=0,
        )

    # ZMIANA: Dostosuj marginesy w zależności od liczby tenantów
    if num_tenants <= 3:
        left, right = 0.05, 0.82
        if len(variants) == 1:
            left, right = 0.05, 0.89
    elif num_tenants <= 6:
        left, right = 0.04, 0.84
        if len(variants) == 1:
            left, right = 0.04, 0.91
    else:  # 8 tenantów
        left, right = 0.03, 0.88
        if len(variants) == 1:
            left, right = 0.03, 0.93

    plt.subplots_adjust(left=left, right=right, top=0.98, bottom=0.16)
    plt.savefig(os.path.join(output_dir, filename), dpi=300)
    plt.close()


def _natural_sort_key(tenant: str):
    """
    Klucz sortujący: prefix literowy + opcjonalny sufiks numeryczny.
    e.g. 'A' -> ('A', 0), 'A1' -> ('A', 1), 'B2' -> ('B', 2)
    """
    m = re.match(r"^([A-Za-z]+)(\d*)$", tenant)
    if not m:
        return (tenant, 0)
    prefix, num = m.groups()
    return (prefix, int(num) if num else 0)


def draw_resource_share_combined(df, scenario, output_dir):
    """
    Rysuje łączony wykres udziału zasobów dla danego scenariusza.
    Łączy metryki CPU, Pamięć, GPU (jeśli dostępne) na jednym wykresie.
    """
    # Mapowanie scenariuszy na dostępne zasoby
    scenario_resources = {
        "F1": ["CPU", "Memory"],
        "F2": ["CPU", "Memory"],
        "F3": ["CPU", "Memory", "GPU"],
        "F4": [],  # Brak metryk udziału
    }

    resources = scenario_resources.get(scenario, [])
    if not resources:
        return

    # Mapowanie nazw zasobów na nazwy metryk w danych
    resource_metrics = {
        "CPU": "Śr. Udział CPU (w nasyceniu) [%]",
        "Memory": "Śr. Udział Pamięć (w nasyceniu) [%]",
        "GPU": "Śr. Udział GPU (w nasyceniu) [%]",
    }

    df_s = df[df["Scenariusz"] == scenario]

    # Sprawdź które metryki są rzeczywiście dostępne w danych
    available_resources = []
    for resource in resources:
        metric_name = resource_metrics[resource]
        if not df_s[df_s["Metryka"] == metric_name].empty:
            available_resources.append(resource)

    if not available_resources:
        return

    # Pobierz unikalne systemy, warianty i tenantów
    systems = sorted(
        df_s["System"].unique(),
        key=lambda x: ["Kueue", "Volcano", "YuniKorn"].index(x)
        if x in ["Kueue", "Volcano", "YuniKorn"]
        else x,
    )

    variants = sorted(
        df_s["Wariant"].unique(),
        key=lambda x: ["Z gwarancjami", "Bez gwarancji", "Brak"].index(x)
        if x in ["Z gwarancjami", "Bez gwarancji", "Brak"]
        else x,
    )

    tenants = sorted(df_s["Tenant"].dropna().unique(), key=_natural_sort_key)

    # Tworzenie kombinacji system-tenant-resource
    combos = [
        (sys, ten, res)
        for sys in systems
        for ten in tenants
        for res in available_resources
    ]

    width = 0.25
    # Dostosuj szerokość i skale na podstawie liczby systemów
    if len(systems) == 2:
        # Dla 2 systemów znacznie zmniejsz odstępy
        scale = 0.3
    else:
        # Dla 3 systemów użyj standardowych wartości
        scale = 1.0

    x = np.arange(len(combos)) * scale

    # Oblicz maksymalną wartość dla marginesu
    max_val = 0
    for var in variants:
        for sys, ten, res in combos:
            metric_name = resource_metrics[res]
            has_variants = df_s["Wariant"].dropna().shape[0] > 0
            if not has_variants:
                row = df_s[
                    (df_s["System"] == sys)
                    & (df_s["Tenant"] == ten)
                    & (df_s["Metryka"] == metric_name)
                    & (df_s["Wariant"].isna())
                ]
            else:
                row = df_s[
                    (df_s["System"] == sys)
                    & (df_s["Tenant"] == ten)
                    & (df_s["Wariant"] == var)
                    & (df_s["Metryka"] == metric_name)
                ]
            if not row.empty and not pd.isna(row["Mean"].iloc[0]):
                val_with_error = row["Mean"].iloc[0] + (
                    row["Std"].iloc[0] if not pd.isna(row["Std"].iloc[0]) else 0
                )
                if val_with_error > max_val:
                    max_val = val_with_error

    # ZMIANA: Dostosuj rozmiar figury w zależności od liczby tenantów
    num_tenants = len(tenants)
    if num_tenants <= 3:
        figsize = (16, 8)  # Oryginalna wielkość dla 3 tenantów
    elif num_tenants <= 6:
        figsize = (24, 8)  # Większa szerokość dla 6 tenantów
    else:
        figsize = (32, 8)  # Jeszcze większa szerokość dla 8 tenantów

    fig, ax = plt.subplots(figsize=figsize)

    for i, var in enumerate(variants):
        heights, errs, positions, cols, hatches_list = [], [], [], [], []
        offset = (i - (len(variants) - 1) / 2) * width
        current_pos = 0

        for idx, (sys, ten, res) in enumerate(combos):
            # Dla scenariuszy F1 i F2, pomiń YuniKorn w wariancie "Bez gwarancji"
            if (
                scenario in ["F1", "F2"]
                and sys == "YuniKorn"
                and var == "Bez gwarancji"
            ):
                continue

            metric_name = resource_metrics[res]

            # Sprawdź czy scenariusz ma warianty czy nie na podstawie pierwszego wiersza danych
            has_variants = df_s["Wariant"].dropna().shape[0] > 0

            if not has_variants:
                # Dla scenariuszy bez wariantów (F3, F4) filtruj po NaN w kolumnie Wariant
                row = df_s[
                    (df_s["System"] == sys)
                    & (df_s["Tenant"] == ten)
                    & (df_s["Metryka"] == metric_name)
                    & (df_s["Wariant"].isna())
                ]
            else:
                # Dla scenariuszy z wariantami filtruj normalnie
                row = df_s[
                    (df_s["System"] == sys)
                    & (df_s["Tenant"] == ten)
                    & (df_s["Wariant"] == var)
                    & (df_s["Metryka"] == metric_name)
                ]

            if not row.empty and not pd.isna(row["Mean"].iloc[0]):
                heights.append(row["Mean"].iloc[0])
                errs.append(
                    row["Std"].iloc[0] if not pd.isna(row["Std"].iloc[0]) else 0
                )
            else:
                heights.append(0)
                errs.append(0)

            # Użyj odcienia koloru odpowiedniego dla systemu i wariantu
            cols.append(
                color_variants[sys][var]
                if sys in color_variants and var in color_variants[sys]
                else colors.get(sys, "black")
            )
            # Użyj wzorka dla zasobu
            hatches_list.append(hatches_resource.get(res, ""))
            positions.append(current_pos * scale + offset)
            current_pos += 1

        bars = ax.bar(
            positions,
            heights,
            width=width,
            yerr=errs,
            capsize=2,
            color=cols,
            hatch=hatches_list,
            alpha=0.8,
            edgecolor="black",
            linewidth=0.5,
            label=var,
        )

        # Dodaj wartości na słupkach
        add_value_labels(ax, bars, heights, errs, max_val)

    # Utwórz etykiety tylko dla kombinacji, które rzeczywiście są wyświetlane
    labels = []
    x_positions = []
    current_pos = 0
    for sys, ten, res in combos:
        # Sprawdź czy ta kombinacja jest pomijana dla któregokolwiek wariantu
        should_include = False
        for var in variants:
            if not (
                scenario in ["F1", "F2"]
                and sys == "YuniKorn"
                and var == "Bez gwarancji"
            ):
                should_include = True
                break
        if should_include:
            labels.append(f"{sys}-{ten}-{res}")
            x_positions.append(current_pos * scale)
            current_pos += 1

    # Etykiety osi X
    ax.set_xlabel("System-Tenant-Resource")
    ax.set_ylabel("Resource share [%]")
    ax.set_xticks(x_positions)
    # ZMIANA: Dostosuj rotację etykiet w zależności od liczby tenantów
    rotation_angle = 45 if num_tenants <= 3 else (60 if num_tenants <= 6 else 75)
    fontsize = 8 if num_tenants <= 3 else (6 if num_tenants <= 6 else 5)
    ax.set_xticklabels(labels, rotation=rotation_angle, ha="right", fontsize=fontsize)
    ax.set_ylim(0, max_val * 1.15)  # Margines górny
    ax.grid(True, alpha=0.3, axis="y")  # Siatka

    # Legenda dla systemów
    system_handles = [
        Patch(facecolor=colors[sys], edgecolor="black", label=sys) for sys in systems
    ]
    system_legend = ax.legend(
        handles=system_handles,
        title="Systems",
        loc="upper left",
        bbox_to_anchor=(1.02, 1),
        borderaxespad=0,
    )
    ax.add_artist(system_legend)

    # Legenda dla wariantów - tylko jeśli mamy więcej niż jeden wariant
    if len(variants) > 1:
        # Użyj neutralnych odcieni szarości dla legendy wariantów
        variant_colors = {"Z gwarancjami": "#404040", "Bez gwarancji": "#808080"}
        variant_handles = []
        for var in variants:
            # Translate variant names for display
            display_var = {
                "Z gwarancjami": "With guarantees",
                "Bez gwarancji": "Without guarantees",
            }.get(var, var)
            variant_handles.append(
                Patch(
                    facecolor=variant_colors.get(var, "#606060"),
                    edgecolor="black",
                    label=display_var,
                )
            )
        variant_legend = ax.legend(
            handles=variant_handles,
            title="Variants",
            loc="upper left",
            bbox_to_anchor=(1.02, 0.82),
            borderaxespad=0,
        )
        ax.add_artist(variant_legend)

    # Legenda dla zasobów
    resource_handles = [
        Patch(
            facecolor="white",
            edgecolor="black",
            hatch=hatches_resource[res],
            label=res,
        )
        for res in available_resources
    ]

    # Dostosuj pozycję legendy zasobów w zależności od obecności legendy wariantów
    resource_bbox_y = 0.67 if len(variants) > 1 else 0.82

    ax.legend(
        handles=resource_handles,
        title="Resources",
        loc="upper left",
        bbox_to_anchor=(1.02, resource_bbox_y),
        borderaxespad=0,
    )

    # ZMIANA: Dostosuj marginesy w zależności od liczby tenantów
    if num_tenants <= 3:
        left, right = 0.035, 0.86
        if len(variants) == 1:
            left, right = 0.04, 0.91
    elif num_tenants <= 6:
        left, right = 0.025, 0.88
        if len(variants) == 1:
            left, right = 0.03, 0.93
    else:  # 8 tenantów
        left, right = 0.02, 0.92
        if len(variants) == 1:
            left, right = 0.025, 0.95

    plt.subplots_adjust(left=left, right=right, top=0.98, bottom=0.15)
    filename = f"{scenario}_resource_share_combined.svg"
    plt.savefig(os.path.join(output_dir, filename), dpi=300)
    plt.close()


def draw_jfi_combined(df, scenario, output_dir):
    """
    Rysuje łączony wykres JFI dla danego scenariusza.
    Łączy metryki JFI CPU, JFI Pamięć, JFI GPU (jeśli dostępne) na jednym wykresie.
    """
    # Mapowanie scenariuszy na dostępne zasoby JFI
    scenario_resources = {
        "F1": ["CPU", "Memory"],
        "F2": ["CPU", "Memory"],
        "F3": ["CPU", "Memory", "GPU"],
        "F4": [],  # Brak metryk JFI
    }

    resources = scenario_resources.get(scenario, [])
    if not resources:
        return

    # Mapowanie nazw zasobów na nazwy metryk JFI w danych
    jfi_metrics = {
        "CPU": "Śr. JFI CPU (w nasyceniu)",
        "Memory": "Śr. JFI Pamięć (w nasyceniu)",
        "GPU": "Śr. JFI GPU (w nasyceniu)",
    }

    df_s = df[df["Scenariusz"] == scenario]

    # Sprawdź które metryki JFI są rzeczywiście dostępne w danych
    available_resources = []
    for resource in resources:
        metric_name = jfi_metrics[resource]
        if not df_s[df_s["Metryka"] == metric_name].empty:
            available_resources.append(resource)

    if not available_resources:
        return

    # Sprawdź jakie warianty są dostępne
    all_variants = df_s["Wariant"].dropna().unique()  # Usuń NaN przed sprawdzeniem

    # Sprawdź czy scenariusz ma warianty czy nie
    has_variants = df_s["Wariant"].dropna().shape[0] > 0

    if not has_variants:
        # Scenariusz nie ma wariantów (F3, F4) - traktuj jako jeden "wariant"
        variants = ["Brak"]
    else:
        # Scenariusz ma warianty z gwarancjami
        variants = sorted(
            [v for v in all_variants if v in ["Z gwarancjami", "Bez gwarancji"]],
            key=lambda x: ["Z gwarancjami", "Bez gwarancji"].index(x),
        )

    # Pobierz unikalne systemy (JFI to metryki ogólne, nie per-tenant)
    systems = sorted(
        df_s["System"].unique(),
        key=lambda x: ["Kueue", "Volcano", "YuniKorn"].index(x)
        if x in ["Kueue", "Volcano", "YuniKorn"]
        else x,
    )

    # Tworzenie kombinacji system-resource
    combos = [(sys, res) for sys in systems for res in available_resources]

    width = 0.25
    # Dostosuj szerokość i skale na podstawie liczby systemów
    if len(systems) == 2:
        # Dla 2 systemów znacznie zmniejsz odstępy
        scale = 0.4
    else:
        # Dla 3 systemów użyj standardowych wartości
        scale = 1.0

    x = np.arange(len(combos)) * scale

    # Oblicz maksymalną wartość dla marginesu
    max_val = 0
    for var in variants:
        for sys, res in combos:
            metric_name = jfi_metrics[res]
            has_variants = df_s["Wariant"].dropna().shape[0] > 0
            if not has_variants:
                row = df_s[
                    (df_s["System"] == sys)
                    & (df_s["Metryka"] == metric_name)
                    & (df_s["Wariant"].isna())
                ]
            else:
                row = df_s[
                    (df_s["System"] == sys)
                    & (df_s["Wariant"] == var)
                    & (df_s["Metryka"] == metric_name)
                ]
            if not row.empty and not pd.isna(row["Mean"].iloc[0]):
                val_with_error = row["Mean"].iloc[0] + (
                    row["Std"].iloc[0] if not pd.isna(row["Std"].iloc[0]) else 0
                )
                if val_with_error > max_val:
                    max_val = val_with_error

    fig, ax = plt.subplots(figsize=(16, 8))  # Zwiększone rozmiary

    for i, var in enumerate(variants):
        heights, errs, positions, cols, hatches_list = [], [], [], [], []
        offset = (i - (len(variants) - 1) / 2) * width
        current_pos = 0

        for idx, (sys, res) in enumerate(combos):
            # Dla scenariuszy F1 i F2, pomiń YuniKorn w wariancie "Bez gwarancji"
            if (
                scenario in ["F1", "F2"]
                and sys == "YuniKorn"
                and var == "Bez gwarancji"
            ):
                continue

            metric_name = jfi_metrics[res]

            # Sprawdź czy scenariusz ma warianty czy nie na podstawie pierwszego wiersza danych
            has_variants = df_s["Wariant"].dropna().shape[0] > 0

            if not has_variants:
                # Dla scenariuszy bez wariantów (F3, F4) filtruj po NaN w kolumnie Wariant
                row = df_s[
                    (df_s["System"] == sys)
                    & (df_s["Metryka"] == metric_name)
                    & (df_s["Wariant"].isna())
                ]
            else:
                # Dla scenariuszy z wariantami filtruj normalnie
                row = df_s[
                    (df_s["System"] == sys)
                    & (df_s["Wariant"] == var)
                    & (df_s["Metryka"] == metric_name)
                ]

            if not row.empty and not pd.isna(row["Mean"].iloc[0]):
                heights.append(row["Mean"].iloc[0])
                errs.append(
                    row["Std"].iloc[0] if not pd.isna(row["Std"].iloc[0]) else 0
                )
            else:
                heights.append(0)
                errs.append(0)

            # Użyj odcienia koloru odpowiedniego dla systemu i wariantu
            cols.append(
                color_variants[sys][var]
                if sys in color_variants and var in color_variants[sys]
                else colors.get(sys, "black")
            )
            # Użyj wzorka dla zasobu
            hatches_list.append(hatches_resource.get(res, ""))
            positions.append(current_pos * scale + offset)
            current_pos += 1

        bars = ax.bar(
            positions,
            heights,
            width=width,
            yerr=errs,
            capsize=2,
            color=cols,
            hatch=hatches_list,
            alpha=0.8,
            edgecolor="black",
            linewidth=0.5,
            label=var,
        )

        # Dodaj wartości na słupkach
        add_value_labels(ax, bars, heights, errs, max_val)

    # Utwórz etykiety tylko dla kombinacji, które rzeczywiście są wyświetlane
    labels = []
    x_positions = []
    current_pos = 0
    for sys, res in combos:
        # Sprawdź czy ta kombinacja jest pomijana dla któregokolwiek wariantu
        should_include = False
        for var in variants:
            if not (
                scenario in ["F1", "F2"]
                and sys == "YuniKorn"
                and var == "Bez gwarancji"
            ):
                should_include = True
                break
        if should_include:
            labels.append(f"{sys}-{res}")
            x_positions.append(current_pos * scale)
            current_pos += 1

    # Etykiety osi X
    ax.set_xlabel("System-Resource")
    ax.set_ylabel("JFI")
    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylim(0, max_val * 1.15)  # Margines górny
    ax.grid(True, alpha=0.3, axis="y")  # Siatka

    # Legenda dla systemów
    system_handles = [
        Patch(facecolor=colors[sys], edgecolor="black", label=sys) for sys in systems
    ]
    system_legend = ax.legend(
        handles=system_handles,
        title="Systems",
        loc="upper left",
        bbox_to_anchor=(1.02, 1),
        borderaxespad=0,
    )
    ax.add_artist(system_legend)

    # Legenda dla wariantów - tylko jeśli mamy więcej niż jeden wariant
    if len(variants) > 1:
        # Użyj neutralnych odcieni szarości dla legendy wariantów
        variant_colors = {"Z gwarancjami": "#404040", "Bez gwarancji": "#808080"}
        variant_handles = []
        for var in variants:
            # Translate variant names for display
            display_var = {
                "Z gwarancjami": "With guarantees",
                "Bez gwarancji": "Without guarantees",
            }.get(var, var)
            variant_handles.append(
                Patch(
                    facecolor=variant_colors.get(var, "#606060"),
                    edgecolor="black",
                    label=display_var,
                )
            )
        variant_legend = ax.legend(
            handles=variant_handles,
            title="Variants",
            loc="upper left",
            bbox_to_anchor=(1.02, 0.82),
            borderaxespad=0,
        )
        ax.add_artist(variant_legend)

    # Legenda dla zasobów
    resource_handles = [
        Patch(
            facecolor="white",
            edgecolor="black",
            hatch=hatches_resource[res],
            label=res,
        )
        for res in available_resources
    ]

    # Dostosuj pozycję legendy zasobów w zależności od obecności legendy wariantów
    resource_bbox_y = 0.67 if len(variants) > 1 else 0.82

    ax.legend(
        handles=resource_handles,
        title="Resources",
        loc="upper left",
        bbox_to_anchor=(1.02, resource_bbox_y),
        borderaxespad=0,
    )

    left, right = 0.04, 0.86
    if len(variants) == 1:
        left, right = 0.04, 0.91

    plt.subplots_adjust(left=left, right=right, top=0.98, bottom=0.16)
    filename = f"{scenario}_jfi_combined.svg"
    plt.savefig(os.path.join(output_dir, filename), dpi=300)
    plt.close()


if __name__ == "__main__":
    input_file = "wyniki/NoweWyniki.xlsx"
    sheet = "Sprawiedliwość"
    output_base = "wyniki/nowe_wyniki_sprawiedliwosc"
    os.makedirs(output_base, exist_ok=True)

    data = load_data(input_file, sheet)
    scenarios = ["F1", "F2", "F3", "F4"]

    for scen in scenarios:
        df_s = data[data["Scenariusz"] == scen]
        if df_s.empty:
            continue
        print(f"Generowanie wykresów dla scenariusza {scen}...")

        # Wykresy łączone dla udziału zasobów i JFI
        draw_resource_share_combined(data, scen, output_base)
        draw_jfi_combined(data, scen, output_base)

        # Metryki ogólne (oryginalne)
        general_metrics = [
            (
                "Makespan (Faza 2) [s]",
                f"{scen}_makespan_phase2.svg",
                "Makespan (Phase 2) [s]",
            ),
            ("Makespan [s]", f"{scen}_makespan.svg", "Makespan [s]"),
        ]
        for metric, filename, ylabel in general_metrics:
            draw_general_metric(data, scen, output_base, metric, ylabel, filename)

        tenant_metrics = [
            (
                "Śr. Czas Oczekiwania (Faza 2 do momentu nasycenia klastra) [s]",
                f"{scen}_wait_time_phase2.svg",
                "Wait time (Phase 2 until cluster saturation) [s]",
            ),
            (
                "Śr. Czas Oczekiwania (wszystkie zadadania) [s]",
                f"{scen}_wait_time.svg",
                "Wait time [s]",
            ),
            (
                "Śr. Liczba Uruchomionych Podów (w nasyceniu)",
                f"{scen}_no_pods.svg",
                "Number of Pods (at saturation)",
            ),
        ]
        for metric, filename, ylabel in tenant_metrics:
            draw_per_tenant_metric(data, scen, output_base, metric, ylabel, filename)

        print(f"Zakończono generowanie wykresów dla scenariusza {scen}")

    print("Zakończono generowanie wszystkich wykresów sprawiedliwości!")

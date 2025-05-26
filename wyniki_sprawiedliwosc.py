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
hatches_resource = {"CPU": "///", "Pamięć": "\\\\\\", "GPU": "+++"}

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

    fig, ax = plt.subplots(figsize=(6, 4))
    for i, var in enumerate(variants):
        heights, errs, positions, cols = [], [], [], []
        offset = (i - (len(variants) - 1) / 2) * width
        for j, sys in enumerate(systems):
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
            positions.append(j * scale + offset)
        ax.bar(
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

    ax.set_xlabel("System")
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(systems)

    # Legenda dla systemów
    system_handles = [
        Patch(facecolor=colors[sys], edgecolor="black", label=sys) for sys in systems
    ]
    system_legend = ax.legend(
        handles=system_handles,
        title="Systemy",
        loc="upper left",
        bbox_to_anchor=(1, 1),
        frameon=False,
    )
    ax.add_artist(system_legend)

    # Legenda dla wariantów - tylko jeśli mamy więcej niż jeden wariant i nie jest "Brak"
    if not (len(variants) == 1 and variants[0] == "Brak"):
        # ZMIANA: Użyj neutralnych odcieni szarości dla legendy wariantów (jak w jfi_combined)
        variant_colors = {"Z gwarancjami": "#404040", "Bez gwarancji": "#808080"}
        variant_handles = []
        for var in variants:
            variant_handles.append(
                Patch(
                    facecolor=variant_colors.get(var, "#606060"),
                    edgecolor="black",
                    label=var,
                )
            )
        ax.legend(
            handles=variant_handles,
            title="Warianty",
            loc="upper left",
            bbox_to_anchor=(1, 0.7),
            frameon=False,
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

    fig, ax = plt.subplots(figsize=(10, 6))
    for i, var in enumerate(variants):
        heights, errs, positions, cols = [], [], [], []
        offset = (i - (len(variants) - 1) / 2) * width
        for idx, (sys, ten) in enumerate(combos):
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
            positions.append(idx * scale + offset)
        ax.bar(
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

    labels = [f"{sys}-{ten}" for sys, ten in combos]
    ax.set_xlabel("System-Tenant")
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")

    # Legenda dla systemów
    system_handles = [
        Patch(facecolor=colors[sys], edgecolor="black", label=sys) for sys in systems
    ]
    system_legend = ax.legend(
        handles=system_handles,
        title="Systemy",
        loc="upper left",
        bbox_to_anchor=(1, 1),
        frameon=False,
    )
    ax.add_artist(system_legend)

    # Legenda dla wariantów - tylko jeśli mamy więcej niż jeden wariant i nie jest "Brak"
    if not (len(variants) == 1 and variants[0] == "Brak"):
        # ZMIANA: Użyj neutralnych odcieni szarości dla legendy wariantów (jak w jfi_combined)
        variant_colors = {"Z gwarancjami": "#404040", "Bez gwarancji": "#808080"}
        variant_handles = []
        for var in variants:
            variant_handles.append(
                Patch(
                    facecolor=variant_colors.get(var, "#606060"),
                    edgecolor="black",
                    label=var,
                )
            )
        ax.legend(
            handles=variant_handles,
            title="Warianty",
            loc="upper left",
            bbox_to_anchor=(1, 0.7),
            frameon=False,
        )

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, filename))
    plt.close()


def draw_resource_share_combined(df, scenario, output_dir):
    """
    Rysuje łączony wykres udziału zasobów dla danego scenariusza.
    Łączy metryki CPU, Pamięć, GPU (jeśli dostępne) na jednym wykresie.
    """
    # Mapowanie scenariuszy na dostępne zasoby
    scenario_resources = {
        "F1": ["CPU", "Pamięć"],
        "F2": ["CPU", "Pamięć"],
        "F3": ["CPU", "Pamięć", "GPU"],
        "F4": [],  # Brak metryk udziału
    }

    resources = scenario_resources.get(scenario, [])
    if not resources:
        return

    # Mapowanie nazw zasobów na nazwy metryk w danych
    resource_metrics = {
        "CPU": "Śr. Udział CPU (w nasyceniu) [%]",
        "Pamięć": "Śr. Udział Pamięć (w nasyceniu) [%]",
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

    # Pobierz tenantów - tylko rzeczywiste tenancy (A, B, C), pomiń NaN
    tenants_order = {"A": 0, "B": 1, "C": 2}
    all_tenants = df_s["Tenant"].dropna().unique()
    tenants = sorted(
        [t for t in all_tenants if t in tenants_order],
        key=lambda x: tenants_order.get(x, 999),
    )

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

    fig, ax = plt.subplots(figsize=(14, 7))

    for i, var in enumerate(variants):
        heights, errs, positions, cols, hatches_list = [], [], [], [], []
        offset = (i - (len(variants) - 1) / 2) * width

        for idx, (sys, ten, res) in enumerate(combos):
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
            positions.append(idx * scale + offset)

        ax.bar(
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

    # Etykiety osi X
    labels = [f"{sys}-{ten}-{res}" for sys, ten, res in combos]
    ax.set_xlabel("System-Tenant-Zasób")
    ax.set_ylabel("Udział zasobu [%]")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")

    # Legenda dla systemów
    system_handles = [
        Patch(facecolor=colors[sys], edgecolor="black", label=sys) for sys in systems
    ]
    system_legend = ax.legend(
        handles=system_handles,
        title="Systemy",
        loc="upper left",
        bbox_to_anchor=(1, 1),
        frameon=False,
    )
    ax.add_artist(system_legend)

    # Legenda dla wariantów - tylko jeśli mamy więcej niż jeden wariant
    if len(variants) > 1:
        # Użyj neutralnych odcieni szarości dla legendy wariantów
        variant_colors = {"Z gwarancjami": "#404040", "Bez gwarancji": "#808080"}
        variant_handles = []
        for var in variants:
            variant_handles.append(
                Patch(
                    facecolor=variant_colors.get(var, "#606060"),
                    edgecolor="black",
                    label=var,
                )
            )
        variant_legend = ax.legend(
            handles=variant_handles,
            title="Warianty",
            loc="upper left",
            bbox_to_anchor=(1, 0.7),
            frameon=False,
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
    ax.legend(
        handles=resource_handles,
        title="Zasoby",
        loc="upper left",
        bbox_to_anchor=(1, 0.4),
        frameon=False,
    )

    left, right = 0.04, 0.88
    if len(variants) == 1:
        left, right = 0.05, 0.91

    plt.subplots_adjust(left=left, right=right, top=0.98, bottom=0.2)
    filename = f"{scenario}_resource_share_combined.svg"
    plt.savefig(os.path.join(output_dir, filename))
    plt.close()


def draw_jfi_combined(df, scenario, output_dir):
    """
    Rysuje łączony wykres JFI dla danego scenariusza.
    Łączy metryki JFI CPU, JFI Pamięć, JFI GPU (jeśli dostępne) na jednym wykresie.
    """
    # Mapowanie scenariuszy na dostępne zasoby JFI
    scenario_resources = {
        "F1": ["CPU", "Pamięć"],
        "F2": ["CPU", "Pamięć"],
        "F3": ["CPU", "Pamięć", "GPU"],
        "F4": [],  # Brak metryk JFI
    }

    resources = scenario_resources.get(scenario, [])
    if not resources:
        return

    # Mapowanie nazw zasobów na nazwy metryk JFI w danych
    jfi_metrics = {
        "CPU": "Śr. JFI CPU (w nasyceniu)",
        "Pamięć": "Śr. JFI Pamięć (w nasyceniu)",
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

    fig, ax = plt.subplots(figsize=(14, 7))

    for i, var in enumerate(variants):
        heights, errs, positions, cols, hatches_list = [], [], [], [], []
        offset = (i - (len(variants) - 1) / 2) * width

        for idx, (sys, res) in enumerate(combos):
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
            positions.append(idx * scale + offset)

        ax.bar(
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

    # Etykiety osi X
    labels = [f"{sys}-{res}" for sys, res in combos]
    ax.set_xlabel("System-Zasób")
    ax.set_ylabel("JFI")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")

    # Legenda dla systemów
    system_handles = [
        Patch(facecolor=colors[sys], edgecolor="black", label=sys) for sys in systems
    ]
    system_legend = ax.legend(
        handles=system_handles,
        title="Systemy",
        loc="upper left",
        bbox_to_anchor=(1, 1),
        frameon=False,
    )
    ax.add_artist(system_legend)

    # Legenda dla wariantów - tylko jeśli mamy więcej niż jeden wariant
    if len(variants) > 1:
        # Użyj neutralnych odcieni szarości dla legendy wariantów
        variant_colors = {"Z gwarancjami": "#404040", "Bez gwarancji": "#808080"}
        variant_handles = []
        for var in variants:
            variant_handles.append(
                Patch(
                    facecolor=variant_colors.get(var, "#606060"),
                    edgecolor="black",
                    label=var,
                )
            )
        variant_legend = ax.legend(
            handles=variant_handles,
            title="Warianty",
            loc="upper left",
            bbox_to_anchor=(1, 0.7),
            frameon=False,
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
    ax.legend(
        handles=resource_handles,
        title="Zasoby",
        loc="upper left",
        bbox_to_anchor=(1, 0.4),
        frameon=False,
    )

    left, right = 0.04, 0.88
    if len(variants) == 1:
        left, right = 0.05, 0.91

    plt.subplots_adjust(left=left, right=right, top=0.98, bottom=0.2)
    filename = f"{scenario}_jfi_combined.svg"
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

        # Wykresy łączone dla udziału zasobów i JFI
        draw_resource_share_combined(data, scen, output_base)
        draw_jfi_combined(data, scen, output_base)

        # Metryki ogólne (oryginalne)
        general_metrics = [
            (
                "Makespan (Faza 2) [s]",
                f"{scen}_makespan_phase2.svg",
                "Całkowity zakres czasowy (Faza 2) [s]",
            ),
            ("Makespan [s]", f"{scen}_makespan.svg", "Całkowity zakres czasowy [s]"),
        ]
        for metric, filename, ylabel in general_metrics:
            draw_general_metric(data, scen, output_base, metric, ylabel, filename)

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
        ]
        for metric, filename, ylabel in tenant_metrics:
            draw_per_tenant_metric(data, scen, output_base, metric, ylabel, filename)

        print(f"Zakończono generowanie wykresów dla scenariusza {scen}")

    print("Zakończono generowanie wszystkich wykresów sprawiedliwości!")

#!/usr/bin/env python3
"""
Skrypt `wyniki_sprawiedliwosc.py`
Wczytuje dane z arkusza 'Sprawiedliwość' pliku Excel i generuje wykresy:
 - Udział zasobów CPU/RAM/GPU
 - Równomierność rozłożenia (JFI) CPU/RAM/GPU
 - Liczba uruchomionych podów
 - Średni czas oczekiwania (w tym fazy)
 - Makespan

Dla scenariusza F4, gdzie występują tylko metryki czasu oczekiwania fazy 2 i Makespan, wygenerowane zostaną tylko te dwa wykresy.
Wyniki zapisuje jako pliki SVG w katalogu `wyniki/wyniki_sprawiedliwosc`.
"""

import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# --------- Ustawienia globalne ---------
plt.rcParams["hatch.linewidth"] = 0.5

# --------- Definicje stylu z istniejących skryptów ---------
colors = {"Kueue": "#1f77b4", "Volcano": "#d62728", "YuniKorn": "#2ca02c"}
variant_hatches = {"Bez gwarancji": "", "Z gwarancjami": "///"}


# --------- Funkcje pomocnicze ---------
def load_data(path, sheet_name="Sprawiedliwość"):
    raw = pd.read_excel(path, sheet_name=sheet_name)
    return prepare_blocks(raw)


def prepare_blocks(df):
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
        temp = df[cols].copy()
        temp.columns = [
            "Scenariusz",
            "Wariant",
            "System",
            "Metryka",
            "Tenant",
            "Mean",
            "Std",
        ]
        blocks.append(temp)
    data = pd.concat(blocks, ignore_index=True)
    mask = (data["Scenariusz"] != "Scenariusz") & (data["Metryka"] != "Metryka")
    data = data[mask].copy()
    data["Mean"] = pd.to_numeric(data["Mean"], errors="coerce")
    data["Std"] = pd.to_numeric(data["Std"], errors="coerce")
    return data


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


# --------- Wykresy ---------
def draw_resources(df, scenario, out_dir):
    df_s = df[df["Scenariusz"] == scenario]
    mapping = {
        "Śr. Udział CPU (w nasyceniu) [%]": "CPU",
        "Śr. Udział Pam. (w nasyceniu) [%]": "RAM",
        "Śr. Udział GPU (w nasyceniu) [%]": "GPU",
    }
    resources = [res for met, res in mapping.items() if (df_s["Metryka"] == met).any()]
    if not resources:
        return
    variants, systems = ["Bez gwarancji", "Z gwarancjami"], list(colors)
    N, bars = len(resources), len(variants) * len(systems)
    width = 0.8 / bars
    offsets = [(i * width) - 0.4 + width / 2 for i in range(bars)]
    fig, ax = plt.subplots(figsize=(8, 4))
    for i, var in enumerate(variants):
        for j, sys in enumerate(systems):
            idx = i * len(systems) + j
            means, stds = [], []
            for met, res in mapping.items():
                if res in resources:
                    sel = df_s[
                        (df_s["Metryka"] == met)
                        & (df_s["Wariant"] == var)
                        & (df_s["System"] == sys)
                    ]
                    means.append(sel["Mean"].iat[0] if not sel.empty else 0)
                    stds.append(sel["Std"].iat[0] if not sel.empty else 0)
            ax.bar(
                np.arange(N) + offsets[idx],
                means,
                width,
                label=f"{sys} – {var}",
                facecolor=colors[sys],
                edgecolor="black",
                hatch=variant_hatches[var],
                yerr=stds,
                capsize=3,
            )
    ax.set_xticks(range(N))
    ax.set_xticklabels(resources)
    ax.set_xlabel("Zasób")
    ax.set_ylabel("Udział [%]")
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1), frameon=False)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"{scenario}_resources.svg"))
    plt.close()


def draw_jfi(df, scenario, out_dir):
    df_s = df[df["Scenariusz"] == scenario]
    mapping = {
        "Śr. JFI CPU (w nasyceniu)": "CPU",
        "Śr. JFI Pam. (w nasyceniu)": "RAM",
        "Śr. JFI GPU (w nasyceniu)": "GPU",
    }
    resources = [res for met, res in mapping.items() if (df_s["Metryka"] == met).any()]
    if not resources:
        return
    variants, systems = ["Bez gwarancji", "Z gwarancjami"], list(colors)
    N, bars = len(resources), len(variants) * len(systems)
    width = 0.8 / bars
    offsets = [(i * width) - 0.4 + width / 2 for i in range(bars)]
    fig, ax = plt.subplots(figsize=(8, 4))
    for i, var in enumerate(variants):
        for j, sys in enumerate(systems):
            idx = i * len(systems) + j
            means, stds = [], []
            for met, res in mapping.items():
                if res in resources:
                    sel = df_s[
                        (df_s["Metryka"] == met)
                        & (df_s["Wariant"] == var)
                        & (df_s["System"] == sys)
                    ]
                    means.append(sel["Mean"].iat[0] if not sel.empty else 0)
                    stds.append(sel["Std"].iat[0] if not sel.empty else 0)
            ax.bar(
                np.arange(N) + offsets[idx],
                means,
                width,
                label=f"{sys} – {var}",
                facecolor=colors[sys],
                edgecolor="black",
                hatch=variant_hatches[var],
                yerr=stds,
                capsize=3,
            )
    ax.set_xticks(range(N))
    ax.set_xticklabels(resources)
    ax.set_xlabel("Zasób")
    ax.set_ylabel("JFI [%]")
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1), frameon=False)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"{scenario}_jfi.svg"))
    plt.close()


def draw_pods(df, scenario, out_dir):
    df_s = df[df["Scenariusz"] == scenario]
    metric = "Śr. Liczba Uruch. Podów (w nasyceniu)"
    df_m = df_s[df_s["Metryka"] == metric]
    if df_m.empty:
        return
    variants, systems = ["Bez gwarancji", "Z gwarancjami"], list(colors)
    N = len(variants)
    width = 0.8 / len(systems)
    offsets = [(i * width) - 0.4 + width / 2 for i in range(len(systems))]
    fig, ax = plt.subplots(figsize=(6, 4))
    for j, sys in enumerate(systems):
        means, stds = [], []
        for var in variants:
            sel = df_m[(df_m["Wariant"] == var) & (df_m["System"] == sys)]
            means.append(sel["Mean"].iat[0] if not sel.empty else 0)
            stds.append(sel["Std"].iat[0] if not sel.empty else 0)
        ax.bar(
            np.arange(N) + offsets[j],
            means,
            width,
            label=sys,
            facecolor=colors[sys],
            edgecolor="black",
            hatch=variant_hatches[variants[0]],
            yerr=stds,
            capsize=3,
        )
    ax.set_xticks(range(N))
    ax.set_xticklabels(variants)
    ax.set_xlabel("Wariant")
    ax.set_ylabel("Liczba podów")
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1), frameon=False)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"{scenario}_pods.svg"))
    plt.close()


def draw_wait(df, scenario, out_dir):
    df_s = df[df["Scenariusz"] == scenario]
    # Wyszukaj dowolną metrykę czasu oczekiwania
    possible = [
        "Śr. Czas Oczekiwania (wszystkie zad.) [s]",
        "Śr. Czas Oczek. (Faza 2) [s]",
    ]
    metric = next((m for m in possible if (df_s["Metryka"] == m).any()), None)
    if metric is None:
        return
    df_m = df_s[df_s["Metryka"] == metric]
    variants, systems = ["Bez gwarancji", "Z gwarancjami"], list(colors)
    N = len(variants)
    width = 0.8 / len(systems)
    offsets = [(i * width) - 0.4 + width / 2 for i in range(len(systems))]
    fig, ax = plt.subplots(figsize=(6, 4))
    for j, sys in enumerate(systems):
        means, stds = [], []
        for var in variants:
            sel = df_m[(df_m["Wariant"] == var) & (df_m["System"] == sys)]
            means.append(sel["Mean"].iat[0] if not sel.empty else 0)
            stds.append(sel["Std"].iat[0] if not sel.empty else 0)
        ax.bar(
            np.arange(N) + offsets[j],
            means,
            width,
            label=sys,
            facecolor=colors[sys],
            edgecolor="black",
            hatch=variant_hatches[var],
            yerr=stds,
            capsize=3,
        )
    ax.set_xticks(range(N))
    ax.set_xticklabels(variants)
    ax.set_xlabel("Wariant")
    ax.set_ylabel(f"{metric}")
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1), frameon=False)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"{scenario}_wait.svg"))
    plt.close()


def draw_makespan(df, scenario, out_dir):
    df_s = df[df["Scenariusz"] == scenario]
    metric = "Makespan [s]"
    df_m = df_s[df_s["Metryka"] == metric]
    if df_m.empty:
        return
    variants, systems = ["Bez gwarancji", "Z gwarancjami"], list(colors)
    N, len_vars = len(variants), len(systems)
    width = 0.8 / len_vars
    offsets = [(i * width) - 0.4 + width / 2 for i in range(len_vars)]
    fig, ax = plt.subplots(figsize=(6, 4))
    for j, sys in enumerate(systems):
        means, stds = [], []
        for var in variants:
            sel = df_m[(df_m["Wariant"] == var) & (df_m["System"] == sys)]
            means.append(sel["Mean"].iat[0] if not sel.empty else 0)
            stds.append(sel["Std"].iat[0] if not sel.empty else 0)
        ax.bar(
            np.arange(N) + offsets[j],
            means,
            width,
            label=sys,
            facecolor=colors[sys],
            edgecolor="black",
            hatch=variant_hatches[var],
            yerr=stds,
            capsize=3,
        )
    ax.set_xticks(range(N))
    ax.set_xticklabels(variants)
    ax.set_xlabel("Wariant")
    ax.set_ylabel("Makespan [s]")
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1), frameon=False)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"{scenario}_makespan.svg"))
    plt.close()


# --------- Główna sekcja ---------
if __name__ == "__main__":
    excel_path = "wyniki_sprawiedliwosc.xlsx"
    out_dir = os.path.join("wyniki", "wyniki_sprawiedliwosc")
    ensure_dir(out_dir)
    df = load_data(excel_path)
    for sc in ["F1", "F2", "F3", "F4"]:
        draw_resources(df, sc, out_dir)
        draw_jfi(df, sc, out_dir)
        draw_pods(df, sc, out_dir)
        draw_wait(df, sc, out_dir)
        draw_makespan(df, sc, out_dir)
    print(f"Wykresy zapisano w katalogu: {out_dir}")

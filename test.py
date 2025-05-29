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
}

tools = ["Kueue", "Volcano", "YuniKorn"]
colors = {"Kueue": "blue", "Volcano": "red", "YuniKorn": "green"}
light_colors = {"Kueue": "lightblue", "Volcano": "lightcoral", "YuniKorn": "lightgreen"}
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


def linear_regression_simple(x, y):
    """
    Prosta implementacja regresji liniowej bez zewnętrznych zależności.
    Zwraca slope, intercept, r_squared
    """
    n = len(x)
    if n < 2:
        return 0, 0, 0

    # Usuń pary z NaN
    valid_mask = ~(np.isnan(x) | np.isnan(y))
    x_clean = x[valid_mask]
    y_clean = y[valid_mask]

    if len(x_clean) < 2:
        return 0, 0, 0

    # Oblicz średnie
    x_mean = np.mean(x_clean)
    y_mean = np.mean(y_clean)

    # Oblicz slope i intercept
    numerator = np.sum((x_clean - x_mean) * (y_clean - y_mean))
    denominator = np.sum((x_clean - x_mean) ** 2)

    if denominator == 0:
        return 0, y_mean, 0

    slope = numerator / denominator
    intercept = y_mean - slope * x_mean

    # Oblicz R²
    y_pred = slope * x_clean + intercept
    ss_res = np.sum((y_clean - y_pred) ** 2)
    ss_tot = np.sum((y_clean - y_mean) ** 2)

    if ss_tot == 0:
        r_squared = 1.0  # Perfect fit when all y values are the same
    else:
        r_squared = 1 - (ss_res / ss_tot)

    return slope, intercept, max(0, r_squared)  # R² nie może być ujemne


def extract_numeric_values(combos):
    """
    Ekstraktuje wartości numeryczne z kombinacji dla linii trendu.
    """
    numeric_values = []
    for combo in combos:
        if isinstance(combo, str) and "x" in combo:
            try:
                w, h = combo.split("x")
                # Używamy sumy jako reprezentacji wielkości kombinacji
                numeric_values.append(int(w) + int(h))
            except:
                numeric_values.append(0)
        else:
            numeric_values.append(0)
    return np.array(numeric_values)


def add_trend_lines(ax, x_labels, mean_dict, colors_dict, labels):
    """
    Dodaje linie trendu do wykresów słupkowych.
    """
    x_numeric = extract_numeric_values(x_labels)
    x_positions = np.arange(len(x_labels))

    for i, (tool, resource) in enumerate(labels):
        tool_name = tool if resource == "" else tool
        means = np.array(mean_dict[(tool, resource)])

        # Sprawdź czy są nietrywialne różnice w danych
        unique_means = means[~np.isnan(means)]
        if len(set(unique_means)) <= 1:  # Wszystkie wartości są takie same
            continue

        # Użyj prostej regresji liniowej
        slope, intercept, r2 = linear_regression_simple(x_numeric, means)

        # Rysuj linię trendu tylko jeśli R² > 0.3 (umiarkowana korelacja)
        if r2 > 0.3:
            color = colors_dict[tool_name]

            # Oblicz przewidywane wartości dla wszystkich punktów
            y_pred = slope * x_numeric + intercept

            # Linia trendu - bez etykiety w legendzie
            ax.plot(
                x_positions, y_pred, color=color, linestyle="--", alpha=0.7, linewidth=2
            )


def plot_grouped_bar_with_trends(
    x_labels,
    mean_dict,
    std_dict,
    title,
    xlabel,
    ylabel,
    labels,
    outfile,
    output_dir,
    add_trends=True,
):
    """
    Pomocnicza funkcja do rysowania grupowanych wykresów słupkowych z wartościami na słupkach i liniami trendu.
    """
    fig, ax = plt.subplots(figsize=(12, 8))  # Zwiększone rozmiary
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

    # Rysuj słupki
    for i, (tool, resource) in enumerate(labels):
        means = mean_dict[(tool, resource)]
        stds = std_dict[(tool, resource)]

        bars = ax.bar(
            np.arange(N) + offsets[i],
            means,
            width,
            label=f"{tool} {resource}".strip(),
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
            y_pos = mean_val + std_val + (max_val * 0.02)
            x_pos = bar.get_x() + bar.get_width() / 2
            text_val = f"{mean_val:.2f}"

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
                    boxstyle="round,pad=0.2",
                    facecolor="white",
                    alpha=0.8,
                    edgecolor="none",
                ),
            )

    # Dodaj linie trendu dla metryk, które na to zasługują
    if add_trends and len(labels) <= 3:  # Tylko dla pojedynczych metryk
        add_trend_lines(ax, x_labels, mean_dict, colors, labels)

    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xticks(np.arange(N))
    ax.set_xticklabels(x_labels, rotation=45, ha="right")

    # Zwiększ margines górny o 20% dla zmieszczenia etykiet i linii trendu
    ax.set_ylim(0, max_val * 1.2)

    # Ulepszona legenda
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), borderaxespad=0, fontsize=10)
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, outfile), bbox_inches="tight", dpi=300)
    plt.close()


def create_performance_comparison_chart(df, scenario, output_dir):
    """
    Tworzy wykres porównawczy normalizujący wydajność wszystkich systemów.
    """
    df_s = df[df["Scenariusz"] == scenario]
    combos = sorted(df_s["Kombinacja"].dropna().unique(), key=sort_key)

    # Zbierz kluczowe metryki dla porównania
    key_metrics = [
        "Makespan [s]",
        "Śr. Narzut CPU Harmonogr. [cores]",
        "Śr. Narzut Pam. Harmonogr. [MB]",
    ]

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(
        f"Scenario {scenario} - Performance Comparison Overview",
        fontsize=16,
        fontweight="bold",
    )

    for idx, raw_metric in enumerate(key_metrics):
        ax = axes[idx]
        df_m = df_s[df_s["Metryka"] == raw_metric]

        if df_m.empty:
            continue

        piv_mean = df_m.pivot(
            index="Kombinacja", columns="System", values="Mean"
        ).reindex(combos)

        # Normalizacja względem najlepszego wyniku (najniższa wartość = 1.0)
        normalized_data = piv_mean.copy()
        for combo in combos:
            row_values = piv_mean.loc[combo]
            min_val = row_values.min()
            if min_val > 0:
                normalized_data.loc[combo] = row_values / min_val

        # Wykres słupkowy znormalizowanych wartości
        x_pos = np.arange(len(combos))
        width = 0.25

        for i, tool in enumerate(tools):
            if tool in normalized_data.columns:
                values = normalized_data[tool].values
                # Dodaj label tylko dla pierwszego wykresu (idx == 0)
                label = tool if idx == 0 else ""
                bars = ax.bar(
                    x_pos + i * width,
                    values,
                    width,
                    label=label,
                    color=colors[tool],
                    alpha=0.8,
                )

                # Dodaj wartości na słupkach
                for j, (bar, val) in enumerate(zip(bars, values)):
                    if not np.isnan(val):
                        ax.text(
                            bar.get_x() + bar.get_width() / 2,
                            bar.get_height() + 0.02,
                            f"{val:.2f}x",
                            ha="center",
                            va="bottom",
                            fontsize=8,
                        )

        ax.set_xlabel("Node and task combinations")
        ax.set_ylabel("Relative Performance\n(1.0 = best)")
        ax.set_title(file_key_map[raw_metric])
        ax.set_xticks(x_pos + width)
        ax.set_xticklabels(combos, rotation=45, ha="right")
        ax.grid(True, alpha=0.3, axis="y")
        ax.axhline(y=1.0, color="black", linestyle="-", alpha=0.5, linewidth=1)

    # Jedna wspólna legenda dla całej figury, umieszczona po prawej stronie
    fig.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=12)

    plt.tight_layout()
    plt.savefig(
        os.path.join(output_dir, f"{scenario}_Performance_Comparison.svg"),
        bbox_inches="tight",
        dpi=300,
    )
    plt.close()


def draw_resource_utilization(df, scenario, output_dir):
    """
    Rysuje wykres wykorzystania zasobów (CPU, RAM, GPU) dla danego scenariusza z liniami trendu.
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

    plot_grouped_bar_with_trends(
        combos,
        mean_util,
        std_util,
        f"Scenario {scenario} – Resource utilization",
        "Node and task combinations",
        "Resource utilization (%)",
        labels_util,
        f"{scenario}_Wykorzystanie_zasobow.svg",
        output_dir,
        add_trends=False,  # Zbyt wiele linii byłoby nieczytelne
    )


def draw_resource_distribution(df, scenario, output_dir):
    """
    Rysuje wykres równomierności rozłożenia zasobów (std CPU, std RAM) dla danego scenariusza.
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

    plot_grouped_bar_with_trends(
        combos,
        mean_std,
        std_std,
        f"Scenario {scenario} – Resource distribution evenness",
        "Node and task combinations",
        "Resource distribution evenness (%)",
        labels_std,
        f"{scenario}_Rownomiernosc_zasobow.svg",
        output_dir,
        add_trends=False,  # YuniKorn ma wszystkie wartości 0, więc trend nie ma sensu
    )


def draw_other_metrics(df, scenario, output_dir):
    """
    Rysuje wykresy dla pozostałych metryk: Makespan i narzutów zasobów z liniami trendu.
    """
    df_s = df[df["Scenariusz"] == scenario]
    combos = sorted(df_s["Kombinacja"].dropna().unique(), key=sort_key)

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

            plot_grouped_bar_with_trends(
                combos,
                {(tool, ""): mean_vals[tool] for tool in tools},
                {(tool, ""): std_vals[tool] for tool in tools},
                f"Scenario {scenario} – {title_label_map[file_key]}",
                "Node and task combinations",
                display_label_map[file_key],
                labels_single,
                f"{scenario}_{file_key}.svg",
                output_dir,
                add_trends=True,  # Te metryki mają wyraźne trendy
            )


if __name__ == "__main__":
    input_file = "Wyniki.xlsx"
    sheet = "Wydajność i Skalowalność"
    output_base = "wyniki/wyniki_wydajnosc_i_skalowalnosc_enhanced"
    os.makedirs(output_base, exist_ok=True)

    data = load_data(input_file, sheet)
    scenarios = ["V1", "V2", "V3"]

    print(f"Loaded {len(data)} data points")
    print(f"Scenarios found: {data['Scenariusz'].unique()}")
    print(f"Systems found: {data['System'].unique()}")
    print(f"Metrics found: {len(data['Metryka'].unique())} unique metrics")

    # Generuj ulepszone wykresy dla każdego scenariusza
    for scen in scenarios:
        df_s = data[data["Scenariusz"] == scen]
        if df_s.empty:
            print(f"No data found for scenario {scen}")
            continue

        print(f"Processing scenario {scen}...")
        draw_resource_utilization(data, scen, output_base)
        draw_resource_distribution(data, scen, output_base)
        draw_other_metrics(data, scen, output_base)
        create_performance_comparison_chart(data, scen, output_base)

    print(f"Enhanced visualizations generated in {output_base}")

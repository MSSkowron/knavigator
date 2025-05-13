import logging
import os
import re
import time
from collections import defaultdict

import kubernetes
import kubernetes.client
import kubernetes.config
from prometheus_client import CollectorRegistry, Gauge, start_http_server

# --- Konfiguracja ---
LISTEN_PORT = int(
    os.environ.get("LISTEN_PORT", 8001)
)  # Inny port niż unified-job-exporter
SCRAPE_INTERVAL = int(
    os.environ.get("SCRAPE_INTERVAL", 15)
)  # Zwiększony interwał może być lepszy dla node/pod
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s - %(levelname)s - %(message)s")

KNOWN_GPU_KEYS = [
    "nvidia.com/gpu",
    "amd.com/gpu",
    "intel.com/gpu",
    # "example.com/gpu", # Przykład
]

# --- Definicje Metryk ---
# Użyj nowej, dedykowanej registry
NODE_REGISTRY = CollectorRegistry()
NODE_LABELS = [
    "node_name",
    "hostname",
    "datacenter",
    "spine",
    "block",
    "is_kwok",
]

# --- Metryki Pojemności (Capacity) ---
node_capacity_cpu_cores = Gauge(
    "node_capacity_cpu_cores",
    "Total CPU capacity of the node in cores",
    NODE_LABELS,
    registry=NODE_REGISTRY,
)
node_capacity_memory_bytes = Gauge(
    "node_capacity_memory_bytes",
    "Total memory capacity of the node in bytes",
    NODE_LABELS,
    registry=NODE_REGISTRY,
)
node_capacity_pods = Gauge(
    "node_capacity_pods",
    "Total pod capacity of the node",
    NODE_LABELS,
    registry=NODE_REGISTRY,
)
node_capacity_gpu_cards = Gauge(
    "node_capacity_gpu_cards",
    "Total GPU capacity of the node (e.g., nvidia.com/gpu, amd.com/gpu)",
    NODE_LABELS,
    registry=NODE_REGISTRY,
)

# --- Metryki Zasobów Alokowalnych (Allocatable) ---
node_allocatable_cpu_cores = Gauge(
    "node_allocatable_cpu_cores",
    "Allocatable CPU resources of the node in cores",
    NODE_LABELS,
    registry=NODE_REGISTRY,
)
node_allocatable_memory_bytes = Gauge(
    "node_allocatable_memory_bytes",
    "Allocatable memory resources of the node in bytes",
    NODE_LABELS,
    registry=NODE_REGISTRY,
)
node_allocatable_pods = Gauge(
    "node_allocatable_pods",
    "Allocatable pod resources of the node",
    NODE_LABELS,
    registry=NODE_REGISTRY,
)
node_allocatable_gpu_cards = Gauge(
    "node_allocatable_gpu_cards",
    "Allocatable GPU resources of the node (e.g., nvidia.com/gpu, amd.com/gpu)",
    NODE_LABELS,
    registry=NODE_REGISTRY,
)

# --- Metryki Symulowanego Wykorzystania (Simulated Usage based on Pod Requests) ---
node_simulated_usage_cpu_cores = Gauge(
    "node_simulated_usage_cpu_cores",
    "Simulated CPU usage based on sum of pod requests in cores",
    NODE_LABELS,
    registry=NODE_REGISTRY,
)
node_simulated_usage_memory_bytes = Gauge(
    "node_simulated_usage_memory_bytes",
    "Simulated memory usage based on sum of pod requests in bytes",
    NODE_LABELS,
    registry=NODE_REGISTRY,
)
node_simulated_pod_count = Gauge(
    "node_simulated_pod_count",
    "Number of non-terminal pods scheduled on the node",
    NODE_LABELS,
    registry=NODE_REGISTRY,
)
node_simulated_usage_gpu_cards = Gauge(
    "node_simulated_usage_gpu_cards",
    "Simulated GPU usage based on sum of pod requests for known GPU types",
    NODE_LABELS,
    registry=NODE_REGISTRY,
)

# --- Metryka Statusu Węzła ---
node_status_ready = Gauge(
    "node_status_ready",
    "Readiness status of the node (1 if Ready, 0 otherwise)",
    NODE_LABELS,
    registry=NODE_REGISTRY,
)

# --- Metryka Nieschedulowanych Podów ---
cluster_unscheduled_pods_count = Gauge(
    "cluster_unscheduled_pods_count",
    "Number of pods in Pending phase without an assigned node",
    registry=NODE_REGISTRY,
)

# Zmienna globalna do przechowywania etykiet węzłów z poprzedniego cyklu
# Klucz: node_name, Wartość: słownik etykiet użyty dla tego węzła
previous_node_labels = {}

# --- Funkcje Pomocnicze ---


def parse_resource_quantity(quantity_str):
    """Parsuje string zasobu K8s (np. '10Gi', '500m', '1', '0.5') na wartość numeryczną.
    Zwraca:
    - float dla CPU (cores), także jeśli podano bez 'm' (np. '0.5')
    - int dla pamięci (bytes)
    - int dla innych (np. GPU, pods), jeśli podano jako liczba całkowita bez sufiksu.
    """
    if not quantity_str:
        return 0

    # Upewnij się, że to string, obsłuż przypadki gdy K8s API zwraca int/float
    quantity_str = str(quantity_str)

    # Memory Suffixes (Binary - Ki, Mi, Gi, Ti, Pi, Ei and Decimal - K, M, G, T, P, E)
    memory_multipliers = {
        "Ki": 1024,
        "Mi": 1024**2,
        "Gi": 1024**3,
        "Ti": 1024**4,
        "Pi": 1024**5,
        "Ei": 1024**6,
        "K": 1000,
        "M": 1000**2,
        "G": 1000**3,
        "T": 1000**4,
        "P": 1000**5,
        "E": 1000**6,
    }
    # CPU Suffix (milli)
    cpu_milli_match = re.match(r"^(\d+)m$", quantity_str)
    if cpu_milli_match:
        # Zawsze zwracaj float dla miliCPU
        return float(cpu_milli_match.group(1)) / 1000.0

    # Generic Suffix Match (obejmuje liczby całkowite i zmiennoprzecinkowe)
    # Grupa 1: Cała liczba (np. "10", "0.5")
    # Grupa 2: Opcjonalna część dziesiętna z kropką (np. ".5")
    # Grupa 3: Opcjonalny sufiks (np. "Gi", "K")
    match = re.match(r"^(\d+(\.\d+)?)([A-Za-z]+)?$", quantity_str)
    if not match:
        try:
            return int(quantity_str)
        except ValueError:
            logging.warning(f"Could not parse resource quantity: '{quantity_str}'")
            return 0

    value_str = match.group(1)
    decimal_part = match.group(2)
    suffix = match.group(3)

    try:
        value = float(value_str)
    except ValueError:
        logging.warning(
            f"Could not convert value part '{value_str}' to float in quantity '{quantity_str}'"
        )
        return 0

    if suffix:
        multiplier = memory_multipliers.get(suffix)
        if multiplier:
            return int(value * multiplier)
        else:
            logging.warning(
                f"Unknown resource suffix '{suffix}' in quantity '{quantity_str}'. Assuming integer count."
            )
            if decimal_part:
                logging.warning(
                    f"Returning float value {value} for quantity '{quantity_str}' with unknown suffix."
                )
                return value
            else:
                return int(value)

    else:
        if decimal_part:
            return value
        else:
            return int(value)


def get_node_labels(node_metadata):
    """Ekstrahuje niestandardowe etykiety topologii węzła."""
    labels = getattr(node_metadata, "labels", {}) or {}

    hostname = labels.get("kubernetes.io/hostname", "unknown")
    datacenter = labels.get("network.topology.kubernetes.io/datacenter", "unknown")
    spine = labels.get("network.topology.kubernetes.io/spine", "unknown")
    block = labels.get("network.topology.kubernetes.io/block", "unknown")

    return hostname, datacenter, spine, block


def is_kwok_node(node):
    """Sprawdza, czy węzeł jest zarządzany przez KWOK."""
    # Sprawdź etykietę 'type=kwok'
    labels = getattr(node.metadata, "labels", {}) or {}
    if labels.get("type") == "kwok":
        return True
    # Sprawdź providerID
    provider_id = getattr(node.spec, "provider_id", None)
    if provider_id and provider_id.startswith("kwok://"):
        return True
    return False


def get_node_status_ready(node):
    """Sprawdza status Ready węzła."""
    conditions = getattr(node.status, "conditions", []) or []
    for cond in conditions:
        if cond.type == "Ready":
            return 1 if cond.status == "True" else 0
    return 0  # Domyślnie nie gotowy, jeśli brakuje warunku


# --- Główna Pętla ---


def collect_node_metrics(
    core_v1_api: kubernetes.client.CoreV1Api,
):
    """Pobiera dane o węzłach i podach, oblicza i eksportuje metryki."""

    global previous_node_labels

    start_time_cycle = time.time()
    logging.info("Starting node resource metrics collection cycle...")

    nodes_list = []
    pods_list = []

    # --- Pobieranie Węzłów ---
    try:
        logging.info("Fetching Nodes...")
        # Użycie przekazanego klienta core_v1_api
        nodes_response = core_v1_api.list_node(watch=False, timeout_seconds=60)
        nodes_list = nodes_response.items
        logging.info(f"Fetched {len(nodes_list)} Nodes.")
    except kubernetes.client.ApiException as e:
        logging.error(f"API error fetching Nodes: {e.reason}", exc_info=True)
        # Jeśli nie można pobrać węzłów, dalsze przetwarzanie ma mały sens
        # Dodano sprawdzenie statusu dla potencjalnych problemów z autoryzacją/połączeniem
        if e.status == 401:
            logging.error(
                "Authorization error (401): Check RBAC permissions for the service account to list nodes."
            )
        elif e.status == 403:
            logging.error(
                "Forbidden error (403): Check RBAC permissions for the service account to list nodes."
            )
        return  # Krytyczny błąd, nie kontynuuj bez węzłów
    except Exception as e:
        logging.error(f"Unexpected error fetching Nodes: {e}", exc_info=True)
        return  # Nieoczekiwany błąd również uniemożliwia kontynuację

    # --- Identyfikacja węzłów KWOK ---
    kwok_node_names = set()
    for node in nodes_list:
        if is_kwok_node(node):
            node_name = getattr(node.metadata, "name", None)
            if node_name:
                kwok_node_names.add(node_name)
    logging.info(f"Identified {len(kwok_node_names)} KWOK nodes: {kwok_node_names}")

    # --- Pobieranie Podów ---
    try:
        logging.info("Fetching Pods (all namespaces, non-terminal)...")
        # Filtrujemy po stronie API, aby zmniejszyć ilość danych
        field_selector = (
            "status.phase!=Succeeded,status.phase!=Failed,status.phase!=Unknown"
        )
        pods_response = core_v1_api.list_pod_for_all_namespaces(
            watch=False,
            timeout_seconds=120,
            field_selector=field_selector,
        )
        pods_list = pods_response.items
        logging.info(
            f"Fetched {len(pods_list)} non-terminal Pods (including unscheduled)."
        )
    except kubernetes.client.ApiException as e:
        logging.error(f"API error fetching Pods: {e.reason}", exc_info=True)
        if e.status == 401:
            logging.error(
                "Authorization error (401): Check RBAC permissions for the service account to list pods."
            )
        elif e.status == 403:
            logging.error(
                "Forbidden error (403): Check RBAC permissions for the service account to list pods."
            )
        # Można kontynuować nawet bez podów, metryki użycia będą zerowe
    except Exception as e:
        logging.error(f"Unexpected error fetching Pods: {e}", exc_info=True)
        # Można kontynuować

    # --- Agregacja Żądań Podów ---
    node_simulated_requests = defaultdict(
        lambda: {"cpu": 0.0, "memory": 0, "gpu": 0, "pods": 0}
    )
    kindnet_requests_on_node = defaultdict(lambda: {"cpu": 0.0, "memory": 0})

    pod_count = 0
    unscheduled_pod_count = 0
    processed_infra_pods = 0

    for pod in pods_list:
        node_name = getattr(pod.spec, "node_name", None)
        pod_name = getattr(pod.metadata, "name", "")
        pod_namespace = getattr(pod.metadata, "namespace", "")

        # --- Sprawdzenie i pominięcie podów infra na węzłach KWOK ---
        is_infra_pod_on_kwok_node = False
        if node_name in kwok_node_names:
            if pod_namespace == "kube-system":
                if pod_name.startswith("kube-proxy-"):
                    logging.info(
                        f"[KWOK Node: {node_name}] Ignoring infra pod (kube-proxy): {pod_namespace}/{pod_name}"
                    )
                    is_infra_pod_on_kwok_node = True
                    processed_infra_pods += 1
                elif pod_name.startswith("kindnet-"):
                    logging.info(
                        f"[KWOK Node: {node_name}] Ignoring infra pod (kindnet): {pod_namespace}/{pod_name}"
                    )
                    is_infra_pod_on_kwok_node = True
                    processed_infra_pods += 1
                    # Zapisz żądania kindnet tylko jeśli jest na węźle KWOK
                    kindnet_cpu_req = 0.0
                    kindnet_mem_req = 0
                    all_containers = (getattr(pod.spec, "containers", []) or []) + (
                        getattr(pod.spec, "init_containers", []) or []
                    )
                    for container in all_containers:
                        requests = getattr(container.resources, "requests", None) or {}
                        kindnet_cpu_req += parse_resource_quantity(
                            requests.get("cpu", "0")
                        )
                        kindnet_mem_req += parse_resource_quantity(
                            requests.get("memory", "0")
                        )

                    # Zapisz żądania tylko dla węzła KWOK
                    kindnet_requests_on_node[node_name]["cpu"] += kindnet_cpu_req
                    kindnet_requests_on_node[node_name]["memory"] += kindnet_mem_req
                    logging.info(
                        f"[KWOK Node: {node_name}] Recorded kindnet requests: CPU={kindnet_cpu_req}, Mem={kindnet_mem_req}. Total for node now: {kindnet_requests_on_node[node_name]}"  # Dodano kontekst węzła
                    )

        if is_infra_pod_on_kwok_node:
            continue

        if not node_name:
            unscheduled_pod_count += 1
            continue

        node_simulated_requests[node_name]["pods"] += 1
        pod_count += 1

        containers = getattr(pod.spec, "containers", []) or []
        init_containers = getattr(pod.spec, "init_containers", []) or []

        # --- Obliczanie efektywnych żądań dla Poda ---
        pod_effective_cpu_request = 0.0
        pod_effective_memory_request = 0
        pod_effective_gpu_request = 0

        # 1. Oblicz sumę żądań dla głównych kontenerów
        regular_containers_cpu_sum = 0.0
        regular_containers_memory_sum = 0
        regular_containers_gpu_sum = 0
        for container in containers:
            requests = getattr(container.resources, "requests", None) or {}
            if requests:
                regular_containers_cpu_sum += parse_resource_quantity(
                    requests.get("cpu", "0")
                )
                regular_containers_memory_sum += parse_resource_quantity(
                    requests.get("memory", "0")
                )
                gpu_req_str = "0"
                for gpu_key in KNOWN_GPU_KEYS:
                    _req = requests.get(gpu_key)
                    if _req and _req != "0":
                        gpu_req_str = _req
                        break
                regular_containers_gpu_sum += parse_resource_quantity(gpu_req_str)

        # 2. Znajdź maksymalne żądanie wśród init-kontenerów
        max_init_container_cpu = 0.0
        max_init_container_memory = 0
        max_init_container_gpu = 0
        for container in init_containers:
            requests = getattr(container.resources, "requests", None) or {}
            if requests:
                current_init_cpu = parse_resource_quantity(requests.get("cpu", "0"))
                current_init_memory = parse_resource_quantity(
                    requests.get("memory", "0")
                )

                current_init_gpu = 0
                gpu_req_str = "0"
                for gpu_key in KNOWN_GPU_KEYS:
                    _req = requests.get(gpu_key)
                    if _req and _req != "0":
                        gpu_req_str = _req
                        break
                current_init_gpu = parse_resource_quantity(gpu_req_str)

                max_init_container_cpu = max(max_init_container_cpu, current_init_cpu)
                max_init_container_memory = max(
                    max_init_container_memory, current_init_memory
                )
                max_init_container_gpu = max(max_init_container_gpu, current_init_gpu)

        # 3. Oblicz efektywne żądanie dla Poda jako maximum(suma_glownych, max_init)
        pod_effective_cpu_request = max(
            regular_containers_cpu_sum, max_init_container_cpu
        )
        pod_effective_memory_request = max(
            regular_containers_memory_sum, max_init_container_memory
        )
        pod_effective_gpu_request = max(
            regular_containers_gpu_sum, max_init_container_gpu
        )

        # --- Dodaj efektywne żądania Poda do sumy dla węzła ---
        node_simulated_requests[node_name]["cpu"] += pod_effective_cpu_request
        node_simulated_requests[node_name]["memory"] += pod_effective_memory_request
        node_simulated_requests[node_name]["gpu"] += pod_effective_gpu_request
        # ----------------------------------------------------------

    logging.info(
        f"Aggregated EFFECTIVE pod requests for {len(node_simulated_requests)} nodes "
        f"from {pod_count} scheduled non-infrastructure pods."
        f" Ignored {processed_infra_pods} infrastructure pods (kube-proxy/kindnet)."
    )
    logging.info(f"Found {unscheduled_pod_count} unscheduled (Pending, no node) pods.")

    current_node_labels = {}
    processed_node_names_current_cycle = set()

    for node in nodes_list:
        node_name = getattr(node.metadata, "name", None)
        if not node_name:
            logging.warning("Found node without a name, skipping.")
            continue

        processed_node_names_current_cycle.add(node_name)
        log_prefix = f"[Node: {node_name}]"
        logging.info(f"{log_prefix} Processing...")

        hostname, datacenter, spine, block = get_node_labels(node.metadata)
        is_kwok = is_kwok_node(node)
        labels = {
            "node_name": node_name,
            "hostname": hostname,
            "datacenter": datacenter,
            "spine": spine,
            "block": block,
            "is_kwok": str(is_kwok).lower(),
        }
        current_node_labels[node_name] = labels

        ready_status = get_node_status_ready(node)
        node_status_ready.labels(**labels).set(ready_status)
        logging.info(f"{log_prefix} Status Ready: {ready_status}")

        capacity = getattr(node.status, "capacity", {}) or {}
        original_cap_cpu = parse_resource_quantity(capacity.get("cpu", "0"))
        original_cap_mem = parse_resource_quantity(capacity.get("memory", "0"))
        cap_pods = parse_resource_quantity(capacity.get("pods", "0"))

        cap_gpu_str = "0"
        found_gpu_key = None
        for gpu_key in KNOWN_GPU_KEYS:
            _cap = capacity.get(gpu_key)
            if _cap is not None:
                cap_gpu_str = _cap
                found_gpu_key = gpu_key
                break
        cap_gpu = parse_resource_quantity(cap_gpu_str)

        report_cap_cpu = original_cap_cpu
        report_cap_mem = original_cap_mem
        report_cap_pods = cap_pods
        report_cap_gpu = cap_gpu

        is_current_node_kwok = node_name in kwok_node_names
        if is_current_node_kwok:
            kindnet_reqs = kindnet_requests_on_node.get(
                node_name,
                {"cpu": 0.0, "memory": 0},
            )
            cpu_to_subtract = kindnet_reqs["cpu"]
            mem_to_subtract = kindnet_reqs["memory"]

            adjusted_cap_cpu = max(0.0, original_cap_cpu - cpu_to_subtract)
            adjusted_cap_mem = max(0, original_cap_mem - mem_to_subtract)

            report_cap_cpu = adjusted_cap_cpu
            report_cap_mem = adjusted_cap_mem

            logging.info(
                f"{log_prefix} Capacity (Original from K8s API) - CPU: {original_cap_cpu}, Mem: {original_cap_mem}, Pods: {report_cap_pods}"
            )
            if cpu_to_subtract > 0 or mem_to_subtract > 0:
                logging.info(
                    f"{log_prefix} [KWOK Node] Subtracting Kindnet requests from Capacity - CPU: {cpu_to_subtract}, Mem: {mem_to_subtract}"
                )
        # else: # Dla węzłów nie-KWOK nie robimy nic, używamy oryginalnych wartości

        node_capacity_cpu_cores.labels(**labels).set(report_cap_cpu)
        node_capacity_memory_bytes.labels(**labels).set(report_cap_mem)
        node_capacity_pods.labels(**labels).set(report_cap_pods)
        node_capacity_gpu_cards.labels(**labels).set(report_cap_gpu)

        logging.info(
            f"{log_prefix} Capacity (Reported by exporter{' - Adjusted for Kindnet' if is_current_node_kwok and (cpu_to_subtract > 0 or mem_to_subtract > 0) else ''}) "
            f"- CPU: {report_cap_cpu}, Mem: {report_cap_mem}, Pods: {report_cap_pods}, GPU ({found_gpu_key or 'none'}): {report_cap_gpu}"
        )

        allocatable = getattr(node.status, "allocatable", {}) or {}
        original_alloc_cpu = parse_resource_quantity(allocatable.get("cpu", "0"))
        original_alloc_mem = parse_resource_quantity(allocatable.get("memory", "0"))
        original_alloc_pods = parse_resource_quantity(allocatable.get("pods", "0"))

        alloc_gpu_str = "0"
        found_alloc_gpu_key = None
        for gpu_key in KNOWN_GPU_KEYS:
            _alloc = allocatable.get(gpu_key)
            if _alloc is not None:
                alloc_gpu_str = _alloc
                found_alloc_gpu_key = gpu_key
                break
        alloc_gpu = parse_resource_quantity(alloc_gpu_str)

        report_alloc_cpu = original_alloc_cpu
        report_alloc_mem = original_alloc_mem
        report_alloc_pods = original_alloc_pods
        report_alloc_gpu = alloc_gpu

        if is_current_node_kwok:
            kindnet_reqs = kindnet_requests_on_node.get(
                node_name, {"cpu": 0.0, "memory": 0}
            )
            cpu_to_subtract = kindnet_reqs["cpu"]
            mem_to_subtract = kindnet_reqs["memory"]

            adjusted_alloc_cpu = max(0.0, original_alloc_cpu - cpu_to_subtract)
            adjusted_alloc_mem = max(0, original_alloc_mem - mem_to_subtract)

            report_alloc_cpu = adjusted_alloc_cpu
            report_alloc_mem = adjusted_alloc_mem

            logging.info(
                f"{log_prefix} Allocatable (Original from K8s API) - CPU: {original_alloc_cpu}, Mem: {original_alloc_mem}, Pods: {report_alloc_pods}"
            )
            if cpu_to_subtract > 0 or mem_to_subtract > 0:
                logging.info(
                    f"{log_prefix} [KWOK Node] Subtracting Kindnet requests from Allocatable - CPU: {cpu_to_subtract}, Mem: {mem_to_subtract}"
                )
        # else: # Dla węzłów nie-KWOK nie robimy nic, używamy oryginalnych wartości

        node_allocatable_cpu_cores.labels(**labels).set(report_alloc_cpu)
        node_allocatable_memory_bytes.labels(**labels).set(report_alloc_mem)
        node_allocatable_pods.labels(**labels).set(report_alloc_pods)
        node_allocatable_gpu_cards.labels(**labels).set(report_alloc_gpu)

        logging.info(
            f"{log_prefix} Allocatable (Reported by exporter{' - Adjusted for Kindnet' if is_current_node_kwok and (cpu_to_subtract > 0 or mem_to_subtract > 0) else ''}) "
            f"- CPU: {report_alloc_cpu}, Mem: {report_alloc_mem}, Pods: {report_alloc_pods}, GPU ({found_alloc_gpu_key or 'none'}): {report_alloc_gpu}"
        )

        sim_usage = node_simulated_requests.get(
            node_name, {"cpu": 0.0, "memory": 0, "gpu": 0, "pods": 0}
        )
        node_simulated_usage_cpu_cores.labels(**labels).set(sim_usage["cpu"])
        node_simulated_usage_memory_bytes.labels(**labels).set(sim_usage["memory"])
        node_simulated_usage_gpu_cards.labels(**labels).set(sim_usage["gpu"])
        node_simulated_pod_count.labels(**labels).set(sim_usage["pods"])

        logging.info(
            f"{log_prefix} Simulated Usage ({'non-infra pods only' if is_current_node_kwok else 'all non-terminal pods'}) "
            f"- CPU: {sim_usage['cpu']}, Mem: {sim_usage['memory']}, GPU: {sim_usage['gpu']}, Pods: {sim_usage['pods']}"
        )

        logging.info(f"{log_prefix} Processing finished.")

    # --- Ustaw Metrykę Nieschedulowanych Podów ---
    cluster_unscheduled_pods_count.set(unscheduled_pod_count)

    # --- Czyszczenie Starych Metryk ---
    logging.info("Starting cleanup of metrics for removed nodes...")
    previous_nodes = set(previous_node_labels.keys())
    current_nodes = set(current_node_labels.keys())
    removed_node_names = previous_nodes - current_nodes

    if removed_node_names:
        logging.info(
            f"Found {len(removed_node_names)} nodes to remove metrics for: {removed_node_names}"
        )
        for node_name in removed_node_names:
            labels_to_remove = previous_node_labels.get(node_name)
            if labels_to_remove:
                try:
                    label_values_in_order = [
                        labels_to_remove[label_key] for label_key in NODE_LABELS
                    ]
                except KeyError as e:
                    logging.error(
                        f"Inconsistency detected: Label key '{e}' from NODE_LABELS not found in stored labels for node {node_name}. Skipping removal for this node. Stored labels: {labels_to_remove}"
                    )
                    continue

                try:
                    logging.info(
                        f"Removing metrics for node: {node_name} with label values (in order): {label_values_in_order}"
                    )
                    # Usuń wszystkie metryki dla tego zestawu wartości etykiet
                    node_capacity_cpu_cores.remove(*label_values_in_order)
                    node_capacity_memory_bytes.remove(*label_values_in_order)
                    node_capacity_pods.remove(*label_values_in_order)
                    node_capacity_gpu_cards.remove(*label_values_in_order)
                    node_allocatable_cpu_cores.remove(*label_values_in_order)
                    node_allocatable_memory_bytes.remove(*label_values_in_order)
                    node_allocatable_pods.remove(*label_values_in_order)
                    node_allocatable_gpu_cards.remove(*label_values_in_order)
                    node_simulated_usage_cpu_cores.remove(*label_values_in_order)
                    node_simulated_usage_memory_bytes.remove(*label_values_in_order)
                    node_simulated_pod_count.remove(*label_values_in_order)
                    node_simulated_usage_gpu_cards.remove(*label_values_in_order)
                    node_status_ready.remove(*label_values_in_order)
                    logging.info(f"Successfully removed metrics for node: {node_name}")
                except KeyError:
                    logging.warning(
                        f"Tried to remove metrics for node {node_name}, but the specific label combination was not found in the registry (or already removed). Label values: {label_values_in_order}"
                    )
                except Exception as e:
                    logging.error(
                        f"Error removing metrics for node {node_name} with label values {label_values_in_order}: {e}",
                        exc_info=True,
                    )
            else:
                logging.warning(
                    f"Node name {node_name} was marked for removal, but its labels were not found in previous_node_labels."
                )
    else:
        logging.info("No nodes found for metric cleanup in this cycle.")

    # --- Aktualizacja Stanu na Następny Cykl ---
    previous_node_labels = current_node_labels

    end_time_cycle = time.time()
    duration_cycle = end_time_cycle - start_time_cycle
    logging.info(
        f"Node resource metrics collection cycle finished. Processed {len(processed_node_names_current_cycle)} nodes. Cycle duration: {duration_cycle:.2f}s"
    )


if __name__ == "__main__":
    logging.info(f"Starting Node Resource Exporter on port {LISTEN_PORT}")
    logging.info(f"Scrape interval recommendation: {SCRAPE_INTERVAL} seconds or more")
    # --- Inicjalizacja Klienta K8s (Tylko raz) ---
    try:
        try:
            logging.info("Attempting to load incluster config...")
            kubernetes.config.load_incluster_config()
            logging.info("Using incluster Kubernetes config.")
        except kubernetes.config.ConfigException:
            logging.info("Incluster config failed, trying kube config...")
            kubernetes.config.load_kube_config()
            logging.info("Using kube config.")

        # Tworzenie instancji klienta API
        core_v1_api = kubernetes.client.CoreV1Api()

        logging.info("Kubernetes client initialized successfully.")

    except Exception as e:
        logging.error(
            f"FATAL: Failed to initialize Kubernetes client: {e}", exc_info=True
        )
        # Zakończ działanie, jeśli klient nie może zostać zainicjalizowany
        import sys

        sys.exit(1)

    # --- Start serwera HTTP ---
    # Użyj dedykowanej registry dla serwera HTTP
    start_http_server(LISTEN_PORT, registry=NODE_REGISTRY)
    logging.info("HTTP server started.")

    # --- Główna pętla ---
    while True:
        collect_node_metrics(core_v1_api)
        time.sleep(SCRAPE_INTERVAL)

import os
import time
import logging
import re
from collections import defaultdict
from prometheus_client import start_http_server, Gauge, CollectorRegistry
import kubernetes
import kubernetes.client
import kubernetes.config

# --- Konfiguracja ---
LISTEN_PORT = int(os.environ.get('LISTEN_PORT', 8001)) # Inny port niż unified-job-exporter
SCRAPE_INTERVAL = int(os.environ.get('SCRAPE_INTERVAL', 15)) # Zwiększony interwał może być lepszy dla node/pod
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Definicje Metryk ---
# Użyj nowej, dedykowanej registry
NODE_REGISTRY = CollectorRegistry()
NODE_LABELS = ['node_name', 'instance_type', 'zone', 'region', 'is_kwok'] # Dodatkowe etykiety węzła

# --- Metryki Pojemności (Capacity) ---
node_capacity_cpu_cores = Gauge(
    'node_capacity_cpu_cores', 'Total CPU capacity of the node in cores', NODE_LABELS, registry=NODE_REGISTRY
)
node_capacity_memory_bytes = Gauge(
    'node_capacity_memory_bytes', 'Total memory capacity of the node in bytes', NODE_LABELS, registry=NODE_REGISTRY
)
node_capacity_pods = Gauge(
    'node_capacity_pods', 'Total pod capacity of the node', NODE_LABELS, registry=NODE_REGISTRY
)
node_capacity_gpu_cards = Gauge(
    'node_capacity_gpu_cards', 'Total GPU capacity of the node (nvidia.com/gpu)', NODE_LABELS, registry=NODE_REGISTRY
)

# --- Metryki Zasobów Alokowalnych (Allocatable) ---
node_allocatable_cpu_cores = Gauge(
    'node_allocatable_cpu_cores', 'Allocatable CPU resources of the node in cores', NODE_LABELS, registry=NODE_REGISTRY
)
node_allocatable_memory_bytes = Gauge(
    'node_allocatable_memory_bytes', 'Allocatable memory resources of the node in bytes', NODE_LABELS, registry=NODE_REGISTRY
)
node_allocatable_pods = Gauge(
    'node_allocatable_pods', 'Allocatable pod resources of the node', NODE_LABELS, registry=NODE_REGISTRY
)
node_allocatable_gpu_cards = Gauge(
    'node_allocatable_gpu_cards', 'Allocatable GPU resources of the node (nvidia.com/gpu)', NODE_LABELS, registry=NODE_REGISTRY
)

# --- Metryki Symulowanego Wykorzystania (Simulated Usage based on Pod Requests) ---
node_simulated_usage_cpu_cores = Gauge(
    'node_simulated_usage_cpu_cores', 'Simulated CPU usage based on sum of pod requests in cores', NODE_LABELS, registry=NODE_REGISTRY
)
node_simulated_usage_memory_bytes = Gauge(
    'node_simulated_usage_memory_bytes', 'Simulated memory usage based on sum of pod requests in bytes', NODE_LABELS, registry=NODE_REGISTRY
)
node_simulated_pod_count = Gauge(
    'node_simulated_pod_count', 'Number of non-terminal pods scheduled on the node', NODE_LABELS, registry=NODE_REGISTRY
)
node_simulated_usage_gpu_cards = Gauge(
    'node_simulated_usage_gpu_cards', 'Simulated GPU usage based on sum of pod requests (nvidia.com/gpu)', NODE_LABELS, registry=NODE_REGISTRY
)

# --- Metryka Statusu Węzła ---
node_status_ready = Gauge(
    'node_status_ready', 'Readiness status of the node (1 if Ready, 0 otherwise)', NODE_LABELS, registry=NODE_REGISTRY
)

# --- Funkcje Pomocnicze ---

def parse_resource_quantity(quantity_str):
    """Parsuje string zasobu K8s (np. '10Gi', '500m', '1') na wartość numeryczną.
       Zwraca:
       - float dla CPU (cores)
       - int dla pamięci (bytes)
       - int dla innych (np. GPU, pods)
    """
    if not quantity_str:
        return 0

    quantity_str = str(quantity_str) # Upewnij się, że to string

    # Memory Suffixes (Binary - Ki, Mi, Gi, Ti, Pi, Ei)
    memory_multipliers = {
        'Ki': 1024, 'Mi': 1024**2, 'Gi': 1024**3, 'Ti': 1024**4, 'Pi': 1024**5, 'Ei': 1024**6,
        'K': 1000, 'M': 1000**2, 'G': 1000**3, 'T': 1000**4, 'P': 1000**5, 'E': 1000**6 # Decimal (mniej typowe dla mem, ale dla spójności)
    }
    # CPU Suffix (milli)
    cpu_milli_match = re.match(r'^(\d+)m$', quantity_str)
    if cpu_milli_match:
        return float(cpu_milli_match.group(1)) / 1000.0

    # Generic Suffix Match
    match = re.match(r'^(\d+(\.\d+)?)([A-Za-z]+)?$', quantity_str)
    if not match:
        logging.warning(f"Could not parse resource quantity: '{quantity_str}'")
        return 0

    value = float(match.group(1))
    suffix = match.group(3)

    if suffix:
        multiplier = memory_multipliers.get(suffix)
        if multiplier:
            # Memory or Decimal unit - treat as integer bytes
            return int(value * multiplier)
        else:
            logging.warning(f"Unknown resource suffix '{suffix}' in quantity '{quantity_str}'")
            # Treat as plain integer if suffix is unknown but value exists (e.g., GPU count '1')
            return int(value)
    else:
        # No suffix - likely CPU core count, GPU count, or Pod count
        return int(value)


def get_node_labels(node_metadata):
    """Ekstrahuje standardowe etykiety węzła."""
    labels = getattr(node_metadata, 'labels', {}) or {} # Handle None
    # Standardowe etykiety topologii (mogą nie istnieć)
    instance_type = labels.get('node.kubernetes.io/instance-type', 'unknown')
    zone = labels.get('topology.kubernetes.io/zone', 'unknown')
    region = labels.get('topology.kubernetes.io/region', 'unknown')
    return instance_type, zone, region

def is_kwok_node(node):
    """Sprawdza, czy węzeł jest zarządzany przez KWOK."""
    # Sprawdź etykietę 'type=kwok'
    labels = getattr(node.metadata, 'labels', {}) or {}
    if labels.get('type') == 'kwok':
        return True
    # Sprawdź providerID
    provider_id = getattr(node.spec, 'provider_id', None)
    if provider_id and provider_id.startswith('kwok://'):
        return True
    return False

def get_node_status_ready(node):
    """Sprawdza status Ready węzła."""
    conditions = getattr(node.status, 'conditions', []) or []
    for cond in conditions:
        if cond.type == 'Ready':
            return 1 if cond.status == 'True' else 0
    return 0 # Domyślnie nie gotowy, jeśli brakuje warunku

# --- Główna Pętla ---

def collect_node_metrics():
    """Pobiera dane o węzłach i podach, oblicza i eksportuje metryki."""
    start_time_cycle = time.time()
    logging.info("Starting node resource metrics collection cycle...")

    api_clients = {}
    nodes_list = []
    pods_list = []

    try:
        # --- Konfiguracja Klienta K8s ---
        try:
            kubernetes.config.load_incluster_config()
            logging.debug("Using incluster config.")
        except kubernetes.config.ConfigException:
            kubernetes.config.load_kube_config()
            logging.debug("Using kube config.")

        api_clients['core_v1'] = kubernetes.client.CoreV1Api()
        logging.debug("Successfully created Kubernetes CoreV1Api client.")

        # --- Pobieranie Węzłów ---
        try:
            logging.debug("Fetching Nodes...")
            nodes_response = api_clients['core_v1'].list_node(watch=False, timeout_seconds=60)
            nodes_list = nodes_response.items
            logging.info(f"Fetched {len(nodes_list)} Nodes.")
        except kubernetes.client.ApiException as e:
            logging.error(f"API error fetching Nodes: {e.reason}", exc_info=True)
            return # Krytyczny błąd, nie kontynuuj bez węzłów
        except Exception as e:
             logging.error(f"Unexpected error fetching Nodes: {e}", exc_info=True)
             return

        # --- Pobieranie Podów (tylko te, które mają przypisany węzeł i nie są zakończone) ---
        try:
            logging.debug("Fetching Pods (all namespaces, with nodeName, non-terminal)...")
            # Filtrujemy po stronie API, aby zmniejszyć ilość danych
            field_selector = 'spec.nodeName!="",status.phase!=Succeeded,status.phase!=Failed,status.phase!=Unknown'
            pods_response = api_clients['core_v1'].list_pod_for_all_namespaces(
                watch=False,
                timeout_seconds=120, # Daj więcej czasu na pobranie podów
                field_selector=field_selector
            )
            pods_list = pods_response.items
            logging.info(f"Fetched {len(pods_list)} non-terminal Pods with assigned nodes.")
        except kubernetes.client.ApiException as e:
            logging.error(f"API error fetching Pods: {e.reason}", exc_info=True)
            # Można kontynuować, ale metryki użycia będą zerowe
        except Exception as e:
             logging.error(f"Unexpected error fetching Pods: {e}", exc_info=True)
             # Można kontynuować

    except Exception as e:
        logging.error(f"Error initializing Kubernetes client: {e}", exc_info=True)
        return

    # --- Agregacja Żądań Podów ---
    node_simulated_requests = defaultdict(lambda: {'cpu': 0.0, 'memory': 0, 'gpu': 0, 'pods': 0})
    pod_count = 0
    for pod in pods_list:
        node_name = getattr(pod.spec, 'node_name', None)
        pod_phase = getattr(pod.status, 'phase', 'Unknown')

        if not node_name:
            continue # Pomiń pody bez przypisanego węzła (nie powinno się zdarzyć z field_selector, ale dla pewności)

        # Zlicz pod
        node_simulated_requests[node_name]['pods'] += 1
        pod_count += 1

        # Sumuj żądania kontenerów
        containers = getattr(pod.spec, 'containers', []) or []
        init_containers = getattr(pod.spec, 'init_containers', []) or [] # Uwzględnij init containery

        for container in containers + init_containers:
            requests = getattr(container.resources, 'requests', None) or {}
            if requests:
                node_simulated_requests[node_name]['cpu'] += parse_resource_quantity(requests.get('cpu', '0'))
                node_simulated_requests[node_name]['memory'] += parse_resource_quantity(requests.get('memory', '0'))
                # Sprawdź różne nazwy GPU (najczęściej nvidia.com/gpu)
                gpu_req = requests.get('nvidia.com/gpu', '0') # Najpierw standardowa
                if gpu_req == '0':
                    gpu_req = requests.get('amd.com/gpu', '0') # Potem AMD
                    if gpu_req == '0':
                         # Sprawdź inne potencjalne, jeśli potrzebujesz
                         pass
                node_simulated_requests[node_name]['gpu'] += parse_resource_quantity(gpu_req)

    logging.debug(f"Aggregated pod requests for {len(node_simulated_requests)} nodes from {pod_count} pods.")

    # --- Eksport Metryk dla Każdego Węzła ---
    processed_node_names = set()
    for node in nodes_list:
        node_name = getattr(node.metadata, 'name', None)
        if not node_name:
            logging.warning("Found node without a name, skipping.")
            continue

        processed_node_names.add(node_name)
        log_prefix = f"[Node: {node_name}]"
        logging.debug(f"{log_prefix} Processing...")

        # Etykiety
        instance_type, zone, region = get_node_labels(node.metadata)
        is_kwok = is_kwok_node(node)
        labels = {
            'node_name': node_name,
            'instance_type': instance_type,
            'zone': zone,
            'region': region,
            'is_kwok': str(is_kwok).lower() # Prometheus preferuje stringi dla bool
        }

        # Status
        ready_status = get_node_status_ready(node)
        node_status_ready.labels(**labels).set(ready_status)
        logging.debug(f"{log_prefix} Status Ready: {ready_status}")

        # Capacity
        capacity = getattr(node.status, 'capacity', {}) or {}
        cap_cpu = parse_resource_quantity(capacity.get('cpu'))
        cap_mem = parse_resource_quantity(capacity.get('memory'))
        cap_pods = parse_resource_quantity(capacity.get('pods'))
        cap_gpu = parse_resource_quantity(capacity.get('nvidia.com/gpu', '0')) # Uwzględnij inne, jeśli trzeba
        node_capacity_cpu_cores.labels(**labels).set(cap_cpu)
        node_capacity_memory_bytes.labels(**labels).set(cap_mem)
        node_capacity_pods.labels(**labels).set(cap_pods)
        node_capacity_gpu_cards.labels(**labels).set(cap_gpu)
        logging.debug(f"{log_prefix} Capacity - CPU: {cap_cpu}, Mem: {cap_mem}, Pods: {cap_pods}, GPU: {cap_gpu}")


        # Allocatable
        allocatable = getattr(node.status, 'allocatable', {}) or {}
        alloc_cpu = parse_resource_quantity(allocatable.get('cpu'))
        alloc_mem = parse_resource_quantity(allocatable.get('memory'))
        alloc_pods = parse_resource_quantity(allocatable.get('pods'))
        alloc_gpu = parse_resource_quantity(allocatable.get('nvidia.com/gpu', '0'))
        node_allocatable_cpu_cores.labels(**labels).set(alloc_cpu)
        node_allocatable_memory_bytes.labels(**labels).set(alloc_mem)
        node_allocatable_pods.labels(**labels).set(alloc_pods)
        node_allocatable_gpu_cards.labels(**labels).set(alloc_gpu)
        logging.debug(f"{log_prefix} Allocatable - CPU: {alloc_cpu}, Mem: {alloc_mem}, Pods: {alloc_pods}, GPU: {alloc_gpu}")


        # Simulated Usage (z zagregowanych żądań podów)
        sim_usage = node_simulated_requests.get(node_name, {'cpu': 0.0, 'memory': 0, 'gpu': 0, 'pods': 0})
        node_simulated_usage_cpu_cores.labels(**labels).set(sim_usage['cpu'])
        node_simulated_usage_memory_bytes.labels(**labels).set(sim_usage['memory'])
        node_simulated_usage_gpu_cards.labels(**labels).set(sim_usage['gpu'])
        node_simulated_pod_count.labels(**labels).set(sim_usage['pods'])
        logging.debug(f"{log_prefix} Simulated Usage - CPU: {sim_usage['cpu']}, Mem: {sim_usage['memory']}, GPU: {sim_usage['gpu']}, Pods: {sim_usage['pods']}")

        logging.debug(f"{log_prefix} Processing finished.")

    # --- Czyszczenie starych metryk (opcjonalne, Prometheus radzi sobie ze stalesnością Gauges) ---
    # Można by porównać processed_node_names z poprzednim cyklem i usunąć metryki dla znikniętych węzłów
    # node_capacity_cpu_cores.clear() # Przykład - czyści wszystkie metryki tego typu! Używać ostrożnie.
    # Lepsze jest usuwanie konkretnych labelsetów, ale wymaga śledzenia stanu.
    # Na razie polegamy na Prometheusie.

    end_time_cycle = time.time()
    duration_cycle = end_time_cycle - start_time_cycle
    logging.info(f"Node resource metrics collection cycle finished. Processed {len(processed_node_names)} nodes. Cycle duration: {duration_cycle:.2f}s")


if __name__ == '__main__':
    logging.info(f"Starting Node Resource Exporter on port {LISTEN_PORT}")
    logging.info(f"Scrape interval recommendation: {SCRAPE_INTERVAL} seconds or more")

    # Użyj dedykowanej registry dla serwera HTTP
    start_http_server(LISTEN_PORT, registry=NODE_REGISTRY)
    logging.info("HTTP server started.")

    while True:
        collect_node_metrics()
        time.sleep(SCRAPE_INTERVAL)

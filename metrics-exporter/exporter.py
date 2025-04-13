import logging
import os
import time
from datetime import datetime, timezone

import kubernetes
import kubernetes.client
from dateutil.parser import isoparse
from prometheus_client import (
    REGISTRY,
    CollectorRegistry,
    Gauge,
    Histogram,
    start_http_server,
)

# --- Konfiguracja ---
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", 8000))
SCRAPE_INTERVAL = int(os.environ.get("SCRAPE_INTERVAL", 10))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG")
TARGET_NAMESPACE = os.environ.get("TARGET_NAMESPACE", None)

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Globalne Zmienne ---
volcano_start_times_cache = {}
previously_exported_completion_metrics = {}
observed_wait_times_uids = set()
observed_executiontotal_durations_uids = set()

# --- Definicje Metryk ---
REGISTRY = CollectorRegistry()
LABELS = ["job_name", "namespace", "uid", "job_kind", "queue"]
COMPLETION_LABELS = LABELS + ["status"]

unified_job_created_timestamp_seconds = Gauge(
    "unified_job_created_timestamp_seconds",
    "Timestamp when the Job (K8s or Volcano) was created",
    LABELS,
    registry=REGISTRY,
)
unified_job_start_timestamp_seconds = Gauge(
    "unified_job_start_timestamp_seconds",
    "Timestamp when the Job first started running",
    LABELS,
    registry=REGISTRY,
)
unified_job_completion_timestamp_seconds = Gauge(
    "unified_job_completion_timestamp_seconds",
    "Timestamp when the Job completed or failed",
    COMPLETION_LABELS,
    registry=REGISTRY,
)
unified_job_wait_duration_seconds = Gauge(
    "unified_job_wait_duration_seconds",
    "Time duration between creation and start of the job in seconds",
    LABELS,
    registry=REGISTRY,
)
unified_job_execution_duration_seconds = Gauge(
    "unified_job_execution_duration_seconds",
    "Time duration between start and completion/failure of the job in seconds",
    COMPLETION_LABELS,
    registry=REGISTRY,
)
unified_job_total_duration_seconds = Gauge(
    "unified_job_total_duration_seconds",
    "Time duration between creation and completion/failure of the job in seconds",
    COMPLETION_LABELS,
    registry=REGISTRY,
)
JOB_STATUS_MAP = {
    "Pending": 0,
    "Running": 1,
    "Succeeded": 2,
    "Failed": 3,
    "Completed": 2,
    "Terminating": 4,
    "Terminated": 5,
    "Aborting": 6,
    "Aborted": 7,
    "Unknown": -1,
}
unified_job_status_phase = Gauge(
    "unified_job_status_phase",
    "Current phase of the Job (Pending=0, Running=1, Succeeded=2, Failed=3, ...)",
    LABELS,
    registry=REGISTRY,
)

WAIT_DURATION_BUCKETS = [
    0.1,
    1.0,
    5.0,
    15.0,
    30.0,
    60.0,
    120.0,
    300.0,
    600.0,
    1800.0,
    3600.0,
    float("inf"),
]

unified_job_wait_duration_seconds_histogram = Histogram(
    "unified_job_wait_duration_seconds_histogram",
    "Histogram of time duration between creation and start of the job in seconds",
    ["job_kind"],
    registry=REGISTRY,
    buckets=WAIT_DURATION_BUCKETS,
)

DURATION_BUCKETS = [
    0.1,
    1.0,
    5.0,
    15.0,
    30.0,
    60.0,
    120.0,
    300.0,
    600.0,
    1800.0,
    3600.0,
    float("inf"),
]

unified_job_execution_duration_seconds_histogram = Histogram(
    "unified_job_execution_duration_seconds_histogram",
    "Histogram of time duration between start and completion/failure of the job in seconds",
    ["job_kind", "status"],
    registry=REGISTRY,
    buckets=DURATION_BUCKETS,
)

unified_job_total_duration_seconds_histogram = Histogram(
    "unified_job_total_duration_seconds_histogram",
    "Histogram of time duration between creation and completion/failure of the job in seconds",
    ["job_kind", "status"],
    registry=REGISTRY,
    buckets=DURATION_BUCKETS,
)


# --- Funkcje Pomocnicze ---
def parse_timestamp(ts_input):
    """Parsuje timestamp (string ISO 8601 lub obiekt datetime) do obiektu datetime."""
    if ts_input is None:
        return None
    if isinstance(ts_input, datetime):
        if ts_input.tzinfo is None:
            return ts_input.replace(tzinfo=timezone.utc)
        return ts_input
    if isinstance(ts_input, str):
        try:
            dt = isoparse(ts_input)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            logging.warning(
                f"Could not parse timestamp string: {ts_input}", exc_info=False
            )
            return None
    logging.warning(f"Unexpected timestamp type: {type(ts_input)}")
    return None


def get_k8s_job_final_status(conditions):
    """Określa status końcowy (Succeeded/Failed) i czas dla standardowego Joba."""
    if not conditions or not isinstance(conditions, list):
        return None, None

    completion_time_dt = None
    final_status = None
    # Filtruj tylko poprawne obiekty condition
    valid_conditions = [
        c
        for c in conditions
        if c
        and hasattr(c, "last_transition_time")
        and hasattr(c, "type")
        and hasattr(c, "status")
    ]
    # Sortuj po czasie malejąco
    sorted_conditions = sorted(
        valid_conditions,
        key=lambda x: x.last_transition_time
        or datetime(1970, 1, 1, tzinfo=timezone.utc),
        reverse=True,
    )

    for condition in sorted_conditions:
        if condition.status == "True":
            if condition.type == "Complete":
                final_status = "Succeeded"
                completion_time_dt = parse_timestamp(condition.last_transition_time)
                break
            elif condition.type == "Failed":
                final_status = "Failed"
                completion_time_dt = parse_timestamp(condition.last_transition_time)
                break

    return final_status, completion_time_dt


def get_volcano_start_time(uid, conditions_list):
    """Pobiera czas startu Volcano Job z cache lub conditions (lista dictów)."""
    global volcano_start_times_cache
    start_time_ts = volcano_start_times_cache.get(uid)
    if start_time_ts:
        logging.debug(
            f"[get_volcano_start_time] UID: {uid} - Found start time in cache: {start_time_ts}"
        )
        return datetime.fromtimestamp(start_time_ts, tz=timezone.utc)

    earliest_running_time = None
    if conditions_list and isinstance(conditions_list, list):
        for condition in conditions_list:
            if isinstance(condition, dict) and condition.get("status") == "Running":
                ts = parse_timestamp(condition.get("lastTransitionTime"))
                if ts:
                    logging.debug(
                        f"[get_volcano_start_time] UID: {uid} - Found 'Running' condition with time: {ts}"
                    )
                    if earliest_running_time is None or ts < earliest_running_time:
                        earliest_running_time = ts
                else:
                    logging.debug(
                        f"[get_volcano_start_time] UID: {uid} - Found 'Running' condition but failed to parse time: {condition.get('lastTransitionTime')}"
                    )

    if earliest_running_time:
        logging.debug(
            f"[get_volcano_start_time] UID: {uid} - Determined earliest start time: {earliest_running_time}, caching."
        )
        volcano_start_times_cache[uid] = earliest_running_time.timestamp()
        return earliest_running_time
    else:
        logging.debug(
            f"[get_volcano_start_time] UID: {uid} - No 'Running' condition found."
        )
        return None


def process_job(job_obj):
    """Przetwarza pojedynczy obiekt Job (K8s lub Volcano) i eksportuje metryki."""
    global previously_exported_completion_metrics
    global observed_wait_times_uids
    global observed_executiontotal_durations_uids
    uid = None
    name = None
    namespace = None
    job_kind = "Unknown"
    log_prefix = "[process_job]"

    try:
        # --- Rozpoznawanie typu obiektu i pobieranie danych ---
        if isinstance(job_obj, kubernetes.client.V1Job):
            job_kind = "Job"
            metadata = job_obj.metadata
            status_data = job_obj.status
            spec_data = job_obj.spec
            api_version = job_obj.api_version
            name = getattr(metadata, "name", None)
            namespace = getattr(metadata, "namespace", None)
            uid = getattr(metadata, "uid", None)
            creation_time_input = getattr(metadata, "creation_timestamp", None)
        elif isinstance(job_obj, dict) and job_obj.get("apiVersion", "").startswith(
            "batch.volcano.sh/"
        ):
            job_kind = "VolcanoJob"
            metadata_dict = job_obj.get("metadata", {})
            status_data = job_obj.get("status", {})
            spec_data = job_obj.get("spec", {})
            api_version = job_obj.get("apiVersion")
            name = metadata_dict.get("name")
            namespace = metadata_dict.get("namespace")
            uid = metadata_dict.get("uid")
            creation_time_input = metadata_dict.get("creationTimestamp")
            metadata = metadata_dict
        else:
            logging.warning(
                f"{log_prefix} Skipping unknown job object type or missing apiVersion: {type(job_obj)}"
            )
            return None

        log_prefix = f"[process_job][{namespace}/{name}({uid[:8]})]"

        if not all([name, namespace, uid]):
            logging.warning(f"{log_prefix} Job missing essential metadata.")
            return None

        queue_name = "<unknown>"  # Domyślna wartość

        if job_kind == "VolcanoJob":
            try:
                queue_name = spec_data.get("queue", "<none>")
                if not queue_name:
                    queue_name = "<none>"
            except Exception as e:
                logging.warning(
                    f"{log_prefix} Failed to extract queue from VolcanoJob spec: {e}"
                )
                queue_name = "<error>"
        elif job_kind == "Job":
            try:
                job_labels = {}
                if isinstance(metadata, kubernetes.client.V1ObjectMeta):
                    job_labels = metadata.labels or {}
                elif isinstance(metadata, dict):  # Dla VolcanoJob
                    job_labels = metadata.get("labels", {}) or {}

                # 1. Sprawdź etykietę Kueue
                kueue_queue = job_labels.get("kueue.x-k8s.io/queue-name")
                if kueue_queue:
                    queue_name = kueue_queue
                    logging.debug(f"{log_prefix} Found Kueue queue label: {queue_name}")
                else:
                    # 2. Sprawdź etykietę YuniKorn
                    yunikorn_queue = job_labels.get("queue")
                    if yunikorn_queue:
                        queue_name = yunikorn_queue
                        logging.debug(
                            f"{log_prefix} Found YuniKorn queue label: {queue_name}"
                        )
                    else:
                        # 3. Fallback - brak znanej etykiety kolejki
                        queue_name = "<k8s-job-no-queue>"
                        logging.debug(
                            f"{log_prefix} No known queue label (Kueue/YuniKorn) found."
                        )

            except Exception as e:
                logging.warning(
                    f"{log_prefix} Failed to extract labels for queue from K8s Job metadata: {e}"
                )
                queue_name = "<error>"

        logging.debug(f"{log_prefix} Determined queue: {queue_name}")

        base_labels = {
            "job_name": name,
            "namespace": namespace,
            "uid": uid,
            "job_kind": job_kind,
            "queue": queue_name,
        }
        logging.debug(
            f"{log_prefix} Processing start. Kind: {job_kind}, Queue: {queue_name}"
        )

        # --- Timestamps i Status ---
        creation_time_dt = parse_timestamp(creation_time_input)
        start_time_dt = None
        completion_time_dt = None
        final_status = None
        current_phase_str = "Unknown"

        logging.debug(f"{log_prefix} Raw creation_time_input: {creation_time_input}")
        if creation_time_dt:
            logging.debug(
                f"{log_prefix} Parsed creation_time_dt: {creation_time_dt.isoformat()}"
            )
        else:
            logging.warning(
                f"{log_prefix} Failed to parse or missing creation timestamp."
            )

        if job_kind == "Job":
            start_time_input = getattr(status_data, "start_time", None)
            completion_time_input = getattr(status_data, "completion_time", None)
            conditions = getattr(status_data, "conditions", None)

            logging.debug(f"{log_prefix} Raw start_time_input: {start_time_input}")
            logging.debug(
                f"{log_prefix} Raw completion_time_input: {completion_time_input}"
            )

            start_time_dt = parse_timestamp(start_time_input)
            completion_time_dt = parse_timestamp(completion_time_input)
            final_status_cond, completion_time_cond = get_k8s_job_final_status(
                conditions
            )

            if completion_time_dt is None and completion_time_cond:
                logging.debug(
                    f"{log_prefix} Using completion time from conditions: {completion_time_cond}"
                )
                completion_time_dt = completion_time_cond
            if final_status_cond:
                final_status = final_status_cond
                logging.debug(
                    f"{log_prefix} Determined final status from conditions: {final_status}"
                )

            # Określ bieżącą fazę
            succeeded_count = getattr(status_data, "succeeded", 0) or 0
            failed_count = getattr(status_data, "failed", 0) or 0
            active_count = getattr(status_data, "active", 0) or 0
            is_suspended = getattr(spec_data, "suspend", False)
            logging.debug(
                f"{log_prefix} K8s status counts: succeeded={succeeded_count}, failed={failed_count}, active={active_count}, suspended={is_suspended}"
            )

            if succeeded_count > 0:
                current_phase_str = "Succeeded"
            elif failed_count > 0:
                current_phase_str = "Failed"
            elif active_count > 0:
                current_phase_str = "Running"
            elif is_suspended:
                current_phase_str = "Pending"
            elif creation_time_dt:
                current_phase_str = "Pending"
            else:
                current_phase_str = "Unknown"
            logging.debug(
                f"{log_prefix} Determined current_phase_str: {current_phase_str}"
            )

        elif job_kind == "VolcanoJob":
            conditions_list = status_data.get("conditions")
            logging.debug(f"{log_prefix} Raw conditions_list: {conditions_list}")
            start_time_dt = get_volcano_start_time(
                uid, conditions_list
            )  # Logowanie jest wewnątrz tej funkcji
            current_phase_str = status_data.get("state", {}).get("phase", "Unknown")
            logging.debug(
                f"{log_prefix} Volcano current_phase_str: {current_phase_str}"
            )

            if current_phase_str in ["Completed", "Failed", "Aborted", "Terminated"]:
                completion_time_input = status_data.get("state", {}).get(
                    "lastTransitionTime"
                )
                logging.debug(
                    f"{log_prefix} Raw completion_time_input (from state): {completion_time_input}"
                )
                completion_time_dt = parse_timestamp(completion_time_input)
                final_status = (
                    "Succeeded" if current_phase_str == "Completed" else "Failed"
                )
                if completion_time_dt is None:
                    logging.warning(
                        f"{log_prefix} Could not parse completion time for phase {current_phase_str}"
                    )
                else:
                    logging.debug(
                        f"{log_prefix} Determined final status: {final_status} at {completion_time_dt.isoformat()}"
                    )

        # --- Koniec części specyficznej dla typu ---

        # --- Przetwarzanie i Eksport Metryk (wspólne) ---
        logging.debug(
            f"{log_prefix} Final Timestamps - Creation: {creation_time_dt}, Start: {start_time_dt}, Completion: {completion_time_dt}"
        )

        if creation_time_dt:
            ts_val = creation_time_dt.timestamp()
            logging.debug(f"{log_prefix} Exporting created_timestamp: {ts_val}")
            unified_job_created_timestamp_seconds.labels(**base_labels).set(ts_val)

        if start_time_dt:
            ts_val = start_time_dt.timestamp()
            logging.debug(f"{log_prefix} Exporting start_timestamp: {ts_val}")
            unified_job_start_timestamp_seconds.labels(**base_labels).set(ts_val)
            if creation_time_dt:
                wait_duration = (start_time_dt - creation_time_dt).total_seconds()
                if wait_duration < 0:
                    logging.warning(
                        f"{log_prefix} Negative wait duration calculated ({wait_duration}), setting to 0."
                    )
                    wait_duration = 0

                logging.debug(
                    f"{log_prefix} Exporting wait_duration GAUGE: {wait_duration}"
                )
                unified_job_wait_duration_seconds.labels(**base_labels).set(
                    wait_duration
                )

                # --- Obserwacja dla Histogramu (tylko raz) ---
                if uid not in observed_wait_times_uids:
                    logging.debug(
                        f"{log_prefix} Observing wait_duration HISTOGRAM ({wait_duration}) for the first time."
                    )
                    unified_job_wait_duration_seconds_histogram.labels(
                        job_kind=job_kind
                    ).observe(wait_duration)
                    observed_wait_times_uids.add(uid)
                else:
                    logging.debug(
                        f"{log_prefix} Wait duration HISTOGRAM already observed for this UID."
                    )
            else:
                logging.debug(
                    f"{log_prefix} Cannot calculate wait_duration, missing creation_time_dt."
                )

        if completion_time_dt and final_status:
            completion_labels = {**base_labels, "status": final_status}
            ts_val = completion_time_dt.timestamp()
            logging.debug(
                f"{log_prefix} Exporting completion_timestamp (status={final_status}): {ts_val}"
            )
            unified_job_completion_timestamp_seconds.labels(**completion_labels).set(
                ts_val
            )

            # Usunięcie flagowania w previously_exported... - histogram zajmie się unikalnością obserwacji
            # previously_exported_completion_metrics.setdefault(uid, set()).add("completion")

            execution_duration = None
            total_duration = None

            if start_time_dt:
                execution_duration = (
                    completion_time_dt - start_time_dt
                ).total_seconds()
                if execution_duration < 0:
                    logging.warning(
                        f"{log_prefix} Negative execution duration calculated ({execution_duration}), setting to 0."
                    )
                    execution_duration = 0
                logging.debug(
                    f"{log_prefix} Exporting execution_duration GAUGE (status={final_status}): {execution_duration}"
                )
                unified_job_execution_duration_seconds.labels(**completion_labels).set(
                    execution_duration
                )
                # previously_exported_completion_metrics.setdefault(uid, set()).add("duration_exec")
            else:
                logging.debug(
                    f"{log_prefix} Cannot calculate execution_duration, missing start_time_dt."
                )

            if creation_time_dt:
                total_duration = (completion_time_dt - creation_time_dt).total_seconds()
                if total_duration < 0:
                    logging.warning(
                        f"{log_prefix} Negative total duration calculated ({total_duration}), setting to 0."
                    )
                    total_duration = 0
                logging.debug(
                    f"{log_prefix} Exporting total_duration GAUGE (status={final_status}): {total_duration}"
                )
                unified_job_total_duration_seconds.labels(**completion_labels).set(
                    total_duration
                )
                # previously_exported_completion_metrics.setdefault(uid, set()).add("duration_total")
            else:
                logging.debug(
                    f"{log_prefix} Cannot calculate total_duration, missing creation_time_dt."
                )

            # --- Obserwacja dla Histogramów Czasów Trwania (tylko raz) ---
            if uid not in observed_executiontotal_durations_uids:
                logging.debug(
                    f"{log_prefix} Observing completion duration HISTOGRAMS for the first time (status={final_status})."
                )
                hist_duration_labels = {"job_kind": job_kind, "status": final_status}

                if execution_duration is not None:
                    unified_job_execution_duration_seconds_histogram.labels(
                        **hist_duration_labels
                    ).observe(execution_duration)
                    logging.debug(
                        f"{log_prefix} Observed execution_duration: {execution_duration}"
                    )
                else:
                    logging.debug(
                        f"{log_prefix} Cannot observe execution_duration histogram, value is None."
                    )

                if total_duration is not None:
                    unified_job_total_duration_seconds_histogram.labels(
                        **hist_duration_labels
                    ).observe(total_duration)
                    logging.debug(
                        f"{log_prefix} Observed total_duration: {total_duration}"
                    )
                else:
                    logging.debug(
                        f"{log_prefix} Cannot observe total_duration histogram, value is None."
                    )

                observed_executiontotal_durations_uids.add(uid)
            else:
                logging.debug(
                    f"{log_prefix} Completion duration HISTOGRAMS already observed for this UID."
                )

        phase_value = JOB_STATUS_MAP.get(current_phase_str, JOB_STATUS_MAP["Unknown"])
        logging.debug(
            f"{log_prefix} Exporting status_phase ({current_phase_str}): {phase_value}"
        )
        unified_job_status_phase.labels(**base_labels).set(phase_value)

        logging.debug(f"{log_prefix} Processing finished.")
        return uid

    except Exception as e:
        uid_safe = uid if uid else "unknown"  # Użyj uid jeśli zostało już ustalone
        job_name_safe = name if name else "unknown"
        job_ns_safe = namespace if namespace else "unknown"
        logging.error(
            f"{log_prefix} UNEXPECTED error during processing job {job_ns_safe}/{job_name_safe} (UID: {uid_safe}): {e}",
            exc_info=True,
        )
        return uid  # Zwróć UID, aby nie czyścić cache przez pomyłkę


# --- Główna Pętla ---


def collect_metrics(
    batch_v1_api: kubernetes.client.BatchV1Api,
    custom_objects_api: kubernetes.client.CustomObjectsApi,
    core_v1_api: kubernetes.client.CoreV1Api,
):
    """Pobiera zadania K8s i Volcano, przetwarza je i aktualizuje metryki."""
    start_time_cycle = time.time()
    global volcano_start_times_cache, previously_exported_completion_metrics
    global observed_wait_times_uids
    global observed_executiontotal_durations_uids
    current_job_uids_processed = set()  # UIDy przetworzone w tym cyklu
    metrics_to_remove_candidates = previously_exported_completion_metrics.copy()
    previously_exported_completion_metrics.clear()

    logging.info("Starting unified metrics collection cycle...")
    all_jobs_raw = []  # Lista obiektów/słowników z API

    # --- Pobieranie Standardowych Jobów ---
    try:
        logging.debug("Fetching Kubernetes Jobs (batch/v1)...")
        if TARGET_NAMESPACE:
            k8s_jobs_list = batch_v1_api.list_namespaced_job(
                namespace=TARGET_NAMESPACE, watch=False, timeout_seconds=60
            )
        else:
            k8s_jobs_list = batch_v1_api.list_job_for_all_namespaces(
                watch=False, timeout_seconds=60
            )
        all_jobs_raw.extend(k8s_jobs_list.items)
        logging.info(f"Fetched {len(k8s_jobs_list.items)} Kubernetes Jobs.")
    except kubernetes.client.ApiException as e:
        logging.error(f"API error fetching Kubernetes Jobs: {e.reason}")
        if e.status == 401:
            logging.error(
                "Authorization error (401): Check RBAC permissions for the service account."
            )
        elif e.status == 403:
            logging.error(
                "Forbidden error (403): Check RBAC permissions for the service account."
            )
    except Exception as e:
        logging.error(f"Unexpected error fetching Kubernetes Jobs: {e}", exc_info=True)

    # --- Pobieranie Volcano Jobów ---
    try:
        logging.debug("Fetching Volcano Jobs (batch.volcano.sh/v1alpha1)...")
        if TARGET_NAMESPACE:
            volcano_jobs_list = custom_objects_api.list_namespaced_custom_object(
                group="batch.volcano.sh",
                version="v1alpha1",
                plural="jobs",
                namespace=TARGET_NAMESPACE,
                timeout_seconds=60,
            )
        else:
            volcano_jobs_list = custom_objects_api.list_cluster_custom_object(
                group="batch.volcano.sh",
                version="v1alpha1",
                plural="jobs",
                timeout_seconds=60,
            )
        volcano_items = volcano_jobs_list.get("items", [])
        all_jobs_raw.extend(volcano_items)
        logging.info(f"Fetched {len(volcano_items)} Volcano Jobs.")
    except kubernetes.client.ApiException as e:
        if e.status == 404:
            logging.warning(
                "Volcano CRD (batch.volcano.sh/v1alpha1/jobs) not found in cluster."
            )
        else:
            logging.error(f"API error fetching Volcano Jobs: {e.reason}")
            if e.status == 401:
                logging.error(
                    "Authorization error (401): Check RBAC permissions for the service account for Volcano CRDs."
                )
            elif e.status == 403:
                logging.error(
                    "Forbidden error (403): Check RBAC permissions for the service account for Volcano CRDs."
                )
    except Exception as e:
        logging.error(f"Unexpected error fetching Volcano Jobs: {e}", exc_info=True)

    if not all_jobs_raw and start_time_cycle == time.time():
        logging.warning(
            "No job objects fetched in this cycle. Possible connection or permission issue."
        )

    # --- Przetwarzanie Wszystkich Zadań ---
    logging.info(f"Processing a total of {len(all_jobs_raw)} job objects...")
    processed_count = 0
    error_count = 0
    for job_obj in all_jobs_raw:
        # Przekaż oryginalny obiekt/słownik do process_job
        processed_uid = process_job(job_obj)
        if processed_uid:
            current_job_uids_processed.add(processed_uid)
            metrics_to_remove_candidates.pop(processed_uid, None)
            processed_count += 1
        else:
            # process_job zwraca None lub UID, nawet przy błędzie, więc to raczej się nie zdarzy,
            # ale można dodać licznik błędów, jeśli process_job zostanie zmieniony
            error_count += 1

    # --- Czyszczenie Starych Metryk Zakończenia ---
    if metrics_to_remove_candidates:
        logging.info(
            f"Stale completion metrics detected for UIDs: {list(metrics_to_remove_candidates.keys())}. Relying on Prometheus staleness."
        )
        # W przyszłości można by tu dodać logikę aktywnego usuwania, ale obecne podejście jest OK.

    # --- Czyszczenie Cache Czasu Startu Volcano ---
    volcano_uids_to_remove_from_cache = (
        set(volcano_start_times_cache.keys()) - current_job_uids_processed
    )
    if volcano_uids_to_remove_from_cache:
        logging.info(
            f"Removing {len(volcano_uids_to_remove_from_cache)} UIDs from Volcano start time cache: {list(volcano_uids_to_remove_from_cache)}"
        )
        for uid in volcano_uids_to_remove_from_cache:
            volcano_start_times_cache.pop(uid, None)

    # --- Czyszczenie Zbioru Zaobserwowanych Czasów Oczekiwania ---
    uids_to_remove_from_observed = observed_wait_times_uids - current_job_uids_processed
    if uids_to_remove_from_observed:
        logging.info(
            f"Removing {len(uids_to_remove_from_observed)} UIDs from observed wait times set."
        )
        logging.debug(
            f"UIDs to remove from observed set: {list(uids_to_remove_from_observed)}"
        )
        observed_wait_times_uids.difference_update(uids_to_remove_from_observed)

    # --- NOWA LOGIKA: Czyszczenie Zbioru Zaobserwowanych Czasów Zakończenia ---
    uids_to_remove_from_observed_completion = (
        observed_executiontotal_durations_uids - current_job_uids_processed
    )
    if uids_to_remove_from_observed_completion:
        logging.info(
            f"Removing {len(uids_to_remove_from_observed_completion)} UIDs from observed completion durations set."
        )
        observed_executiontotal_durations_uids.difference_update(
            uids_to_remove_from_observed_completion
        )
    # --- Koniec nowej logiki czyszczenia ---

    end_time_cycle = time.time()
    duration_cycle = end_time_cycle - start_time_cycle
    logging.info(
        f"Unified metrics collection cycle finished. Processed {processed_count} unique job UIDs seen this cycle (Errors: {error_count}). Cycle duration: {duration_cycle:.2f}s"
    )


if __name__ == "__main__":
    logging.info(f"Starting Unified Job Metrics Exporter on port {LISTEN_PORT}")
    logging.info(f"Scrape interval set to {SCRAPE_INTERVAL} seconds")
    if TARGET_NAMESPACE:
        logging.info(f"Monitoring namespace: {TARGET_NAMESPACE}")
    else:
        logging.info("Monitoring cluster-wide")

    try:
        try:
            logging.debug("Attempting to load incluster config...")
            kubernetes.config.load_incluster_config()
            logging.info("Using incluster Kubernetes config.")
        except kubernetes.config.ConfigException:
            logging.info("Incluster config failed, trying kube config...")
            kubernetes.config.load_kube_config()
            logging.info("Using kube config.")

        batch_v1_api = kubernetes.client.BatchV1Api()
        custom_objects_api = kubernetes.client.CustomObjectsApi()
        core_v1_api = kubernetes.client.CoreV1Api()

        logging.info("Kubernetes client initialized successfully.")

    except Exception as e:
        logging.error(
            f"FATAL: Failed to initialize Kubernetes client: {e}", exc_info=True
        )
        import sys

        sys.exit(1)

    # --- Start serwera HTTP ---
    start_http_server(LISTEN_PORT, registry=REGISTRY)
    logging.info("HTTP server started.")

    # --- Główna pętla ---
    while True:
        collect_metrics(batch_v1_api, custom_objects_api, core_v1_api)
        time.sleep(SCRAPE_INTERVAL)

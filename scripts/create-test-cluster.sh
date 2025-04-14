#!/bin/bash

# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
# Copyright (c) 2025, Mateusz Skowron (Modifications for dynamic resources).
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Enable strict error handling
set -euo pipefail

# Determine script and repository locations
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
REPO_HOME=$(readlink -f "${SCRIPT_DIR}/../")

# Source environment and functions (assuming env.sh exists and provides logging etc.)
# Make sure env.sh is sourced *before* using log functions etc.
if [[ -f "${REPO_HOME}/scripts/env.sh" ]]; then
    source "${REPO_HOME}/scripts/env.sh"
else
    echo "ERROR: env.sh not found at ${REPO_HOME}/scripts/env.sh"
    exit 1
fi

# --- Global Configuration ---
readonly KIND_NODE_VERSION="v1.30.0" # Make sure this matches your intended K8s version
readonly REQUIRED_COMMANDS=(kind helm kubectl)
readonly KIND_CLUSTER_NAME="kind" # Define cluster name once

# Default target allocatable resources for the Kind node.
# These values might be adjusted downwards if the host doesn't have enough capacity.
readonly TARGET_CPU="12"
readonly TARGET_MEMORY_GIB="32"
# --- End Global Configuration ---

get_host_cpu_count() {
    local os_type
    os_type=$(uname -s)
    case "$os_type" in
    Linux*)
        nproc --all 2>/dev/null || echo "2" # Default to 2 if nproc fails
        ;;
    Darwin*)
        sysctl -n hw.ncpu 2>/dev/null || echo "2" # Default to 2 if sysctl fails
        ;;
    *)
        log_warning "Unsupported OS '$os_type' for CPU detection. Assuming 2 CPUs."
        echo "2"
        ;;
    esac
}

get_host_memory_gib() {
    local os_type
    os_type=$(uname -s)
    local mem_kb mem_bytes mem_gib=0

    case "$os_type" in
    Linux*)
        mem_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
        if [[ -n "$mem_kb" && "$mem_kb" -gt 0 ]]; then
            mem_gib=$((mem_kb / 1024 / 1024)) # KiB to GiB (integer division)
        fi
        ;;
    Darwin*)
        mem_bytes=$(sysctl -n hw.memsize)
        if [[ -n "$mem_bytes" && "$mem_bytes" -gt 0 ]]; then
            mem_gib=$((mem_bytes / 1024 / 1024 / 1024)) # Bytes to GiB (integer division)
        fi
        ;;
    *)
        log_warning "Unsupported OS '$os_type' for memory detection."
        # Leave mem_gib=0
        ;;
    esac

    # Return detected value or a reasonable default (e.g., 4GiB) if detection failed
    if [[ "$mem_gib" -le 0 ]]; then
        log_warning "Failed to detect host memory or result is zero. Assuming 4 GiB."
        echo "4"
    else
        echo "$mem_gib"
    fi
}

main() {
    log_info "Starting test cluster creation script..."

    # Check required commands
    for cmd in "${REQUIRED_COMMANDS[@]}"; do
        check_command "$cmd" || exit 1
    done

    setup_kind_cluster
    deploy_prometheus_and_grafana
    deploy_unified_job_exporter
    deploy_node_resource_exporter
    deploy_kwok
    select_and_deploy_workload_manager
    create_additional_dashboards

    log_success "Cluster setup complete!"
}

setup_kind_cluster() {
    # Check if cluster with the specific name exists
    if kind get clusters | grep -q "^${KIND_CLUSTER_NAME}$"; then
        log_info "Existing kind cluster '${KIND_CLUSTER_NAME}' detected."
        # Adding -i '' for macOS compatibility with read -p
        read -r -p "Delete existing cluster '${KIND_CLUSTER_NAME}'? (y/n) > " choice </dev/tty
        if [[ "${choice,,}" == "y" ]]; then
            log_info "Deleting existing cluster '${KIND_CLUSTER_NAME}'..."
            kind delete cluster --name "${KIND_CLUSTER_NAME}"
            create_new_cluster # Create new after deleting
        else
            log_info "Using existing cluster '${KIND_CLUSTER_NAME}'. Note: Resource limits might not match desired configuration."
            # Optionally, add checks here to see if the existing cluster has the desired config? Hard to do reliably.
        fi
    else
        create_new_cluster # Create new if not found
    fi
}

create_new_cluster() {
    log_info "Creating new kind cluster '${KIND_CLUSTER_NAME}' with dynamically calculated resources..."
    local config_file="${SCRIPT_DIR}/kind-config-${KIND_CLUSTER_NAME}.yaml" # Store config near script

    log_info "Detecting host resources..."
    local detected_cpu
    detected_cpu=$(get_host_cpu_count)
    local detected_memory_gib
    detected_memory_gib=$(get_host_memory_gib)

    if [[ -z "$detected_cpu" || "$detected_cpu" -le 0 || -z "$detected_memory_gib" || "$detected_memory_gib" -le 0 ]]; then
        log_error "Failed to reliably detect host resources. Aborting cluster creation."
        exit 1
    fi
    log_info "Detected host resources: CPU=${detected_cpu}, Memory=${detected_memory_gib}Gi (approx. total)"

    local target_cpu="${TARGET_CPU}"
    local target_memory_gib="${TARGET_MEMORY_GIB}"

    # Check if host has enough resources for the target, adjust if necessary
    if [[ "$detected_cpu" -lt "$target_cpu" ]]; then
        log_warning "Host CPU count (${detected_cpu}) is less than target allocatable CPU (${target_cpu}). Adjusting target."
        # Leave at least 1 CPU for the host, or set target to 1 if host has only 1
        target_cpu=$((detected_cpu > 1 ? detected_cpu - 1 : 1))
        log_warning "New target allocatable CPU: ${target_cpu}"
    fi
    if [[ "$detected_memory_gib" -lt "$target_memory_gib" ]]; then
        log_warning "Host memory (${detected_memory_gib}Gi) is less than target allocatable memory (${target_memory_gib}Gi). Adjusting target."
        # Leave at least 1 GiB for the host
        target_memory_gib=$((detected_memory_gib > 1 ? detected_memory_gib - 1 : 1))
        log_warning "New target allocatable memory: ${target_memory_gib}Gi"
    fi

    # Calculate Kubelet reservations needed
    local reserved_cpu=$((detected_cpu - target_cpu))
    local reserved_memory_gib=$((detected_memory_gib - target_memory_gib))

    # Ensure reservations are not negative
    if [[ "$reserved_cpu" -lt 0 ]]; then reserved_cpu=0; fi
    if [[ "$reserved_memory_gib" -lt 0 ]]; then reserved_memory_gib=0; fi

    log_info "Target Allocatable for Kind node: CPU=${target_cpu}, Memory=${target_memory_gib}Gi"
    log_info "Calculated Kubelet Reservation: CPU=${reserved_cpu}, Memory=${reserved_memory_gib}Gi"

    # Create Kind configuration file
    # Using KubeletConfiguration v1beta1 which is standard
    cat <<EOF >"${config_file}"
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  image: kindest/node:${KIND_NODE_VERSION} # Use the global variable
  kubeadmConfigPatches:
  - |
    kind: KubeletConfiguration
    apiVersion: kubelet.config.k8s.io/v1beta1
    # Reserve the difference between detected capacity and target allocatable
    # This makes Kubelet report lower Allocatable resources
    systemReserved:
      cpu: "${reserved_cpu}"
      memory: "${reserved_memory_gib}Gi"
    # Also set eviction thresholds based on the *target* memory
    # Kubelet reserves this amount *in addition* to systemReserved/kubeReserved
    evictionHard:
      memory.available: "128Mi" # Evict when free memory drops below 128Mi
      nodefs.available: "10%"   # Standard disk usage thresholds
      imagefs.available: "15%"
EOF

    log_info "Generated kind config file '${config_file}' with dynamic resource reservations."

    # Create the cluster using the configuration file
    log_info "Running 'kind create cluster'..."
    if ! kind create cluster --name "${KIND_CLUSTER_NAME}" --config "${config_file}"; then
        log_error "Failed to create kind cluster with configuration file."
        log_error "Check the output above and '${config_file}' for details."
        rm -f "${config_file}" # Clean up config file on failure
        exit 1
    fi
    log_success "Kind cluster '${KIND_CLUSTER_NAME}' created successfully using configuration file."

    # Clean up the configuration file after successful creation
    log_info "Removing temporary config file '${config_file}'."
    rm -f "${config_file}"

    log_info "Skipping Docker container resource limit updates."

    log_info "Waiting for cluster nodes to be ready..."
    kubectl wait --for=condition=ready node --all --timeout=300s || {
        log_error "Nodes did not become ready in time."
        kind delete cluster --name "${KIND_CLUSTER_NAME}"
        exit 1
    }
    log_success "Cluster nodes are ready."
}

select_and_deploy_workload_manager() {
    log_info "Select workload manager:"
    PS3="Enter choice > "
    select manager in "Kueue" "Volcano" "YuniKorn"; do
        case "$manager" in
        "Kueue" | "Volcano" | "YuniKorn")
            if declare -f deploy_workload_manager >/dev/null; then
                deploy_workload_manager "${manager,,}"
            else
                log_error "Function 'deploy_workload_manager' not found. Cannot deploy ${manager}."
                exit 1
            fi
            break
            ;;
        *)
            log_error "Invalid selection. Please choose 1, 2, or 3."
            ;;
        esac
    done
}

create_additional_dashboards() {
    log_info "Creating additional Grafana dashboards for test metrics..."
    local monitoring_namespace="monitoring" # Assume standard namespace

    # Wait for Grafana deployment to be available (adjust label selector if needed)
    log_info "Waiting for Grafana deployment in namespace '${monitoring_namespace}'..."
    if ! kubectl -n "${monitoring_namespace}" wait --for=condition=available deployment -l app.kubernetes.io/name=grafana --timeout=300s; then
        log_error "Grafana deployment did not become available in time. Skipping dashboard import."
        return 1 # Indicate failure
    fi
    log_info "Grafana deployment is available."

    # Import dashboards
    local dashboard_dir="${REPO_HOME}/dashboards"
    if [[ ! -d "${dashboard_dir}" ]]; then
        log_warning "Dashboard directory not found at '${dashboard_dir}'. No dashboards to import."
        return 0
    fi

    for dashboard_file in "${dashboard_dir}"/*.json; do
        # Check if the glob found any files
        if [[ ! -f "$dashboard_file" ]]; then
            log_info "No .json dashboard files found in '${dashboard_dir}'."
            break
        fi

        local dashboard_name
        dashboard_name=$(basename "$dashboard_file" .json | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g') # Sanitize name for k8s
        local configmap_name="grafana-dashboard-${dashboard_name}"

        log_info "Importing dashboard: $(basename "$dashboard_file") as ConfigMap '${configmap_name}'"

        # Create or update ConfigMap for dashboard
        local dashboard_filename
        dashboard_filename=$(basename "$dashboard_file")
        kubectl create configmap "${configmap_name}" \
            --namespace "${monitoring_namespace}" \
            --from-file="${dashboard_filename}=${dashboard_file}" \
            --dry-run=client -o yaml | kubectl apply -f -

        # Label ConfigMap for Grafana sidecar to pick it up
        kubectl label configmap "${configmap_name}" \
            --namespace "${monitoring_namespace}" \
            grafana_dashboard=1 --overwrite=true
    done

    log_success "Additional dashboards import process complete."
}

# Run main function, passing all script arguments
main "$@"

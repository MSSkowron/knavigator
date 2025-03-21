#!/bin/bash

# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
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

# Source environment and functions
source "${REPO_HOME}/scripts/env.sh"

# Configuration
readonly KIND_NODE_VERSION="v1.30.0"
readonly REQUIRED_COMMANDS=(kind helm kubectl)

main() {
    log_info "Creating test cluster..."

    # Check required commands
    for cmd in "${REQUIRED_COMMANDS[@]}"; do
        check_command "$cmd" || exit 1
    done

    setup_kind_cluster
    deploy_prometheus_and_grafana
    deploy_kwok
    select_and_deploy_workload_manager
    create_additional_dashboards

    log_success "Cluster setup complete!"
}

setup_kind_cluster() {
    if kind get clusters &>/dev/null; then
        log_info "Existing kind cluster detected."
        read -rp "Delete existing cluster? (y/n) > " choice
        if [[ "${choice,,}" == "y" ]]; then
            kind delete cluster
            create_new_cluster
        fi
    else
        create_new_cluster
    fi
}

create_new_cluster() {
    log_info "Creating new kind cluster..."
    kind create cluster --image="kindest/node:${KIND_NODE_VERSION}"
}

select_and_deploy_workload_manager() {
    log_info "Select workload manager:"
    PS3="Enter choice > "
    select manager in "Kueue" "Volcano" "YuniKorn"; do
        case "$manager" in
        "Kueue" | "Volcano" | "YuniKorn")
            deploy_workload_manager "${manager,,}"
            break
            ;;
        *)
            log_error "Invalid selection"
            ;;
        esac
    done
}

create_additional_dashboards() {
    log_info "Creating additional Grafana dashboards for test metrics..."

    # Wait for Grafana to be ready
    kubectl -n monitoring wait --for=condition=ready pod \
        -l app.kubernetes.io/name=grafana --timeout=300s

    # Import dashboards
    for dashboard in "${REPO_HOME}/dashboards"/*.json; do
        dashboard_name=$(basename "$dashboard" .json)
        log_info "Importing dashboard: $dashboard_name"

        # Create ConfigMap for dashboard
        kubectl create configmap -n monitoring "grafana-dashboard-${dashboard_name}" \
            --from-file="dashboard.json=${dashboard}" \
            --dry-run=client -o yaml | kubectl apply -f -

        # Label ConfigMap for Grafana to pick it up
        kubectl label -n monitoring configmap "grafana-dashboard-${dashboard_name}" \
            grafana_dashboard=1 --overwrite
    done

    log_success "Additional dashboards created"
}

# Run main function
main "$@"

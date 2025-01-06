#!/bin/bash
# env.sh

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

# Constants and Configuration
readonly KWOK_REPO="kubernetes-sigs/kwok"
readonly KWOK_RELEASE="v0.6.1"

readonly PROMETHEUS_STACK_VERSION="61.5.0"

readonly KUEUE_VERSION="v0.9.0"
readonly VOLCANO_VERSION="v1.10.0"
readonly YUNIKORN_VERSION="v1.6.0"

# Color definitions
declare -A COLORS=(
    ["RED"]='\033[0;31m'
    ["GREEN"]='\033[0;32m'
    ["YELLOW"]='\033[0;33m'
    ["BLUE"]='\033[0;34m'
    ["NC"]='\033[0m'
)

# Logging functions
log() {
    local color=$1
    shift
    echo -e "${COLORS[$color]}$*${COLORS[NC]}"
}

log_error() { log "RED" "$@"; }
log_success() { log "GREEN" "$@"; }
log_info() { log "YELLOW" "$@"; }
log_debug() { log "BLUE" "$@"; }

# Error handling
set -euo pipefail
trap 'log_error "Error on line $LINENO"' ERR

# Utility functions
check_command() {
    local cmd=$1
    if ! command -v "$cmd" &> /dev/null; then
        log_error "$cmd is not installed"
        return 1
    fi
}

wait_for_pods() {
    local namespace=$1
    local expected_count=$2
    local timeout=${3:-60}
    local interval=${4:-5}
    local elapsed=0

    log_info "Waiting for $expected_count pods in namespace $namespace..."

    while true; do
        local current_count
        current_count=$(kubectl get pods -n "$namespace" --no-headers 2>/dev/null | wc -l)

        if [ "$current_count" -eq "$expected_count" ]; then
            log_success "Found expected number of pods: $current_count"
            return 0
        fi

        log_debug "Current pods: $current_count, expecting: $expected_count"

        if [ "$elapsed" -ge "$timeout" ]; then
            log_error "Timeout waiting for pods (${elapsed}s)"
            return 1
        fi

        sleep "$interval"
        elapsed=$((elapsed + interval))
    done
}

# Deployment functions
deploy_kwok() {
    log_info "Deploying KWOK..."

    # Deploy KWOK controller
    kubectl apply -f "https://github.com/${KWOK_REPO}/releases/download/${KWOK_RELEASE}/kwok.yaml"

    # Deploy stages
    local base_url="https://github.com/${KWOK_REPO}"
    kubectl apply -f "${base_url}/releases/download/${KWOK_RELEASE}/stage-fast.yaml"
    kubectl apply -f "${base_url}/raw/main/kustomize/stage/pod/chaos/pod-init-container-running-failed.yaml"
    kubectl apply -f "${base_url}/raw/main/kustomize/stage/pod/chaos/pod-container-running-failed.yaml"
    #kubectl apply -f https://github.com/${KWOK_REPO}/raw/main/kustomize/stage/pod/general/pod-complete.yaml

    log_success "KWOK deployment complete"
}

deploy_prometheus_and_grafana() {
    log_info "Deploying Prometheus and Grafana..."

    helm repo add --force-update prometheus-community https://prometheus-community.github.io/helm-charts

    helm upgrade --install -n monitoring --create-namespace kube-prometheus-stack \
        prometheus-community/kube-prometheus-stack \
        --version="$PROMETHEUS_STACK_VERSION" \
        --wait \
        --values - <<EOF
grafana:
  enabled: true
  adminPassword: 'admin'
  persistence:
    enabled: true
alertmanager:
  enabled: false
nodeExporter:
  enabled: false
defaultRules:
  rules:
    alertmanager: false
    nodeExporterAlerting: false
    nodeExporterRecording: false
prometheus:
  prometheusSpec:
    serviceMonitorSelectorNilUsesHelmValues: false
    podMonitorSelectorNilUsesHelmValues: false
EOF

    kubectl -n monitoring wait --for=condition=ready pod \
        -l app.kubernetes.io/instance=kube-prometheus-stack --timeout=600s

    log_success "Prometheus and Grafana deployment complete"

    log_info "Deploying Node Resource Exporter"

    helm upgrade --install -n monitoring node-resource-exporter --wait $REPO_HOME/charts/node-resource-exporter

    kubectl -n monitoring wait --for=condition=ready pod \
        -l app.kubernetes.io/name=node-resource-exporter --timeout=600s

    log_success "Node Resource Exported deployment complete"
}

deploy_workload_manager() {
    local choice=$1

    case "$choice" in
        "kueue")
            deploy_kueue
            ;;
        "volcano")
            deploy_volcano
            ;;
        "yunikorn")
            deploy_yunikorn
            ;;
        *)
            log_error "Invalid workload manager: $choice"
            return 1
            ;;
    esac
}

deploy_kueue() {
    log_info "Deploying Kueue..."

    kubectl apply --server-side -f "https://github.com/kubernetes-sigs/kueue/releases/download/${KUEUE_VERSION}/manifests.yaml"

    # Apply KWOK affinity patch
    kubectl -n kueue-system patch deployment kueue-controller-manager \
        --patch-file="${REPO_HOME}/charts/overrides/kwok-affinity-deployment-patch.yaml"

    wait_for_pods "kueue-system" 1
    kubectl -n kueue-system wait --for=condition=ready pod -l control-plane=controller-manager --timeout=600s

    log_success "Kueue deployment complete"
}

deploy_volcano() {
    log_info "Deploying Volcano..."

    helm repo add --force-update volcano-sh https://volcano-sh.github.io/helm-charts

    helm upgrade --install volcano volcano-sh/volcano -n volcano-system --create-namespace \
        --version="$VOLCANO_VERSION" \
        --wait \
        --set-json 'affinity={"nodeAffinity":{"requiredDuringSchedulingIgnoredDuringExecution":{"nodeSelectorTerms":[{"matchExpressions":[{"key":"type","operator":"NotIn","values":["kwok"]}]}]}}}'

    for app in volcano-admission volcano-controller volcano-scheduler; do
        kubectl -n volcano-system wait --for=condition=ready pod -l app="$app" --timeout=600s
    done

    # TODO: Replace sleep with deterministic readiness check
    sleep 10

    log_success "Volcano deployment complete"
}

deploy_yunikorn() {
    log_info "Deploying YuniKorn..."

    helm repo add --force-update yunikorn https://apache.github.io/yunikorn-release

    helm upgrade --install yunikorn yunikorn/yunikorn -n yunikorn --create-namespace \
        --version="$YUNIKORN_VERSION" \
        --wait \
        --set-json 'affinity={"nodeAffinity":{"requiredDuringSchedulingIgnoredDuringExecution":{"nodeSelectorTerms":[{"matchExpressions":[{"key":"type","operator":"NotIn","values":["kwok"]}]}]}}}'

    kubectl -n yunikorn wait --for=condition=ready pod -l app=yunikorn --timeout=600s

    log_success "YuniKorn deployment complete"
}

# Export functions and variables for use in other scripts
export -f log log_error log_success log_info log_debug
export -f check_command wait_for_pods
export -f deploy_kwok deploy_prometheus_and_grafana deploy_workload_manager
export -f deploy_kueue deploy_volcano deploy_yunikorn

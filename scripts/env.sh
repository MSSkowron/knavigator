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

readonly PROMETHEUS_STACK_VERSION="69.8.0"

readonly KUEUE_VERSION="v0.10.2"
readonly VOLCANO_VERSION="v1.11.0"
readonly YUNIKORN_VERSION="v1.6.1"

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
    if ! command -v "$cmd" &>/dev/null; then
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
    kubectl apply -f "${REPO_HOME}/charts/overrides/kwok/pod-complete.yaml"

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
  enabled: true
kubeStateMetrics:
  enabled: true
defaultRules:
  rules:
    alertmanager: false
    nodeExporterAlerting: false
    nodeExporterRecording: true
prometheus:
  prometheusSpec:
    serviceMonitorSelectorNilUsesHelmValues: false
    podMonitorSelectorNilUsesHelmValues: false
EOF

    # Wait for the Prometheus and Grafana pods to be ready
    log_info "Waiting for Prometheus and Grafana pods to be ready..."
    kubectl -n monitoring wait --for=condition=ready pod \
        -l app.kubernetes.io/instance=kube-prometheus-stack --timeout=600s || {
        log_error "Timed out waiting for Prometheus pods"
        return 1
    }

    # Set up port-forwarding script for easy access
    log_info "Creating port-forwarding helper script..."
    cat <<EOF >"${REPO_HOME}/monitoring-portforward.sh"
#!/bin/bash
# Script to set up port forwarding for monitoring tools

# Start port forwarding for Grafana
kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 8080:80 &
GRAFANA_PID=\$!

# Start port forwarding for Prometheus
kubectl -n monitoring port-forward svc/kube-prometheus-stack-prometheus 9090:9090 &
PROMETHEUS_PID=\$!

echo "Port forwarding started:"
echo "  - Grafana: http://localhost:8080 (admin/admin)"
echo "  - Prometheus: http://localhost:9090"
echo ""
echo "Press Ctrl+C to stop port forwarding"

# Handle cleanup on script exit
trap "kill \$GRAFANA_PID \$PROMETHEUS_PID 2>/dev/null" EXIT

# Wait for user to cancel
wait
EOF

    chmod +x "${REPO_HOME}/monitoring-portforward.sh"

    log_success "Enhanced Prometheus, Grafana and monitoring deployment complete"
    log_info "You can access the monitoring interfaces using: ${REPO_HOME}/monitoring-portforward.sh"
    log_info "Grafana credentials: admin/admin"
    log_info "Additional scheduler-specific dashboards have been created"
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
    log_info "Deploying Kueue ${KUEUE_VERSION}..."

    # Install the main Kueue components
    kubectl apply --server-side -f "https://github.com/kubernetes-sigs/kueue/releases/download/${KUEUE_VERSION}/manifests.yaml"

    # Install Prometheus metrics scraping configuration
    log_info "Configuring Prometheus metrics scraping for Kueue..."
    kubectl apply -f "https://github.com/kubernetes-sigs/kueue/releases/download/${KUEUE_VERSION}/prometheus.yaml"

    # Apply KWOK affinity patch
    log_info "Applying KWOK affinity patch..."
    kubectl -n kueue-system patch deployment kueue-controller-manager \
        --patch-file="${REPO_HOME}/charts/overrides/kwok-affinity-deployment-patch.yaml"

    # Validate configuration to ensure webhook is properly setup
    log_info "Waiting for Kueue controller manager to be ready..."
    wait_for_pods "kueue-system" 1
    kubectl -n kueue-system wait --for=condition=available deployment/kueue-controller-manager --timeout=300s

    # Verify the installation by checking if controller manager is running
    if kubectl -n kueue-system get pods -l control-plane=controller-manager | grep -q Running; then
        log_success "Kueue deployment complete"
    else
        log_error "Kueue deployment failed - controller manager is not running"
        return 1
    fi

    log_info "Kueue metrics are available at the /metrics endpoint of the controller-manager"
}

deploy_volcano() {
    log_info "Deploying Volcano ${VOLCANO_VERSION}..."

    helm repo add --force-update volcano-sh https://volcano-sh.github.io/helm-charts

    # Deploy Volcano with metrics enabled
    log_info "Installing Volcano with metrics enabled..."
    helm upgrade --install volcano volcano-sh/volcano -n volcano-system --create-namespace \
        --version="$VOLCANO_VERSION" \
        --wait \
        --set custom.metrics_enable=true \
        --set-json 'affinity={"nodeAffinity":{"requiredDuringSchedulingIgnoredDuringExecution":{"nodeSelectorTerms":[{"matchExpressions":[{"key":"type","operator":"NotIn","values":["kwok"]}]}]}}}'

    # Wait for all Volcano deployments to be available
    log_info "Waiting for Volcano deployments to be available..."
    kubectl -n volcano-system wait --for=condition=available \
        deployment/volcano-admission \
        deployment/volcano-controllers \
        deployment/volcano-scheduler \
        --timeout=600s || {
        log_error "Timed out waiting for Volcano deployments to be available"
        return 1
    }

    # Verify the installation
    if kubectl -n volcano-system get pods | grep -q "volcano-scheduler"; then
        log_success "Volcano deployment complete"
        log_info "Volcano metrics are available at the /metrics endpoint of each component"
    else
        log_error "Volcano deployment failed - scheduler is not running"
        return 1
    fi
}

deploy_yunikorn() {
    log_info "Deploying YuniKorn ${YUNIKORN_VERSION}..."

    helm repo add --force-update yunikorn https://apache.github.io/yunikorn-release

    # Deploy YuniKorn using Helm
    log_info "Installing YuniKorn with metrics enabled..."
    helm upgrade --install yunikorn yunikorn/yunikorn -n yunikorn --create-namespace \
        --version="$YUNIKORN_VERSION" \
        --wait \
        --set embedAdmissionController=true \
        --set-json 'affinity={"nodeAffinity":{"requiredDuringSchedulingIgnoredDuringExecution":{"nodeSelectorTerms":[{"matchExpressions":[{"key":"type","operator":"NotIn","values":["kwok"]}]}]}}}'

    # Wait for YuniKorn pods to be ready
    log_info "Waiting for YuniKorn pods to be ready..."
    kubectl -n yunikorn wait --for=condition=ready pod -l app=yunikorn --timeout=600s || {
        log_error "Timed out waiting for YuniKorn pods to be ready"
        return 1
    }

    # Create ServiceMonitor for Prometheus integration if Prometheus Operator is installed
    if kubectl get crd servicemonitors.monitoring.coreos.com &>/dev/null; then
        log_info "Creating ServiceMonitor for YuniKorn metrics..."
        cat <<EOF | kubectl apply -f -
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: yunikorn-service-monitor
  namespace: yunikorn
  labels:
    release: prometheus
spec:
  selector:
    matchLabels:
      app: yunikorn
  namespaceSelector:
    matchNames:
    - yunikorn
  endpoints:
  - port: yunikorn-service
    path: /ws/v1/metrics
    interval: 30s
EOF
        log_success "ServiceMonitor created for Prometheus integration"
    else
        log_info "Prometheus Operator CRDs not found. Skipping ServiceMonitor creation."
        log_info "To manually configure Prometheus monitoring, see: https://yunikorn.apache.org/docs/user_guide/observability/prometheus"
    fi

    # Verify the installation
    if kubectl -n yunikorn get pods | grep -q "yunikorn-scheduler-"; then
        log_success "YuniKorn deployment complete"

        # Provide information about accessing the web UI
        log_info "YuniKorn Web UI is available via port forwarding:"
        log_info "  kubectl port-forward svc/yunikorn-service 9889:9889 -n yunikorn"
        log_info "  Then access: http://localhost:9889"

        # Provide information about metrics
        log_info "YuniKorn metrics are exposed at the /ws/v1/metrics endpoint:"
        log_info "  kubectl port-forward svc/yunikorn-service 9080:9080 -n yunikorn"
        log_info "  Then access: http://localhost:9080/ws/v1/metrics"

        # Provide additional documentation references
        log_info "For Prometheus and Grafana integration details, see:"
        log_info "  https://yunikorn.apache.org/docs/user_guide/observability/prometheus"
    else
        log_error "YuniKorn deployment failed - scheduler is not running"
        return 1
    fi
}

# Export functions and variables for use in other scripts
export -f log log_error log_success log_info log_debug
export -f check_command wait_for_pods
export -f deploy_kwok deploy_prometheus_and_grafana deploy_workload_manager
export -f deploy_kueue deploy_volcano deploy_yunikorn

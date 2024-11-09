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

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

function printRed() {
  echo -e "${RED}$@${NC}"
}

function printGreen() {
  echo -e "${GREEN}$@${NC}"
}

function printYellow() {
  echo -e "${YELLOW}$@${NC}"
}

function printBlue() {
  echo -e "${BLUE}$@${NC}"
}

### check for command
function fail_if_command_not_found() {
  local command_name="$1"
  if ! command -v $command_name &> /dev/null; then
    printRed "$command_name is not installed"
    exit 1
  fi
}

### wait for specific number of pods in a namespace
function wait_for_pods() {
  local namespace=$1
  local pods=$2
  local wait_time=60
  local sleep_interval=5
  local elapsed_time=0

  while true; do
    count=$(kubectl get pods -n $namespace --no-headers 2>/dev/null | wc -l)
    if [ "$count" -eq $pods ]; then
      break
    fi
    echo "current pods $count, expecting $pods"

    sleep "$sleep_interval"
    elapsed_time=$((elapsed_time + sleep_interval))
    if [ "$elapsed_time" -gt "$wait_time" ]; then
      exit 1
    fi
  done
}

# KWOK
#

KWOK_REPO=kubernetes-sigs/kwok
KWOK_RELEASE="v0.6.1"

function deploy_kwok() {
  printGreen Deploying KWOK

  # Deploy KWOK controller
  kubectl apply -f https://github.com/${KWOK_REPO}/releases/download/${KWOK_RELEASE}/kwok.yaml

  # Deploy and adjust the stages
  kubectl apply -f https://github.com/${KWOK_REPO}/releases/download/${KWOK_RELEASE}/stage-fast.yaml
  kubectl apply -f https://github.com/${KWOK_REPO}/raw/main/kustomize/stage/pod/chaos/pod-init-container-running-failed.yaml
  kubectl apply -f https://github.com/${KWOK_REPO}/raw/main/kustomize/stage/pod/chaos/pod-container-running-failed.yaml
  #kubectl apply -f https://github.com/${KWOK_REPO}/raw/main/kustomize/stage/pod/general/pod-complete.yaml
}

# Prometheus
#

PROMETHEUS_STACK_VERSION=61.5.0

function deploy_prometheus_and_grafana() {
  printGreen Deploying Prometheus

  helm repo add --force-update prometheus-community https://prometheus-community.github.io/helm-charts

  helm upgrade --install -n monitoring --create-namespace kube-prometheus-stack \
    prometheus-community/kube-prometheus-stack \
    --version=$PROMETHEUS_STACK_VERSION --wait \
    --set grafana.enabled=true \
    --set grafana.adminPassword='admin' \
    --set grafana.persistence.enabled=true \
    --set alertmanager.enabled=false \
    --set nodeExporter.enabled=false \
    --set defaultRules.rules.alertmanager=false \
    --set defaultRules.rules.nodeExporterAlerting=false \
    --set defaultRules.rules.nodeExporterRecording=false \
    --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
    --set prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues=false

  kubectl -n monitoring wait --for=condition=ready pod -l app.kubernetes.io/instance=kube-prometheus-stack --timeout=600s
}

# Tested workload managers
#

# https://github.com/kubernetes-sigs/kueue
KUEUE_VERSION=v0.9.0

function deploy_kueue() {
  printGreen Deploying kueue

  kubectl apply --server-side -f https://github.com/kubernetes-sigs/kueue/releases/download/${KUEUE_VERSION}/manifests.yaml

  kubectl -n kueue-system patch deployment kueue-controller-manager \
    --patch-file=$REPO_HOME/charts/overrides/kwok-affinity-deployment-patch.yaml

  wait_for_pods "kueue-system" 1

  kubectl -n kueue-system wait --for=condition=ready pod -l control-plane=controller-manager --timeout=600s
}

# https://github.com/volcano-sh/volcano
VOLCANO_VERSION=v1.10.0

function deploy_volcano() {
  printGreen Deploying volcano

  helm repo add --force-update volcano-sh https://volcano-sh.github.io/helm-charts

  helm upgrade --install volcano volcano-sh/volcano -n volcano-system --create-namespace \
    --version=$VOLCANO_VERSION --wait \
    --set-json 'affinity={"nodeAffinity":{"requiredDuringSchedulingIgnoredDuringExecution":{"nodeSelectorTerms":[{"matchExpressions":[{"key":"type","operator":"NotIn","values":["kwok"]}]}]}}}'

  for app in volcano-admission volcano-controller volcano-scheduler; do
    kubectl -n volcano-system wait --for=condition=ready pod -l app=$app --timeout=600s
  done

  # Wait until volcano webhook is ready
  # TODO: we need a deterministric way to check if it's ready
  sleep 10
}

# https://github.com/apache/yunikorn-core
YUNIKORN_VERSION=v1.6.0

function deploy_yunikorn() {
  printGreen Deploying yunikorn

  helm repo add --force-update yunikorn https://apache.github.io/yunikorn-release

  helm upgrade --install yunikorn yunikorn/yunikorn -n yunikorn --create-namespace \
    --version=$YUNIKORN_VERSION --wait \
    --set-json 'affinity={"nodeAffinity":{"requiredDuringSchedulingIgnoredDuringExecution":{"nodeSelectorTerms":[{"matchExpressions":[{"key":"type","operator":"NotIn","values":["kwok"]}]}]}}}'

  kubectl -n yunikorn wait --for=condition=ready pod -l app=yunikorn --timeout=600s
}

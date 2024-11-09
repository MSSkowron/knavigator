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

set -e

REPO_HOME=$(readlink -f $(dirname $(readlink -f "$0"))/../)

source $REPO_HOME/scripts/env.sh

printYellow Creating test cluster

echo "This script installs a kind cluster and deploys Prometheus, Grafana, KWOK, and workload manager of your choice (Kueue/Volcano/Apache YuniKorn)"

fail_if_command_not_found kind
fail_if_command_not_found helm
fail_if_command_not_found kubectl

if kind get clusters > /dev/null 2>&1; then
  echo "Kind is running. Delete? (y/n)"
  read -p "> " choice
  if [[ "$choice" == "y" ]]; then
    kind delete cluster
    kind create cluster --image=kindest/node:v1.29.7
  fi
else
  kind create cluster --image=kindest/node:v1.29.7
fi

deploy_prometheus_and_grafana

deploy_kwok
kubectl apply -f $REPO_HOME/charts/overrides/kwok/pod-complete.yaml

echo ""
printYellow "Select workload manager"
cat << EOF
  1: Kueue
  2: Volcano
  3: YuniKorn
EOF
read -p "> " choice

case "$choice" in
  1)
    deploy_kueue
    ;;
  2)
    deploy_volcano
    ;;
  3)
    deploy_yunikorn
    ;;
esac

printYellow Cluster is ready

Cluster setup
```bash
  ./scripts/create-test-cluster.sh
  ./monitoring-portforward.sh
```
Cleanup commands
```bash
  kubectl -n default delete job --all
  kubectl -n default delete localqueue --all
  kubectl -n default delete clusterqueue --all
  kubectl -n default delete resourceflavor --all
  kubectl -n default delete topology --all
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-cleanup.yaml
  kubectl -n monitoring delete pod --all
```
Test scenarios
```bash
  ./bin/knavigator -workflow resources/tests-psocala/gang/kueue/test3-heterogeneous/run-test-standard-TAS.yaml
  ./bin/knavigator -workflow resources/tests-psocala/gang/kueue/test3-heterogeneous/run-test-large-TAS.yaml
```
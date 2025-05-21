
```bash
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-gang-2.yaml
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-cleanup.yaml
  ./scripts/create-test-cluster.sh
  ./monitoring-portforward.sh
```
```bash
  kubectl -n default delete job --all
  kubectl -n default delete localqueue --all
  kubectl -n default delete clusterqueue --all
  kubectl -n default delete resourceflavor --all
  kubectl -n default delete topology --all
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-cleanup.yaml
  kubectl -n monitoring delete pod --all
```
```bash
  ./bin/knavigator -workflow resources/tests-psocala/gang/kueue/test2-homogeneous/run-test-small-cluster-10-pods.yaml
  ./bin/knavigator -workflow resources/tests-psocala/gang/kueue/test2-homogeneous/run-test-small-cluster-100-pods.yaml
  ./bin/knavigator -workflow resources/tests-psocala/gang/kueue/test2-homogeneous/run-test-big-cluster-10-pods.yaml
  ./bin/knavigator -workflow resources/tests-psocala/gang/kueue/test2-homogeneous/run-test-big-cluster-100-pods.yaml
```
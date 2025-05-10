
```bash
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-gang-2.yaml
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-cleanup.yaml
  kubectl apply -f resources/tests-psocala/templates/kueue/podgroup-crd.yaml
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
```
```bash
  ./bin/knavigator -workflow resources/tests-psocala/gang/kueue/test1-gang-functionality/run-test-standard.yaml
  ./bin/knavigator -workflow resources/tests-psocala/gang/kueue/test1-gang-functionality/run-test-standard-blocking-job.yaml
```
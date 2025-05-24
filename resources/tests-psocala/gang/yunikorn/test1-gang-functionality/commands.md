
```bash
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-gang-2.yaml
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-cleanup.yaml
  ./scripts/create-test-cluster.sh
  ./monitoring-portforward.sh
```
```bash
  kubectl -n default delete job --all
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-cleanup.yaml
  kubectl -n yunikorn delete pod --all
```
```bash
  ./bin/knavigator -workflow resources/tests-psocala/gang/yunikorn/test1-gang-functionality/run-test-standard.yaml
  ./bin/knavigator -workflow resources/tests-psocala/gang/yunikorn/test1-gang-functionality/run-test-standard-blocking-job.yaml
```
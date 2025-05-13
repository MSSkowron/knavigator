
```bash
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-gang-2.yaml
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-cleanup.yaml
  ./scripts/create-test-cluster.sh
  ./monitoring-portforward.sh
```
```bash
  kubectl delete jobs.batch.volcano.sh --all
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-cleanup.yaml
```
```bash
  ./bin/knavigator -workflow resources/tests-psocala/gang/volcano/test1-gang-functionality/run-test-standard-TAS.yaml
  ./bin/knavigator -workflow resources/tests-psocala/gang/volcano/test1-gang-functionality/run-test-standard-blocking-job.yaml
```

```bash
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/mytests/templates/nodes/nodes-backfill-100x100.yaml
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/mytests/templates/nodes/nodes-backfill-35x100.yaml
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/mytests/templates/nodes/nodes-backfill-10x100.yaml
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/mytests/templates/nodes/nodes-cleanup.yaml
```
```bash
  kubectl -n default delete job --all
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/mytests/templates/nodes/nodes-cleanup.yaml
```
```bash
  ./bin/knavigator -workflow resources/mytests/backfill/k8s/test2/run-test-10x100.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/k8s/test2/run-test-35x100.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/k8s/test2/run-test-100x100.yaml
```
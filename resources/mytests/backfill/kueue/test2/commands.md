
```bash
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/mytests/templates/nodes/nodes-backfill-100x100.yaml
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/mytests/templates/nodes/nodes-backfill-10x100.yaml
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/mytests/templates/nodes/nodes-cleanup.yaml
```
```bash
  kubectl -n default delete job --all
  kubectl -n default delete localqueue --all
  kubectl -n default delete clusterqueue --all
  kubectl -n default delete resourceflavor --all
```
```bash
  ./bin/knavigator -workflow resources/mytests/backfill/kueue/test2/run-test-10x100.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/kueue/test2/run-test-10x100-multiple-queues.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/kueue/test2/run-test-100x100.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/kueue/test2/run-test-100x100-multiple-queues.yaml
```
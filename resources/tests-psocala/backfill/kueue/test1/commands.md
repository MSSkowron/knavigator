
```bash
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-backfill-1.yaml
```
```bash
  kubectl -n default delete job --all
  kubectl -n default delete localqueue --all
  kubectl -n default delete clusterqueue --all
  kubectl -n default delete resourceflavor --all
```
```bash
  ./bin/knavigator -workflow resources/tests-psocala/backfill/kueue/test1/run-test-100x100.yaml
```
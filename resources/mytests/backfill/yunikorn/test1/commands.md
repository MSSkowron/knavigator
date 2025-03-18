
```bash
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/mytests/templates/nodes/nodes-backfill-1.yaml
```
```bash
  kubectl -n default delete job --all
```
```bash
  ./bin/knavigator -workflow resources/mytests/backfill/yunikorn/test1/run-test-100x100.yaml
```
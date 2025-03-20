
```bash
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/mytests/templates/nodes/nodes-backfill-10x100.yaml
```
```bash
  kubectl -n default delete job --all
```
```bash
  ./bin/knavigator -workflow resources/mytests/backfill/yunikorn/test2/run-test-10x100.yaml
```
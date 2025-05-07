
```bash
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-backfill-1.yaml
```
```bash
  kubectl -n default delete job --all
```
```bash
  ./bin/knavigator -workflow resources/tests-psocala/backfill/yunikorn/test1/run-test-100x100.yaml
```
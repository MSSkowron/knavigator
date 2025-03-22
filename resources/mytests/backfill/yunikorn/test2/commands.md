
```bash
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/mytests/templates/nodes/nodes-backfill-10x100.yaml
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/mytests/templates/nodes/nodes-backfill-100x100.yaml
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/mytests/templates/nodes/nodes-cleanup.yaml
```
```bash
  kubectl -n default delete job --all
```
```bash
  ./bin/knavigator -workflow resources/mytests/backfill/yunikorn/test2/run-test-10x100.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/yunikorn/test2/run-test-10x100-fifo.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/yunikorn/test2/run-test-10x100-fifo-gang.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/yunikorn/test2/run-test-10x100-fair.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/yunikorn/test2/run-test-10x100-big-queue.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/yunikorn/test2/run-test-10x100-fifo-big-queue.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/yunikorn/test2/run-test-10x100-fair-big-queue.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/yunikorn/test2/run-test-10x100-fifo-separate-queues.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/yunikorn/test2/run-test-10x100-fair-separate-queues.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/yunikorn/test2/run-test-10x100-fifo-reversed.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/yunikorn/test2/run-test-100x100.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/yunikorn/test2/run-test-100x100-fifo.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/yunikorn/test2/run-test-100x100-fair.yaml
```
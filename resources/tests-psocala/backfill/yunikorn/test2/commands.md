
```bash
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-backfill-10x100.yaml
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-backfill-35x100.yaml
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-backfill-100x100.yaml
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-cleanup.yaml
  ./scripts/create-test-cluster.sh
  ./monitoring-portforward.sh
```
```bash
  kubectl -n default delete job --all
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-cleanup.yaml
```
```bash
  ./bin/knavigator -workflow resources/tests-psocala/backfill/yunikorn/test2/run-test-10x100-fifo.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/yunikorn/test2/run-test-10x100-fifo-gang.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/yunikorn/test2/run-test-10x100-fair.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/yunikorn/test2/run-test-10x100-big-big-queue.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/yunikorn/test2/run-test-10x100-fifo-big-big-queue.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/yunikorn/test2/run-test-10x100-fair-big-big-queue.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/yunikorn/test2/run-test-10x100-fair-separate-queues.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/yunikorn/test2/run-test-10x100-fifo-reversed.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/yunikorn/test2/run-test-100x100-fifo.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/yunikorn/test2/run-test-100x100-fair.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/yunikorn/test2/run-test-10x100.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/yunikorn/test2/run-test-10x100-fifo-separate-queues.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/yunikorn/test2/run-test-35x100.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/yunikorn/test2/run-test-35x100-fifo-separate-queues.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/yunikorn/test2/run-test-100x100.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/yunikorn/test2/run-test-100x100-fifo-separate-queues.yaml
```
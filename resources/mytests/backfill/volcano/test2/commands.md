```bash
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/mytests/templates/nodes/nodes-backfill-100x100.yaml
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/mytests/templates/nodes/nodes-backfill-35x100.yaml
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/mytests/templates/nodes/nodes-backfill-10x100.yaml
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/mytests/templates/nodes/nodes-cleanup.yaml
```
```bash
  kubectl delete queue big-queue
  kubectl delete queue queue-a
  kubectl delete queue queue-b
  kubectl delete queue queue-c
  kubectl delete jobs.batch.volcano.sh --all
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/mytests/templates/nodes/nodes-cleanup.yaml
  
```
```bash
  ./bin/knavigator -workflow resources/mytests/backfill/volcano/test2/config-volcano.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/volcano/test2/cleanup.yaml
  kubectl create -f resources/mytests/templates/volcano/big-queue.yaml
  kubectl create -f resources/mytests/templates/volcano/queue-a.yaml
  kubectl create -f resources/mytests/templates/volcano/queue-b.yaml
  kubectl create -f resources/mytests/templates/volcano/queue-c.yaml
```
```bash
  ./bin/knavigator -workflow resources/mytests/backfill/volcano/test2/run-test-10x100-big-queue.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/volcano/test2/run-test-10x100-binpack.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/volcano/test2/run-test-10x100-drf.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/volcano/test2/run-test-10x100.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/volcano/test2/run-test-10x100-proportion.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/volcano/test2/run-test-35x100.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/volcano/test2/run-test-35x100-proportion.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/volcano/test2/run-test-100x100.yaml
  ./bin/knavigator -workflow resources/mytests/backfill/volcano/test2/run-test-100x100-proportion.yaml
```
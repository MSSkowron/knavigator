Cluster setup
```bash
  ./scripts/create-test-cluster.sh
  ./monitoring-portforward.sh
```
Cleanup commands
```bash
  kubectl delete queue queue-a
  kubectl delete queue queue-b
  kubectl delete queue queue-c
  kubectl delete jobs.batch.volcano.sh --all
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-cleanup.yaml
```
Volcano setup for multiple queues scenario
```bash
  kubectl create -f resources/tests-psocala/templates/volcano/queue-a.yaml
  kubectl create -f resources/tests-psocala/templates/volcano/queue-b.yaml
  kubectl create -f resources/tests-psocala/templates/volcano/queue-c.yaml
```
Test scenarios
```bash
  ./bin/knavigator -workflow resources/tests-psocala/backfill/volcano/test2-backfill-performance/run-test-10x100.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/volcano/test2-backfill-performance/run-test-10x100-multiple-queues.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/volcano/test2-backfill-performance/run-test-35x100.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/volcano/test2-backfill-performance/run-test-35x100-multiple-queues.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/volcano/test2-backfill-performance/run-test-100x100.yaml
  ./bin/knavigator -workflow resources/tests-psocala/backfill/volcano/test2-backfill-performance/run-test-100x100-multiple-queues.yaml
```
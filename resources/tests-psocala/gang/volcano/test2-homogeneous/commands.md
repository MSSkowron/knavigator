
```bash
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-gang-2.yaml
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-cleanup.yaml
  ./scripts/create-test-cluster.sh
  ./monitoring-portforward.sh
```
```bash
  kubectl delete jobs.batch.volcano.sh --all
  helm upgrade --install virtual-nodes charts/virtual-nodes -f resources/tests-psocala/templates/nodes/nodes-cleanup.yaml
  kubectl -n volcano-system delete pod --all
```
```bash
  ./bin/knavigator -workflow resources/tests-psocala/gang/volcano/test2-homogeneous/run-test-small-cluster-10-pods.yaml
  ./bin/knavigator -workflow resources/tests-psocala/gang/volcano/test2-homogeneous/run-test-small-cluster-100-pods.yaml
  ./bin/knavigator -workflow resources/tests-psocala/gang/volcano/test2-homogeneous/run-test-big-cluster-10-pods.yaml
  ./bin/knavigator -workflow resources/tests-psocala/gang/volcano/test2-homogeneous/run-test-big-cluster-100-pods.yaml
```

```bash
kubectl -n volcano-system patch deployment volcano-admission \
  --type='json' \
  -p='[
    {"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kube-api-qps=1500"},
    {"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kube-api-burst=3000"}
  ]'
```
```bash
kubectl patch validatingwebhookconfiguration volcano-admission-service-pods-validate \
  --type=json -p='[{"op":"replace","path":"/webhooks/0/timeoutSeconds","value":30}]'
```
```bash
kubectl patch validatingwebhookconfiguration volcano-admission-service-jobs-validate \
  --type=json -p='[{"op":"replace","path":"/webhooks/0/timeoutSeconds","value":30}]'
```
# Benchmark Tests

This directory contains benchmark tests for the following workload managers and schedulers:

- Kueue
- Volcano
- Yunikorn

The benchmark tests involve submitting workloads intended to evaluate the scheduler's performance under specific scenarios.

These workloads are designed to fully utilize the cluster under optimal scheduling conditions.

One approach to benchmarking is to run this workload on clusters with different schedulers and then compare the average GPU occupancy of the nodes.

For all workload managers, the benchmark test involves two sequential workflows. The first workflow registers the CRDs, and the second workflow runs the common part of the test.

## Gang Scheduling Benchmark

Gang scheduling is a critical capability for AI and ML workloads where all pods in a job must be scheduled simultaneously to prevent resource deadlocks and inefficiencies.

The benchmark workflow operates on 32 virtual GPU nodes, submitting a burst of 53 jobs with replica numbers ranging from 1 to 32 in a [predetermined order](gang-scheduling/workflows/run-test.yaml).

For Kueue:

```bash
./bin/knavigator -workflow "./resources/benchmarks/gang-scheduling/workflows/{config-nodes.yaml,config-kueue.yaml,run-test.yaml}"
```

For Volcano:

```bash
./bin/knavigator -workflow "./resources/benchmarks/gang-scheduling/workflows/{config-nodes.yaml,config-volcano.yaml,run-test.yaml}"
```

For YuniKorn:

```bash
./bin/knavigator -workflow "./resources/benchmarks/gang-scheduling/workflows/{config-nodes.yaml,config-yunikorn.yaml,run-test.yaml}"
```

For Coscheduling:

```bash
./bin/knavigator -workflow "./resources/benchmarks/gang-scheduling/workflows/{config-nodes.yaml,config-combo-coscheduling.yaml,run-test.yaml}"
```

## Performance

### V1

For Kueue:

```bash
./bin/knavigator -workflow "./resources/benchmarks/performance/workflows/{kueue-v1.yaml}" -v 4
```

For Volcano:

```bash
./bin/knavigator -workflow "./resources/benchmarks/performance/workflows/{volcano-v1.yaml}" -v 4
```

For YuniKorn:

```bash
./bin/knavigator -workflow "./resources/benchmarks/performance/workflows/{yunikorn-v1.yaml}" -v 4
```

### V2

For Kueue:

```bash
./bin/knavigator -workflow "./resources/benchmarks/performance/workflows/{kueue-v2.yaml}" -v 4
```

For Volcano:

```bash
./bin/knavigator -workflow "./resources/benchmarks/performance/workflows/{volcano-v2.yaml}" -v 4
```

For YuniKorn:

```bash
./bin/knavigator -workflow "./resources/benchmarks/performance/workflows/{yunikorn-v2.yaml}" -v 4
```

### V3

For Kueue:

```bash
./bin/knavigator -workflow "./resources/benchmarks/performance/workflows/{kueue-v3.yaml}" -v 4
```

For Volcano:

```bash
./bin/knavigator -workflow "./resources/benchmarks/performance/workflows/{volcano-v3.yaml}" -v 4
```

For YuniKorn:

```bash
./bin/knavigator -workflow "./resources/benchmarks/performance/workflows/{yunikorn-v3.yaml}" -v 4
```

## Topology Aware Benchmark

The topology aware benchmark evaluates a scheduler's ability to intelligently place pods based on topology considerations. This capability is crucial for distributed workloads like deep learning training, where inter-pod communication latency can significantly impact performance.

This benchmark creates a simulated network topology with various layers (datacenter, spine, block, accelerator) and tests how well each scheduler can place pods to minimize network distances between collaborating pods.

### Topology Structure

The benchmark configures 12 nodes with a tree-like network topology:

![topology aware scheduling](../../docs/assets/network-aware-scheduling.png)

In this diagram:

- Nodes n1, n3, n6, n11, and n12 are marked as unschedulable (X)
- Nodes n5, n7, and n8 are marked as "optimal" for network topology considerations

### Test Methodology

- **Node Setup**: The test creates 12 virtual nodes with network topology labels at different levels:

  - network.topology.kubernetes.io/datacenter: Top-level network segment
  - network.topology.kubernetes.io/spine: Mid-level network segment
  - network.topology.kubernetes.io/block: Low-level network segment
  - Some configurations also include network.topology.kubernetes.io/accelerator for NVLink-aware scheduling

- **Workload**: A job with 3 pods requiring co-location for optimal performance is submitted to the cluster.

- **Evaluation**: Success is measured by whether the scheduler places all 3 pods on the optimal nodes (n5, n7, n8) that have been marked with net-optimal: true and have the lowest network distance between them.

### Scheduler-Specific Implementations

#### Kueue Topology Benchmark

Kueue's implementation focuses on resource flavors and affinity rules:

- **Resource Flavors**: Defines a net-optimal-nodes flavor targeting nodes with optimal network characteristics
- **Affinity Rules**: Uses both nodeAffinity to prefer optimal nodes and podAffinity with block and spine topology keys
- **Test Pattern**: Submits a job with 3 replicas and validates pod placement

```bash
./bin/knavigator -workflow "./resources/benchmarks/topology-aware/workflows/{config-nodes.yaml,config-kueue.yaml,run-test.yaml}"
```

#### Volcano Topology Benchmark

Volcano's implementation leverages its plugin system:

- **Scheduler Plugins**: Configures the nodeorder plugin with network topology weights
- **Predicates**: Uses LabelsPresence to filter for optimal nodes
- **Gang Scheduling**: Ensures all pods in the job are scheduled together

```bash
./bin/knavigator -workflow "./resources/benchmarks/topology-aware/workflows/{config-nodes.yaml,config-volcano.yaml,run-test.yaml}"
```

#### YuniKorn Topology Benchmark

YuniKorn's implementation uses placement rules and scheduling policies:

- **Placement Rules**: Configures tag-based placement to target optimal nodes
- **Scheduling Policies**: Creates a custom default-topology-aware policy with node ordering weights
- **Task Groups**: Uses gangScheduling with affinity terms to optimize placement

```bash
./bin/knavigator -workflow "./resources/benchmarks/topology-aware/workflows/{config-nodes.yaml,config-yunikorn.yaml,run-test.yaml}"
```

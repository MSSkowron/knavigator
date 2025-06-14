# Kubernetes Scheduler Benchmark Scenarios

This repository contains a collection of benchmark scenarios designed to evaluate and compare the performance of various Kubernetes schedulers. The tests are organized into major scheduling concepts, primarily focusing on **Backfill** and **Gang Scheduling**.

Each test scenario is located in its respective directory (e.g., `backfill/`, `gang/`). Within these, you will find subdirectories for each scheduler being tested (e.g., `kueue`, `volcano`, `yunikorn`, and the default `k8s` scheduler).

The structure for each test is generally as follows:
- `commands.md`: A file containing useful, aggregated commands for setting up the environment and running the test scenario.
- `run-test-*.yaml`: Knavigator Workflow definitions that execute the specific test logic and job submissions.

---

## Backfill Scheduling

The tests in the `backfill/` directory are designed to assess the backfilling capabilities of different schedulers. Backfilling is a scheduling optimization that allows smaller, lower-priority jobs to run on available resources, even if higher-priority jobs are waiting.

We distinguish between two main types of backfilling:
- **Greedy Backfill**: The scheduler fills available resource gaps with any jobs that fit based on current resource availability. This can be efficient but risks starving larger jobs if a continuous stream of smaller jobs arrives.
- **HPC-like Backfill**: The scheduler uses estimated job runtimes to ensure that backfilling a smaller job will not postpone the reserved start time of a higher-priority job.

The tests are divided into two main categories.

### Test 1: HPC-like vs. Greedy Backfill Functionality

This preliminary test is designed to determine which type of backfill a scheduler implements.

- **Directory:** `test1-hpc-backfill`
- **Goal:** To verify if a scheduler considers job duration (HPC-like) or simply fills resource gaps as they appear (Greedy).
- **Setup:** A single worker node with 100 CPU and 100 GiB of memory.
- **Jobs:**
    - **Job A (High-resource):** Requests 60% of node resources (60 CPU/GiB), runs for 1 minute.
    - **Job B (Low-resource, long):** Requests 50% of node resources (50 CPU/GiB), runs for 1.5 minutes.
    - **Job C (Low-resource, short):** Requests 50% of node resources (50 CPU/GiB), runs for 0.5 minutes.
- **Methodology & Flow:**
    -  One **Job B** is submitted and starts executing, occupying 50% of the node's resources.
    -  10 seconds later, **Job A** is submitted. It cannot run as it requires 60% of resources, so it enters a pending state.
    -  20 seconds later, a second **Job B** is submitted. An HPC-like scheduler would not schedule this job, as it would delay the pending Job A.
    -  10 seconds later, **Job C** is submitted. An HPC-like scheduler *should* schedule this job, as it fits in the remaining 50% of resources and its 30-second runtime allows it to complete before the first Job B finishes, thus not delaying Job A.
- **Conclusion:** These tests confirmed that all evaluated schedulers implement a **greedy backfill** strategy. In practice, the second Job B was scheduled as soon as it was submitted, delaying the start of the waiting Job A. This indicates that none of the schedulers account for job duration to protect the start times of pending, higher-priority jobs.

### Test 2: Greedy Backfill Efficiency Benchmark

Given that the schedulers implement greedy backfill, this benchmark measures how efficiently they perform this task under load.

- **Directory:** `test2-backfill-performance`
- **Goal:** To assess the performance and resource utilization achieved by the scheduler's greedy backfill implementation when faced with a mixed workload.
- **Setup:**
    - All jobs are submitted to the cluster *before* any worker nodes are available.
    - Worker nodes are created only after all jobs are in a pending state. This gives the scheduler full visibility of the entire workload before it begins scheduling.
- **Jobs:**
    - **Job A:** Requests 60% of a node's capacity (60 CPU/GiB), runs for 4 minutes.
    - **Job B:** Requests 30% of a node's capacity (30 CPU/GiB), runs for 1 minute.
    - **Job C:** Requests 10% of a node's capacity (10 CPU/GiB), runs for 20 seconds.
- **Methodology & Flow:**
  The job mix is designed to create an ideal packing scenario. One "block" of jobs, consisting of **1 Job A**, **4 Jobs B**, and **12 Jobs C**, can theoretically utilize 100% of a single node's resources for exactly 4 minutes. The total workload is designed to assign two such blocks per node. With optimal scheduling, the entire cluster should run at 100% utilization for 8 minutes.
- **Test Variants:** The benchmark is executed at three different scales to test scalability. These correspond to the different `run-test-*.yaml` files:
    - **Small Cluster:** 10 nodes (`run-test-10x100.yaml`)
    - **Medium Cluster:** 35 nodes (`run-test-35x100.yaml`)
    - **Large Cluster:** 100 nodes (`run-test-100x100.yaml`)
    - *Note: Variants for testing with multiple queues also exist (e.g., `run-test-*-multiple-queues.yaml`).*
- **Key Metrics:**
    - **Turnaround Time:** The total time from when the first pod is scheduled until the last pod completes.
    - **Cluster Utilization:** The average percentage of allocated resources (CPU/memory) over the entire workload's duration.

---

## Gang Scheduling

The tests in the `gang/` directory evaluate the scheduler's ability to implement "all-or-nothing" scheduling for groups of tightly-coupled workloads. This ensures that a group of pods belonging to a single job starts together or not at all, preventing resource deadlocks and partial application execution. The benchmarks in this section evaluate Kueue, Volcano, and Yunikorn, as the default Kubernetes scheduler does not provide this functionality.

**A Note on Kueue**: To enable true gang scheduling in Kueue, these tests require the **Topology Aware Scheduling (TAS)** feature to be activated. By default, Kueue's "all-or-nothing" mechanism is based on a simple timeout, which is not sufficient for robust gang scheduling. Enabling TAS forces Kueue to consider the actual resource distribution across nodes, achieving the expected behavior.

### Test 1: Gang Scheduling Functionality

This preliminary test verifies that each scheduler correctly implements the core "all-or-nothing" logic.

- **Directory:** `test1-gang-functionality`
- **Goal:** To confirm that a job with multiple pods is only scheduled when sufficient resources exist for *all* of its pods simultaneously.
- **Methodology & Flow:** Two scenarios are executed:
  1.  **Partial Resource Test (`run-test-standard.yaml`):** A job requiring 8 pods is submitted to a cluster that can only fit 6 of them. The expected outcome is that the job remains pending and does not start partially.
  2.  **Blocking Job Test (`run-test-standard-blocking-job.yaml`):** A large "blocking" job is scheduled first, consuming most of the cluster's resources. A second, smaller job is then submitted, which cannot fit in the remaining space. This second job should remain pending until the blocking job completes, at which point it should be scheduled.
- **Conclusion:** All evaluated frameworks passed these functional tests, proving they correctly implement the fundamental principles of gang scheduling.

### Test 2: Homogeneous Cluster & Workload Benchmark

This benchmark evaluates gang scheduling performance in a controlled environment with uniform nodes and workloads.

- **Directory:** `test2-homogeneous`
- **Goal:** To measure scheduling efficiency and throughput under different scales and workload granularities.
- **Setup:** Nodes are homogeneous (100 CPU/100 GiB). Jobs consist of pods requesting 1 CPU and 1 GiB each, with a randomized runtime between 180-240 seconds to introduce variability.
- **Test Variants:** Four scenarios are tested by combining cluster size and workload granularity:
  - **Cluster Size:**
    - Small Cluster: 20 nodes
    - Big Cluster: 100 nodes
  - **Workload Granularity:**
    - Fine-grained: 500 jobs of 10 pods each (`*-10-pods.yaml`)
    - Coarse-grained: 50 jobs of 100 pods each (`*-100-pods.yaml`)
- **Key Metrics:**
  - Turnaround Time
  - CPU & Memory Utilization Percentage
  - Average Number of Running Pods

### Test 3: Heterogeneous Cluster & Workload Benchmark

This scenario evaluates gang scheduling in a more realistic environment with diverse node types and job resource requirements.

- **Directory:** `test3-heterogeneous`
- **Goal:** To assess scheduler performance with complex placement decisions involving varied resource requests and node capacities.
- **Setup:** The cluster consists of three node types (Small: 8 CPU/16 GiB, Medium: 32 CPU/64 GiB, Large: 64 CPU/128 GiB). Five different job types with varying CPU/memory requests, pod counts, and runtimes are submitted in batches.
- **Methodology & Flow:**
  The test submits batches of mixed jobs every 2 seconds. The job mix is designed to create complex scheduling puzzles, forcing the scheduler to distribute pods across different node types and handle potential resource fragmentation. Pod runtimes are randomized to ensure dynamic resource deallocation.
- **Test Variants:**
  - **Standard Load (`run-test-standard.yaml`):** A total of 650 jobs are submitted.
  - **Extensive Load (`run-test-large.yaml`):** A total of 1300 jobs are submitted to further stress the scheduler.
- **Key Metrics:**
  - Turnaround Time
  - CPU & Memory Utilization Percentage
  - Average Number of Running Pods
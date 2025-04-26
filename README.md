<p align="center"><a href="https://github.com/NVIDIA/knavigator" target="_blank"><img src="docs/assets/knavigator-logo.png" width="100" alt="Logo"></a></p>

# Knavigator

![Build Status](https://github.com/NVIDIA/knavigator/actions/workflows/go.yml/badge.svg)
![Static Badge](https://img.shields.io/badge/license-Apache_2.0-green)

## Overview

Knavigator is a project designed to analyze, optimize, and compare scheduling systems, with a focus on AI/ML workloads. It addresses various needs, including testing, troubleshooting, benchmarking, chaos engineering, performance analysis, and optimization.

The term "knavigator" is derived from "navigator," with a silent "k" prefix representing "kubernetes." Much like a navigator, this initiative assists in charting a secure route and steering clear of obstacles within the cluster.

Knavigator interfaces with Kubernetes clusters to manage tasks such as manipulating with Kubernetes objects, evaluating PromQL queries, as well as executing specific operations.

Knavigator can operate both outside and inside a Kubernetes cluster, leveraging the Kubernetes API for task management.

To facilitate large-scale experiments without the overhead of running actual user workloads, Knavigator utilizes [KWOK](https://kwok.sigs.k8s.io/) for creating virtual nodes in extensive clusters.

## Architecture

![knavigator architecture](docs/assets/knavigator-design.png)

### Components

- **K8S control plane**: a set of components that manage the state and configuration of a vanilla Kubernetes cluster.
- **Scheduling Framework**: cloud-native job scheduling system for batch, HPC, AI/ML, and similar applications in a Kubernetes cluster.
- **KWOK**: Allows for the rapid setup of simulated Kubernetes clusters with minimal resource usage.
- **Knavigator**: Facilitates communication with the Kubernetes cluster via the Kubernetes API, enabling task management and data retrieval.
- **Metrics & Dashboard**: Gathers and processes metrics from the cluster, focusing on scheduling performance and resource utilization.

### Workflow

Knavigator offers versatile configuration options, allowing it to function independently, serve as an HTTP/gRPC server, or seamlessly integrate as a package or library within other systems.

In its standalone mode, Knavigator can be set up using a descriptive YAML file, where users specify the sequence of tasks to be executed. This mode is ideal for isolated testing scenarios where Knavigator operates independently.

Alternatively, in server or package configurations, Knavigator can receive a series of API calls to define the tasks to be performed. This mode facilitates integration with existing systems or frameworks, providing flexibility in how tasks are defined and managed.

Regardless of the configuration mode, Knavigator executes tasks sequentially. Each task is dependent on the successful completion of the preceding one. Therefore, if any task fails during execution, the entire test is marked as failed. This ensures comprehensive testing and accurate reporting of results, maintaining the integrity of the testing process.

## Getting Started

### Prerequisites

Ensure you have the following tools installed on your system before proceeding:

- [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation): For creating local Kubernetes clusters
- [helm](https://helm.sh/docs/helm/helm_install/): The package manager for Kubernetes
- [kubectl](https://kubernetes.io/docs/tasks/tools/#kubectl): The Kubernetes command-line tool

Important notes:

- A real node (like kind's) is required for proper scheduling framework or workload manager functionality
- Deploying the workload manager on a virtual node will cause it to malfunction
- If you have existing virtual nodes or workloads, clean them up:

    ```bash
    kubectl delete node -l type=kwok
    ```

### Installation

1. Clone the repository

    ```bash
    git clone https://github.com/NVIDIA/knavigator.git
    cd knavigator
    ```

2. Build the binary

    ```bash
    make build
    ```

3. Create and configure the test cluster

    ```bash
    ./scripts/create-test-cluster.sh
    ```

    This script will:
    - Create a kind cluster if one doesn't exist
    - Deploy Prometheus and Grafana for monitoring
    - Deploy KWOK for simulating nodes
    - Prompt you to select a workload manager (Kueue, Volcano, or YuniKorn)
    - Create additional dashboards for monitoring

### Monitoring Setup

Use the provided script to set up port forwarding for both services:

```bash
./monitoring-portforward.sh
```

- Grafana dashboard
  - URL: <http://localhost:8080>
  - Credentials:
    - Username: `admin`
    - Password: `admin`

- Prometheus dashboard
  - URL: <http://localhost:9090>

### Virtual Nodes

KWOK allows you to extend your cluster with virtual nodes that simulate real Kubernetes nodes but without consuming actual hardware resources. These virtual nodes can be configured and managed through Knavigator workflows.

#### Configuration with Knavigator

The simplest way to create virtual nodes is through Knavigator's `Configure` task:

```yaml
- id: configure
  type: Configure
  params:
    nodes:
    - type: dgxa100.80g
      count: 2
      labels:
        nvidia.com/gpu.count: "8"
    timeout: 1m
```

This example creates 2 virtual nodes with the dgxa100.80g type and NVIDIA GPU labels.

#### Pre-defined Node Types

Knavigator supports several pre-defined node types:

- `dgxa100.40g`: NVIDIA DGX A100 with 40GB GPUs
- `dgxa100.80g`: NVIDIA DGX A100 with 80GB GPUs
- `dgxh100.80g`: NVIDIA DGX H100 with 80GB GPUs

For these types, the resource attributes are pre-configured, but you can still modify `count`, `annotations`, `labels`, and `conditions`.

#### Custom Node Configuration

For custom node types, you can specify detailed resource configurations:

```yaml
- type: cpu.x86
  count: 2
  resources:
    hugepages-1Gi: 0
    hugepages-2Mi: 0
    pods: 110
    cpu: 48
    memory: 196692052Ki
    ephemeral-storage: 2537570228Ki
  labels:
    custom-label: "value"
  annotations:
    custom-annotation: "value"
```

#### Using Helm Charts

You can also manage virtual nodes directly with Helm charts:

1. Configure your virtual nodes in a values file (e.g., `values-custom.yaml`):

    ```yaml
    - type: dgxa100.80g
      count: 4
      labels:
        nvidia.com/gpu.count: "8"
    ```

2. Deploy or update the virtual nodes:

    ```bash
    helm upgrade --install virtual-nodes charts/virtual-nodes -f values-custom.yaml
    ```

3. Verify the deployment:

    ```bash
    kubectl get nodes
    kubectl get node <node-name> -o yaml # View detailed node configuration
    ```

4. To remove virtual nodes:

    ```bash
    helm uninstall virtual-nodes
    ```

**Warning**: Deploy virtual nodes as the final step before launching knavigator. If you deploy components after virtual nodes are created, the pods for these components might be assigned to virtual nodes, which could impact their functionality.

### Using Knavigator

Knavigator requires the `KUBECONFIG` environment variable or the presence of the `-kubeconfig` (kube config) or `-kubectx` (kube context) command-line arguments.

To run a workflow:

```bash
./bin/knavigator -workflow <workflow>
```

Command-line options:

- `workflow`: Path to workflow configuration file(s)
- `cleanup`: Remove objects created during test execution
- `v <level>`: Set verbosity level (e.g., -v 4 for detailed logs)
- `kubeconfig`: Path to kubeconfig file (optional if KUBECONFIG environment variable is set)
- `kubectx`: Kubernetes context to use
- `port`: Run Knavigator as a server listening on the specified port

Examples:

```bash
# Run a simple job workflow
./bin/knavigator -workflow resources/workflows/k8s/test-job.yml -cleanup

# Run multiple workflows in sequence
./bin/knavigator -workflow 'resources/workflows/{config-nodes.yaml,kueue/test-job.yaml}'

# Run with increased verbosity
./bin/knavigator -workflow resources/workflows/volcano/test-job.yml -v 4 -cleanup
```

### Creating workflows

Workflows are defined in YAML files and consist of sequential tasks that Knavigator executes in order. Each task performs a specific operation, such as registering Kubernetes object templates, creating/configuring resources, or validating states and conditions.

#### Basic Structure

Every workflow YAML file follows this basic structure:

```yaml
name: my-workflow-name
description: Detailed description of what this workflow does
tasks:
- id: first-task
  type: TaskType
  description: Optional description of this specific task
  params:
    # task-specific parameters
- id: second-task
  type: TaskType
  params:
    # task-specific parameters
```

#### Key Concepts

- **Sequential Execution**: By default, tasks are executed sequentially. If a task fails, the workflow stops unless modified by control flow tasks.
- **Unique IDs**: Each task must have a unique id within the workflow. Tasks defined within `ParallelTask` or `RepeatTask` have their IDs ignored and dynamically generated to prevent conflicts during runtime.
- **Task References**: Tasks can reference other tasks using refTaskId to establish dependencies (e.g., `SubmitObj` referencing `RegisterObj`). This is typically used between top-level sequential tasks.
- **Timeouts**: Most tasks support a timeout parameter to limit execution time.
- **Parameter Propagation**: Values generated in one task (like object names via nameFormat) can be referenced in subsequent tasks.

#### Task Types

- `RegisterObj`

    Registers Kubernetes object templates for later use in the workflow.

    ```yaml
   - id: register
     type: RegisterObj
     params:
       # Required: Path to the template file
       template: "resources/templates/k8s/job.yml"

       # Required: Template for generating unique object names
       # Uses _ENUM_ as an incrementing counter
       # The result is stored as _NAME_ in the parameter map
       nameFormat: "job{{._ENUM_}}"

       # Optional: Pattern for matching pod names created by this object
       # Uses _NAME_ to reference the parent object's name
       # Required when using CheckPod task
       podNameFormat: "{{._NAME_}}-[0-9]-.*"

       # Optional: Number of pods expected per object
       # Can be a fixed number or template expression
       # Required when using CheckPod task
       podCount: "{{.parallelism}}"
    ```

- `SubmitObj`

    Creates Kubernetes objects using templates registered by a previous `RegisterObj` task.

    ```yaml
   - id: submit
     type: SubmitObj
     params:
       # Required: References the RegisterObj task
       refTaskId: register

       # Optional: Number of object instances to create (default: 1)
       # When count > 1, the referenced RegisterObj must specify nameFormat
       count: 2

       # Optional: If true, doesn't error when object already exists
       canExist: true

       # Optional: Parameters for template substitution
       # These replace placeholders in the template
       params:
         namespace: default
         parallelism: 2
         completions: 2
         image: ubuntu
         cpu: 100m
         memory: 512M
    ```

- `UpdateObj`

   Updates existing objects with new values. Useful for modifying object state.

   ```yaml
   - id: update
     type: UpdateObj
     params:
       # Required: References the SubmitObj task that created the object
       refTaskId: submit

       # Required: New state to apply to the object
       state:
         spec:
           parallelism: 3
         status:
           someField: newValue

       # Optional: Timeout for the update operation
       timeout: 30s
   ```

- `DeleteObj`

    Removes objects created by a previous task.

    ```yaml
   - id: cleanup
     type: DeleteObj
     params:
       # Required: References the task that created the objects to delete
    refTaskId: submit
    ```

- `Configure`

    Creates and configures various Kubernetes resources. This versatile task can manage virtual nodes, namespaces, ConfigMaps, PriorityClasses, and deployment restarts.

    ```yaml
   - id: configure
     type: Configure
     params:
       # Optional: Configure virtual nodes
       nodes:
       - type: dgxa100.80g    # Node type (predefined or custom)
         count: 2             # Number of nodes to create
         labels:              # Node labels
           nvidia.com/gpu.count: "8"
         annotations: {}      # Optional annotations
         conditions: []       # Optional node conditions

       # Optional: Manage namespaces
       namespaces:
       - name: test-namespace
         op: create           # Operation: create or delete

       # Optional: Manage ConfigMaps
       configmaps:
       - name: test-config
         namespace: default
         op: create           # Operation: create or delete
         data:                # ConfigMap data (for create operations)
           key1: value1
           key2: value2

       # Optional: Manage PriorityClasses
       priorityClasses:
       - name: high-priority
         value: 90            # Priority value (required for create)
         op: create           # Operation: create or delete

       # Optional: Restart deployments
       deploymentRestarts:
       - name: my-deployment  # Deployment name (exclusive with labels)
         namespace: default   # Required namespace
         # OR use labels to select deployments:
         # labels:
         #   app: my-app

       # Required: Timeout for all configuration operations
       timeout: 1m
    ```

- `UpdateNodes`

    Updates existing nodes based on selectors. Useful for marking nodes as unschedulable or changing node properties.

    ```yaml
   - id: node-update
     type: UpdateNodes
     params:
       # Required: Selectors to identify nodes to update
       selectors:
       - key1: value1     # Nodes matching all these labels will be updated
       - key2: value2     # Multiple selectors work as OR condition

       # Required: New state to apply to matching nodes
       state:
         spec:
           unschedulable: true    # Mark nodes as unschedulable
         # Can also update other node properties

       # Optional: Timeout for the operation
       timeout: 30s
    ```

- `CheckObj`

    Validates object states and conditions. Useful for checking if objects have reached expected states.

    ```yaml
   - id: verify
     type: CheckObj
     params:
       # Required: References the task that created the objects to check
       refTaskId: submit

       # Required: Expected state to verify
       state:
         status:
           active: 3
           succeeded: 0

       # Optional: Timeout for verification
       timeout: 10s
    ```

- `CheckPod`

   Specifically validates pod states, which is useful for verifying that pods are in the expected state (Running, Succeeded, etc.) and on nodes with expected labels.

    ```yaml
   - id: verify-pods
     type: CheckPod
     params:
       # Required: References the task that created the objects whose pods to check
       refTaskId: submit

       # Required: Expected pod status (Running, Succeeded, Failed, etc.)
       status: Running

       # Optional: Verify pods are on nodes with these labels
       nodeLabels:
         nvidia.com/gpu.count: "8"

       # Optional: Timeout for verification
       timeout: 5s
    ```

- `CheckConfigmap`

    Validates ConfigMap content by comparing it with expected values.

    ```yaml
   - id: verify-config
     type: CheckConfigmap
     params:
       # Required: ConfigMap name to check
       name: my-configmap

       # Required: Namespace where the ConfigMap is located
       namespace: default

       # Required: Expected data to verify
       data:
         key1: value1

       # Required: Comparison operation
       # - equal: Exact match (all keys and values must match)
       # - subset: Data must contain at least these keys with matching values
       op: subset
    ```

- `Sleep`

    Introduces delays between tasks. Useful for waiting before checking resource states.

    ```yaml
    - id: wait
      type: Sleep
      params:
        # Required: Duration to wait
        timeout: 5s
    ```

- `Pause`

    Pauses workflow execution until manual intervention. Useful for debugging or manual verification.

    ```yaml
    - id: manual-check
      type: Pause
    ```

- `Parallel`

    Executes a defined list of sub-tasks concurrently. This task completes successfully only if all its sub-tasks complete successfully. If any sub-task fails, the Parallel task fails immediately (though other running parallel sub-tasks might continue until completion or cancellation). This is useful for running independent operations simultaneously.

    Note: Any id specified for the sub-tasks within the tasks list will be ignored. Knavigator generates unique internal IDs for each sub-task during parallel execution to prevent conflicts. Sub-tasks within Parallel cannot directly reference each other using refTaskId.

    ```yaml
    - id: parallel-ops
      type: Parallel
      params:
        # Required: A list of task configurations to execute concurrently.
        tasks:
          - type: SubmitObj # Example: Submit a batch of jobs of type a
            params:
              refTaskId: register-batch-job-a
              count: 10
              params:
                # ... job parameters
          - type: SubmitObj # Example: Submit a batch of jobs of type b
            params:
              refTaskId: register-batch-job-b
              count: 10
              params:
                # ... job parameters
    ```

- `Repeat`

    Executes a sequence of defined sub-tasks repeatedly based on either a specified total duration or a fixed count of iterations. An optional interval can introduce a pause between the end of one iteration and the start of the next. The loop terminates if the duration/count limit is reached, if the workflow context is cancelled (e.g., Ctrl+C), or if any sub-task within an iteration fails.

    Note: Any id specified for the sub-tasks within the tasks list will be ignored. Knavigator generates unique internal IDs for each sub-task within each iteration (e.g., repeat-task-id-iter0-sub0, repeat-task-id-iter0-sub1, repeat-task-id-iter1-sub0, etc.) to prevent conflicts. Sub-tasks within a Repeat iteration cannot directly reference each other using refTaskId.

    ```yaml
    - id: periodic-check
      type: Repeat
      params:
        # Required: Specify EITHER 'duration' OR 'count'. One must be non-empty/positive.
        duration: "5m"     # Example: Repeat the sequence for 5 minutes.
        # count: 10        # Example: Repeat the sequence exactly 10 times.

        # Optional: Pause duration between iterations (e.g., "15s", "1m"). Default is 0 (no pause).
        interval: "30s"

        # Required: A list of task configurations to execute sequentially in EACH iteration.
        tasks:
          - type: CheckObj # Example: Check object status periodically
            params:
              refTaskId: some-monitored-object # Assumes this task exists outside the loop
              state:
                status:
                  phase: Running
              # Note: CheckObj doesn't have its own timeout; use workflow timeout or Repeat duration.
              # If this check fails in any iteration, the Repeat task fails.
          - type: Sleep # Example: A short pause within the iteration sequence
            params:
              timeout: 2s
    ```

#### Examples

##### Example 1: Basic Job Test

```yaml
name: test-k8s-job
description: Submit and validate a Kubernetes job
tasks:
- id: register
  type: RegisterObj
  params:
    template: "resources/templates/k8s/job.yml"
    nameFormat: "job{{._ENUM_}}"
    podNameFormat: "{{._NAME_}}-[0-9]-.*"
    podCount: "{{.parallelism}}"

- id: configure
  type: Configure
  params:
    nodes:
    - type: dgxa100.80g
      count: 2
      labels:
        nvidia.com/gpu.count: "8"
    timeout: 1m

- id: job
  type: SubmitObj
  params:
    refTaskId: register
    count: 1
    params:
      namespace: default
      parallelism: 2
      completions: 2
      image: ubuntu
      cpu: 100m
      memory: 512M
      gpu: 8
      ttl: "10s"

- id: status
  type: CheckPod
  params:
    refTaskId: job
    status: Running
    timeout: 5s
```

##### Example 2: Preemption Test

This example tests scheduler preemption by creating low and high priority jobs:

```yaml
name: test-preemption
description: Test scheduler preemption with priority classes
tasks:
- id: register
  type: RegisterObj
  params:
    template: "resources/templates/kueue/job.yaml"
    nameFormat: "job{{._ENUM_}}"
    podNameFormat: "{{._NAME_}}-[0-9]-.*"
    podCount: "{{.parallelism}}"

- id: configure
  type: Configure
  params:
    nodes:
    - type: dgxa100.80g
      count: 4
      labels:
        nvidia.com/gpu.count: "8"
    priorityClasses:
    - name: high-priority
      value: 90
      op: create
    - name: low-priority
      value: 30
      op: create
    timeout: 1m

- id: low-priority-job
  type: SubmitObj
  params:
    refTaskId: register
    count: 1
    params:
      namespace: default
      priority: low-priority
      parallelism: 3
      completions: 3
      image: ubuntu
      cpu: 100m
      memory: 512M
      gpu: 8

- id: verify-low-running
  type: CheckPod
  params:
    refTaskId: low-priority-job
    status: Running
    timeout: 5s

- id: high-priority-job
  type: SubmitObj
  params:
    refTaskId: register
    count: 1
    params:
      namespace: default
      priority: high-priority
      parallelism: 2
      completions: 2
      image: ubuntu
      cpu: 100m
      memory: 512M
      gpu: 8

- id: check-preemption
  type: CheckObj
  params:
    refTaskId: low-priority-job
    state:
      status:
        ready: 0  # Low priority job should be preempted
    timeout: 5s

- id: verify-high-running
  type: CheckPod
  params:
    refTaskId: high-priority-job
    status: Running
    timeout: 5s
```

##### Example 3: ConfigMap Management & Validation

This example demonstrates how to create, modify, and verify ConfigMaps:

```yaml
name: test-configmap
description: Create, update and verify ConfigMap content
tasks:
- id: configure
  type: Configure
  params:
    configmaps:
    - name: test-config
      namespace: default
      op: create
      data:
        key1: value1
        key2: value2
    timeout: 30s

- id: verify-config
  type: CheckConfigmap
  params:
    name: test-config
    namespace: default
    data:
      key1: value1
      key2: value2
    op: equal

- id: update-config
  type: Configure
  params:
    configmaps:
    - name: test-config
      namespace: default
      op: create  # Also works for updates
      data:
        key1: new-value
        key2: value2
        key3: value3
    timeout: 30s

- id: verify-updated
  type: CheckConfigmap
  params:
    name: test-config
    namespace: default
    data:
      key1: new-value
    op: subset  # Only check specified fields
```

#### Best Practices for Workflow Creation

1. **Use Clear Task IDs**: Choose descriptive task IDs that indicate the purpose of each task.
2. **Define Timeouts**: Always specify timeouts for tasks that wait for state changes to avoid indefinite hanging.
3. **Proper Template Organization**: Store template files in a well-organized directory structure, typically under resources/templates/.
4. **Task Dependencies**: Be careful with task dependencies - ensure that referenced tasks exist and provide the expected outputs.
5. **Error Handling**: Remember that workflows stop at the first error, so order tasks to verify prerequisites before dependent operations.
6. **Template Parameters**: When creating templates, make parameters consistent and well-documented to make workflows more maintainable.
7. **Resource Cleanup**: Consider adding DeleteObj tasks at the end of workflows to clean up resources, or use the -cleanup flag when running Knavigator.

#### Finding More Examples

For more examples and reference implementations, explore the `resources/workflows/` directory in the Knavigator repository, which contains workflows for various scenarios and scheduling frameworks.

## Documentation

- [Deployment](docs/deployment.md)
- [Getting started](docs/getting_started.md)
- [Task management](docs/task_management.md)
- [Metrics and Dashboards](docs/metrics.md)
- [Benchmarking](resources/benchmarks/README.md)

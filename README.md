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

To access the Grafana dashboard:

1. Forward the Grafana service port

    ```bash
    kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 8080:80
    ```

2. Access the Grafana dashboard

    - URL: <http://localhost:8080>
    - Default credentials:
        - Username: `admin`
        - Password: `admin`

To access the Prometheus dashboard:

1. Forward the Prometheus service port

    ```bash
    kubectl port-forward -n monitoring service/kube-prometheus-stack-prometheus 9090:9090
    ```

2. Access the Prometheus dashboard

    - URL: <http://localhost:9090>

Alternatively, you can use the provided script to set up port forwarding for both services:

```bash
./monitoring-portforward.sh
```

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

### Creating a workflow

Workflows are defined in YAML files and consist of sequential tasks. Each task performs a specific operation like registering templates, configuring resources, or validating states.

Example workflows can be found in `./resources/workflows`.

##### Basic Structure

Every workflow YAML file follows this basic structure:

```yaml
name: test-name
description: description of the test
tasks:
- id: unique-task-id-1
  type: TaskType
  params:
    # task-specific parameters
- id: unique-task-id-2
  type: TaskType
  params:
    # task-specific parameters
...
```

Key Concepts:

- Each task must have a unique id
- Tasks are executed sequentially
- Tasks can reference other tasks using refTaskId
- Most tasks support timeout parameters

##### Task types

1. `RegisterObj`

    Registers Kubernetes object templates that will be used by other tasks in the workflow.

    ```yaml
    - id: register
    type: RegisterObj
    params:
        # Required: Path to the object template file (see examples in resources/templates/)
        template: "path/to/template.yaml"

        # Required: Go-template for generating unique object names
        # Uses _ENUM_ as an incrementing counter
        # The templated value is added to parameter map as _NAME_
        # Example: "job{{._ENUM_}}" generates: job1, job2, etc.
        nameFormat: "prefix{{._ENUM_}}"

        # Optional: Regular expression pattern for pod names
        # Uses _NAME_ to reference the parent object's name
        # Required when using CheckPod task
        # Example: "{{._NAME_}}-\d+-\S+" matches: job1-0-xyz, job1-1-abc
        podNameFormat: "{{._NAME_}}-[0-9]-.*"

        # Optional: Number of pods expected per object
        # Can be a fixed number or reference a template parameter
        # Required when using CheckPod task
        # Examples:
        #   - Fixed number: "2"
        #   - Template parameter: "{{.replicas}}"
        podCount: "{{.parallelism}}"
    ```

2. `SubmitObj`

    Creates Kubernetes objects from registered templates.

    ```yaml
    - id: submit-task
    type: SubmitObj
    params:
        # Required: References the ID of a RegisterObj task that defines the template
        refTaskId: string

        # Optional: Number of object instances to create (default: 1)
        # When count > 1, the referenced RegisterObj must specify nameFormat
        count: int

        # Optional: If true, doesn't error when object already exists
        canExist: boolean

        # Optional: Parameters used for template substitution
        # These values are used when executing object and name templates
        # Special parameter '_NAME_' is automatically added with the generated object name
        params:
            key1: value1
            key2: value2
    ```

3. `DeleteObj`

    Removes created objects.

    ```yaml
    - id: cleanup
    type: DeleteObj
    params:
        refTaskId: submit    # References object to delete
    ```

4. `Configure`

    Creates and configures various Kubernetes resources including virtual nodes, namespaces, configmaps, priority classes, and handles deployment restarts.

    ```yaml
    - id: configure
    type: Configure
    params:
        # Optional: Configure virtual nodes using Helm
        nodes:
        - type: string           # Required: Node type identifier
            count: int            # Required: Number of nodes to create
            annotations:          # Optional: Node annotations
            key: value
            labels:              # Optional: Node labels
            key: value
            conditions:          # Optional: Node conditions
            - key: value

        # Optional: Manage namespaces
        namespaces:
        - name: string         # Required: Namespace name
            op: string          # Required: Operation type (create/delete)

        # Optional: Manage configmaps
        configmaps:
        - name: string         # Required: ConfigMap name
            namespace: string    # Required: Namespace for the ConfigMap
            data:               # Required for create: ConfigMap data
            key: value
            op: string          # Required: Operation type (create/delete)

        # Optional: Manage priority classes
        priorityClasses:
        - name: string         # Required: PriorityClass name
            value: int          # Required for create: Priority value
            op: string          # Required: Operation type (create/delete)

        # Optional: Restart deployments
        deploymentRestarts:
        - name: string         # Optional: Deployment name (exclusive with labels)
            namespace: string    # Required: Namespace for the deployment
            labels:             # Optional: Deployment labels (exclusive with name)
            key: value

        # Required: Timeout duration for the entire configuration process
        timeout: duration       # Example: "1m", "5s"
    ```

5. `CheckObj`

    Validates object states and conditions.

    ```yaml
    - id: status
    type: CheckObj
    params:
        refTaskId: task-to-check
        state:
            status:
                key: value
        timeout: duration
    ```

6. `CheckPod`

   Specifically validates pod states.

    ```yaml
    - id: status
    type: CheckPod
    params:
        refTaskId: task-to-check
        status: Expected-Status
        nodeLabels:
            key: value
        timeout: duration
    ```

7. `Sleep`

    Introduces delays between tasks.

    ```yaml
    - id: sleep
    type: Sleep
    params:
        timeout: duration
    ```

##### Examples

1. Basic Job Test

    ```yaml
    name: test-k8s-job
    description: submit and validate a k8s job
    tasks:
    - id: register
    type: RegisterObj
    params:
        template: "resources/templates/k8s/job.yml"
        nameFormat: "job{{._ENUM_}}"
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
    - id: status
    type: CheckPod
    params:
        refTaskId: job
        status: Running
        timeout: 5s
    ```

2. Preemption Test

    ```yaml
    name: test-preemption
    description: test scheduler preemption
    tasks:
    - id: register
    type: RegisterObj
    params:
        template: "resources/templates/job.yml"
    - id: configure
    type: Configure
    params:
        nodes:
        - type: dgxa100.80g
        count: 4
        priorityClasses:
        - name: high-priority
        value: 90
        - name: low-priority
        value: 30
    - id: low-priority-job
    type: SubmitObj
    params:
        refTaskId: register
        params:
        priority: low-priority
        # other job params
    - id: high-priority-job
    type: SubmitObj
    params:
        refTaskId: register
        params:
        priority: high-priority
        # other job params
    - id: check-preemption
    type: CheckObj
    params:
        refTaskId: low-priority-job
        state:
        status:
            ready: 0
        timeout: 5s
    ```

## Documentation

- [Deployment](docs/deployment.md)
- [Getting started](docs/getting_started.md)
- [Task management](docs/task_management.md)
- [Metrics and Dashboards](docs/metrics.md)
- [Benchmarking](resources/benchmarks/README.md)

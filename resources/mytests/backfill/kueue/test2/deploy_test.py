import subprocess

# Stałe do parametryzacji joba
NAMESPACE = "default"
QUEUE_NAME = "default-local-queue"
PRIORITY = "high-priority"
COMPLETIONS = 1
PARALLELISM = 1
COMPLETION_MODE = "Indexed"
TTL = "10s"
IMAGE = "ubuntu"
CPU = 60
MEMORY = "60Gi"

# Liczba jobów do zasubmitowania
NUM_JOBS = 100

for i in range(1, NUM_JOBS + 1):
    job_name = f"test-job-{i}"
    yaml_content = f"""
apiVersion: batch/v1
kind: Job
metadata:
  name: "{job_name}"
  namespace: {NAMESPACE}
  labels:
    kueue.x-k8s.io/queue-name: {QUEUE_NAME}
    kueue.x-k8s.io/priority-class: {PRIORITY}
spec:
  completions: {COMPLETIONS}
  parallelism: {PARALLELISM}
  completionMode: {COMPLETION_MODE}
  template:
    metadata:
      annotations:
        pod-complete.stage.kwok.x-k8s.io/delay: "{TTL}"
        pod-complete.stage.kwok.x-k8s.io/jitter-delay: "{TTL}"
    spec:
      containers:
      - name: test
        image: {IMAGE}
        imagePullPolicy: IfNotPresent
        resources:
          limits:
            cpu: "{CPU}"
            memory: {MEMORY}
          requests:
            cpu: "{CPU}"
            memory: {MEMORY}
      restartPolicy: Never
    """

    # Submit YAML do Kubernetes
    process = subprocess.run(["kubectl", "apply", "-f", "-"], input=yaml_content, text=True, capture_output=False)

    # if process.returncode == 0:
    #     print(f"Job {job_name} submitted successfully.")
    # else:
    #     print(f"Failed to submit job {job_name}: {process.stderr}")

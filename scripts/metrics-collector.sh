#!/bin/bash
# metrics-collector.sh - A script to collect and analyze scheduler performance metrics

# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -e

# Configuration
PROMETHEUS_URL=${PROMETHEUS_URL:-"http://localhost:9090"}
BENCHMARK_NAMESPACE=${BENCHMARK_NAMESPACE:-"perf-benchmark"}
OUTPUT_DIR=${OUTPUT_DIR:-"./benchmark-results"}
SCHEDULER_POD_LABEL=${SCHEDULER_POD_LABEL:-"app.kubernetes.io/name=scheduler"}
SCHEDULER_NAMESPACE=${SCHEDULER_NAMESPACE:-"kube-system"}
SAMPLING_INTERVAL=${SAMPLING_INTERVAL:-"15"}  # seconds
DURATION=${DURATION:-"1800"}  # 30 minutes by default

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Start time
START_TIME=$(date +%s)
START_TIME_ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "Starting scheduler metrics collection at $START_TIME_ISO" | tee "$OUTPUT_DIR/collection.log"
echo "Collection will run for $DURATION seconds, sampling every $SAMPLING_INTERVAL seconds" | tee -a "$OUTPUT_DIR/collection.log"

# Function to query Prometheus
query_prometheus() {
    local query=$1
    local metric_name=$2
    local timestamp=$3
    
    result=$(curl -s -G --data-urlencode "query=$query" "$PROMETHEUS_URL/api/v1/query?time=$timestamp")
    
    # Extract the value
    value=$(echo "$result" | jq -r '.data.result[0].value[1]' 2>/dev/null || echo "N/A")
    
    # Save to CSV
    echo "$timestamp,$value" >> "$OUTPUT_DIR/${metric_name}.csv"
    
    echo "$metric_name: $value"
}

# Initialize CSV files with headers
echo "timestamp,value" > "$OUTPUT_DIR/scheduler_cpu_usage.csv"
echo "timestamp,value" > "$OUTPUT_DIR/scheduler_memory_usage.csv"
echo "timestamp,value" > "$OUTPUT_DIR/scheduler_pod_count.csv"
echo "timestamp,value" > "$OUTPUT_DIR/scheduler_pending_pods.csv"
echo "timestamp,value" > "$OUTPUT_DIR/scheduling_rate.csv"
echo "timestamp,value" > "$OUTPUT_DIR/scheduling_latency_p99.csv"
echo "timestamp,value" > "$OUTPUT_DIR/scheduling_errors.csv"
echo "timestamp,value" > "$OUTPUT_DIR/queue_length.csv"

# Collect Kubernetes scheduler pod info
kubectl get pods -n "$SCHEDULER_NAMESPACE" -l "$SCHEDULER_POD_LABEL" -o wide > "$OUTPUT_DIR/scheduler_pods.txt"

# Main collection loop
while true; do
    current_time=$(date +%s)
    elapsed=$((current_time - START_TIME))
    
    if [ "$elapsed" -ge "$DURATION" ]; then
        echo "Collection complete after $elapsed seconds" | tee -a "$OUTPUT_DIR/collection.log"
        break
    fi
    
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "Collecting metrics at $timestamp (elapsed: ${elapsed}s)" | tee -a "$OUTPUT_DIR/collection.log"
    
    # Scheduler CPU usage (sum across all scheduler pods)
    query_prometheus "sum(rate(container_cpu_usage_seconds_total{namespace=\"$SCHEDULER_NAMESPACE\",container=~\".*scheduler.*\"}[5m]))" "scheduler_cpu_usage" "$timestamp"
    
    # Scheduler memory usage in MB
    query_prometheus "sum(container_memory_working_set_bytes{namespace=\"$SCHEDULER_NAMESPACE\",container=~\".*scheduler.*\"}) / (1024*1024)" "scheduler_memory_usage" "$timestamp"
    
    # Number of pods in the test namespace
    query_prometheus "sum(kube_pod_info{namespace=\"$BENCHMARK_NAMESPACE\"})" "scheduler_pod_count" "$timestamp"
    
    # Number of pending pods
    query_prometheus "sum(kube_pod_status_phase{phase=\"Pending\",namespace=\"$BENCHMARK_NAMESPACE\"})" "scheduler_pending_pods" "$timestamp"
    
    # Scheduling rate (operations per second)
    query_prometheus "sum(rate(scheduler_scheduling_algorithm_duration_seconds_count[5m]))" "scheduling_rate" "$timestamp"
    
    # 99th percentile scheduling latency
    query_prometheus "histogram_quantile(0.99, sum(rate(scheduler_scheduling_algorithm_duration_seconds_bucket[5m])) by (le))" "scheduling_latency_p99" "$timestamp"
    
    # Scheduling errors
    query_prometheus "sum(rate(scheduler_scheduling_algorithm_errors_total[5m]))" "scheduling_errors" "$timestamp"
    
    # Queue length if available (depends on scheduler)
    query_prometheus "sum(scheduler_pending_pods{})" "queue_length" "$timestamp" 
    
    # Also collect current pod/node status
    if [ $((elapsed % 60)) -eq 0 ]; then
        kubectl get pods -n "$BENCHMARK_NAMESPACE" --no-headers | wc -l > "$OUTPUT_DIR/pod_count_${timestamp}.txt"
        kubectl get nodes --no-headers | wc -l > "$OUTPUT_DIR/node_count_${timestamp}.txt"
    fi
    
    sleep "$SAMPLING_INTERVAL"
done

# Generate summary report
END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))
END_TIME_ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

{
    echo "# Scheduler Performance Benchmark Summary"
    echo "- Start time: $START_TIME_ISO"
    echo "- End time: $END_TIME_ISO" 
    echo "- Total duration: $TOTAL_DURATION seconds"
    echo "- Benchmark namespace: $BENCHMARK_NAMESPACE"
    echo "- Scheduler namespace: $SCHEDULER_NAMESPACE"
    echo ""
    echo "## Key Metrics"
    
    # Calculate average, min, max for CPU usage
    cpu_avg=$(awk -F, 'NR>1 {sum+=$2; count++} END {print sum/count}' "$OUTPUT_DIR/scheduler_cpu_usage.csv")
    cpu_max=$(awk -F, 'NR>1 {if($2>max) max=$2} END {print max}' "$OUTPUT_DIR/scheduler_cpu_usage.csv")
    echo "- CPU usage (avg): $cpu_avg cores"
    echo "- CPU usage (max): $cpu_max cores"
    
    # Calculate average, min, max for memory usage
    mem_avg=$(awk -F, 'NR>1 {sum+=$2; count++} END {print sum/count}' "$OUTPUT_DIR/scheduler_memory_usage.csv")
    mem_max=$(awk -F, 'NR>1 {if($2>max) max=$2} END {print max}' "$OUTPUT_DIR/scheduler_memory_usage.csv")
    echo "- Memory usage (avg): $mem_avg MB"
    echo "- Memory usage (max): $mem_max MB"
    
    # Calculate average, min, max for scheduling rate
    rate_avg=$(awk -F, 'NR>1 {sum+=$2; count++} END {print sum/count}' "$OUTPUT_DIR/scheduling_rate.csv")
    rate_max=$(awk -F, 'NR>1 {if($2>max) max=$2} END {print max}' "$OUTPUT_DIR/scheduling_rate.csv")
    echo "- Scheduling rate (avg): $rate_avg pods/sec"
    echo "- Scheduling rate (max): $rate_max pods/sec"
    
    # Calculate average, min, max for scheduling latency
    latency_avg=$(awk -F, 'NR>1 {sum+=$2; count++} END {print sum/count}' "$OUTPUT_DIR/scheduling_latency_p99.csv")
    latency_max=$(awk -F, 'NR>1 {if($2>max) max=$2} END {print max}' "$OUTPUT_DIR/scheduling_latency_p99.csv")
    echo "- Scheduling latency p99 (avg): $latency_avg seconds"
    echo "- Scheduling latency p99 (max): $latency_max seconds"
    
    echo ""
    echo "## Pod Distribution"
    # Use the last recorded pod count
    pod_count=$(tail -1 "$OUTPUT_DIR/pod_count_"*.txt 2>/dev/null || echo "N/A")
    node_count=$(tail -1 "$OUTPUT_DIR/node_count_"*.txt 2>/dev/null || echo "N/A")
    echo "- Total pods: $pod_count"
    echo "- Total nodes: $node_count"
    
    echo ""
    echo "## Recommendations"
    if (( $(echo "$cpu_max > 2" | bc -l) )); then
        echo "- Consider scaling up scheduler CPU resources as utilization peaked at $cpu_max cores"
    fi
    
    if (( $(echo "$mem_max > 2048" | bc -l) )); then
        echo "- Consider scaling up scheduler memory resources as utilization peaked at $mem_max MB"
    fi
    
    if (( $(echo "$latency_max > 1" | bc -l) )); then
        echo "- Scheduling latency spiked to $latency_max seconds. Consider optimizing scheduler configuration."
    fi
    
} > "$OUTPUT_DIR/benchmark_summary.md"

echo "Benchmark analysis complete. Summary saved to $OUTPUT_DIR/benchmark_summary.md"
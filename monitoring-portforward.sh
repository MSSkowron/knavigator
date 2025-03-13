#!/bin/bash
# Script to set up port forwarding for monitoring tools

# Start port forwarding for Grafana
kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 8080:80 &
GRAFANA_PID=$!

# Start port forwarding for Prometheus
kubectl -n monitoring port-forward svc/kube-prometheus-stack-prometheus 9090:9090 &
PROMETHEUS_PID=$!

echo "Port forwarding started:"
echo "  - Grafana: http://localhost:8080 (admin/admin)"
echo "  - Prometheus: http://localhost:9090"
echo ""
echo "Press Ctrl+C to stop port forwarding"

# Handle cleanup on script exit
trap "kill $GRAFANA_PID $PROMETHEUS_PID 2>/dev/null" EXIT

# Wait for user to cancel
wait

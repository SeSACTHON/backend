#!/bin/bash
set -e

echo "Starting gRPC server on port 50052..."
python -m domains.my.rpc.server &
GRPC_PID=$!

echo "Starting FastAPI server on port 8000..."
opentelemetry-instrument uvicorn domains.my.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

# Wait for either process to exit
wait -n $GRPC_PID $API_PID

# If one exits, kill the other
echo "One process exited, shutting down..."
kill $GRPC_PID $API_PID 2>/dev/null || true
wait

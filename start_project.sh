#!/bin/bash

# Ensure the script exits if any command fails
set -e

# Start the Uvicorn application
echo "Starting Uvicorn application..."
uvicorn app:app --host 0.0.0.0 --port "${PORT:-8080}" --reload &
UVICORN_PID=$!

# Wait briefly to ensure Uvicorn starts before launching the dashboard
sleep 2

# Start the Streamlit dashboard
echo "Starting Streamlit dashboard..."
streamlit run dashboard.py &
STREAMLIT_PID=$!

# Function to handle termination signals
cleanup() {
    echo "Shutting down services..."
    kill "$UVICORN_PID" "$STREAMLIT_PID"
    wait
    echo "Services stopped."
}

# Trap SIGINT and SIGTERM to gracefully shut down
trap cleanup SIGINT SIGTERM

# Wait for background processes to complete
wait

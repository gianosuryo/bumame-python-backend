#!/bin/bash

if [ "$WORKER_TYPE" = "api_server" ]; then
    echo "Running in api server mode..."
    uv run run_api_server.py
elif [ "$WORKER_TYPE" = "consumer_server" ]; then
    echo "Running in consumer server mode..."
    uv run report_consumer.py
else
    echo "Running nothing. Only eternity."
fi

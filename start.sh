#!/bin/bash
echo "Starting server..."
python -c "print('Python works')"
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}

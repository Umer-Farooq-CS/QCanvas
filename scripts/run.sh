#!/usr/bin/env bash
# run.sh — Start/Stop frontend and backend services

set -e

FRONTEND_PID="frontend.pid"
BACKEND_PID="backend.pid"
PROJECT_DIR="$(pwd)"

activate_venv() {
    echo "Activating venv..."
    source venv/bin/activate
}

start_services() {
    # ---- PREVENT DOUBLE START ----
    if [ -f "$FRONTEND_PID" ] || [ -f "$BACKEND_PID" ]; then
        echo "❌ Services already running! Run './run.sh stop' first."
        exit 1
    fi

    activate_venv

    mkdir -p logs

    echo "🚀 Launching services in background..."

    # -------------------------
    # FRONTEND (BACKGROUND)
    # -------------------------
    if [ -d "frontend" ]; then
        echo "Starting FRONTEND (background)..."
        (
            cd frontend
            npm run build
            nohup npm run start > "$PROJECT_DIR/logs/frontend.log" 2>&1 &
            echo $! > "$PROJECT_DIR/$FRONTEND_PID"
        )
    else
        echo "❌ frontend/ folder not found!"
    fi

    # -------------------------
    # BACKEND (BACKGROUND)
    # -------------------------
    echo "Starting BACKEND (background)..."

    nohup bash -c "
        cd \"$PROJECT_DIR\"
        source venv/bin/activate
        cd backend
        python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    " > "$PROJECT_DIR/logs/backend.log" 2>&1 &

    echo $! > "$BACKEND_PID"

    echo "✔ Both services started in background."
    echo "Logs: logs/frontend.log , logs/backend.log"
}

stop_services() {
    echo "🛑 Stopping all services..."

    # ==========================================================
    #  REPLACED STOP COMMAND (Your global kill command)
    # ==========================================================
    echo "Killing all node, next, and uvicorn processes with sudo..."

    sudo pkill -f node
    sudo pkill -f next
    sudo pkill -f uvicorn

    echo "Done."
    # ==========================================================

    # Remove stale PID files if they exist
    rm -f "$FRONTEND_PID" "$BACKEND_PID" 2>/dev/null || true

    echo "✔ Services stopped."
}

# =============================
# MAIN ARGUMENT HANDLING
# =============================
case "$1" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    *)
        echo "Usage: ./run.sh {start|stop}"
        exit 1
        ;;
esac


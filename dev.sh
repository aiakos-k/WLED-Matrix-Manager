#!/bin/bash
# Development Helper Script for Home Assistant Add-on

set -e

ADDON_NAME="WLEDMatrixManager"
ADDON_PATH="./WLEDMatrixManager"

echo "🏠 Home Assistant Add-on Development Helper"
echo "==========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if addon directory exists
if [ ! -d "$ADDON_PATH" ]; then
  echo -e "${RED}Error: Add-on directory not found: $ADDON_PATH${NC}"
  exit 1
fi

# Functions
show_help() {
  cat << EOF
Usage: ./dev.sh [command]

Commands:
  setup          - Install all dependencies (backend + frontend)
  build:backend  - Build backend package
  build:frontend - Build frontend (React)
  build:docker   - Build Docker image
  start:backend  - Start FastAPI development server
  start:frontend - Start React development server
  start:addon    - Build and start add-on in Home Assistant
  logs           - Show add-on logs
  clean          - Clean build artifacts and cache
  help           - Show this help message

Examples:
  ./dev.sh setup
  ./dev.sh start:backend
  ./dev.sh start:addon
EOF
}

setup() {
  echo -e "${YELLOW}📦 Installing backend dependencies...${NC}"
  cd "$ADDON_PATH/backend"
  pip install -r requirements.txt
  cd - > /dev/null

  echo -e "${YELLOW}📦 Installing frontend dependencies...${NC}"
  cd "$ADDON_PATH/frontend"
  npm install
  cd - > /dev/null

  echo -e "${GREEN}✅ Setup complete!${NC}"
}

build_backend() {
  echo -e "${YELLOW}🔨 Building backend...${NC}"
  cd "$ADDON_PATH/backend"
  # Add any custom build steps here
  echo -e "${GREEN}✅ Backend ready${NC}"
  cd - > /dev/null
}

build_frontend() {
  echo -e "${YELLOW}🔨 Building frontend...${NC}"
  cd "$ADDON_PATH/frontend"
  npm run build
  echo -e "${GREEN}✅ Frontend built${NC}"
  cd - > /dev/null
}

build_docker() {
  echo -e "${YELLOW}🐳 Building Docker image...${NC}"
  docker build \
    --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.15 \
    -t addon_example:latest \
    "$ADDON_PATH"
  echo -e "${GREEN}✅ Docker image built${NC}"
}

start_backend() {
  echo -e "${YELLOW}🚀 Starting FastAPI server...${NC}"
  cd "$ADDON_PATH/backend"

  # Activate virtual environment if it exists
  if [ -d "venv" ]; then
    source venv/bin/activate
  fi

  python main.py
}

start_frontend() {
  echo -e "${YELLOW}🚀 Starting React dev server...${NC}"
  cd "$ADDON_PATH/frontend"
  npm run dev
}

start_addon() {
  echo -e "${YELLOW}🏗️  Building add-on...${NC}"
  ha apps rebuild --force "local_$ADDON_NAME"

  echo -e "${YELLOW}🚀 Starting add-on...${NC}"
  ha apps start "local_$ADDON_NAME"

  # Enable ingress panel for sidebar access
  docker exec hassio_cli bash -c "curl -s -X POST -H \"Authorization: Bearer \${SUPERVISOR_TOKEN}\" -H \"Content-Type: application/json\" -d '{\"ingress_panel\": true}' http://supervisor/addons/local_${ADDON_NAME}/options" > /dev/null 2>&1 || true

  echo -e "${GREEN}✅ Add-on started${NC}"
  echo ""
  echo "Logs:"
  docker logs --follow "addon_local_$ADDON_NAME"
}

show_logs() {
  echo -e "${YELLOW}📋 Showing add-on logs...${NC}"
  docker logs --follow "addon_local_$ADDON_NAME"
}

clean() {
  echo -e "${YELLOW}🧹 Cleaning up...${NC}"

  # Backend
  cd "$ADDON_PATH/backend"
  find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
  find . -type f -name "*.pyc" -delete
  rm -rf .pytest_cache .coverage
  cd - > /dev/null

  # Frontend
  cd "$ADDON_PATH/frontend"
  rm -rf node_modules dist build
  cd - > /dev/null

  echo -e "${GREEN}✅ Clean complete${NC}"
}

# Main
case "${1:-help}" in
  setup)
    setup
    ;;
  build:backend)
    build_backend
    ;;
  build:frontend)
    build_frontend
    ;;
  build:docker)
    build_docker
    ;;
  start:backend)
    start_backend
    ;;
  start:frontend)
    start_frontend
    ;;
  start:addon)
    build_frontend && start_addon
    ;;
  logs)
    show_logs
    ;;
  clean)
    clean
    ;;
  help)
    show_help
    ;;
  *)
    echo -e "${RED}Unknown command: $1${NC}"
    echo ""
    show_help
    exit 1
    ;;
esac

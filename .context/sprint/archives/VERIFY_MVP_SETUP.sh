#!/bin/bash
# MVP TECH STACK - VERIFICATION SCRIPT
# Run this to verify all components are working

echo "======================================================================"
echo "AI DRONES MVP TECH STACK - VERIFICATION"
echo "======================================================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_count=0
pass_count=0

# Function to check a condition
check() {
    check_count=$((check_count + 1))
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅${NC} $1"
        pass_count=$((pass_count + 1))
    else
        echo -e "${RED}❌${NC} $1"
    fi
}

# Function to check file exists
check_file() {
    if [ -f "$1" ]; then
        check "$2"
    else
        check_count=$((check_count + 1))
        echo -e "${RED}❌${NC} $2 (File not found: $1)"
    fi
}

# Function to check directory exists
check_dir() {
    if [ -d "$1" ]; then
        check "$2"
    else
        check_count=$((check_count + 1))
        echo -e "${RED}❌${NC} $2 (Directory not found: $1)"
    fi
}

echo "CHECKING PROJECT STRUCTURE..."
echo ""

# Check directories
check_dir "poc/src/domain" "Domain layer exists"
check_dir "poc/src/ports" "Ports layer exists"
check_dir "poc/src/adapters" "Adapters layer exists"
check_dir "poc/tests/unit" "Unit tests exist"
check_dir "integration" "Integration tests exist"
check_dir "ops" "Operations (Docker) exists"
check_dir "docs" "Documentation exists"

echo ""
echo "CHECKING CORE FILES..."
echo ""

# Check domain files
check_file "poc/src/domain/telemetry.py" "Telemetry value object"
check_file "poc/src/domain/fault_model.py" "FaultModel interface"
check_file "poc/src/domain/rf_loss_burst.py" "RFLossBurstFault implementation"
check_file "poc/src/domain/fault_registry.py" "FaultModelRegistry"

# Check adapters
check_file "poc/src/adapters/memory_broker.py" "InMemoryBroker adapter"
check_file "poc/src/adapters/mqtt_broker.py" "MQTTBrokerAdapter (NEW)"

# Check tests
check_file "poc/tests/unit/test_telemetry.py" "Telemetry tests"
check_file "poc/tests/unit/test_rf_loss_burst.py" "RF burst fault tests"
check_file "poc/tests/unit/test_fault_registry.py" "Registry tests"
check_file "integration/test_mqtt_adapter.py" "MQTT adapter tests (NEW)"

# Check demos
check_file "poc/demo.py" "In-memory demo (unit tests)"
check_file "integration/demo_mqtt.py" "Real MQTT demo (NEW)"

# Check docker setup
check_file "ops/docker-compose.yml" "Docker Compose config (NEW)"
check_file "ops/mosquitto.conf" "Mosquitto config (NEW)"

# Check documentation
check_file "MVP_TECH_STACK_START_HERE.md" "Quick-start guide (NEW)"
check_file "docs/MQTT_SCHEMA.md" "MQTT schema documentation (NEW)"
check_file "docs/MVP_DEMO_GUIDE.md" "MVP demo guide (NEW)"
check_file ".context/project/IMPLEMENTATION-PLAN-TDD.md" "Implementation plan"
check_file ".context/project/MVP_COMPLETION_SUMMARY.md" "Completion summary (NEW)"
check_file "MVP_DELIVERY_SUMMARY.md" "Delivery summary (NEW)"
check_file ".context/project/MVP_IMPLEMENTATION_CHECKLIST.md" "Implementation checklist (NEW)"

echo ""
echo "CHECKING PYTHON ENVIRONMENT..."
echo ""

# Check Python version
python --version > /dev/null 2>&1
check "Python installed"

# Check pytest
python -m pytest --version > /dev/null 2>&1
check "pytest installed"

# Check if in virtual environment (or can find requirements)
if [ -f "poc/requirements.txt" ]; then
    echo -e "${GREEN}✅${NC} Requirements.txt found"
    pass_count=$((pass_count + 1))
else
    check_count=$((check_count + 1))
    echo -e "${RED}❌${NC} Requirements.txt not found"
fi
check_count=$((check_count + 1))

echo ""
echo "CHECKING UNIT TESTS..."
echo ""

cd poc 2>/dev/null
if python -m pytest tests/unit -q > /dev/null 2>&1; then
    test_output=$(python -m pytest tests/unit -q 2>&1 | grep -E "^[0-9]+ passed")
    echo -e "${GREEN}✅${NC} Unit tests passing: $test_output"
    pass_count=$((pass_count + 1))
else
    check_count=$((check_count + 1))
    echo -e "${RED}❌${NC} Unit tests failed or pytest not available"
fi
check_count=$((check_count + 1))

cd - > /dev/null

echo ""
echo "CHECKING DOCKER..."
echo ""

# Check Docker installed
docker --version > /dev/null 2>&1
check "Docker installed"

# Check docker-compose
docker-compose --version > /dev/null 2>&1
check "Docker Compose installed"

echo ""
echo "OPTIONAL: CHECKING MQTT (requires Docker running)..."
echo ""

# Check if Docker daemon is running
if docker info > /dev/null 2>&1; then
    echo -e "${GREEN}✅${NC} Docker daemon is running"
    pass_count=$((pass_count + 1))
    
    # Try to check if Mosquitto is running
    if docker ps | grep -q mosquitto; then
        echo -e "${GREEN}✅${NC} Mosquitto broker is running"
        pass_count=$((pass_count + 1))
    else
        echo -e "${YELLOW}⚠️${NC} Mosquitto broker not running (run: cd ops && docker-compose up -d)"
    fi
    check_count=$((check_count + 1))
else
    echo -e "${YELLOW}⚠️${NC} Docker daemon not running (start Docker Desktop)"
    check_count=$((check_count + 2))
fi

echo ""
echo "======================================================================"
echo "SUMMARY"
echo "======================================================================"
echo ""
echo "Checks passed: ${GREEN}${pass_count}/${check_count}${NC}"
echo ""

if [ $pass_count -eq $check_count ]; then
    echo -e "${GREEN}✅ ALL CHECKS PASSED!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Start MQTT broker: cd ops && docker-compose up -d"
    echo "  2. Run demo: python integration/demo_mqtt.py"
    echo "  3. Monitor: Open MQTT.Cool and connect to localhost:1883"
    exit 0
else
    missing=$((check_count - pass_count))
    echo -e "${YELLOW}⚠️  $missing check(s) failed${NC}"
    echo ""
    echo "Common issues:"
    echo "  - Missing files: Ensure you're in the project root directory"
    echo "  - Python: Activate virtual environment (cd poc && source .venv/bin/activate)"
    echo "  - Docker: Start Docker Desktop"
    echo "  - Tests: Run from poc directory for correct paths"
    exit 1
fi

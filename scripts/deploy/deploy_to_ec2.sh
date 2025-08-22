#!/bin/bash
# StudyMate API EC2 Deployment Script
# Deploys the StudyMate API to an EC2 instance

set -e

# Configuration
EC2_HOST="54.161.77.144"
EC2_USER="ec2-user"
KEY_PATH="../../server_info/server_key/public_key.pem"
REMOTE_DIR="~/studymate-api"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting StudyMate API deployment to EC2...${NC}"

# Check if SSH key exists
if [ ! -f "$KEY_PATH" ]; then
    echo -e "${RED}Error: SSH key not found at $KEY_PATH${NC}"
    exit 1
fi

# Function to run commands on EC2
run_remote() {
    ssh -i "$KEY_PATH" "$EC2_USER@$EC2_HOST" "$1"
}

# 1. Check server connectivity
echo -e "${YELLOW}Checking server connectivity...${NC}"
if ! run_remote "echo 'Connected to EC2'"; then
    echo -e "${RED}Failed to connect to EC2 instance${NC}"
    exit 1
fi

# 2. Stop existing services
echo -e "${YELLOW}Stopping existing services...${NC}"
run_remote "sudo killall python3 2>/dev/null || true"
run_remote "sudo killall gunicorn 2>/dev/null || true"

# 3. Update code
echo -e "${YELLOW}Updating code repository...${NC}"
run_remote "cd $REMOTE_DIR && git pull origin main || echo 'Git pull skipped'"

# 4. Install/Update dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
run_remote "cd $REMOTE_DIR && source venv/bin/activate && pip install -r requirements.txt --quiet"

# 5. Start the simple API server
echo -e "${YELLOW}Starting API server...${NC}"
run_remote "cd $REMOTE_DIR && nohup python3 scripts/deploy/simple_api_server.py > /tmp/api_server.log 2>&1 &"

# 6. Check if server is running
sleep 3
echo -e "${YELLOW}Verifying server status...${NC}"
if run_remote "curl -s localhost:8000/health | grep -q healthy"; then
    echo -e "${GREEN}✓ Server is running successfully!${NC}"
else
    echo -e "${RED}✗ Server failed to start${NC}"
    exit 1
fi

# 7. Restart Nginx
echo -e "${YELLOW}Restarting Nginx...${NC}"
run_remote "sudo systemctl restart nginx"

# 8. Final verification
echo -e "${YELLOW}Running final checks...${NC}"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "http://$EC2_HOST/health")
if [ "$RESPONSE" = "200" ]; then
    echo -e "${GREEN}✓ Deployment successful!${NC}"
    echo -e "${GREEN}Server is accessible at: http://$EC2_HOST/${NC}"
else
    echo -e "${RED}✗ External access check failed (HTTP $RESPONSE)${NC}"
    echo -e "${YELLOW}Note: Check AWS Security Group settings${NC}"
fi

echo -e "${GREEN}Deployment complete!${NC}"
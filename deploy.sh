#!/bin/bash
# Deploy integration to Home Assistant for testing
HA_IP="192.168.1.14"
HA_PATH="/root/config/custom_components/flamerite_glazer"

echo "Deploying to HA at $HA_IP..."
ssh root@$HA_IP "mkdir -p $HA_PATH"
scp -r custom_components/flamerite_glazer/* root@$HA_IP:$HA_PATH/
echo "Done. Restart HA to pick up changes."

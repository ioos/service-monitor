#!/bin/bash
set -e

echo "[-] Removing crontab"
rm -rf /etc/crontab

echo "[-] Running worker"
cd /service-monitor
/sbin/setuser ioos ./worker

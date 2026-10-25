#!/usr/bin/env bash
code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 6 https://github.com || echo 000)
echo "direct=$code"
if [ "$code" != "200" ] && [ "$code" != "301" ]; then
  for ip in 140.82.112.3 140.82.112.4 140.82.113.3 140.82.113.4 140.82.114.3 140.82.114.4 140.82.116.3 140.82.116.4 140.82.121.3 140.82.121.4 20.205.243.166 20.27.177.113 20.200.245.247; do
    printf "%s -> " "$ip"
    r=$(curl -s -o /dev/null -w "%{http_code} %{time_total}s" --resolve github.com:443:$ip --connect-timeout 4 https://github.com 2>/dev/null) || r=fail
    echo "$r"
  done
fi

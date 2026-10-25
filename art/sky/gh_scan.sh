#!/usr/bin/env bash
ips="140.82.112.3 140.82.112.4 140.82.113.3 140.82.113.4 140.82.114.3 140.82.114.4 140.82.116.3 140.82.116.4 140.82.121.3 140.82.121.4 20.205.243.166 20.27.177.113 20.200.245.247"
tmp=$(mktemp -d)
for ip in $ips; do
  ( curl -s -o /dev/null -m 6 -w "%{http_code} %{time_total}" --resolve github.com:443:$ip --connect-timeout 4 https://github.com > "$tmp/$ip" 2>/dev/null || echo fail > "$tmp/$ip" ) &
done
wait
for ip in $ips; do echo "$ip -> $(cat "$tmp/$ip")"; done
rm -rf "$tmp"

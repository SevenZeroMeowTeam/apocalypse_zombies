#!/usr/bin/env bash
echo "--- system DNS for github.com ---"
nslookup github.com 2>/dev/null | tail -4
echo "--- test system-resolved IPs (-m 6) ---"
for ip in $(nslookup github.com 2>/dev/null | awk "/^Address/{print \$2}" | grep -v ":" | sort -u | head -4); do
  printf "%s -> " "$ip";
  r=$(curl -s -o /dev/null -m 6 -w "%{http_code} %{time_total}s" --resolve github.com:443:$ip https://github.com 2>/dev/null) || r=fail; echo "$r";
done
echo "--- local proxy ports ---"
for p in 7890 7897 10808 1080 8888; do
  code=$(curl -s -o /dev/null -m 6 -w "%{http_code}" -x http://127.0.0.1:$p https://github.com 2>/dev/null) || code=fail;
  echo "127.0.0.1:$p -> $code";
done

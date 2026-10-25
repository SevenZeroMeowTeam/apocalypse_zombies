#!/usr/bin/env bash
cd "F:/mcmod/apocalypse_zombies-main"
proxy=""
for p in 7890 7897 10808 1080 8888; do
  code=$(curl -s -o /dev/null -m 5 -w "%{http_code}" -x http://127.0.0.1:$p https://github.com 2>/dev/null) || code=fail
  echo "port $p -> $code"
  if [ "$code" = "200" ] || [ "$code" = "301" ]; then proxy="http://127.0.0.1:$p"; break; fi
done
if [ -z "$proxy" ]; then echo NO_PROXY_FOUND; exit 9; fi
echo "using proxy: $proxy"
GIT_TERMINAL_PROMPT=0 git -c credential.gui=false -c http.proxy=$proxy push origin main 2>&1 | tail -6
rc=${PIPESTATUS[0]}
echo "push_exit=$rc"
if [ "$rc" = "0" ]; then
  git fetch origin 2>&1 | tail -1
  echo "remote main: $(git log --oneline -1 origin/main)"
fi

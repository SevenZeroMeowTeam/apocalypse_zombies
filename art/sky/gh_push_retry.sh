#!/usr/bin/env bash
cd "F:/mcmod/apocalypse_zombies-main"
for i in 1 2 3; do
  echo "=== attempt $i ==="
  GIT_TERMINAL_PROMPT=0 git -c credential.gui=false -c http.postBuffer=157286400 push origin main 2>&1 | tail -4
  rc=${PIPESTATUS[0]}
  echo "attempt_exit=$rc"
  if [ "$rc" = "0" ]; then break; fi
  sleep 8
done
echo "--- verify ---"
git fetch origin 2>&1 | tail -2
git log --oneline -1 origin/main

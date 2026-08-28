#!/usr/bin/env bash
set -u

child_pid=""

forward_signal() {
  local sig="$1"
  if [ -n "$child_pid" ]; then
    kill "-$sig" "$child_pid" 2>/dev/null || true
    wait "$child_pid" 2>/dev/null || true
  fi
  exit 0
}

trap 'forward_signal TERM' TERM
trap 'forward_signal INT' INT

base_delay="${SD_RESTART_DELAY_SECONDS:-10}"
current_delay="$base_delay"
max_delay=300

while true; do
  python -m app.main &
  child_pid="$!"

  wait "$child_pid"
  status="$?"
  child_pid=""

  # Exit code 2 indicates a configuration error (e.g. invalid settings, bad SD_MODEL)
  if [ "$status" -eq 2 ]; then
    echo "Configuration error detected (exit status 2); stopping service without retry" >&2
    exit 2
  fi

  # Exit cleanly if stopped via signal or clean exit
  if [ "$status" -eq 0 ] || [ "$status" -eq 130 ] || [ "$status" -eq 143 ]; then
    echo "Process exited with status ${status}; exiting entrypoint" >&2
    exit "$status"
  fi

  echo "Image service exited with status ${status}; restarting in ${current_delay}s" >&2
  sleep "$current_delay"

  current_delay=$(( current_delay * 2 ))
  if [ "$current_delay" -gt "$max_delay" ]; then
    current_delay="$max_delay"
  fi
done

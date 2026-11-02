#!/bin/bash
# Run a model the way users get it: ersilia fetch --from_dir, serve, run, close.
#
# Usage:
#   bash served.sh <label> <repo> <work> <cpus> <input.csv> [<input.csv> ...]
#
# <repo> must be a folder named exactly like the model (fetch takes the model ID
# from the folder name). Each input is run once; its output is written to
# <work>/served/<label>_<input basename> and its time to <work>/served/times.tsv.
#
# Safety. ersilia's own delete (called by `ersilia delete` and inside every
# `ersilia fetch`) removes every conda env whose name *starts with* the model ID.
# So this script:
#   - refuses to run if any conda env starting with the model ID already exists
#     (it may be the user's; they decide what to do with it);
#   - runs ersilia with HOME=<work>/ershome, so it never touches ~/eos (the user's
#     fetched models and sessions, or other people's served models);
#   - cleans up itself (conda env remove of the exact model env), never with
#     `ersilia delete`.
#
# The model server is started under `taskset` with the first <cpus> CPUs, so served
# timings use the same budget as the local runs. fetch is not restricted.

set -u
LABEL=$1; REPO=$(cd "$2" && pwd); WORK=$(cd "$3" && pwd); CPUS=$4; shift 4
MODEL=$(basename "$REPO")
OUT=$WORK/served; mkdir -p "$OUT"
REAL_HOME=$HOME
ISO_HOME=$WORK/ershome
LIMIT=2700   # seconds per `ersilia run` (45 min)

envs_with_prefix() {
  conda env list | awk -v m="$MODEL" '$1 ~ "^"m {print $1}'
}

existing=$(envs_with_prefix)
if [ -n "$existing" ]; then
  echo "ABORT: conda env(s) starting with $MODEL exist: $existing" >&2
  echo "ersilia fetch would delete them. Ask the user (rename or remove them first)." >&2
  exit 2
fi

rm -rf "$ISO_HOME"; mkdir -p "$ISO_HOME"
export HOME=$ISO_HOME PIP_CACHE_DIR=${PIP_CACHE_DIR:-$REAL_HOME/.cache/pip}
CPU_LIST=0-$((CPUS - 1))

# fetch, serve, run and close must run in one shell: a model served in one
# `conda run` is invisible to the next.
conda run --no-capture-output -n ersilia bash -c '
  set -u
  ersilia fetch '"$MODEL"' --from_dir "'"$REPO"'" > "'"$OUT"'/fetch_'"$LABEL"'.log" 2>&1 \
    || { echo "fetch failed, see '"$OUT"'/fetch_'"$LABEL"'.log"; exit 3; }
  # --disable-cache: a second run must not get the first run'"'"'s results back.
  taskset -c '"$CPU_LIST"' ersilia serve '"$MODEL"' --disable-cache > "'"$OUT"'/serve_'"$LABEL"'.log" 2>&1 \
    || { echo "serve failed, see '"$OUT"'/serve_'"$LABEL"'.log"; exit 4; }
  for input in '"$*"'; do
    name=$(basename "$input")
    start=$(date +%s.%N)
    # Polled, not wrapped in `timeout`: under timeout ersilia does not find the served model.
    taskset -c '"$CPU_LIST"' ersilia run -i "$input" -o "'"$OUT"'/'"$LABEL"'_$name" \
      > "'"$OUT"'/run_'"$LABEL"'_$name.log" 2>&1 & pid=$!
    for i in $(seq '"$LIMIT"'); do kill -0 $pid 2>/dev/null || break; sleep 1; done
    kill $pid 2>/dev/null && echo "TIMEOUT on $name"
    wait $pid; code=$?
    secs=$(awk -v a="$start" -v b="$(date +%s.%N)" "BEGIN{print b - a}")
    printf "%s\t%s\t%.1f\t%s\n" "'"$LABEL"'" "$name" "$secs" "$code" >> "'"$OUT"'/times.tsv"
    echo "'"$LABEL"' $name: ${secs%.*} s (exit $code)"
  done
  ersilia close > /dev/null 2>&1
'
status=$?

# Cleanup: only the exact env this fetch created, and the isolated ersilia home.
conda env list | awk '{print $1}' | grep -qx "$MODEL" && conda env remove -n "$MODEL" -y > /dev/null 2>&1
rm -rf "$ISO_HOME"
exit $status

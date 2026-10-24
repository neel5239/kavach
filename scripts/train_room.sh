#!/usr/bin/env bash
# After record_room.py: extract room features, retrain with room data, compare old vs new on held-out room speakers.
set -e
cd "$(dirname "$0")/.."
PY=.venv/Scripts/python.exe
export HF_HUB_OFFLINE=1
$PY -u scripts/extract.py data/index/room.csv room --variants clean,noisetr,noise
$PY -u scripts/train2.py kavach_room itw:clean,phone,len2,len10 itw_aug:chan,replay itw_aug_n:noisetr libri_n:noisetr \
    modern:clean,replay libri:clean,replay,chan itw_p2test:clean,r8k,amr,opus,noise,chan room:clean,noisetr,noise@5
$PY -u scripts/compare_room.py kavach kavach_room

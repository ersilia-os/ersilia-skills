# ERSILIA_DEVICE=gpu (set in GPU images) runs main_gpu.py; anything else runs main.py
MAIN=main.py
if [ "$ERSILIA_DEVICE" = "gpu" ]; then MAIN=main_gpu.py; fi
python $1/code/$MAIN $2 $3

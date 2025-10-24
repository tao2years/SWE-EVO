REPO="pylint-dev/pylint"
NAME="pylint-dev__pylint"

python -m swebench.scripts.create_data \
    https://github.com/${REPO}/compare/v2.16.4..v2.17.0 \
    --end_release_note_txt ./_release_note/swe_bench/${NAME}.txt \
    --output-dir output
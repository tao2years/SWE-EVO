REPO="psf/requests"
NAME="psf__requests"

python -m SWE-bench.scripts.create_data \
    https://github.com/${REPO}/compare/v2.4.0..v2.4.1 \
    --end_release_note_txt _release_note/swe_bench/${NAME}/v2_4_1.txt \
    --output-dir output
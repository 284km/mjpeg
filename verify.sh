#!/bin/sh
# verify.sh — the decoded pixels against libjpeg's, exactly, and the headers against
# what the files say.
#
#   MERE=/path/to/mere sh verify.sh
#
# THE EXACTNESS IS A DECISION, AND IT IS WORTH BEING CLEAR WHAT WAS GIVEN UP FOR IT. A
# JPEG's inverse DCT is real-valued and every decoder rounds it somewhere; the standard
# requires two decoders to agree within one, not to agree. So an exact comparison is only
# possible against a NAMED implementation, and jpeg.mere computes libjpeg's own integer
# transform -- its constants, its thirteen bits of fraction, its rounding at both passes.
# What passes here means "the same as libjpeg", which is narrower than "right", and it is
# the widest claim there is anything to check.
#
# The alternative was a tolerance, and a tolerance would have been worse than a narrower
# claim: it hides a real error behind a difference of method, and cannot tell the two
# apart afterwards.
#
# The same holds for the upsampler that puts back the chroma the encoder threw away --
# the standard does not say which filter, libjpeg uses a triangle filter, and this
# implements that one. Repeating the nearest sample instead, which is the obvious
# implementation, is what leaves visible blocks at every chroma edge; it misses 64 lines.
#
# Covered: the marker walk, the Huffman decode including the run-length pairs and the
# sixteen-zeroes escape, dequantisation, the zigzag, the DC predictor across a whole
# scan, restart markers, the MCU interleave of three components at three subsamplings,
# the inverse transform, chroma upsampling and the colour conversion. That is a baseline
# JPEG decoder end to end.
#
# TWO OF THE NINE FILES ARE NOT FLAT, and only those two make several of the numbers
# possible: an AC coefficient is only non-zero where there is detail, so a corpus of flat
# blocks runs the DC half of the entropy decoder and leaves the run-length pairs and the
# escape written but never executed, and every transform constant multiplied by zero.
# `detail.jpg` and `detail420.jpg` carry 2507 and 1407 non-zero AC coefficients, and the
# `ac=` on each header line pins those counts -- so a corpus that quietly stopped having
# detail in it would say so rather than keep passing.
#
# The eighteen deliberate errors this was poisoned with, and which of them the corpus
# catches, are recorded in POISONS.md. Sixteen are caught; the two that are not are not
# holes, and finding that out is why they were tried.
#
# WHAT THIS DECODER REFUSES: lossless, differential and arithmetic-coded frames, and
# progressive files that use SUCCESSIVE APPROXIMATION. Progressive with spectral
# selection is read, exactly.
# JPEGs, each by name. It used to STEP PAST a frame marker it did not know, so a
# progressive file came back as a header reading `0 0 0` having parsed the quantisation
# tables perfectly on the way, and said nothing.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
MERE="${MERE:-mere}"
command -v "$MERE" >/dev/null 2>&1 || { echo "verify: no mere — set MERE=/path/to/mere" >&2; exit 1; }
cd "$ROOT"
T="${TMPDIR:-/tmp}/mjpeg_verify.$$"; mkdir -p "$T"; trap 'rm -rf "$T"' EXIT

pass=0; fail=0

# --- the headers ------------------------------------------------------------------
# A wrong header produces a PLAUSIBLE picture -- the right size in the wrong colours, or
# the right colours at half the resolution -- and a gate that only compares pixels cannot
# say which of the two halves is wrong. Everything a header holds has exactly one answer.
"$MERE" test/jpeg_cases.mere test/data/headers.cases > "$T/h.raw" 2>/dev/null || true
sed '$d' "$T/h.raw" > "$T/h.txt"
if diff -q "$T/h.txt" test/data/headers.expected >/dev/null 2>&1; then
  echo "  ok    headers: $(grep -c '' test/data/headers.expected) lines, exact"
  pass=$((pass + 1))
else
  echo "  FAIL  headers differ"
  diff "$T/h.txt" test/data/headers.expected | head -6 | cut -c1-120 | sed 's/^/        /'
  fail=$((fail + 1))
fi

# --- every pixel of every file ----------------------------------------------------
"$MERE" test/jpeg_pixels_cases.mere test/data/pixels.cases > "$T/p.raw" 2>/dev/null || true
sed '$d' "$T/p.raw" > "$T/p.txt"
total=$(grep -c '' test/data/pixels.expected)
bad=$(diff "$T/p.txt" test/data/pixels.expected 2>/dev/null | grep -c '^<' || true)
same=$((total - bad))
EXPECT_LINES=${EXPECT_LINES:-297}
if [ "$same" -eq "$EXPECT_LINES" ] && [ "$total" -eq "$EXPECT_LINES" ]; then
  echo "  ok    pixels: $same of $total lines, every pixel, no tolerance"
  pass=$((pass + 1))
else
  echo "  FAIL  pixels: $same of $total lines match, expected all $EXPECT_LINES"
  diff "$T/p.txt" test/data/pixels.expected 2>/dev/null | head -6 | cut -c1-120 | sed 's/^/        /'
  fail=$((fail + 1))
fi

# --- against Pillow, through the CLI ----------------------------------------------
# The committed expectations above come from scripts/gen_jpeg_pixels_expected.py, which
# is Pillow -- so they are libjpeg's answer recorded once. This runs Pillow AGAIN, now,
# through the PPM the CLI writes: it catches an expectation file that has drifted from the
# library, which the diff above cannot, because both sides of it are this repository.
if python3 -c 'import PIL' 2>/dev/null; then
  n=0
  for f in test/data/*.jpg; do
    "$MERE" mjpeg.mere ppm "$f" "$T/got.ppm" >/dev/null 2>&1 || {
      echo "  FAIL  $f did not decode"; fail=$((fail + 1)); continue; }
    if python3 - "$f" "$T/got.ppm" <<'PY'
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGB")
want = f"P6\n{im.size[0]} {im.size[1]}\n255\n".encode() + im.tobytes()
sys.exit(0 if open(sys.argv[2], "rb").read() == want else 1)
PY
    then n=$((n + 1))
    else echo "  FAIL  $f differs from Pillow"; fail=$((fail + 1)); fi
  done
  echo "  ok    $n file(s) byte-identical to Pillow's libjpeg, right now"
  [ "$n" -ge 14 ] || { echo "  FAIL  only $n compared against Pillow"; fail=$((fail + 1)); }
  pass=$((pass + 1))
else
  echo "  SKIP  Pillow is not installed, so libjpeg was not asked again"
fi

# --- what it refuses, and whether it says so --------------------------------------
# A frame type this decoder cannot read must be REFUSED BY NAME. Stepping past it is what
# it used to do, and the result was a 0x0 header with no complaint.
python3 - "$T" <<'PY'
import struct, sys, os
T = sys.argv[1]
base = open("test/data/flat444.jpg", "rb").read()
i = 2
while i < len(base) - 1:
    if base[i] == 0xFF and base[i + 1] in (0xC0, 0xC1):
        break
    if base[i] == 0xFF and base[i + 1] not in (0xD8, 0x01) and not 0xD0 <= base[i + 1] <= 0xD7:
        i += 2 + struct.unpack_from(">H", base, i + 2)[0]
    else:
        i += 2
# The same file with its frame marker relabelled: still a well-formed segment, still
# something this decoder must not pretend to read.
#
# PROGRESSIVE IS NO LONGER IN THIS LIST, and that is the point of the change that added
# it to the corpus instead. A baseline file with its marker changed to C2 is not a
# progressive file -- its scan is baseline-shaped -- so once C2 is genuinely read, that
# fixture stops testing anything and starts testing whether the decoder notices a lie.
# The real limit is narrower and is checked below with a file that really has it.
for name, marker in (("lossless.jpg", 0xC3), ("arithmetic.jpg", 0xCA)):
    d = bytearray(base)
    d[i + 1] = marker
    open(os.path.join(T, name), "wb").write(bytes(d))
# And a file with no frame at all.
open(os.path.join(T, "noframe.jpg"), "wb").write(base[:i] + b"\xff\xd9")
PY
# EACH CASE CHECKS ITS OWN WORDS, not a shared prefix. There are two guards here -- the
# frame marker is refused where it is read, and a document with no frame at all is
# refused afterwards -- and they OVERLAP: with the first disabled, the second catches
# every one of these files and answers "no frame header was found". Testing for a `jpeg:`
# prefix therefore passed with the specific refusal deleted, which is the whole thing the
# specific refusal is for. A gate that accepts any refusal cannot tell a precise one from
# a vague one.
check_refusal() { # file expected-words
  msg=$("$MERE" mjpeg.mere info "$T/$1" 2>&1 || true)
  case "$msg" in
    *"$2"*) echo "  ok    $1 — \"$2\""; pass=$((pass + 1)) ;;
    *) echo "  FAIL  $1 was not refused as \"$2\" — got: $(echo "$msg" | head -1 | cut -c1-64)"
       fail=$((fail + 1)) ;;
  esac
}
# WHAT IS ACTUALLY NOT READ YET: successive approximation. Spectral selection -- the
# form `CesiumMilkTruck` uses, and the one the corpus above covers -- is read exactly;
# refinement scans are not, and the file that proves the refusal is REAL rather than
# relabelled comes from Pillow, whose `progressive=True` always emits them.
python3 - "$T" <<'PY2'
import sys, os
try:
    from PIL import Image
except ImportError:
    sys.exit(0)
im = Image.new("RGB", (32, 32))
for y in range(32):
    for x in range(32):
        im.putpixel((x, y), ((x * 8) % 256, (y * 8) % 256, ((x + y) * 4) % 256))
im.save(os.path.join(sys.argv[1], "sapprox.jpg"), quality=90, subsampling=0, progressive=True)
PY2
if [ -f "$T/sapprox.jpg" ]; then
  check_refusal sapprox.jpg "successive approximation, which is not read yet"
else
  echo "  SKIP  no Pillow, so the successive-approximation refusal was not checked"
fi
check_refusal lossless.jpg    "this file is lossless"
check_refusal arithmetic.jpg  "this file is arithmetic-coded progressive"
check_refusal noframe.jpg     "no frame header was found"

echo "verify: $pass passed, $fail failed"
[ "$fail" -eq 0 ]

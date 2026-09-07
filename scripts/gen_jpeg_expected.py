#!/usr/bin/env python3
"""JPEG headers, read out of the same files by an independent decoder.

Headers first and pixels after, which is the order the font took and for the same reason: a wrong
header produces a plausible picture — the right size in the wrong colours, or the right colours at
half the resolution — and a gate that only compares pixels cannot say which of the two halves is
wrong. Everything in a header has exactly one answer, so the comparison is exact.

**Why the test images are flat blocks.** A JPEG's inverse DCT is an approximation and no two decoders
round it alike; the standard itself only requires them to agree within one. So a general image cannot
be compared exactly, and a tolerance would hide a real error behind a difference of method. An image
whose every 8x8 block is one colour has only a DC coefficient, and a flat block comes out the same in
every implementation — so those decode bit-exactly and can be compared with no tolerance at all.

That covers the markers, the Huffman decode, dequantisation, the DC predictor, chroma upsampling and
the colour conversion. It does NOT cover the AC path or the IDCT's accuracy, which need a different
gate and a different claim.

Seven files. See `gen_jpeg_images.py` for what each one punishes; three of them exist only because the
gate was poisoned and let the poison through.

The DRI value is NOT in the line, because Pillow does not expose the restart interval and inventing a
second reading of the same bytes would be comparing this repository with itself.

One line per file:

    <w> <h> <ncomp> | <id>,<h>,<v>,<tq> ; ... | <tq>: 64 values | ...

Needs Pillow. Maintenance command, not a gate — the answers are committed.

  python3 scripts/gen_jpeg_expected.py test/data/jpeg
"""
import os, sys

FILES = ["flat444.jpg", "flat422.jpg", "flat420.jpg", "flatgray.jpg",
         "flatexif.jpg", "flatdri.jpg", "flatq1.jpg",
         "detail.jpg", "detail420.jpg"]


def main(d):
    try:
        from PIL import Image
    except ImportError:
        print("gen_jpeg_expected: needs Pillow", file=sys.stderr)
        return 1
    lines = []
    for n in FILES:
        p = os.path.join(d, n)
        if not os.path.exists(p):
            print("gen_jpeg_expected: no %s — run scripts/gen_jpeg_images.py" % n, file=sys.stderr)
            return 1
        im = Image.open(p)
        im.load()
        w, h = im.size
        comps = " ; ".join("%d,%d,%d,%d" % (cid, hs, vs, tq) for cid, hs, vs, tq in im.layer)
        qs = " | ".join(
            "%d: %s" % (k, " ".join(str(v) for v in im.quantization[k]))
            for k in sorted(im.quantization))
        lines.append("%d %d %d | %s | %s" % (w, h, len(im.layer), comps, qs))
    open(os.path.join(d, "headers.cases"), "w").write("\n".join(FILES) + "\n")
    open(os.path.join(d, "headers.expected"), "w").write("\n".join(lines) + "\n")
    print("gen_jpeg_expected: %d headers written" % len(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

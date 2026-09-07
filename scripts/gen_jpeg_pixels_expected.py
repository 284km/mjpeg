#!/usr/bin/env python3
"""Every decoded pixel of the flat JPEGs, from libjpeg through Pillow.

The comparison is EXACT — no tolerance — and that is only possible because of what these images are.
A JPEG's inverse DCT is an approximation and no two decoders round it alike; the standard requires
only that they agree within one. But a block of a single colour has nothing in it except the DC
coefficient, and the inverse transform of that is the coefficient spread flat — one shift, no
transform at all. libjpeg takes exactly that shortcut and so does `src/jpeg.mere`, so on these images
the two agree to the bit and a tolerance would only hide a real error behind a difference of method.

That covers the marker walk, the Huffman decode, dequantisation, the DC predictor, restart markers,
the MCU interleave and the colour conversion — everything except the AC path and the IDCT's accuracy.

Only the files with no chroma subsampling are here. At 4:2:0 and 4:2:2 the upsampler interpolates
across chroma edges and the filter is a decoder's own choice, so the answer stops being unique; those
are a separate question with a separate gate.

Rows are run-length — `count x rrggbb` — which is the format the painter already writes, for the same
reasons: exact, diffable, and a failing line names the row and the run.

Needs Pillow. Maintenance command, not a gate — the answers are committed.

  python3 scripts/gen_jpeg_pixels_expected.py test/data/jpeg
"""
import os, sys


def rows(im):
    px = im.load()
    w, h = im.size
    gray = im.mode == "L"
    out = []
    for y in range(h):
        runs, cur, n = [], None, 0
        for x in range(w):
            p = px[x, y]
            c = (p << 16) | (p << 8) | p if gray else (p[0] << 16) | (p[1] << 8) | p[2]
            if c == cur:
                n += 1
            else:
                if cur is not None:
                    runs.append("%dx%06x" % (n, cur))
                cur, n = c, 1
        runs.append("%dx%06x" % (n, cur))
        out.append(" ".join(runs))
    return out


def main(d):
    from PIL import Image
    raw = [l.strip() for l in open(os.path.join(d, "pixels.cases")) if l.strip()]
    # `name` or `name ac`; the flat files say 0 and the detailed ones say how many they have.
    names = [l.split()[0] for l in raw]
    acs = {l.split()[0]: (l.split()[1] if len(l.split()) > 1 else "0") for l in raw}
    lines = []
    for n in names:
        im = Image.open(os.path.join(d, n))
        im.load()
        # ac=0 is a claim this generator cannot check and the Mere side reports; it is in the line so
        # that the day a corpus image stops being flat, the gate says so instead of the picture
        # quietly changing.
        # The AC count is a claim the Mere side makes and this generator cannot check, so it is
        # carried through from the cases file rather than asserted here.
        lines.append("--- %s %d %d ac=%s" % (n, im.size[0], im.size[1], acs[n]))
        lines += rows(im)
    open(os.path.join(d, "pixels.expected"), "w").write("\n".join(lines) + "\n")
    print("gen_jpeg_pixels_expected: %d files, %d lines" % (len(names), len(lines)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

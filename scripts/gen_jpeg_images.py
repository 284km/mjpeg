#!/usr/bin/env python3
"""The test JPEGs: seven of flat 16x16 blocks, and two with detail in them.

Flat because a block of one colour has only a DC coefficient, and a flat block comes out identical in
every correct decoder — so these can be compared with no tolerance while a general image cannot. See
`gen_jpeg_expected.py` for why that matters.

The colours are chosen to move both chroma channels in both directions and to include the two ends of
the luma range, so a colour conversion with a sign or a coefficient wrong cannot pass by symmetry.

Each file is here because it is the only one that punishes a particular way of being wrong, and three
of the six were added AFTER the gate was poisoned and let the poison through:

    flat444   three components, no subsampling — the ordinary shape
    flat422   chroma halved HORIZONTALLY ONLY, so the luma factors are 2,1 and not 2,2. With only 444
              and 420 in the corpus every sampling factor is symmetric, and a reader that swaps the
              two nibbles of that byte passes everything. It did.
    flat420   chroma halved both ways
    flatgray  one component, the path with no colour conversion at all
    flatexif  an APP1 with a whole JPEG inside it, which is what a camera's EXIF thumbnail is. Two
              things had to be true before this file bit. The JFIF APP0 is exactly sixteen bytes, so a
              reader that steps over every APPn by a hard-coded sixteen passes a corpus that has only
              JFIF in it — but a long APP1 of ZEROES did not catch it either, because a walker that
              looks for the next FF simply resynchronises on the next real marker. It is only when the
              payload contains markers of its own that landing inside it is fatal: the reader then
              answers with the THUMBNAIL's size and tables, confidently and completely wrongly.
    flatq1    the same eight colours at quality 1, which is here for one reason and it is a small one
              worth stating. The inverse DCT of a DC-only block is that coefficient divided by eight
              and libjpeg rounds that division rather than flooring it — and at quality 95 the two are
              never different, because the quantised DC times its quantiser lands exactly on a
              multiple of eight for every one of the 256 grey levels. It stays exact across all 100
              quality settings until quality 1, where the quantiser is 255 and black comes out as
              -1020: floor says 0, rounding says 1. One value in one file, and without it the gate
              cannot tell a rounding decoder from a truncating one.
    flatdri   a restart interval, so there is a DRI segment to step over. Its VALUE is not compared —
              Pillow does not expose it — but everything after it is, so a mishandled DRI shows up as
              the whole rest of the header being read from the wrong offset.

The last two are not flat and are not there for the same reason. Once the inverse transform is
libjpeg's own integer one rather than a transform, ANY image compares exactly — and only an image with
detail in it ever produces a non-zero AC coefficient, so only an image with detail runs the half of
the entropy decoder that reads run-length pairs and the sixteen-zeroes escape. The pattern is
arithmetic rather than a photograph so that it is reproducible, and it is deliberately full of
high-frequency content, which is what fills the upper coefficients that a flat block leaves empty.

    detail    detail at 4:4:4
    detail420 the same at 4:2:0, where the chroma the upsampler has to invent is not constant either

Needs Pillow. Run once; the files are committed.

  python3 scripts/gen_jpeg_images.py test/data/jpeg
"""
import io, os, sys

COLS = [(255, 0, 0), (0, 128, 0), (0, 0, 255), (255, 255, 255),
        (0, 0, 0), (192, 192, 192), (255, 165, 0), (128, 128, 128)]


def main(d):
    from PIL import Image
    os.makedirs(d, exist_ok=True)
    # 16x16 colour blocks, not 8x8, and the reason is subsampling. A DCT block is 8x8 of its OWN
    # component's samples, so at 4:2:0 an 8x8 chroma block covers 16x16 image pixels — with 8x8
    # colour blocks the chroma blocks would straddle four colours and stop being flat, which is the
    # whole premise. At 16x16 every DCT block of every component, at every subsampling here, lies
    # inside one colour.
    im = Image.new("RGB", (64, 32))
    for by in range(2):
        for bx in range(4):
            c = COLS[by * 4 + bx]
            for y in range(16):
                for x in range(16):
                    im.putpixel((bx * 16 + x, by * 16 + y), c)
    im.save(os.path.join(d, "flat444.jpg"), quality=95, subsampling=0)
    im.save(os.path.join(d, "flat422.jpg"), quality=95, subsampling=1)
    im.save(os.path.join(d, "flat420.jpg"), quality=95, subsampling=2)
    im.convert("L").save(os.path.join(d, "flatgray.jpg"), quality=95)
    thumb = io.BytesIO()
    im.resize((16, 16)).save(thumb, "JPEG", quality=40, subsampling=0)
    im.save(os.path.join(d, "flatexif.jpg"), quality=95, subsampling=0,
            exif=b"Exif\x00\x00" + thumb.getvalue())
    im.save(os.path.join(d, "flatdri.jpg"), quality=95, subsampling=0, restart_marker_blocks=2)
    im.save(os.path.join(d, "flatq1.jpg"), quality=1, subsampling=0)

    det = Image.new("RGB", (48, 32))
    for y in range(32):
        for x in range(48):
            det.putpixel((x, y), (((x * x + y * 7) % 256),
                                  ((x * 5) ^ (y * 11)) % 256,
                                  ((x + y) * 3 + (x * y) % 29) % 256))
    det.save(os.path.join(d, "detail.jpg"), quality=90, subsampling=0)
    det.save(os.path.join(d, "detail420.jpg"), quality=90, subsampling=2)
    print("gen_jpeg_images: 9 written")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

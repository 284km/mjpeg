#!/usr/bin/env python3
"""The test JPEGs: seven of flat 16x16 blocks, two with detail, and five progressive.

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
import io
import shutil
import subprocess, os, sys

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

    # --- progressive -------------------------------------------------------------
    #
    # THESE NEED cjpeg AND PILLOW CANNOT MAKE THEM. Pillow's `progressive=True` always
    # emits successive approximation, and this decoder reads spectral selection only --
    # so a corpus built with Pillow would contain nothing this path can decode and
    # nothing that would catch it being wrong. cjpeg takes a scan script, which is the
    # only way to ask for the spectral-selection-only form that `CesiumMilkTruck` (the
    # file this was written for) actually uses.
    #
    # The generated files are COMMITTED, so cjpeg is needed to regenerate the corpus and
    # not to run the gate.
    #
    # Each earns its place by punishing one way of being wrong:
    #
    #   prog444   the ordinary progressive shape, and the same structure as the model
    #             that motivated it: an interleaved DC scan, then one AC scan per
    #             component. It also redefines the chroma Huffman tables between scans,
    #             which is what caught the real bug -- a second definition of the same
    #             (class, id) has to SHADOW the first, and appending then taking the
    #             first match decoded Cr with Cb's table. Blue came out exact and red
    #             and green were wrong everywhere.
    #   prog420   chroma halved both ways, so a scan's blocks are not the MCU grid's.
    #   progodd   37x29 at 4:2:0, where a component's own block count genuinely differs
    #             from mcux*hs -- a non-interleaved scan is walked in the component's
    #             OWN raster order, and at 64x48 the two happen to agree, so only this
    #             file separates the definition from the coincidence.
    #   proggray  one component: no interleaving and no colour conversion.
    #   progeob   a large uniform field FOLLOWED BY DETAIL, which is the only shape that
    #             punishes the end-of-band run. The uniform field compresses 1024 blocks
    #             into two bytes of entropy data, so the run is long; the detail after it
    #             is what makes swallowing the run visible. A purely uniform image does
    #             NOT catch it -- "skip the run" and "decode each block and find it
    #             empty" both leave the AC coefficients at zero, so the poison and the
    #             correct code agree. That was measured, not guessed: with a uniform
    #             fixture the poison passed, and with this one it fails.
    #
    # NOT COVERED, and recorded rather than left to be assumed: the POINT TRANSFORM
    # (`al` > 0) with spectral selection alone. Such a file is legal and this decoder
    # handles it, but libjpeg BLOCK-SMOOTHS it -- an incompletely-sent DC is exactly its
    # trigger -- so djpeg and Pillow both return something no plain reconstruction
    # produces and there is nothing to compare against exactly. The same is true of a
    # DC-only progressive file. Successive approximation will cover `al` when it lands,
    # because a fully refined file is not smoothed.
    prog_scans = os.path.join(d, "progressive.scan")
    with open(prog_scans, "w") as f:
        f.write("0,1,2: 0 0 0 0;\n0: 1 63 0 0;\n1: 1 63 0 0;\n2: 1 63 0 0;\n")
    gray_scans = os.path.join(d, "progressive_gray.scan")
    with open(gray_scans, "w") as f:
        f.write("0: 0 0 0 0;\n0: 1 63 0 0;\n")

    odd = Image.new("RGB", (37, 29))
    for y in range(29):
        for x in range(37):
            odd.putpixel((x, y), ((x * 7) % 256, (y * 11) % 256, (x * y) % 256))

    def cj(src_img, out, sample, scans, mode="RGB"):
        ppm = os.path.join(d, "_tmp_src.ppm" if mode == "RGB" else "_tmp_src.pgm")
        src_img.convert("RGB" if mode == "RGB" else "L").save(ppm)
        r = subprocess.run(["cjpeg", "-quality", "90", "-sample", sample,
                            "-scans", scans, "-outfile", os.path.join(d, out), ppm],
                           capture_output=True)
        os.unlink(ppm)
        if r.returncode != 0:
            raise SystemExit("gen_jpeg_images: cjpeg failed for %s: %s"
                             % (out, r.stderr.decode()[:200]))

    if shutil.which("cjpeg") is None:
        print("gen_jpeg_images: 11 written; SKIPPED the 5 progressive files — no cjpeg")
        return 0
    cj(det, "prog444.jpg", "1x1", prog_scans)
    cj(det, "prog420.jpg", "2x2", prog_scans)
    cj(odd, "progodd.jpg", "2x2", prog_scans)
    cj(det, "proggray.jpg", "1x1", gray_scans, mode="L")

    eob = Image.new("RGB", (256, 128), (180, 90, 40))
    for y in range(96, 128):
        for x in range(256):
            eob.putpixel((x, y), ((x * 7) % 256, (y * 13) % 256, ((x ^ y) * 3) % 256))
    cj(eob, "progeob.jpg", "1x1", prog_scans)

    os.unlink(prog_scans); os.unlink(gray_scans)
    print("gen_jpeg_images: 16 written")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

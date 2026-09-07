# mjpeg

A baseline JPEG decoder in [Mere](https://merelang.org/), as a package.

```sh
mjpeg info <file.jpg>            # what the header says
mjpeg ppm  <file.jpg> <out.ppm>  # the decoded pixels
```

As a dependency, `jpeg.mere` is the module and holds no program:

```
Jpeg.header d      -> jhead          the frame, the tables, the scan
Jpeg.checked d     -> jhead          the same, refusing a document with no frame
Jpeg.pixels h d    -> (int Vec, int) one packed 0xRRGGBB per pixel, and the AC count
Jpeg.load path     -> jhead          a convenience for a CLI
Jpeg.load_bytes p  -> bytes
```

**It takes bytes, not a path.** That is the one interface change made when this came out
of [mbrowse](https://github.com/284km/mbrowse), and it is what a second consumer needed: a
glTF image is either a file beside the document or a range of a binary chunk, and a
decoder that insisted on a filename could not read the second.

## Exact against libjpeg, which is narrower than "right"

A JPEG's inverse DCT is real-valued and every decoder rounds it somewhere; the standard
requires two decoders to agree *within one*, not to agree. So an exact comparison is only
possible against a **named** implementation, and this computes libjpeg's own integer
transform — its constants, its thirteen bits of fraction, its rounding at both passes.
What `verify.sh` passes means "the same as libjpeg", which is the widest claim there is
anything to check.

The alternative was a tolerance, and a tolerance would have been worse than a narrower
claim: it hides a real error behind a difference of method, and cannot tell the two apart
afterwards. The same reasoning covers the chroma upsampler — the standard does not say
which filter, libjpeg uses a triangle filter, and this implements that one. Repeating the
nearest sample, which is the obvious implementation, is what leaves visible blocks at
every chroma edge.

`verify.sh` compares 297 lines of run-length rows over nine files with no tolerance,
**and then asks Pillow again, now**, through the PPM the CLI writes — because both sides
of the committed expectations are this repository, and a file that had drifted from the
library would still match itself.

## What it refuses, by name

Progressive, lossless, differential and arithmetic-coded JPEGs, and a document with no
frame header at all. It used to **step past** a frame marker it did not recognise, so a
progressive file came back as a header reading `0 0 0` — width zero, height zero, no
components — having parsed the quantisation tables perfectly on the way, and said
nothing. Two of the models in [m3d](https://github.com/284km/m3d)'s corpus are
progressive, which is how that was found.

Progressive JPEG is the obvious thing still missing.

## The poisons

See `POISONS.md`. Eighteen deliberate errors were run against this decoder while it lived
in mbrowse — sixteen caught, and the file says why the two that are not are not holes.
Three more came out of the extraction, and **one of those the gate did not catch until the
gate itself was fixed**: two refusal paths overlapped, so deleting the specific one still
produced a refusal, and a gate testing for "some refusal" passed.

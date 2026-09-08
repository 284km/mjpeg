# mjpeg

A JPEG decoder in [Mere](https://merelang.org/), as a package: baseline, extended
sequential, and progressive with spectral selection.

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

## Progressive

A baseline file codes each block once and completely. A progressive file codes the same
coefficients across several scans — one carrying the DC of every block, then scans
carrying bands of AC coefficients — so the pipeline turns inside out: coefficients for
the whole image are accumulated first, and only when every scan is in is anything
transformed. That is the entire difference. The Huffman reader, the dequantisation, the
inverse transform, the upsampling and the colour conversion are the baseline ones,
unchanged — which is also why this is exact for the same reason baseline is.

**Spectral selection is read; successive approximation is refused by name.** The two
halves of progressive are separable, and the split is not arbitrary: of the two models
that motivated this, `CesiumMilkTruck` uses spectral selection alone — all four of its
scans have `Ah = Al = 0` — and `CesiumMan` has refinement scans. Half the feature opens
half the files, and the refusal says which half is missing rather than producing a
picture nobody should trust.

`CesiumMilkTruck` at 2048×2048 decodes **0 of 12,582,912 bytes different** from libjpeg.

### The bug, and what found it

A progressive file **redefines Huffman tables between scans** — `cjpeg` emits a fresh
chroma DC table before Cb's scan and another before Cr's. Tables were being appended to a
list and looked up by first match, so Cr decoded with Cb's table. In a baseline file,
where every table is defined once and there is one scan, that could never happen.

The symptom named the cause once it was read properly: **blue came out exact** while red
and green were wrong everywhere. Blue does not use Cr. A second definition now shadows
the first, and each scan carries a *snapshot* of the tables in force where it sits —
because a later redefinition must not reach back and change an earlier scan.

Getting there needed three corrections to the harness first, and they are worth naming:

- **`djpeg` is not a valid oracle for a partially-populated progressive file.** libjpeg
  block-smooths one — an incompletely-sent DC is its trigger — so a DC-only file comes
  back *not flat within each 8×8 block*, which is what a DC-only reconstruction is by
  definition. There is no flag to turn it off (`-nosmooth` is about upsampling).
- **`cjpeg` silently ignored an illegal scan script.** A single scan covering `0..63` is
  not legal in progressive, so it emitted a *baseline* file — which decoded exactly and
  told me the progressive path worked, while testing the baseline path.
- Pillow's `progressive=True` always emits successive approximation, so it cannot
  generate anything this reads. The corpus needs `cjpeg` and a scan script.

### The corpus, and what each file punishes

| | |
|---|---|
| `prog444` | the ordinary shape, and the same structure as the model this was written for |
| `prog420` | chroma halved both ways |
| `progodd` | 37×29 at 4:2:0, where a component's own block count genuinely differs from the MCU grid — a non-interleaved scan is walked in the component's *own* raster order, and at 64×48 the two coincide |
| `proggray` | one component: no interleaving, no colour conversion |
| `progeob` | a large uniform field **followed by detail** — the only shape that punishes the end-of-band run |

Two of those were added because a poison went through. Walking a non-interleaved scan over
the MCU grid instead of the component's own blocks fails **only `progodd`**. And a purely
uniform image does *not* catch a swallowed end-of-band run: "skip the run" and "decode
each block and find it empty" both leave the AC coefficients at zero, so the poison and
the correct code agree. It takes content *after* the run to desynchronise, which is why
`progeob` is shaped the way it is.

**Not covered, and recorded rather than assumed**: the point transform (`Al > 0`) with
spectral selection alone. Such a file is legal and this decoder handles it, but it is
exactly the case libjpeg smooths, so there is nothing to compare against exactly.
Successive approximation will cover it, because a fully refined file is not smoothed.

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

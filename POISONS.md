# The eighteen deliberate errors, and which the corpus catches

A gate that has only ever passed has not been shown to be a gate.

**The eighteen below were done while this decoder lived in
[mbrowse](https://github.com/284km/mbrowse), and are recorded here because they travel
with the code rather than with the repository.** They are not re-run by `verify.sh` — the
numbers are the measurements taken then, of how many expectation lines each error changed.
The three at the bottom are from the extraction and were run here.

    the stuffed zero after a literal FF not skipped    99 of 231
    blocks within an MCU taken column-first           198 of 231
    restart markers not consumed                      198 of 231
    nearest-neighbour instead of the triangle filter  167 of 231
    the two quarter positions rounded the same way    215 of 231
    the DC divided by eight without rounding          215 of 231
    the vertical weights made 1:1 instead of 3:1      229 of 231
    the nearer row taken on the wrong side            229 of 231
    the second pass shifted by 17 bits instead of 18    9 of 297
    the first pass shifted by 10 bits instead of 11     9 of 297
    a zero run counted one short                      231 of 297
    coefficients left in zigzag order                 233 of 297
    the coefficient block not cleared between blocks  233 of 297
    the sixteen-zeroes escape treated as end-of-block 265 of 297
    one inverse-transform constant off by one         276 of 297
    two transform outputs written to each other's row 277 of 297
    the empty-length sentinel in maxcode removed      297 of 297  — no answer can change
    the first and last column special cases removed   297 of 297  — no answer can change

**The last two are not holes, and finding that out is why they were tried.** Clamping the
neighbour lookup at a row's edge already makes the general interpolation formula reduce to
the edge value, so libjpeg's special cases are three rules where there is one; they have
been deleted. And the empty-length sentinel cannot be reached on a well-formed stream by
an invariant of canonical Huffman codes, so it is kept for corrupt input and not because
any file here needs it.

**Two of the numbers are worth reading twice.** The DC rounding took a file at quality 1
to catch, because at every other quality setting the quantised DC times its quantiser
lands exactly on a multiple of eight for all 256 grey levels, and rounding and flooring
agree. And 229 of 231 is what a real error looks like when the corpus barely touches it —
the vertical weights only matter at a horizontal chroma edge, and there are two of those.

## Three more, from the extraction

The decoder came out of a browser, where it had only ever been handed files a browser had
already sniffed. Packaging it meant asking what it does with a file it cannot read:

    the frame-marker refusal removed          3 of 4 refusal cases
    the no-frame guard removed                1 of 4 refusal cases
    an inverse-transform constant off by one  27 pixel lines AND 2 Pillow comparisons

(The last is the same *kind* of error as "one inverse-transform constant off by one"
above, on a different constant, and it costs a different number of lines — 27 rather than
21. Both were measured; neither number is the other's.)

**The first of those was not caught at first, and that is the interesting one.** The two
guards overlap: with the frame-marker refusal deleted, the walk steps past the marker, no
frame is found, and the *other* guard answers `no frame header was found`. The gate had
been testing for a `jpeg:` prefix, so it passed — with the specific refusal gone, which is
the whole thing the specific refusal exists for. Each case now checks its own words. **A
gate that accepts any refusal cannot tell a precise one from a vague one.**

## Progressive (2026-09-08)

Four, each reverted, on the corpus as it stands:

| poison | what fails |
|---|---|
| a redefined Huffman table no longer shadows the earlier one | 5 |
| a non-interleaved scan walked over the MCU grid | 2 (`progodd` among them) |
| the end-of-band run swallowed (`EOBRUN = 0`) | 2 |
| the end-of-band run off by one (`1 << r` for `(1 << r) - 1`) | 6 |

**Two of these did not bite at first, and the corpus is what changed.**

Walking a non-interleaved scan over the MCU grid passed everything, because at 64×48
with 4:2:0 a component's own block count and `mcux * hs` happen to be equal. `progodd`
is 37×29, where they are not, and it is the only file that fails when that line is
wrong.

Swallowing the end-of-band run passed too — including against a *purely uniform* image,
which was the obvious thing to reach for because it produces the longest runs (1024
blocks in two bytes of entropy data). It cannot bite there: skipping the run and
decoding each block only to find it empty both leave the AC coefficients at zero, so
the poison and the correct code produce the same picture. The run has to be followed by
CONTENT before swallowing it desynchronises anything. `progeob` is a uniform field with
detail underneath it for that reason, and the poison fails there.

The off-by-one is the same arithmetic and bites everywhere, which is worth noting
beside the other: two poisons on one expression, one detectable almost anywhere and one
needing a particular input.

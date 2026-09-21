# Your puzzle placement guide

For the conceptual explanation, algorithms, and system diagrams, read **[How it works](docs/HOW_IT_WORKS.md)**.

[![Placement example showing the photographed gap, the software's proposed piece overlay, and the matching box artwork](docs/assets/upper-left-example.jpg)](docs/HOW_IT_WORKS.md)

*How the software checks a placement: compare the photographed gap, the proposed overlay, and the box artwork. These example placements are suggestions, not individually confirmed fits.*

Open **[output/index.html](output/index.html)** in a browser. It runs offline without installing anything. Start with the high-confidence entries. Click a piece, locate it on the annotated source sheet, and compare its placement preview before trying the fit.

To track assembly, select a piece and tick **I've placed this piece**. Uncheck it to undo. Completed pieces get checkmarks in the list and on the map; **Hide placed pieces** removes them from both. Your count updates automatically, and progress survives refreshes in the same browser at the same address (for example, `http://localhost:8001`). Progress is stored in that browser, not synced between devices or included in the downloadable ZIP.

The result contains **109 high-confidence suggestions (74% of 147 entries)**, **19 tentative suggestions**, and **19 unresolved entries**. These are image-based suggestions, not physically verified placements.

For a visual explanation, open **[the upper-left example](output/start-here.jpg)**, showing the candidates `A-g5` and `B-a4` against a small photographed gap and the box artwork. These specific placements have not been individually confirmed. The previous five-piece starter group was questioned during physical assembly and has been withdrawn as the featured recommendation.

The owner reports successfully placing roughly half of the suggested pieces. Exact confirmed IDs are not recorded here, so the original confidence totals above remain algorithm-generated labels rather than measured accuracy.

- **A** is the first large sheet, photographed in `sheet-a-main.jpg`.
- **B** is the second large sheet, photographed in `sheet-b-main.jpg`.
- **C** is the small sheet, photographed in `sheet-c-main.jpg`.

The generated labels on the annotated sheets are authoritative. They generally follow the handwritten row/column layout, but connected groups can span handwritten positions. An entry can represent several already joined pieces. Coverage is measured over photographed entries, not a verified count of physical pieces or of all gaps in the puzzle.

Coordinates are percentages from the **left** and **top** of the complete puzzle, with the woman upright. Rotation means **clockwise from the piece's appearance in its annotated sheet/crop**. It is approximate; a few degrees of adjustment may be needed. The three preview panels show the reference, the loose piece superimposed on that reference, and the same piece superimposed on your current board.

Confidence describes the strength of image evidence, not a calibrated probability. Repeated blossoms, gold backgrounds, glare, and photo perspective can cause false matches. Neighbor suggestions use predicted contour proximity and still need a physical fit check. Unresolved pieces are included in the index without placement coordinates.

## Plan and implementation

1. Inventory the photos and distinguish repeated views from unique pieces. Use the clearest complete photo of each loose-piece sheet, the box photograph, and the current puzzle photograph.
2. Correct perspective and register the assembled puzzle to the box artwork using hundreds of consistent image features.
3. Extract loose pieces from the light paper background, including connected groups. Separate accidental contacts between neighboring entries and preserve a labeled source sheet for identification.
4. Generate placement hypotheses with rotation-invariant local features and a full-image search comparing artwork across 36 rotations. Compare the spatial arrangement of colors and details in the artwork.
5. Refine candidate positions, angles, and scale. Check whether the predicted piece lies in a photographed gap, compare alternative matches, and inspect overlaps and visual previews.
6. Publish an offline interactive guide, annotated placement maps, a CSV table, and nearby-piece suggestions. Keep uncertain entries unresolved.

## Files

- `output/index.html`: interactive guide; keep the whole output folder together.
- `output/placement-map-state.jpg`: proposed placements on your current puzzle.
- `output/placement-map-reference.jpg`: proposed placements on the artwork.
- `output/sheet-A-labels.jpg`, `sheet-B-labels.jpg`, `sheet-C-labels.jpg`: piece identification sheets.
- `output/placements.csv`: placements and candidate neighbors in a spreadsheet-friendly format.
- `output/guide-data.json`: machine-readable guide data.
- `output/review-*.jpg`: compact inspection pages.

## Reproduce the analysis

Python 3 with the dependencies in `requirements.txt` is needed only to rerun the analysis, not to view the guide. After cloning the repository, create a local environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Then run the analysis:

```sh
.venv/bin/python scripts/solve.py
.venv/bin/python scripts/dense.py
.venv/bin/python scripts/refine.py
.venv/bin/python scripts/publish.py
.venv/bin/python scripts/starter.py
```

The photo corner coordinates and contact-separation cuts are specific to these photos. New photos require recalibration. The scripts only read from `images/` and never modify those files. The analysis runs locally; it does not call an image-generation service or paid model API.

## Tests

After installing `requirements.txt`, run the basic regression suite:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

The suite uses Python's built-in `unittest`; no additional Python dependencies
are needed. It checks perspective and rotation geometry, synthetic artwork
matching and refinement, guide exports, neighbors and overlaps, documentation
illustrations, metadata removal, and the pre-commit hook. Fixtures and script
outputs live in temporary directories, leaving your photos and guide untouched.
It does not rerun the complete puzzle analysis or measure physical placement
accuracy. The hook tests require Git and Bash 4.4+; illustration generation uses
the same DejaVu Sans font as the scripts (`fonts-dejavu-core` on Debian/Ubuntu).

## Code formatting

Python files are formatted and linted with [ruff](https://docs.astral.sh/ruff/),
configured in `ruff.toml`. A pre-commit hook applies it to staged files
automatically; enable it once per clone:

```sh
git config core.hooksPath .githooks
```

The hook fetches a pinned ruff through [uv](https://docs.astral.sh/uv/), so no
extra entry in `requirements.txt` is needed. It reformats staged files and
restages them, and stops the commit only when a finding needs a human decision.
Skip it for a single commit with `git commit --no-verify`.
Without uv, the hook accepts an installed Ruff only if it matches the pinned version.

Renamed Python files are checked too. Files with both staged and unstaged
changes stop the hook before formatting, to preserve partial staging. Commits
without staged Python changes do not require Ruff. The hook runs formatting and
linting; run the test command above separately.

To run the same checks by hand:

```sh
uv tool run ruff@0.16.8 format .
uv tool run ruff@0.16.8 check --fix .
```

## Continuous integration

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every push to
`main` and on every pull request, in two parallel jobs:

- **Ruff and shell checks**: `ruff format --check` and `ruff check` over the
  repository, plus ShellCheck on the pre-commit hook.
- **Tests**: installs `requirements.txt` on Python 3.13 and runs the suite.

CI installs the Ruff version read straight out of `.githooks/pre-commit`, so a
local commit and a CI run can never disagree about formatting. Nothing in the
workflow needs repository secrets or write permissions.

## License

The code, documentation, and the author's photographs are released under the
[MIT License](LICENSE). The puzzle artwork reproduced in `images/`, `output/`, and
`docs/` is third-party copyright and is **not** covered by that license — see
[NOTICE](NOTICE).

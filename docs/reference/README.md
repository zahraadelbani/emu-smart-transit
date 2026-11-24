# Official reference provenance

The initial checkout contained no PDF. The file `2026-27-fall.pdf` was downloaded on 2026-11-24 from the PDF linked by [EMU Transportation Bus Services](https://transportation.emu.edu.tr/en/bus-services). `timetable-review.png` is a local rendering used for visual review. It is not an application asset and the official logo is not used in the UI.

`verified-timetable.json` records visually reviewed weekday times and Saturday departures that agree in both paired columns. Its runtime copy is `backend/transit/data/verified-timetable.json`. Campus ring departures/returns were also checked against the rendered PDF and are seeded separately. Import effective start is the review date, not an invented semester opening date; the PDF does not provide a precise semester end date.

The Saturday note specifies joint Lines 1+4 and 2+5, while column times differ within each pair. Unmatched times remain explicitly listed under `saturday_review_required` and are not asserted to be joint departures. Ask the transportation department before importing those as an operational service. The UI warns that the Saturday view is incomplete.

External line colours follow the PDF's map strokes: 1 yellow, 2 cyan, 4 purple, 5 red. Display hex values are representative screen colours, not an EMU-published brand specification. The PDF's gradient heading colours are not used as line identifiers. Campus ring uses neutral grey because a single official line colour was not established. Unverified/demo paths are dashed. Named services are verified independently from geography; no official stop coordinates or surveyed route path is claimed.

The current website also mentions Route 3 / Beach Club and an electric shuttle. They were not silently added to the requested four-line operating model. Their current service scope and the second campus service require department confirmation.

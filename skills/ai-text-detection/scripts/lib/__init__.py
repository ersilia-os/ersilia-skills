"""The ai-text-detection library: everything the command-line steps in scripts/ share.

    common      paths, constants, messages, JSON and JSON-lines files
    http        requests with the skill's User-Agent
    stats       AUROC, quantiles, correlation, missing values
    text        text primitives: words, sentences, sections, paragraphs, prose
                detection, fixed-size windows for stylometry
    extract     PDF, DOCX and plain text into text.json: sections, references, hidden text
    style       the style score: window features and the calibrated model
    splits      the units detectors see: passages (the reader's unit) and the
                section / passage / overlapping-window plan
    detectors   the web-detector registry, result parsers, highlight colours, and where
                scores are kept
    evidence    the calibrated combination of detectors across splits
    grading     every line of evidence into one tier and defensible statements
    report      the HTML report
    europepmc   open-access human text for the calibration corpus and the controls

How the code is organised:

* A script in scripts/ is one command: it parses arguments, calls a function that
  returns the result, writes it to the work folder and prints a summary. Logic used by
  one command lives in its script; logic used by two or more lives here.
* The library never imports a script, and no script imports another (selftest.py, which
  tests them, is the exception). Dependencies point from the commands to the library.
* It needs only the standard library. pymupdf, python-docx and Playwright are imported
  where they are used, so everything else runs without the conda env.
"""

"""The ai-text-detection library: everything the command-line steps in scripts/ share.

    common      paths, constants, messages, JSON files
    text        text primitives: words, sentences, prose detection, section lookup,
                fixed-size windows for stylometry
    style       the style score: window features and the calibrated model
    splits      the units detectors see: passages (the reader's unit) and the
                section / passage / overlapping-window plan
    detectors   the web-detector registry, result parsers, highlight colours, and the
                per-document results state
    evidence    the calibrated combination of detectors across splits
    grading     every line of evidence into one tier and defensible statements
    report      the HTML report
    formal      the formal assessment: the evidence as a procedure aligned with official rules

Scripts import it as ``from lib.<module> import ...``; it needs only the standard library.
The library never imports a script: dependencies point from the steps to the library.
"""

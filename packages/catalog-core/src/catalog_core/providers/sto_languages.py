"""Serienstream labels observed together on detail, season and recent metadata.

The combined flag establishes subtitle language only. It does not establish
English (or Japanese) audio; no audio language is inferred for subtitle offers.
"""

LABELS = {"Deutsch": "de-dub", "Englisch": "en-dub", "Ger-Sub": "de-sub"}
FLAGS = {
    "svg-flag-german": "de-dub",
    "svg-flag-english": "en-dub",
    "svg-flag-english-german": "de-sub",
}

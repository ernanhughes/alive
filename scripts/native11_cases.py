"""Frozen, meaningfully different controlled excerpts; no measured user utility."""

GOAL = "Understand Python memory growth and choose a diagnostic for allocation changes."
GC = "https://docs.python.org/3/library/gc.html"
TRACE = "https://docs.python.org/3/library/tracemalloc.html"
CASES = {
    "initial": (
        "Python memory research workbench. Review one source at a time and distinguish "
        "background information from a diagnostic for allocation changes.",
        False,
        None,
    ),
    "distinct-1": (
        "Python memory background: reference counting is supplemented by an optional "
        "cycle collector. This excerpt contains no allocation comparison or diagnostic steps.",
        False,
        GC,
    ),
    "distinct-2": (
        "Python memory configuration: automatic garbage collection can be enabled or "
        "disabled. This excerpt does not identify which code allocated growing memory.",
        False,
        GC,
    ),
    "distinct-3": (
        "Python memory debugging: GC debug flags can retain collected objects for "
        "inspection. This excerpt does not provide a before-and-after allocation trace.",
        False,
        GC,
    ),
    "suppressed-1": (
        "Python memory diagnostic: tracemalloc can compare two allocation snapshots "
        "and report differences by source line. Start tracing before the workload "
        "whose allocation changes you want to investigate.",
        True,
        TRACE,
    ),
    "suppressed-2": (
        "Python memory investigation: take an allocation snapshot before a workload, "
        "take another afterwards, and compare the snapshots to locate allocation growth.",
        True,
        TRACE,
    ),
    "paused-1": (
        "Python memory context: a garbage collection count is not itself a traceback "
        "identifying the source of newly allocated blocks. This observation offers no trace.",
        False,
        None,
    ),
    "paused-2": (
        "Python memory evidence: tracemalloc statistics can group allocated blocks by "
        "filename and line number. Inspect those source locations when investigating growth.",
        True,
        TRACE,
    ),
    "paused-3": (
        "Python memory retention experiment: a test log records that diagnostic output "
        "was not saved. No measured allocation result is available in this controlled record.",
        False,
        None,
    ),
    "probe-1": (
        "Python memory allocation changes can be examined with snapshot2.compare_to"
        "(snapshot1, 'lineno'). The returned statistics describe differences between "
        "the recorded allocations, with their source locations.",
        True,
        TRACE,
    ),
    "restored-1": (
        "Python memory tracing should begin early to capture allocations of interest. "
        "A diagnostic plan can compare a baseline snapshot with a post-workload snapshot.",
        True,
        TRACE,
    ),
    "stale-grant": (
        "Python memory source permissions expired after a backend restart. This is a "
        "controlled consent test, not a new allocation measurement.",
        False,
        None,
    ),
    "post-restart": (
        "Python memory investigation continues with the saved plan: review allocation "
        "differences and their source tracebacks, retaining the original observation date.",
        True,
        TRACE,
    ),
    "bad-hash": (
        "Python memory test: this reviewed excerpt must not be accepted with a different "
        "fingerprint. No diagnostic inference is authorised by a mismatched hash.",
        False,
        None,
    ),
    "budget-check": (
        "Python memory comparison: the next useful step is to inspect before-and-after "
        "allocation statistics, but this test deliberately exhausts the model budget.",
        True,
        None,
    ),
    "irrelevant": (
        "An astronomy reading list describes distant galaxies and telescope schedules. "
        "It contains no programming diagnostic or allocation information.",
        False,
        None,
    ),
}
# Ratings deliberately exercise branches. They are not a claim of genuine owner satisfaction.
RATINGS = {"distinct-1": False, "distinct-2": False, "distinct-3": False, "probe-1": True}
COMPARISON = [
    "distinct-1",
    "distinct-2",
    "distinct-3",
    "suppressed-1",
    "suppressed-2",
    "paused-1",
    "paused-2",
    "paused-3",
    "probe-1",
    "restored-1",
    "irrelevant",
    "probe-1",
]


def content(marker):
    return CASES[marker][0]

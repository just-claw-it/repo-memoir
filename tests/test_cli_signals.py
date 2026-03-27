from repomemoir.cli import _aggregate_contributor_signals


def test_aggregate_contributor_signals_uses_merged_and_closed_by():
    prs = [
        {"merged": True, "merged_by": "alice"},
        {"merged": True, "merged_by": "alice"},
        {"merged": False, "merged_by": "alice"},
        {"merged": True, "merged_by": "bob"},
    ]
    issues = [
        {"state": "closed", "closed_by": "carol"},
        {"state": "open", "closed_by": "carol"},
        {"state": "closed", "closed_by": "alice"},
    ]

    prs_merged, issues_resolved = _aggregate_contributor_signals(prs, issues)
    assert prs_merged == {"alice": 2, "bob": 1}
    assert issues_resolved == {"carol": 1, "alice": 1}


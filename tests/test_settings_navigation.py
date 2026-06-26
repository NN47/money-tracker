from pathlib import Path


def test_report_back_handler_only_matches_without_active_state():
    source = Path("handlers/report.py").read_text()

    assert "@router.message(StateFilter(None), F.text == BACK_TEXT)" in source
    assert "async def report_back" in source

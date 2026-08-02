from pathlib import Path

from solanal.console import ask_float, ask_int, ask_path


def _prompt_from(values):
    items = iter(values)
    return lambda _message: next(items)


def test_console_parses_default_numbers():
    prompt = _prompt_from(["", ""])
    assert ask_int(prompt, "Rayon", 80) == 80
    assert ask_float(prompt, "Décote", 10.0) == 10.0


def test_console_accepts_existing_file(tmp_path: Path):
    file_path = tmp_path / "argus.csv"
    file_path.write_text("make,model,year,min_price_chf,market_price_chf,max_price_chf\n", encoding="utf-8")
    prompt = _prompt_from([str(file_path)])
    assert ask_path(prompt, "CSV: ") == file_path

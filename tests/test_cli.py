import pytest
import os
import sys
from unittest.mock import MagicMock
from main import main, calculate_cost

def test_cli_parsing_missing_args(capsys):
    with pytest.raises(SystemExit):
        main([])
    captured = capsys.readouterr()
    assert "You must provide either an instance_type or a --file argument." in captured.err

def test_cli_quiet_mode_single_instance(mocker, capsys):
    mocker.patch("main.calculate_cost", return_value=123.45)
    
    main(["n4-standard-4", "-q"])
    
    captured = capsys.readouterr()
    # verify prints just the price
    assert captured.out.strip() == "123.45"

def test_cli_quiet_print_name(mocker, capsys):
    mocker.patch("main.calculate_cost", return_value=500.00)
    
    main(["n2d-highmem-32", "-q", "--print-name"])
    
    captured = capsys.readouterr()
    assert captured.out.strip() == "n2d-highmem-32,500.00"

def test_cli_file_batch(mocker, capsys, tmp_path):
    # Use real temp file to bypass open() mock problems with argparse reading gettext
    fake_file = tmp_path / "fake-list.txt"
    fake_file.write_text("n1-standard-1\nn2-standard-2\n")
    
    mock_calc = mocker.patch("main.calculate_cost", side_effect=[10.0, 20.0])
    
    main(["-f", str(fake_file), "-q", "--print-name"])
    
    assert mock_calc.call_count == 2
    captured = capsys.readouterr()
    lines = captured.out.strip().split("\n")
    assert lines[0] == "n1-standard-1,10.00"
    assert lines[1] == "n2-standard-2,20.00"

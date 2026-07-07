from alcove.cli import main


def test_cli_version_prints_package_version(capsys):
    code = main(["--version"])
    captured = capsys.readouterr()

    assert code == 0
    assert "alcove 0.1.0" in captured.out

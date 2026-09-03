from car_agent.verify_cli import Phase1Verifier, main


def test_phase1_verifier_records_all_acceptance_cases() -> None:
    verifier = Phase1Verifier()

    verifier.send("I want something under $45k.")
    recommendation = verifier.send(
        "It will be a weekend car for spirited driving, preferably a coupe."
    )
    assert recommendation.state.stage == "recommending"
    verifier.send("What should I inspect on the Honda S2000?")
    verifier.send("Please schedule a test drive for the Honda S2000.")
    verifier.send(
        "My name is Alex Rivera, my email is alex@example.com, and Saturday at 10am works."
    )

    assert verifier.complete
    assert all(item["status"] == "PASS" for item in verifier.report())


def test_cli_strict_mode_passes_the_guided_flow(monkeypatch, capsys) -> None:
    messages = iter(
        [
            "I want something under $45k.",
            "It will be a weekend car for spirited driving, preferably a coupe.",
            "What should I inspect on the Honda S2000?",
            "Please schedule a test drive for the Honda S2000.",
            "My name is Alex Rivera, my email is alex@example.com, and Saturday at 10am works.",
            "/quit",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _: next(messages))

    exit_code = main(["--strict"])

    assert exit_code == 0
    assert "Phase 1 verification: PASS" in capsys.readouterr().out

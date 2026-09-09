from car_agent.agent import DeterministicRouter
from car_agent.profiling import TimingRecorder


def test_timing_recorder_reports_exclusive_nested_time() -> None:
    recorder = TimingRecorder()

    with recorder.span("parent"):
        with recorder.span("child"):
            pass

    summaries = {summary.name: summary for summary in recorder.summaries()}

    assert summaries["parent"].calls == 1
    assert summaries["child"].calls == 1
    assert summaries["parent"].total_ms >= summaries["parent"].exclusive_ms
    assert recorder.root_total_ms > 0


def test_agent_profile_captures_input_flows_and_domain_tools() -> None:
    recorder = TimingRecorder()
    agent = DeterministicRouter(profiler=recorder)

    agent.respond("profile-test", "I want a weekend coupe under $45k with spirited driving.")

    names = {summary.name for summary in recorder.summaries()}
    assert "agent.turn" in names
    assert "agent.preference_parsing" in names
    assert "agent.inventory_mention_detection" in names
    assert "agent.recommendation_flow" in names
    assert "tool.list_inventory" in names
    assert "tool.get_vehicle_facts" in names

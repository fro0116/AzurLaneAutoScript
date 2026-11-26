from datetime import timedelta
from types import SimpleNamespace

import pytest

from module.island.assets import (
    ISLAND_ORDER_ACCEPT,
    ISLAND_ORDER_BACKGROUND,
    ISLAND_ORDER_COOLDOWN_SPEED_UP,
    ISLAND_ORDER_REQUIREMENTS_CHECK,
)
from module.island.order import IslandOrder


def make_order(monkeypatch, panel, selected_from):
    state = SimpleNamespace(now=100.0, frame=-1, clicks=[])
    monkeypatch.setattr('module.base.timer.time', lambda: state.now)
    main = object.__new__(IslandOrder)

    def screenshot():
        state.now += 0.25
        state.frame += 1
        main.device.image = state.frame

    main.device = SimpleNamespace(
        image=-1,
        screenshot=screenshot,
        click=lambda button: state.clicks.append((state.frame, button)),
    )
    main.is_order_selected = lambda button: state.frame >= selected_from
    main.appear = lambda button, **kwargs: button is panel
    return main, state


@pytest.mark.parametrize('panel', [ISLAND_ORDER_REQUIREMENTS_CHECK, ISLAND_ORDER_COOLDOWN_SPEED_UP])
def test_click_order_waits_for_target_selection(monkeypatch, panel):
    main, state = make_order(monkeypatch, panel, selected_from=4)
    target = object()

    assert main.click_order(target) is True
    assert state.frame == 4
    assert state.clicks == [(0, target)]


def test_click_order_retries_wrong_type_and_reports_timeout(monkeypatch):
    main, state = make_order(monkeypatch, ISLAND_ORDER_ACCEPT, selected_from=0)
    target = object()

    assert main.click_order(target, is_urgent=True) is False
    assert len(state.clicks) >= 3
    assert all(button is target for _, button in state.clicks)
    assert state.now >= 105


def test_execute_order_does_not_read_unconfirmed_requirements():
    main = object.__new__(IslandOrder)
    main.handle_island_additional = lambda: False
    main.handle_info_bar = lambda: False
    main.click_order = lambda *args, **kwargs: False
    main.appear = lambda *args, **kwargs: pytest.fail('Unconfirmed order panel inspected')
    main.scan_current_order_requirements = lambda: pytest.fail('Unconfirmed requirements scanned')

    assert main.execute_order(object()) is False


def make_scan_order(names, counters):
    """Build an IslandOrder whose requirement panel OCR reads the given names and counters."""
    main = object.__new__(IslandOrder)
    main.device = SimpleNamespace(image=object())
    main.requirement_name_ocr = SimpleNamespace(ocr=lambda image: names)
    main.requirement_counter_ocr = SimpleNamespace(ocr=lambda image: counters)
    return main


def test_scan_requirements_flags_unreadable_rows():
    main = make_scan_order(
        # A shortfall is colored, so its counter is read as a lone number: 11/12 became 70402/.
        names=['鋼鉱石', '皮素材', ''],
        counters=[(70402, 0, 70402), (937, 6, 931), (0, 0, 0)],
    )
    # object.__new__ has no DIC lookup, so map the two read names to item ids
    main.item_name_to_item_id = lambda name: {'鋼鉱石': 2701, '皮素材': 2603, '': None}[name]

    requirements, verified = main.scan_current_order_requirements()

    assert verified is False
    assert requirements == {2603: (937, 6, 931)}


def test_scan_requirements_accepts_complete_rows():
    main = make_scan_order(names=['白菜', '鉄鉱石', ''], counters=[(14, 34, -20), (1, 3, -2), (0, 0, 0)])
    main.item_name_to_item_id = lambda name: {'白菜': 2003, '鉄鉱石': 2703, '': None}[name]

    requirements, verified = main.scan_current_order_requirements()

    assert verified is True
    assert requirements == {2003: (14, 34, -20), 2703: (1, 3, -2)}


def test_execute_order_does_not_submit_unverified_requirements():
    main = object.__new__(IslandOrder)
    main.handle_island_additional = lambda: False
    main.handle_info_bar = lambda: False
    main.click_order = lambda *args, **kwargs: True
    main.appear = lambda *args, **kwargs: False
    main.next_runtime = []
    main.scan_current_order_requirements = lambda: ({2701: (11, 0, 11)}, False)
    main.is_order_satisfied = lambda *args, **kwargs: pytest.fail('Unverified requirements judged')
    main.submit_order = lambda **kwargs: pytest.fail('Unverified requirements submitted')

    assert main.execute_order(object()) is False


def make_submit_order(monkeypatch, panels, submit_visible_frames=None):
    """
    Build an IslandOrder whose fake device never changes the order panel.

    Args:
        panels (set): Buttons that match on the screenshot.
        submit_visible_frames (int | None): Frames in which the submit button is shown, None for always.
            The loop reuses the screenshot of the previous loop, so its first frame is -1.
    """
    state = SimpleNamespace(now=100.0, frame=-1, clicks=[])
    monkeypatch.setattr('module.base.timer.time', lambda: state.now)
    main = object.__new__(IslandOrder)

    def screenshot():
        state.now += 0.25
        state.frame += 1
        main.device.image = state.frame

    main.device = SimpleNamespace(
        image=-1,
        screenshot=screenshot,
        click=lambda button: state.clicks.append((state.now, button)),
    )
    main.handle_island_additional = lambda: False
    main.handle_island_order_level_up = lambda: False

    def match_template_color(button, **kwargs):
        if button is ISLAND_ORDER_ACCEPT:
            if submit_visible_frames is None:
                return True
            return state.frame < submit_visible_frames
        return button in panels

    main.match_template_color = match_template_color
    return main, state


def test_submit_order_stops_clicking_when_game_refuses(monkeypatch):
    main, state = make_submit_order(monkeypatch, panels=set())

    assert main.submit_order() is False
    assert len(state.clicks) == IslandOrder.SUBMIT_ATTEMPTS
    assert all(button is ISLAND_ORDER_ACCEPT for _, button in state.clicks)
    times = [now for now, _ in state.clicks]
    assert all(later - earlier >= 3 for earlier, later in zip(times, times[1:]))


def test_submit_order_reports_success_when_panel_closes(monkeypatch):
    main, state = make_submit_order(monkeypatch, panels={ISLAND_ORDER_BACKGROUND}, submit_visible_frames=0)

    assert main.submit_order() is True
    assert len(state.clicks) == 1


def test_cooldown_fallback_does_not_read_unconfirmed_panel(monkeypatch):
    main = object.__new__(IslandOrder)
    delays = []
    main.config = SimpleNamespace(task_delay=lambda **kwargs: delays.append(kwargs))
    main.device = SimpleNamespace(image=object())
    main.ui_ensure = lambda page: None
    main.detect_all_orders = lambda: None
    main.run_any_order = lambda: False
    main.season_orders = [object()]
    main.regular_cooldown_orders = [object()]
    main.get_order_remain_time = lambda button: timedelta(0)
    main.click_order = lambda button: False
    monkeypatch.setattr(IslandOrder, 'cooldown_time_ocr', property(
        lambda self: pytest.fail('Unconfirmed cooldown scanned')))

    main.run()

    assert main.next_runtime == []
    assert delays == [{'server_update': True}]

from fronda.adaptive import DisplayProfile, HeightMode, LayoutMode, ViewportMetrics, calculate_layout


def test_breakpoints_are_based_on_available_logical_width() -> None:
    assert calculate_layout(ViewportMetrics(800, 600, 719, 600)).layout_mode is LayoutMode.COMPACT
    assert calculate_layout(ViewportMetrics(800, 600, 720, 600)).layout_mode is LayoutMode.MEDIUM
    assert calculate_layout(ViewportMetrics(1400, 900, 1100, 900)).layout_mode is LayoutMode.EXPANDED
    assert calculate_layout(ViewportMetrics(2000, 1100, 1600, 1000)).layout_mode is LayoutMode.WIDE


def test_auto_television_uses_physical_size_only_as_signal() -> None:
    state = calculate_layout(ViewportMetrics(1280, 720, 1180, 660, physical_diagonal_inches=55, maximized=True))
    assert state.effective_profile is DisplayProfile.TELEVISION
    assert state.touch_target == 52


def test_compact_window_profile() -> None:
    state = calculate_layout(ViewportMetrics(900, 650, 860, 610))
    assert state.effective_profile is DisplayProfile.COMPACT_WINDOW
    assert state.height_mode is HeightMode.LOW


def test_4k_television_at_300_percent_keeps_television_profile() -> None:
    # 3840×2160 at 300% becomes ~1280×720 logical pixels. It must not be
    # treated as a compact monitor merely because the logical width shrinks.
    state = calculate_layout(
        ViewportMetrics(1280, 720, 1280, 720, dpr=3.0, physical_diagonal_inches=55, maximized=True)
    )
    assert state.effective_profile is DisplayProfile.TELEVISION
    assert state.layout_mode is LayoutMode.EXPANDED

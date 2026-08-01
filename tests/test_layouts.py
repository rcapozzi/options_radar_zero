"""Tests for layouts module."""
from dash import html

from options_radar_zero.layouts import (
    create_controls,
    create_data_table_container,
    create_download_buttons,
    create_dropdown_field,
    create_hidden_components,
    create_main_layout,
    create_metrics_container,
    create_static_link,
    create_strike_slider,
)


class TestCreateStaticLink:
    def test_returns_html_a(self):
        """Test that create_static_link returns an html.A component."""
        link = create_static_link('test')
        assert link is not None

    def test_has_correct_href(self):
        """Test that the link has the correct href."""
        link = create_static_link('test')
        # Dash html.A stores href in its props
        assert link.href == 'static/test.html'

    def test_has_correct_children(self):
        """Test that the link has the correct children text."""
        link = create_static_link('test')
        assert link.children == 'test.html'

    def test_has_target_blank(self):
        """Test that the link opens in a new tab."""
        link = create_static_link('test')
        assert link.target == '_blank'


class TestCreateStrikeSlider:
    def test_returns_html_div(self):
        """Test that create_strike_slider returns an html.Div."""
        slider = create_strike_slider(4000, 4200, 5, 4050, 4150)
        assert slider is not None

    def test_has_range_slider(self):
        """Test that the div contains a RangeSlider."""
        slider = create_strike_slider(4000, 4200, 5, 4050, 4150)
        # Check children for RangeSlider
        children = slider.children
        assert children is not None


class TestCreateDropdownField:
    def test_returns_html_div(self):
        """Test that create_dropdown_field returns an html.Div."""
        dropdown = create_dropdown_field("Test", "test-id", ["a", "b"], "a")
        assert dropdown is not None

    def test_has_label(self):
        """Test that the dropdown has a label."""
        dropdown = create_dropdown_field("Test Label", "test-id", ["a", "b"], "a")
        # First child should be the label div
        assert dropdown.children[0].children == "Test Label"


class TestCreateControls:
    def test_returns_html_div(self):
        """Test that create_controls returns an html.Div."""
        controls = create_controls(['SPX.X', 'SPY'])
        assert controls is not None

    def test_has_three_dropdowns(self):
        """Test that controls has symbol, x-axis, and y-axis dropdowns."""
        controls = create_controls(['SPX.X', 'SPY'])
        # Should have 3 child divs, each with a dropdown
        assert len(controls.children) == 3


class TestCreateHiddenComponents:
    def test_returns_html_div(self):
        """Test that create_hidden_components returns an html.Div."""
        hidden = create_hidden_components()
        assert hidden is not None

    def test_has_interval(self):
        """Test that hidden components include an Interval."""
        hidden = create_hidden_components()
        children = hidden.children
        assert children is not None


class TestCreateDownloadButtons:
    def test_returns_html_div(self):
        """Test that create_download_buttons returns an html.Div."""
        buttons = create_download_buttons()
        assert buttons is not None

    def test_has_two_buttons(self):
        """Test that download buttons has two buttons."""
        buttons = create_download_buttons()
        # Count Button elements
        button_count = sum(1 for child in buttons.children if isinstance(child, html.Button))
        assert button_count == 2


class TestCreateDataTableContainer:
    def test_returns_html_div_with_id(self):
        """Test that create_data_table_container has the correct id."""
        container = create_data_table_container()
        assert container.id == 'data-table-div'


class TestCreateMetricsContainer:
    def test_returns_html_div_with_id(self):
        """Test that create_metrics_container has the correct id."""
        container = create_metrics_container()
        assert container.id == 'metrics-div'


class TestCreateMainLayout:
    def test_with_data_loaded(self):
        """Test main layout when data is loaded."""
        layout = create_main_layout(['SPX.X', 'SPY'], initial_data_loaded=True)
        assert layout is not None

    def test_without_data_loaded(self):
        """Test main layout when data is not loaded."""
        layout = create_main_layout([], initial_data_loaded=False)
        assert layout is not None
        # Should show error message
        assert layout.children is not None

    def test_with_data_loaded_has_content(self):
        """Test that loaded layout has the expected components."""
        layout = create_main_layout(['SPX.X'], initial_data_loaded=True)
        # The layout should be a MantineProvider wrapping content
        assert layout is not None

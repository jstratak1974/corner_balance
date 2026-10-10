"""Corner Balance Lab - a touch-friendly Kivy app for Android and desktop.

The app calculates static corner-weight metrics, target wheel weights for a
chosen cross-weight percentage, and vertical centre-of-gravity height from a
rear-axle lift test.

The calculation model and workshop workflow are independently implemented from
the concepts described by Rob Robinette:

* https://robrobinette.com/corner_weight_calc.htm
* https://robrobinette.com/corner_weight.htm
* https://robrobinette.com/cg_height_calc.htm

Run the calculation tests without installing Kivy:

    python main.py --self-test

Run the graphical application after installing Kivy:

    python main.py
"""

from __future__ import annotations

__version__ = "1.0.0"

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
from typing import Any


class CalculationError(ValueError):
    """Raised when an input set cannot produce a meaningful result."""


@dataclass(frozen=True)
class CornerWeights:
    """Static wheel loads in one consistent unit (lb or kg)."""

    left_front: float
    right_front: float
    left_rear: float
    right_rear: float

    def validate(self) -> None:
        values = asdict(self)
        for name, value in values.items():
            if not math.isfinite(value):
                raise CalculationError(f"{name.replace('_', ' ').title()} must be finite.")
            if value <= 0:
                raise CalculationError(f"{name.replace('_', ' ').title()} must be greater than zero.")


@dataclass(frozen=True)
class CornerBalanceResult:
    """Calculated static balance metrics and cross-weight targets."""

    weights: CornerWeights
    target_cross_percent: float
    total: float
    front: float
    rear: float
    left: float
    right: float
    cross: float
    opposite_cross: float
    front_percent: float
    rear_percent: float
    left_percent: float
    right_percent: float
    cross_percent: float
    bite: float
    wedge_delta: float
    diagonal_step: float
    targets: CornerWeights

    @property
    def cross_error_percent(self) -> float:
        """Current cross percentage minus requested cross percentage."""

        return self.cross_percent - self.target_cross_percent

    @property
    def target_deltas(self) -> CornerWeights:
        """Target minus measured load at each wheel."""

        return CornerWeights(
            self.targets.left_front - self.weights.left_front,
            self.targets.right_front - self.weights.right_front,
            self.targets.left_rear - self.weights.left_rear,
            self.targets.right_rear - self.weights.right_rear,
        )


@dataclass(frozen=True)
class CGHeightResult:
    """Result of a rear-axle lift centre-of-gravity calculation."""

    total_weight: float
    level_front_weight: float
    raised_front_weight: float
    front_weight_change: float
    rear_lift: float
    incline_angle_degrees: float
    cg_height: float
    sensitivity_per_front_weight_unit: float


def parse_number(text: str, field_name: str) -> float:
    """Parse a finite decimal while accepting either decimal separator.

    A single comma is treated as a decimal separator. If both a comma and a
    period are present, commas are treated as grouping marks.
    """

    cleaned = text.strip().replace(" ", "")
    if not cleaned:
        raise CalculationError(f"{field_name} is required.")
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError as exc:
        raise CalculationError(f"{field_name} must be a number.") from exc
    if not math.isfinite(value):
        raise CalculationError(f"{field_name} must be finite.")
    return value


def calculate_corner_balance(
    weights: CornerWeights,
    target_cross_percent: float = 50.0,
) -> CornerBalanceResult:
    """Calculate balance metrics and target corner loads.

    Cross weight uses the right-front/left-rear diagonal. The target operation
    moves equal load between diagonals, so total, front/rear, and left/right
    totals are preserved mathematically.
    """

    weights.validate()
    if not math.isfinite(target_cross_percent):
        raise CalculationError("Target cross percentage must be finite.")
    if not 0.0 < target_cross_percent < 100.0:
        raise CalculationError("Target cross percentage must be between 0 and 100.")

    lf = weights.left_front
    rf = weights.right_front
    lr = weights.left_rear
    rr = weights.right_rear

    total = lf + rf + lr + rr
    front = lf + rf
    rear = lr + rr
    left = lf + lr
    right = rf + rr
    cross = rf + lr
    opposite_cross = lf + rr

    desired_cross = total * target_cross_percent / 100.0
    diagonal_step = (desired_cross - cross) / 2.0
    targets = CornerWeights(
        left_front=lf - diagonal_step,
        right_front=rf + diagonal_step,
        left_rear=lr + diagonal_step,
        right_rear=rr - diagonal_step,
    )

    if min(asdict(targets).values()) <= 0:
        raise CalculationError(
            "That target would require a zero or negative corner load. "
            "Choose a physically realistic target."
        )

    return CornerBalanceResult(
        weights=weights,
        target_cross_percent=target_cross_percent,
        total=total,
        front=front,
        rear=rear,
        left=left,
        right=right,
        cross=cross,
        opposite_cross=opposite_cross,
        front_percent=100.0 * front / total,
        rear_percent=100.0 * rear / total,
        left_percent=100.0 * left / total,
        right_percent=100.0 * right / total,
        cross_percent=100.0 * cross / total,
        bite=lr - rr,
        wedge_delta=cross - opposite_cross,
        diagonal_step=diagonal_step,
        targets=targets,
    )


def calculate_cg_height(
    level_weights: CornerWeights,
    raised_left_front: float,
    raised_right_front: float,
    wheelbase: float,
    level_rear_axle_height: float,
    raised_rear_axle_height: float,
) -> CGHeightResult:
    """Estimate CG height from level and rear-raised scale readings.

    Weight inputs must use one consistent unit. Wheelbase and both axle heights
    must use one consistent length unit. The result uses that same length unit.

    Formula::

        lift = raised_rear_axle_height - level_rear_axle_height
        angle = asin(lift / wheelbase)
        delta_front = raised_front_weight - level_front_weight
        cg_height = level_rear_axle_height
                    + delta_front * wheelbase / (total_weight * tan(angle))
    """

    level_weights.validate()
    named_values = {
        "Raised left-front weight": raised_left_front,
        "Raised right-front weight": raised_right_front,
        "Wheelbase": wheelbase,
        "Level rear-axle height": level_rear_axle_height,
        "Raised rear-axle height": raised_rear_axle_height,
    }
    for name, value in named_values.items():
        if not math.isfinite(value):
            raise CalculationError(f"{name} must be finite.")
        if value <= 0:
            raise CalculationError(f"{name} must be greater than zero.")

    rear_lift = raised_rear_axle_height - level_rear_axle_height
    if rear_lift <= 0:
        raise CalculationError("Raised rear-axle height must exceed its level height.")
    if rear_lift >= wheelbase:
        raise CalculationError("Rear lift must be smaller than the wheelbase.")

    total = sum(asdict(level_weights).values())
    level_front = level_weights.left_front + level_weights.right_front
    raised_front = raised_left_front + raised_right_front
    front_change = raised_front - level_front
    if front_change <= 0:
        raise CalculationError(
            "Raised front-axle weight must exceed level front-axle weight. "
            "Check scale positions, entered values, and suspension settling."
        )

    angle = math.asin(rear_lift / wheelbase)
    tangent = math.tan(angle)
    height_above_axle_line = front_change * wheelbase / (total * tangent)
    cg_height = level_rear_axle_height + height_above_axle_line
    sensitivity = wheelbase / (total * tangent)

    if not math.isfinite(cg_height) or cg_height <= 0:
        raise CalculationError("The entered measurements did not produce a valid CG height.")

    return CGHeightResult(
        total_weight=total,
        level_front_weight=level_front,
        raised_front_weight=raised_front,
        front_weight_change=front_change,
        rear_lift=rear_lift,
        incline_angle_degrees=math.degrees(angle),
        cg_height=cg_height,
        sensitivity_per_front_weight_unit=sensitivity,
    )


def signed(value: float, decimals: int = 1) -> str:
    """Format a number with an explicit sign."""

    return f"{value:+,.{decimals}f}"


def corner_report_text(result: CornerBalanceResult, unit: str) -> str:
    """Create the plain-text report used by copy and save actions."""

    w = result.weights
    t = result.targets
    d = result.target_deltas
    return (
        "CORNER BALANCE LAB\n"
        f"Measured: LF {w.left_front:.1f}, RF {w.right_front:.1f}, "
        f"LR {w.left_rear:.1f}, RR {w.right_rear:.1f} {unit}\n"
        f"Total: {result.total:.1f} {unit}\n"
        f"Front / rear: {result.front_percent:.2f}% / {result.rear_percent:.2f}%\n"
        f"Left / right: {result.left_percent:.2f}% / {result.right_percent:.2f}%\n"
        f"Cross (RF + LR): {result.cross:.1f} {unit} ({result.cross_percent:.2f}%)\n"
        f"Bite (LR - RR): {signed(result.bite)} {unit}\n"
        f"Wedge delta: {signed(result.wedge_delta)} {unit}\n"
        f"Target cross: {result.target_cross_percent:.2f}%\n"
        f"Targets: LF {t.left_front:.1f} ({signed(d.left_front)}), "
        f"RF {t.right_front:.1f} ({signed(d.right_front)}), "
        f"LR {t.left_rear:.1f} ({signed(d.left_rear)}), "
        f"RR {t.right_rear:.1f} ({signed(d.right_rear)}) {unit}\n"
        "Target deltas are scale-load changes, not coilover turns."
    )


def cg_report_text(result: CGHeightResult, weight_unit: str, length_unit: str) -> str:
    """Create the plain-text CG report used by copy and save actions."""

    return (
        "CG HEIGHT - REAR LIFT TEST\n"
        f"Total vehicle weight: {result.total_weight:.1f} {weight_unit}\n"
        f"Level front weight: {result.level_front_weight:.1f} {weight_unit}\n"
        f"Raised front weight: {result.raised_front_weight:.1f} {weight_unit}\n"
        f"Front weight change: {signed(result.front_weight_change)} {weight_unit}\n"
        f"Rear lift: {result.rear_lift:.2f} {length_unit}\n"
        f"Incline angle: {result.incline_angle_degrees:.3f} degrees\n"
        f"Estimated CG height: {result.cg_height:.2f} {length_unit} above ground\n"
        f"Sensitivity: {result.sensitivity_per_front_weight_unit:.3f} "
        f"{length_unit} per 1 {weight_unit} of total front-axle change"
    )


def run_self_tests() -> None:
    """Exercise the pure calculation layer without importing Kivy."""

    balanced = calculate_corner_balance(CornerWeights(700, 700, 700, 700))
    assert math.isclose(balanced.cross_percent, 50.0)
    assert math.isclose(balanced.wedge_delta, 0.0)
    assert all(math.isclose(value, 700.0) for value in asdict(balanced.targets).values())

    measured = CornerWeights(700, 650, 700, 750)
    result = calculate_corner_balance(measured, 50.0)
    expected = CornerWeights(675, 675, 725, 725)
    for name, expected_value in asdict(expected).items():
        assert math.isclose(getattr(result.targets, name), expected_value)
    assert math.isclose(result.targets.left_front + result.targets.right_front, result.front)
    assert math.isclose(result.targets.left_front + result.targets.left_rear, result.left)
    assert math.isclose(result.targets.right_front + result.targets.left_rear, result.total / 2)

    cg = calculate_cg_height(
        measured,
        raised_left_front=725,
        raised_right_front=675,
        wheelbase=94.5,
        level_rear_axle_height=11.75,
        raised_rear_axle_height=21.75,
    )
    expected_angle = math.degrees(math.asin(10.0 / 94.5))
    expected_height = 11.75 + 50.0 * 94.5 / (
        2800.0 * math.tan(math.asin(10.0 / 94.5))
    )
    assert math.isclose(cg.incline_angle_degrees, expected_angle, rel_tol=1e-12)
    assert math.isclose(cg.cg_height, expected_height, rel_tol=1e-12)

    assert math.isclose(parse_number("1,25", "test"), 1.25)
    assert math.isclose(parse_number("1,234.5", "test"), 1234.5)
    print("Corner Balance Lab: all calculation self-tests passed.")


KV = r"""
#:import dp kivy.metrics.dp
#:set BG (0.025, 0.043, 0.062, 1)
#:set PANEL (0.055, 0.082, 0.109, 1)
#:set PANEL_2 (0.074, 0.11, 0.145, 1)
#:set TEXT (0.91, 0.95, 0.98, 1)
#:set MUTED (0.59, 0.68, 0.74, 1)
#:set CYAN (0.10, 0.77, 0.88, 1)
#:set ORANGE (1.00, 0.55, 0.22, 1)
#:set GREEN (0.28, 0.82, 0.57, 1)

<Card@BoxLayout>:
    orientation: "vertical"
    size_hint_y: None
    height: self.minimum_height
    padding: dp(14)
    spacing: dp(10)
    canvas.before:
        Color:
            rgba: PANEL
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(14)]

<SectionTitle@Label>:
    color: CYAN
    font_size: "18sp"
    bold: True
    size_hint_y: None
    height: dp(30)
    text_size: self.width, None
    halign: "left"
    valign: "middle"

<BodyText@Label>:
    color: TEXT
    font_size: "14sp"
    markup: True
    size_hint_y: None
    text_size: self.width, None
    height: self.texture_size[1] + dp(6)
    halign: "left"
    valign: "top"

<FieldLabel@Label>:
    color: MUTED
    font_size: "12sp"
    size_hint_y: None
    height: dp(22)
    text_size: self.width, None
    halign: "left"
    valign: "middle"

<NumericInput@TextInput>:
    multiline: False
    input_type: "number"
    font_size: "18sp"
    foreground_color: TEXT
    background_normal: ""
    background_active: ""
    background_color: PANEL_2
    cursor_color: CYAN
    padding: [dp(12), dp(12), dp(12), dp(10)]
    size_hint_y: None
    height: dp(50)

<PrimaryButton@Button>:
    bold: True
    font_size: "14sp"
    color: BG
    background_normal: ""
    background_down: ""
    background_color: CYAN if self.state == "normal" else (0.08, 0.60, 0.69, 1)
    size_hint_y: None
    height: dp(48)

<SecondaryButton@Button>:
    font_size: "13sp"
    color: TEXT
    background_normal: ""
    background_down: ""
    background_color: PANEL_2 if self.state == "normal" else (0.10, 0.16, 0.20, 1)
    size_hint_y: None
    height: dp(46)

<UnitSpinner@Spinner>:
    font_size: "16sp"
    color: TEXT
    background_normal: ""
    background_color: PANEL_2
    size_hint_y: None
    height: dp(50)

<StatusText@Label>:
    color: GREEN
    font_size: "12sp"
    size_hint_y: None
    text_size: self.width, None
    height: max(dp(24), self.texture_size[1] + dp(6))
    halign: "left"
    valign: "middle"

<MainView>:
    do_default_tab: False
    tab_width: dp(145)
    tab_height: dp(52)
    background_color: BG
    border: [0, 0, 0, 0]
    strip_border: [0, 0, 0, 0]

    TabbedPanelItem:
        text: "BALANCE"
        background_normal: ""
        background_down: ""
        background_color: CYAN if self.state == "down" else PANEL_2
        color: BG if self.state == "down" else TEXT
        ScrollView:
            do_scroll_x: False
            bar_width: dp(5)
            BoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                padding: dp(14)
                spacing: dp(12)

                Label:
                    text: "CORNER BALANCE LAB"
                    color: TEXT
                    font_size: "25sp"
                    bold: True
                    size_hint_y: None
                    height: dp(38)
                    text_size: self.width, None
                    halign: "left"

                Label:
                    text: "Static load, cross weight, wedge, bite and target wheel loads"
                    color: MUTED
                    font_size: "13sp"
                    size_hint_y: None
                    height: dp(38)
                    text_size: self.width, None
                    halign: "left"
                    valign: "top"

                Card:
                    SectionTitle:
                        text: "1  SCALE READINGS"
                    BodyText:
                        text: "Enter all four readings in the same unit. Front of car is the first row."
                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: dp(166)
                        BoxLayout:
                            orientation: "vertical"
                            FieldLabel:
                                text: "LEFT FRONT  •  LF"
                            NumericInput:
                                id: lf_input
                                hint_text: "e.g. 700"
                        BoxLayout:
                            orientation: "vertical"
                            FieldLabel:
                                text: "RIGHT FRONT  •  RF"
                            NumericInput:
                                id: rf_input
                                hint_text: "e.g. 650"
                        BoxLayout:
                            orientation: "vertical"
                            FieldLabel:
                                text: "LEFT REAR  •  LR"
                            NumericInput:
                                id: lr_input
                                hint_text: "e.g. 700"
                        BoxLayout:
                            orientation: "vertical"
                            FieldLabel:
                                text: "RIGHT REAR  •  RR"
                            NumericInput:
                                id: rr_input
                                hint_text: "e.g. 750"
                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: dp(76)
                        BoxLayout:
                            orientation: "vertical"
                            FieldLabel:
                                text: "WEIGHT UNIT"
                            UnitSpinner:
                                id: weight_unit
                                text: "lb"
                                values: ["lb", "kg"]
                        BoxLayout:
                            orientation: "vertical"
                            FieldLabel:
                                text: "TARGET CROSS %"
                            NumericInput:
                                id: target_cross
                                text: "50.0"

                Card:
                    SectionTitle:
                        text: "2  CALCULATE & RECORD"
                    GridLayout:
                        cols: 2
                        spacing: dp(8)
                        size_hint_y: None
                        height: dp(154)
                        PrimaryButton:
                            text: "CALCULATE"
                            on_release: root.calculate_corner()
                        SecondaryButton:
                            text: "LOAD EXAMPLE"
                            on_release: root.load_corner_example()
                        SecondaryButton:
                            text: "SAVE SESSION"
                            on_release: root.save_session()
                        SecondaryButton:
                            text: "LOAD SESSION"
                            on_release: root.load_session()
                        SecondaryButton:
                            text: "COPY REPORT"
                            on_release: root.copy_corner_report()
                        SecondaryButton:
                            text: "CLEAR"
                            on_release: root.clear_corner()
                    StatusText:
                        id: corner_status
                        text: "No calculation yet."

                Card:
                    SectionTitle:
                        text: "3  RESULTS"
                    BodyText:
                        id: corner_results
                        text: root.corner_result_markup

                BodyText:
                    text: "[color=97aeba]Workshop note:[/color] Targets are desired scale readings, not a direct prescription for spring-perch turns. Make small changes, settle the suspension, and measure again."

    TabbedPanelItem:
        text: "CG HEIGHT"
        background_normal: ""
        background_down: ""
        background_color: CYAN if self.state == "down" else PANEL_2
        color: BG if self.state == "down" else TEXT
        ScrollView:
            do_scroll_x: False
            bar_width: dp(5)
            BoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                padding: dp(14)
                spacing: dp(12)

                Label:
                    text: "CG HEIGHT • REAR LIFT TEST"
                    color: TEXT
                    font_size: "23sp"
                    bold: True
                    size_hint_y: None
                    height: dp(42)
                    text_size: self.width, None
                    halign: "left"

                Card:
                    SectionTitle:
                        text: "1  LEVEL WEIGHTS"
                    BodyText:
                        text: "Use the same vehicle loading and scale positions for both measurements."
                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: dp(166)
                        BoxLayout:
                            orientation: "vertical"
                            FieldLabel:
                                text: "LEVEL LF"
                            NumericInput:
                                id: cg_lf
                        BoxLayout:
                            orientation: "vertical"
                            FieldLabel:
                                text: "LEVEL RF"
                            NumericInput:
                                id: cg_rf
                        BoxLayout:
                            orientation: "vertical"
                            FieldLabel:
                                text: "LEVEL LR"
                            NumericInput:
                                id: cg_lr
                        BoxLayout:
                            orientation: "vertical"
                            FieldLabel:
                                text: "LEVEL RR"
                            NumericInput:
                                id: cg_rr
                    SecondaryButton:
                        text: "USE BALANCE-TAB VALUES"
                        on_release: root.use_balance_for_cg()

                Card:
                    SectionTitle:
                        text: "2  REAR RAISED • FRONT ON SCALES"
                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: dp(76)
                        BoxLayout:
                            orientation: "vertical"
                            FieldLabel:
                                text: "RAISED LF"
                            NumericInput:
                                id: raised_lf
                        BoxLayout:
                            orientation: "vertical"
                            FieldLabel:
                                text: "RAISED RF"
                            NumericInput:
                                id: raised_rf

                Card:
                    SectionTitle:
                        text: "3  GEOMETRY"
                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: dp(250)
                        BoxLayout:
                            orientation: "vertical"
                            FieldLabel:
                                text: "WHEELBASE"
                            NumericInput:
                                id: wheelbase
                        BoxLayout:
                            orientation: "vertical"
                            FieldLabel:
                                text: "LEVEL REAR AXLE HEIGHT"
                            NumericInput:
                                id: axle_level
                        BoxLayout:
                            orientation: "vertical"
                            FieldLabel:
                                text: "RAISED REAR AXLE HEIGHT"
                            NumericInput:
                                id: axle_raised
                        BoxLayout:
                            orientation: "vertical"
                            FieldLabel:
                                text: "LENGTH UNIT"
                            UnitSpinner:
                                id: length_unit
                                text: "in"
                                values: ["in", "mm", "cm"]
                        BoxLayout:
                            orientation: "vertical"
                            FieldLabel:
                                text: "WEIGHT UNIT"
                            UnitSpinner:
                                id: cg_weight_unit
                                text: "lb"
                                values: ["lb", "kg"]

                Card:
                    SectionTitle:
                        text: "4  CALCULATE"
                    GridLayout:
                        cols: 2
                        spacing: dp(8)
                        size_hint_y: None
                        height: dp(102)
                        PrimaryButton:
                            text: "CALCULATE CG"
                            on_release: root.calculate_cg()
                        SecondaryButton:
                            text: "LOAD EXAMPLE"
                            on_release: root.load_cg_example()
                        SecondaryButton:
                            text: "COPY REPORT"
                            on_release: root.copy_cg_report()
                        SecondaryButton:
                            text: "CLEAR"
                            on_release: root.clear_cg()
                    StatusText:
                        id: cg_status
                        text: "For useful resolution, raise the rear axle substantially and safely."

                Card:
                    SectionTitle:
                        text: "5  RESULT"
                    BodyText:
                        text: root.cg_result_markup

                BodyText:
                    text: "[color=ff8c38]Safety:[/color] Use rated equipment, rigid level platforms, wheel restraints and redundant supports. Never work under a vehicle supported only by a jack."

    TabbedPanelItem:
        text: "SETUP GUIDE"
        background_normal: ""
        background_down: ""
        background_color: CYAN if self.state == "down" else PANEL_2
        color: BG if self.state == "down" else TEXT
        ScrollView:
            do_scroll_x: False
            bar_width: dp(5)
            BoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                padding: dp(14)
                spacing: dp(12)

                Label:
                    text: "MEASURE • ADJUST • REPEAT"
                    color: TEXT
                    font_size: "23sp"
                    bold: True
                    size_hint_y: None
                    height: dp(42)
                    text_size: self.width, None
                    halign: "left"

                Card:
                    SectionTitle:
                        text: "BEFORE THE SCALES"
                    BodyText:
                        text: "• Choose the exact fuel, ballast, driver and tyre-pressure condition you want to tune.\n• Put all four scale pads on a flat plane; shim and verify them carefully.\n• Confirm every cable/channel matches the physical LF, RF, LR and RR pad.\n• Power and zero the scales before loading the car.\n• Record initial ride heights and spring-perch positions."

                Card:
                    SectionTitle:
                        text: "ON THE SCALES"
                    BodyText:
                        text: "• Keep the steering straight and brakes released.\n• If adjustable anti-roll-bar links are fitted, remove preload according to your setup procedure.\n• Lower the car consistently, roll or slip the tyres to release bind, then bounce/settle gently.\n• Repeat the settling routine after every adjustment.\n• Take repeated readings and investigate any result that will not reproduce."

                Card:
                    SectionTitle:
                        text: "HOW ADJUSTMENTS PROPAGATE"
                    BodyText:
                        text: "Increasing support/preload at one corner generally adds static load to that corner and its diagonal partner while unloading the other diagonal. For example, adding at LF tends to increase LF and RR while decreasing RF and LR. The exact load change per turn depends on spring rate, motion ratio, geometry, friction and platform conditions."

                Card:
                    SectionTitle:
                        text: "TARGET STRATEGY"
                    BodyText:
                        text: "A 50% RF+LR cross target is a common neutral starting point for cars expected to turn both directions. An oval or asymmetric course may use a deliberate bias. The app accepts a custom target, but only track testing, temperatures and driver feedback can establish the best value for a particular car and venue."

                Card:
                    SectionTitle:
                        text: "CG LIFT TEST"
                    BodyText:
                        text: "Measure the car level first. Then raise the rear axle symmetrically while the front tyres remain on their scales. Measure rear axle-centre height before and after, not ramp height. Keep the car restrained, re-settle it, and repeat. Greater safe lift increases weight-transfer signal relative to scale resolution."

                BodyText:
                    text: "This app is a setup aid. It does not model suspension kinematics, aerodynamic load, tyre behaviour, transient weight transfer or vehicle stability. Validate all changes in a controlled environment."

    TabbedPanelItem:
        text: "ABOUT"
        background_normal: ""
        background_down: ""
        background_color: CYAN if self.state == "down" else PANEL_2
        color: BG if self.state == "down" else TEXT
        ScrollView:
            do_scroll_x: False
            bar_width: dp(5)
            BoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                padding: dp(14)
                spacing: dp(12)

                Label:
                    text: "ABOUT"
                    color: TEXT
                    font_size: "25sp"
                    bold: True
                    size_hint_y: None
                    height: dp(42)
                    text_size: self.width, None
                    halign: "left"

                Card:
                    SectionTitle:
                        text: "CORNER BALANCE LAB  •  v1.0.0"
                    BodyText:
                        text: "A standalone Kivy application for static corner-balance analysis and rear-lift CG-height estimation. It works offline and requests no Android permissions."

                Card:
                    SectionTitle:
                        text: "REFERENCE MATERIAL"
                    BodyText:
                        text: "Concepts and workshop procedure are based on Rob Robinette's public educational pages:\n\nhttps://robrobinette.com/corner_weight_calc.htm\n\nhttps://robrobinette.com/corner_weight.htm\n\nhttps://robrobinette.com/cg_height_calc.htm\n\nThis is an independent implementation and is not affiliated with or endorsed by the reference-site author."

                Card:
                    SectionTitle:
                        text: "DATA & LIMITATIONS"
                    BodyText:
                        text: "The app performs calculations on-device. The Save Session button stores one JSON file in the app's private data directory. Results depend entirely on correct scale mapping, consistent units, safe test geometry and repeatable measurements."

                BodyText:
                    text: "Use at your own risk. Vehicle setup changes can affect handling. Make small changes and test only where it is safe and legal to do so."
"""


def run_gui() -> None:
    """Import Kivy lazily and launch the app."""

    try:
        from kivy.app import App
        from kivy.core.clipboard import Clipboard
        from kivy.lang import Builder
        from kivy.properties import StringProperty
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.popup import Popup
        from kivy.uix.tabbedpanel import TabbedPanel
        from kivy.utils import platform
    except ImportError as exc:
        raise SystemExit(
            "Kivy is not installed. Run 'python -m pip install kivy==2.3.1' "
            "or use 'python main.py --self-test' for calculation tests."
        ) from exc

    if platform not in ("android", "ios"):
        from kivy.core.window import Window

        Window.size = (430, 850)
        Window.clearcolor = (0.025, 0.043, 0.062, 1)

    class MainView(TabbedPanel):
        corner_result_markup = StringProperty(
            "[color=97aeba]Enter four scale readings, then tap CALCULATE.[/color]"
        )
        cg_result_markup = StringProperty(
            "[color=97aeba]Enter the level and rear-raised measurements.[/color]"
        )

        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self._corner_result: CornerBalanceResult | None = None
            self._cg_result: CGHeightResult | None = None
            self._corner_plain_report = ""
            self._cg_plain_report = ""

        @staticmethod
        def _fmt(value: float) -> str:
            return f"{value:,.1f}"

        def _show_error(self, message: str) -> None:
            content = BoxLayout(orientation="vertical", padding=14, spacing=12)
            label = Label(
                text=message,
                color=(0.91, 0.95, 0.98, 1),
                text_size=(330, None),
                halign="left",
                valign="middle",
            )
            content.add_widget(label)
            popup = Popup(
                title="Check the inputs",
                content=content,
                size_hint=(0.9, None),
                height=260,
                auto_dismiss=True,
            )
            popup.open()

        def calculate_corner(self) -> None:
            try:
                weights = CornerWeights(
                    parse_number(self.ids.lf_input.text, "Left front"),
                    parse_number(self.ids.rf_input.text, "Right front"),
                    parse_number(self.ids.lr_input.text, "Left rear"),
                    parse_number(self.ids.rr_input.text, "Right rear"),
                )
                target = parse_number(self.ids.target_cross.text, "Target cross percentage")
                result = calculate_corner_balance(weights, target)
            except CalculationError as exc:
                self.ids.corner_status.text = str(exc)
                self._show_error(str(exc))
                return

            unit = self.ids.weight_unit.text
            d = result.target_deltas
            t = result.targets
            self._corner_result = result
            self._corner_plain_report = corner_report_text(result, unit)
            self.corner_result_markup = (
                f"[b]TOTAL[/b]  {self._fmt(result.total)} {unit}\n\n"
                f"[b]FRONT / REAR[/b]  {self._fmt(result.front)} ({result.front_percent:.2f}%)  /  "
                f"{self._fmt(result.rear)} ({result.rear_percent:.2f}%)\n"
                f"[b]LEFT / RIGHT[/b]  {self._fmt(result.left)} ({result.left_percent:.2f}%)  /  "
                f"{self._fmt(result.right)} ({result.right_percent:.2f}%)\n\n"
                f"[color=19c4e0][b]CROSS • RF + LR[/b][/color]  {self._fmt(result.cross)} {unit}  "
                f"({result.cross_percent:.2f}%)\n"
                f"Target error  {result.cross_error_percent:+.2f} percentage points\n"
                f"Bite • LR − RR  {signed(result.bite)} {unit}\n"
                f"Wedge delta  {signed(result.wedge_delta)} {unit}\n\n"
                f"[color=47d191][b]TARGETS AT {result.target_cross_percent:.2f}% CROSS[/b][/color]\n"
                f"LF  {self._fmt(t.left_front)}  [color=97aeba]({signed(d.left_front)})[/color]     "
                f"RF  {self._fmt(t.right_front)}  [color=97aeba]({signed(d.right_front)})[/color]\n"
                f"LR  {self._fmt(t.left_rear)}  [color=97aeba]({signed(d.left_rear)})[/color]     "
                f"RR  {self._fmt(t.right_rear)}  [color=97aeba]({signed(d.right_rear)})[/color]\n\n"
                "[color=97aeba]Parentheses show target minus measured load.[/color]"
            )
            self.ids.corner_status.text = "Calculation complete. Re-measure after every adjustment."

        def calculate_cg(self) -> None:
            try:
                weights = CornerWeights(
                    parse_number(self.ids.cg_lf.text, "Level left front"),
                    parse_number(self.ids.cg_rf.text, "Level right front"),
                    parse_number(self.ids.cg_lr.text, "Level left rear"),
                    parse_number(self.ids.cg_rr.text, "Level right rear"),
                )
                result = calculate_cg_height(
                    level_weights=weights,
                    raised_left_front=parse_number(self.ids.raised_lf.text, "Raised left front"),
                    raised_right_front=parse_number(self.ids.raised_rf.text, "Raised right front"),
                    wheelbase=parse_number(self.ids.wheelbase.text, "Wheelbase"),
                    level_rear_axle_height=parse_number(
                        self.ids.axle_level.text, "Level rear-axle height"
                    ),
                    raised_rear_axle_height=parse_number(
                        self.ids.axle_raised.text, "Raised rear-axle height"
                    ),
                )
            except CalculationError as exc:
                self.ids.cg_status.text = str(exc)
                self._show_error(str(exc))
                return

            weight_unit = self.ids.cg_weight_unit.text
            length_unit = self.ids.length_unit.text
            recommended_lift = {"in": 10.0, "mm": 254.0, "cm": 25.4}[length_unit]
            warning = ""
            if result.rear_lift < recommended_lift:
                warning = (
                    f"\n[color=ff8c38]Rear lift is below {recommended_lift:g} {length_unit}; "
                    "scale resolution may dominate the estimate.[/color]"
                )

            self._cg_result = result
            self._cg_plain_report = cg_report_text(result, weight_unit, length_unit)
            self.cg_result_markup = (
                f"[color=47d191][b]ESTIMATED CG HEIGHT[/b][/color]\n"
                f"[size=28sp]{result.cg_height:,.2f} {length_unit}[/size] above ground\n\n"
                f"Total weight  {result.total_weight:,.1f} {weight_unit}\n"
                f"Level front axle  {result.level_front_weight:,.1f} {weight_unit}\n"
                f"Raised front axle  {result.raised_front_weight:,.1f} {weight_unit}\n"
                f"Front change  {signed(result.front_weight_change)} {weight_unit}\n"
                f"Rear lift  {result.rear_lift:,.2f} {length_unit}\n"
                f"Incline angle  {result.incline_angle_degrees:.3f}°\n"
                f"Sensitivity  {result.sensitivity_per_front_weight_unit:.3f} {length_unit} "
                f"per 1 {weight_unit} front-axle change"
                f"{warning}"
            )
            self.ids.cg_status.text = "CG estimate complete. Repeat the lift test to check reproducibility."

        def load_corner_example(self) -> None:
            for widget_id, value in {
                "lf_input": "700",
                "rf_input": "650",
                "lr_input": "700",
                "rr_input": "750",
                "target_cross": "50.0",
            }.items():
                self.ids[widget_id].text = value
            self.ids.weight_unit.text = "lb"
            self.calculate_corner()

        def load_cg_example(self) -> None:
            values = {
                "cg_lf": "700",
                "cg_rf": "650",
                "cg_lr": "700",
                "cg_rr": "750",
                "raised_lf": "725",
                "raised_rf": "675",
                "wheelbase": "94.5",
                "axle_level": "11.75",
                "axle_raised": "21.75",
            }
            for widget_id, value in values.items():
                self.ids[widget_id].text = value
            self.ids.cg_weight_unit.text = "lb"
            self.ids.length_unit.text = "in"
            self.calculate_cg()

        def use_balance_for_cg(self) -> None:
            mapping = {
                "cg_lf": "lf_input",
                "cg_rf": "rf_input",
                "cg_lr": "lr_input",
                "cg_rr": "rr_input",
            }
            if any(not self.ids[source].text.strip() for source in mapping.values()):
                self._show_error("Enter all four readings on the Balance tab first.")
                return
            for target, source in mapping.items():
                self.ids[target].text = self.ids[source].text
            self.ids.cg_weight_unit.text = self.ids.weight_unit.text
            self.ids.cg_status.text = "Level weights copied from the Balance tab."

        def clear_corner(self) -> None:
            for widget_id in ("lf_input", "rf_input", "lr_input", "rr_input"):
                self.ids[widget_id].text = ""
            self.ids.target_cross.text = "50.0"
            self._corner_result = None
            self._corner_plain_report = ""
            self.corner_result_markup = (
                "[color=97aeba]Enter four scale readings, then tap CALCULATE.[/color]"
            )
            self.ids.corner_status.text = "Inputs cleared."

        def clear_cg(self) -> None:
            for widget_id in (
                "cg_lf",
                "cg_rf",
                "cg_lr",
                "cg_rr",
                "raised_lf",
                "raised_rf",
                "wheelbase",
                "axle_level",
                "axle_raised",
            ):
                self.ids[widget_id].text = ""
            self._cg_result = None
            self._cg_plain_report = ""
            self.cg_result_markup = (
                "[color=97aeba]Enter the level and rear-raised measurements.[/color]"
            )
            self.ids.cg_status.text = "Inputs cleared."

        def copy_corner_report(self) -> None:
            if not self._corner_plain_report:
                self._show_error("Calculate a corner-balance result before copying it.")
                return
            Clipboard.copy(self._corner_plain_report)
            self.ids.corner_status.text = "Corner-balance report copied to the clipboard."

        def copy_cg_report(self) -> None:
            if not self._cg_plain_report:
                self._show_error("Calculate a CG-height result before copying it.")
                return
            Clipboard.copy(self._cg_plain_report)
            self.ids.cg_status.text = "CG-height report copied to the clipboard."

        def _session_path(self) -> Path:
            return Path(App.get_running_app().user_data_dir) / "corner_balance_session.json"

        def save_session(self) -> None:
            payload = {
                "schema_version": 1,
                "saved_utc": datetime.now(timezone.utc).isoformat(),
                "corner": {
                    "lf": self.ids.lf_input.text,
                    "rf": self.ids.rf_input.text,
                    "lr": self.ids.lr_input.text,
                    "rr": self.ids.rr_input.text,
                    "target_cross_percent": self.ids.target_cross.text,
                    "weight_unit": self.ids.weight_unit.text,
                },
                "cg": {
                    "lf": self.ids.cg_lf.text,
                    "rf": self.ids.cg_rf.text,
                    "lr": self.ids.cg_lr.text,
                    "rr": self.ids.cg_rr.text,
                    "raised_lf": self.ids.raised_lf.text,
                    "raised_rf": self.ids.raised_rf.text,
                    "wheelbase": self.ids.wheelbase.text,
                    "level_rear_axle_height": self.ids.axle_level.text,
                    "raised_rear_axle_height": self.ids.axle_raised.text,
                    "weight_unit": self.ids.cg_weight_unit.text,
                    "length_unit": self.ids.length_unit.text,
                },
            }
            path = self._session_path()
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            except OSError as exc:
                self._show_error(f"Could not save the session: {exc}")
                return
            self.ids.corner_status.text = f"Session saved in the app data folder: {path.name}"

        def load_session(self) -> None:
            path = self._session_path()
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                corner = payload["corner"]
                cg = payload.get("cg", {})
            except FileNotFoundError:
                self._show_error("No saved session was found on this device.")
                return
            except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
                self._show_error(f"The saved session could not be loaded: {exc}")
                return

            corner_map = {
                "lf_input": "lf",
                "rf_input": "rf",
                "lr_input": "lr",
                "rr_input": "rr",
                "target_cross": "target_cross_percent",
            }
            for widget_id, key in corner_map.items():
                self.ids[widget_id].text = str(corner.get(key, ""))
            self.ids.weight_unit.text = str(corner.get("weight_unit", "lb"))

            cg_map = {
                "cg_lf": "lf",
                "cg_rf": "rf",
                "cg_lr": "lr",
                "cg_rr": "rr",
                "raised_lf": "raised_lf",
                "raised_rf": "raised_rf",
                "wheelbase": "wheelbase",
                "axle_level": "level_rear_axle_height",
                "axle_raised": "raised_rear_axle_height",
            }
            for widget_id, key in cg_map.items():
                self.ids[widget_id].text = str(cg.get(key, ""))
            self.ids.cg_weight_unit.text = str(cg.get("weight_unit", "lb"))
            self.ids.length_unit.text = str(cg.get("length_unit", "in"))
            self.ids.corner_status.text = "Saved session loaded. Tap CALCULATE to refresh results."

    class CornerBalanceApp(App):
        title = "Corner Balance Lab"

        def build(self) -> MainView:
            Builder.load_string(KV)
            return MainView()

    CornerBalanceApp().run()


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        run_self_tests()
    else:
        run_gui()

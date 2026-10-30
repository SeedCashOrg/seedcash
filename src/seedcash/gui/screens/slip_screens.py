import logging
import math
from seedcash.gui.components import (
    Button,
    GUIConstants,
    IconButton,
    SeedCashIconsConstants,
    TextArea,
)

from seedcash.gui.keyboard import TextEntryDisplay
from seedcash.gui.screens.screen import (
    RET_CODE__BACK_BUTTON,
    BaseTopNavScreen,
    BaseScreen,
    SeedCashButtonListWithNav,
)
from seedcash.hardware.buttons import HardwareButtonsConstants
from dataclasses import dataclass
from gettext import gettext as _
from PIL import ImageDraw
from seedcash.models import visual_hash as vh
from seedcash.models.scheme import Scheme

logger = logging.getLogger(__name__)

@dataclass
class SlipEntryScreen(BaseTopNavScreen):
    max_bits: int = 0

    def __post_init__(self):
        self.bits = ""
        self.cursor_position = 0
        self.show_back_button = True
        self.title = f"Introduce the {self.max_bits} bits"

        super().__post_init__()
        self._render_buttons()

    def _render_buttons(self):
        edge = GUIConstants.EDGE_PADDING
        padding = GUIConstants.COMPONENT_PADDING
        button_height = GUIConstants.BUTTON_HEIGHT
        self.input_y = GUIConstants.TOP_NAV_HEIGHT + padding
        self.input_text_height = button_height

        self.bits_display = TextEntryDisplay(
            canvas=self.renderer.canvas,
            rect=(
                edge,
                self.input_y,
                self.canvas_width - edge,
                self.input_y + self.input_text_height,
            ),
            cursor_mode=TextEntryDisplay.CURSOR_MODE__BAR,
            is_centered=False,
            cur_text=self.bits,
        )
        self.components.append(self.bits_display)

        button_width = (self.canvas_width - 4 * edge) // 3

        # Two rows of buttons, avoiding overlapping controls.
        first_row_y = (
            self.canvas_height
            - 2 * button_height
            - 2 * padding
        )
        second_row_y = first_row_y + button_height + padding

        x_positions = [
            edge,
            2 * edge + button_width,
            3 * edge + 2 * button_width,
        ]

        # Row 1: 0, 1, Delete
        self.components.extend([
            Button(
                text="0",
                width=button_width,
                height=button_height,
                screen_x=x_positions[0],
                screen_y=first_row_y,
            ),
            Button(
                text="1",
                width=button_width,
                height=button_height,
                screen_x=x_positions[1],
                screen_y=first_row_y,
            ),
            IconButton(
                icon_name=SeedCashIconsConstants.DELETE,
                width=button_width,
                height=button_height,
                screen_x=x_positions[2],
                screen_y=first_row_y,
            ),

            # Row 2: Cursor left, Cursor right, Confirm
            IconButton(
                icon_name=SeedCashIconsConstants.CHEVRON_LEFT,
                width=button_width,
                height=button_height,
                screen_x=x_positions[0],
                screen_y=second_row_y,
            ),
            IconButton(
                icon_name=SeedCashIconsConstants.CHEVRON_RIGHT,
                width=button_width,
                height=button_height,
                screen_x=x_positions[1],
                screen_y=second_row_y,
            ),
            IconButton(
                icon_name=SeedCashIconsConstants.CHECK,
                width=button_width,
                height=button_height,
                screen_x=x_positions[2],
                screen_y=second_row_y,
            ),
        ])

        self.selected_button = 2
        self.last_button = 2
        self.top_nav.is_selected = False
        self.components[self.selected_button].is_selected = True

        self._update_bits_display()

    def _update_bits_display(self):
        """Redraw the text and place the cursor at its current position."""
        self.bits_display.render(
            cur_text=self.bits,
            cursor_position=self.cursor_position,
        )

    def _select_button(self, next_button: int):
        """Change the selected button and redraw both selection states."""
        if next_button == self.selected_button:
            return

        current = self.components[self.selected_button]
        current.is_selected = False
        current.render()

        self.selected_button = next_button

        selected = self.components[self.selected_button]
        selected.is_selected = True
        selected.render()

    def _button_pressed(self, button: str):
        """Apply an action to the bit string at the current cursor position."""
        if button in ("0", "1"):
            if len(self.bits) < self.max_bits:
                self.bits = (
                    self.bits[:self.cursor_position]
                    + button
                    + self.bits[self.cursor_position:]
                )
                self.cursor_position += 1

        elif button == "BACKSPACE":
            if self.cursor_position > 0:
                self.bits = (
                    self.bits[:self.cursor_position - 1]
                    + self.bits[self.cursor_position:]
                )
                self.cursor_position -= 1

        elif button == "CURSOR_LEFT":
            self.cursor_position = max(0, self.cursor_position - 1)

        elif button == "CURSOR_RIGHT":
            self.cursor_position = min(
                len(self.bits),
                self.cursor_position + 1,
            )

        self._update_bits_display()

    def _run(self):
        while True:
            user_input = self.hw_inputs.wait_for(
                HardwareButtonsConstants.KEYS__LEFT_RIGHT_UP_DOWN
                + HardwareButtonsConstants.KEYS__ANYCLICK
            )

            with self.renderer.lock:

                # Handle top navigation.
                if self.top_nav.is_selected:
                    if user_input in (
                        HardwareButtonsConstants.KEY_DOWN,
                        HardwareButtonsConstants.KEY_RIGHT,
                    ):
                        self.top_nav.is_selected = False
                        self.top_nav.render_buttons()

                        self.components[self.last_button].is_selected = True
                        self.components[self.last_button].render()

                    elif user_input in (
                        HardwareButtonsConstants.KEY_LEFT,
                        HardwareButtonsConstants.KEY_UP,
                    ):
                        continue

                    elif user_input in HardwareButtonsConstants.KEYS__ANYCLICK:
                        if self.top_nav.show_back_button:
                            return RET_CODE__BACK_BUTTON

                    self.renderer.show_image()
                    continue

                next_button = None

                # Horizontal navigation within each row.
                if user_input == HardwareButtonsConstants.KEY_LEFT:
                    next_button = {3: 2,4: 3,6: 5,7: 6}.get(self.selected_button)

                elif user_input == HardwareButtonsConstants.KEY_RIGHT:
                    next_button = {2: 3,3: 4,5: 6,6: 7}.get(self.selected_button)

                # Vertical navigation between rows and top navigation.
                elif user_input == HardwareButtonsConstants.KEY_UP:
                    if self.selected_button in (5, 6, 7):
                        next_button = self.selected_button - 3

                    elif self.selected_button in (2, 3, 4):
                        self.last_button = self.selected_button
                        self.components[self.selected_button].is_selected = False
                        self.components[self.selected_button].render()

                        self.top_nav.is_selected = True
                        self.top_nav.render_buttons()

                elif user_input == HardwareButtonsConstants.KEY_DOWN:
                    if self.selected_button in (2, 3, 4):
                        next_button = self.selected_button + 3

                if next_button is not None:
                    self._select_button(next_button)

                elif user_input in HardwareButtonsConstants.KEYS__ANYCLICK:
                    button_actions = {
                        2: "0",
                        3: "1",
                        4: "BACKSPACE",
                        5: "CURSOR_LEFT",
                        6: "CURSOR_RIGHT",
                        7: "CONFIRM",
                    }

                    action = button_actions[self.selected_button]

                    if action == "CONFIRM":
                        if len(self.bits) != self.max_bits:
                            self.renderer.show_image()
                            continue

                        return self.bits

                    self._button_pressed(action)

                self.renderer.show_image()

@dataclass
class SlipBitsScreen(BaseScreen):
    bits: str = ""

    def __post_init__(self):
        super().__post_init__()

        if not self.bits:
            self.bits = ""

        self.bits_length = len(self.bits)
        self.current_page = 0
        self.bits_per_page = 64  # 4 buttons × 16 bits per button
        self.total_pages = (
            self.bits_length + self.bits_per_page - 1
        ) // self.bits_per_page

        # Calculate layout for bit display
        self.bit_height = GUIConstants.BUTTON_HEIGHT

        # Position bits below the top navigation
        self.bit_y = 4 * GUIConstants.COMPONENT_PADDING
        self.bit_x = 2 * GUIConstants.COMPONENT_PADDING
        self.bit_width = self.canvas_width - 4 * GUIConstants.COMPONENT_PADDING

        # Position for navigation buttons
        self.nav_buttons_y = (
            self.canvas_height - GUIConstants.BUTTON_HEIGHT - GUIConstants.EDGE_PADDING
        )

        # Create initial components
        self._create_components()

        # Start with back button selected
        self.selected_button = 0
        self.components[self.selected_button].is_selected = True

    def _create_components(self):
        """Create components for displaying seed words and navigation"""
        self.components.clear()

        # Add back button to return to the previous screen
        self.back_button = IconButton(
            icon_name=SeedCashIconsConstants.BACK,
            icon_size=GUIConstants.ICON_INLINE_FONT_SIZE,
            screen_x=GUIConstants.EDGE_PADDING,
            screen_y=self.nav_buttons_y,
            width=GUIConstants.TOP_NAV_BUTTON_SIZE,
            height=GUIConstants.TOP_NAV_BUTTON_SIZE,
            is_text_centered=False,
            is_selected=False,
        )

        # Add next/confirm button
        next_icon = (
            SeedCashIconsConstants.CHECK
            if self.current_page == self.total_pages - 1
            else SeedCashIconsConstants.CHEVRON_RIGHT
        )

        self.next_button = IconButton(
            icon_name=next_icon,
            icon_size=GUIConstants.ICON_INLINE_FONT_SIZE,
            screen_x=self.canvas_width
            - GUIConstants.TOP_NAV_BUTTON_SIZE
            - GUIConstants.EDGE_PADDING,
            screen_y=self.nav_buttons_y,
            width=GUIConstants.TOP_NAV_BUTTON_SIZE,
            height=GUIConstants.TOP_NAV_BUTTON_SIZE,
            is_selected=False,
        )
        self.components.append(self.next_button)

        if self.current_page > 0:
            self.components.append(self.back_button)

        # Add bits for current page as non-selectable buttons (16 bits per button)
        start_index = self.current_page * self.bits_per_page
        end_index = min(start_index + self.bits_per_page, self.bits_length)

        # Group bits into chunks of 16
        bits_chunk = self.bits[start_index:end_index]
        button_count = 0

        for i in range(0, len(bits_chunk), 16):
            # Get 16 bits for this button
            sixteen_bits = bits_chunk[i : i + 16]

            # Add spacing every 4 bits for readability (e.g., "0000 1111 0101 1010")
            formatted_bits = " ".join(
                [sixteen_bits[j : j + 4] for j in range(0, len(sixteen_bits), 4)]
            )

            bit_y_pos = self.bit_y + (button_count * (self.bit_height))

            button = Button(
                text=formatted_bits,
                is_text_centered=True,
                font_name=GUIConstants.FIXED_WIDTH_FONT_NAME,
                font_size=GUIConstants.BODY_FONT_SIZE,
                screen_x=self.bit_x,
                screen_y=bit_y_pos,
                width=self.bit_width,
                height=self.bit_height + 2 * GUIConstants.COMPONENT_PADDING,
                is_selected=False,
                background_color=GUIConstants.BUTTON_BACKGROUND_COLOR,
                font_color=GUIConstants.BUTTON_FONT_COLOR,
            )
            self.components.append(button)
            button_count += 1

    def _render(self):
        """Render the screen with seed words"""
        super()._render()

        # Render all components
        for component in self.components:
            component.render()

        self.renderer.show_image()

    def _run(self):
        self._render()  # Initial render
        while True:
            ret = self._run_callback()
            if ret is not None:
                logging.info("Exiting SeedCashSeedWordsScreen due to _run_callback")
                return ret

            user_input = self.hw_inputs.wait_for(
                [
                    HardwareButtonsConstants.KEY_LEFT,
                    HardwareButtonsConstants.KEY_RIGHT,
                ]
                + HardwareButtonsConstants.KEYS__ANYCLICK
            )

            with self.renderer.lock:
                if self.current_page == 0:  # select the next button
                    self.components[self.selected_button].is_selected = False
                    self.components[self.selected_button].render()
                    self.selected_button = 0
                    self.components[self.selected_button].is_selected = True
                    self.components[self.selected_button].render()

                    if user_input in HardwareButtonsConstants.KEYS__ANYCLICK:
                        self.current_page += 1
                        self._create_components()
                        # Keep selection on next button
                        self.selected_button = 0
                        self.components[self.selected_button].is_selected = True
                        self._render()

                else:
                    if user_input == HardwareButtonsConstants.KEY_LEFT:
                        # Move selection to back button
                        if self.selected_button == 0:
                            self.components[self.selected_button].is_selected = False
                            self.components[self.selected_button].render()
                            self.selected_button = 1
                            self.components[self.selected_button].is_selected = True
                            self.components[self.selected_button].render()

                    elif user_input == HardwareButtonsConstants.KEY_RIGHT:
                        # Move selection to next button
                        if self.selected_button == 1:
                            self.components[self.selected_button].is_selected = False
                            self.components[self.selected_button].render()
                            self.selected_button = 0
                            self.components[self.selected_button].is_selected = True
                            self.components[self.selected_button].render()
                    elif user_input in HardwareButtonsConstants.KEYS__ANYCLICK:
                        if self.selected_button == 1:  # Back button
                            if self.current_page > 1:
                                # Go back to previous page
                                self.current_page -= 1
                                self._create_components()
                                # Keep selection on back button
                                self.selected_button = 1
                                self.components[self.selected_button].is_selected = True
                                self._render()
                            else:
                                self.current_page = 0
                                self._create_components()
                                # Keep the selection on the next button
                                self.selected_button = 0
                                self.components[self.selected_button].is_selected = True
                                self._render()
                        elif self.selected_button == 0:  # Next/Confirm button
                            if self.current_page < self.total_pages - 1:
                                # Go to next page
                                self.current_page += 1
                                self._create_components()
                                # Keep selection on next button
                                self.selected_button = 0
                                self.components[self.selected_button].is_selected = True
                                self._render()
                            else:
                                # Confirm action
                                return "CONFIRM"

            self.renderer.show_image()


@dataclass
class GroupShareListScreen(SeedCashButtonListWithNav):
    fingerprint: str = None

    def __post_init__(self):
        if self.fingerprint:
            self.title = self.fingerprint
        super().__post_init__()

        icon_size = GUIConstants.ICON_FONT_SIZE + 12

        if self.fingerprint:
            fingerprint_image = vh.generate_lifehash(self.fingerprint)
            if self.show_check_button == True:
                self.paste_images.append(
                    (
                        fingerprint_image.resize((icon_size, icon_size)),
                        (3 * GUIConstants.EDGE_PADDING, GUIConstants.EDGE_PADDING),
                    )
                )
            elif self.show_back_button == True:
                self.paste_images.append(
                    (
                        fingerprint_image.resize((icon_size, icon_size)),
                        (self.canvas_width - icon_size - 3 * GUIConstants.EDGE_PADDING, GUIConstants.EDGE_PADDING),
                    )
                )
            


@dataclass
class VisualGroupShareScreen(BaseTopNavScreen):
    text: str = "Groups"
    threshold: int = 1
    total_members: int = 1
    passphrase: str = ""

    def __post_init__(self):
        self.show_back_button = True
        self.title = f"{self.text} Scheme"
        super().__post_init__()

        # Circle visualization parameters
        self.radius_int = int(self.canvas_width // 5)
        self.circle_radius = min(80, self.radius_int)
        self.circle_center = (
            self.canvas_width // 4,
            GUIConstants.EDGE_PADDING
            + GUIConstants.TOP_NAV_TITLE_FONT_SIZE
            + 20
            + self.circle_radius,
        )

        # Groups controls (left side)
        groups_x = (
            self.canvas_width
            - GUIConstants.EDGE_PADDING
            - GUIConstants.TOP_NAV_BUTTON_SIZE
        )

        # Threshold controls (right side)
        threshold_x = (
            groups_x - GUIConstants.EDGE_PADDING - GUIConstants.TOP_NAV_BUTTON_SIZE
        )

        self.up_btns_y = GUIConstants.TOP_NAV_HEIGHT
        self.down_btns_y = (
            self.canvas_height
            - GUIConstants.TOP_NAV_HEIGHT
            - GUIConstants.TOP_NAV_BUTTON_SIZE
        )

        # Groups up arrow
        self.total_members_up_button = IconButton(
            icon_name=SeedCashIconsConstants.PAGE_UP,
            screen_x=groups_x,
            screen_y=self.up_btns_y,
            width=GUIConstants.TOP_NAV_BUTTON_SIZE,
            height=GUIConstants.TOP_NAV_BUTTON_SIZE,
            is_text_centered=True,
        )
        self.components.append(self.total_members_up_button)

        # Groups down arrow
        self.total_members_down_button = IconButton(
            icon_name=SeedCashIconsConstants.PAGE_DOWN,
            screen_x=groups_x,
            screen_y=self.down_btns_y,
            width=GUIConstants.TOP_NAV_BUTTON_SIZE,
            height=GUIConstants.TOP_NAV_BUTTON_SIZE,
            is_text_centered=True,
        )
        self.components.append(self.total_members_down_button)

        # Threshold up arrow
        self.threshold_up_button = IconButton(
            icon_name=SeedCashIconsConstants.PAGE_UP,
            screen_x=threshold_x,
            screen_y=self.up_btns_y,
            width=GUIConstants.TOP_NAV_BUTTON_SIZE,
            height=GUIConstants.TOP_NAV_BUTTON_SIZE,
            is_text_centered=True,
        )
        self.components.append(self.threshold_up_button)

        # Threshold down button
        self.threshold_down_button = IconButton(
            icon_name=SeedCashIconsConstants.PAGE_DOWN,
            screen_x=threshold_x,
            screen_y=self.down_btns_y,
            width=GUIConstants.TOP_NAV_BUTTON_SIZE,
            height=GUIConstants.TOP_NAV_BUTTON_SIZE,
            is_text_centered=True,
        )
        self.components.append(self.threshold_down_button)

        self._buttons()

        # Set initial selection
        self.selected_key = 1
        self.selected_button = 5
        self.components[self.selected_key].is_selected = True
        self.components[self.selected_button].is_selected = True

    def _buttons(self):
        # Confirm button
        confirm_btn_width = self.canvas_width // 2 - 4 * GUIConstants.EDGE_PADDING
        if self.passphrase is not None:
            self.confirm_button = Button(
                text=_("Confirm"),
                screen_x=GUIConstants.EDGE_PADDING,
                screen_y=self.canvas_height
                - GUIConstants.BUTTON_HEIGHT
                - GUIConstants.EDGE_PADDING,
                width=confirm_btn_width,
                height=GUIConstants.BUTTON_HEIGHT,
            )

            # Add Passphrase button
            self.add_passphrase_button = Button(
                text=_("Add Passphrase") if not self.passphrase else _("Passphrase"),
                screen_x=confirm_btn_width + 2 * GUIConstants.EDGE_PADDING,
                screen_y=self.canvas_height
                - GUIConstants.BUTTON_HEIGHT
                - GUIConstants.EDGE_PADDING,
                width=self.canvas_width
                - confirm_btn_width
                - 3 * GUIConstants.EDGE_PADDING,
                height=GUIConstants.BUTTON_HEIGHT,
            )

            self.components.append(self.confirm_button)
            self.components.append(self.add_passphrase_button)

        else:
            self.confirm_button = Button(
                text=_("Confirm"),
                screen_x=GUIConstants.EDGE_PADDING,
                screen_y=self.canvas_height
                - GUIConstants.BUTTON_HEIGHT
                - GUIConstants.EDGE_PADDING,
                width=self.canvas_width - 2 * GUIConstants.EDGE_PADDING,
                height=GUIConstants.BUTTON_HEIGHT,
            )
            self.components.append(self.confirm_button)

    def _update_labels(self):
        """Update the text labels with current values"""
        label_y = (
            2 * self.radius_int
            + 3 * GUIConstants.COMPONENT_PADDING
            + GUIConstants.BUTTON_HEIGHT
        )
        label_x = 4 * GUIConstants.BUTTON_HEIGHT + 2 * GUIConstants.EDGE_PADDING

        self.total_members_label = TextArea(
            text=f"{self.text}:{self.total_members}",
            screen_x=GUIConstants.EDGE_PADDING,
            screen_y=label_y,
            width=label_x,
            font_name=GUIConstants.FIXED_WIDTH_FONT_NAME,
            font_size=GUIConstants.BODY_FONT_SIZE,
            is_text_centered=False,
        )

        self.threshold_label = TextArea(
            text=f"Threshold:{self.threshold}",
            screen_x=GUIConstants.EDGE_PADDING,
            screen_y=label_y
            + GUIConstants.BUTTON_HEIGHT
            - 2 * GUIConstants.EDGE_PADDING,
            width=label_x,
            font_name=GUIConstants.FIXED_WIDTH_FONT_NAME,
            font_size=GUIConstants.BODY_FONT_SIZE,
            is_text_centered=False,
        )

        self.total_members_label.render()
        self.threshold_label.render()

    def _draw_circle_segments(self):
        """Draw the circle with segments showing groups and threshold"""
        draw = ImageDraw.Draw(self.renderer.canvas)

        # Ensure threshold doesn't exceed groups
        self.threshold = min(self.threshold, self.total_members)

        # Draw the full circle outline
        draw.ellipse(
            [
                self.circle_center[0] - self.circle_radius,
                self.circle_center[1] - self.circle_radius,
                self.circle_center[0] + self.circle_radius,
                self.circle_center[1] + self.circle_radius,
            ],
            outline=GUIConstants.ACCENT_COLOR,
            width=2,
        )

        # If only 1 group, draw full circle filled or empty based on threshold
        if self.total_members == 1:
            fill_color = "white" if self.threshold >= 1 else "#333333"
            draw.ellipse(
                [
                    self.circle_center[0] - self.circle_radius,
                    self.circle_center[1] - self.circle_radius,
                    self.circle_center[0] + self.circle_radius,
                    self.circle_center[1] + self.circle_radius,
                ],
                fill=fill_color,
                width=2,
            )
            return

        # Calculate segment angles for multiple groups
        angle_per_group = 360 / self.total_members
        filled_color = "white"
        empty_color = "#333333"  # Dark gray for unfilled segments

        # Draw each segment
        for i in range(self.total_members):
            start_angle = i * angle_per_group - 90  # Start from top (-90 degrees)
            end_angle = (i + 1) * angle_per_group - 90

            # Determine if this segment should be filled (part of threshold)
            fill_color = filled_color if i < self.threshold else empty_color

            # Draw pie segment
            draw.pieslice(
                [
                    self.circle_center[0] - self.circle_radius,
                    self.circle_center[1] - self.circle_radius,
                    self.circle_center[0] + self.circle_radius,
                    self.circle_center[1] + self.circle_radius,
                ],
                start=start_angle,
                end=end_angle,
                fill=fill_color,
                outline=GUIConstants.BACKGROUND_COLOR,
                width=1,
            )

        # Draw dividing lines between segments (only if more than 1 group)
        if self.total_members > 1:
            for i in range(self.total_members):
                # Calculate the angle for the dividing line at the start of each segment
                line_angle = math.radians(i * angle_per_group - 90)  # Start from top
                line_end = (
                    self.circle_center[0] + self.circle_radius * math.cos(line_angle),
                    self.circle_center[1] + self.circle_radius * math.sin(line_angle),
                )
                draw.line(
                    [self.circle_center, line_end],
                    fill=GUIConstants.BACKGROUND_COLOR,
                    width=2,
                )

    def _render(self):
        super()._render()
        self._update_labels()
        self._draw_circle_segments()  # Draw our custom visualization
        for component in self.components:
            component.render()
        self.renderer.show_image()

    def _run(self):
        is_groups = True
        while True:
            input = self.hw_inputs.wait_for(HardwareButtonsConstants.ALL_KEYS)

            with self.renderer.lock:
                # Clear current selection
                if input == HardwareButtonsConstants.KEY1:
                    if is_groups and self.total_members < 16:
                        self.total_members += 1
                        if (
                            self.total_members > 1
                            and self.threshold == 1
                            and self.text == "Shares"
                        ):
                            self.threshold = 2
                        # Ensure threshold doesn't exceed groups when groups increase
                        self.threshold = min(self.threshold, self.total_members)
                        self.components[self.selected_key].is_selected = False
                        self.components[self.selected_key].render()
                        self.selected_key = 1  # Reset to first button
                        self.components[self.selected_key].is_selected = True
                        self.components[self.selected_key].render()
                    elif not is_groups and self.threshold < 16:
                        # Only increase threshold if it won't exceed groups
                        if self.threshold < self.total_members:
                            self.threshold += 1
                        self.components[self.selected_key].is_selected = False
                        self.components[self.selected_key].render()
                        self.selected_key = 3  # Reset to fourth button
                        self.components[self.selected_key].is_selected = True
                        self.components[self.selected_key].render()
                elif input == HardwareButtonsConstants.KEY2:
                    self.components[self.selected_key].is_selected = False
                    self.components[self.selected_key].render()
                    if is_groups:
                        is_groups = False
                        self.selected_key = 3  # Reset to fourth button
                    else:
                        is_groups = True
                        self.selected_key = 1  # Reset to first button
                    self.components[self.selected_key].is_selected = True
                    self.components[self.selected_key].render()
                elif input == HardwareButtonsConstants.KEY3:
                    if is_groups:
                        if self.total_members > 1:  # Prevent groups from going below 1
                            self.total_members = max(1, self.total_members - 1)
                            # Ensure threshold doesn't exceed groups when groups decrease
                            self.threshold = min(self.threshold, self.total_members)
                        self.components[self.selected_key].is_selected = False
                        self.components[self.selected_key].render()
                        self.selected_key = 2
                        self.components[self.selected_key].is_selected = True
                    else:
                        if (
                            self.total_members > 1
                            and self.threshold <= 2
                            and self.text == "Shares"
                        ):
                            self.threshold = 2
                        else:
                            self.threshold = max(1, self.threshold - 1)

                        self.components[self.selected_key].is_selected = False
                        self.components[self.selected_key].render()
                        self.selected_key = 4
                        self.components[self.selected_key].is_selected = True

                # Handle confirm button and back button
                if input in [
                    HardwareButtonsConstants.KEY_LEFT,
                    HardwareButtonsConstants.KEY_RIGHT,
                ]:
                    if self.top_nav.is_selected:
                        continue

                    if self.selected_button == 5 and self.passphrase is not None:
                        self.components[self.selected_button].is_selected = False
                        self.components[self.selected_button].render()
                        self.selected_button = 6
                        self.components[self.selected_button].is_selected = True
                        self.components[self.selected_button].render()
                    else:
                        self.components[self.selected_button].is_selected = False
                        self.components[self.selected_button].render()
                        self.selected_button = 5
                        self.components[self.selected_button].is_selected = True
                        self.components[self.selected_button].render()

                if input == HardwareButtonsConstants.KEY_DOWN:
                    if self.top_nav.is_selected:
                        self.top_nav.is_selected = False
                        self.top_nav.render_buttons()
                        self.selected_button = 5
                        self.components[self.selected_button].is_selected = True
                        self.components[self.selected_button].render()

                if input == HardwareButtonsConstants.KEY_UP:
                    if not self.top_nav.is_selected:
                        self.components[self.selected_button].is_selected = False
                        self.components[self.selected_button].render()
                        self.top_nav.is_selected = True
                        self.top_nav.render_buttons()

                if input in [
                    HardwareButtonsConstants.KEY_PRESS,
                ]:
                    if self.top_nav.is_selected:
                        return RET_CODE__BACK_BUTTON
                    if self.selected_button == 5:
                        return ("CONFIRM", self.threshold, self.total_members)
                    if self.selected_button == 6:
                        return ("PASSPHRASE", self.threshold, self.total_members)

                self._render()  # Render the updated screen


@dataclass
class VisualLoadedSchemeScreen(BaseTopNavScreen):
    scheme: Scheme = None

    def __post_init__(self):
        self.show_back_button = True
        super().__post_init__()

        self.group_indices = self.scheme.get_group_indices()

        (
            self.processed_groups,
            self.group_threshold,
            self.total_groups,
            self.completed_groups,
        ) = self.scheme.get_scheme_info()

        self.group_index = 0

        # navigate groups
        self._navigate_groups()

        # Group Circle
        self.group_radius_int = int(self.canvas_width // 6)
        self.group_circle_radius = min(80, self.group_radius_int)
        self.group_circle_center = (
            self.canvas_width // 6 + GUIConstants.EDGE_PADDING,
            GUIConstants.EDGE_PADDING
            + GUIConstants.TOP_NAV_TITLE_FONT_SIZE
            + 20
            + self.group_circle_radius,
        )

        # Share Circle
        self.share_radius_int = int(self.canvas_width // 6)
        self.share_circle_radius = min(80, self.share_radius_int)
        self.share_circle_center = (
            self.canvas_width // 2 + 2 * GUIConstants.EDGE_PADDING,
            GUIConstants.EDGE_PADDING
            + GUIConstants.TOP_NAV_TITLE_FONT_SIZE
            + 20
            + self.share_circle_radius,
        )

        # Groups controls (left side)
        groups_x = (
            self.canvas_width
            - GUIConstants.EDGE_PADDING
            - GUIConstants.TOP_NAV_BUTTON_SIZE
        )

        self.up_btns_y = GUIConstants.TOP_NAV_HEIGHT
        self.down_btns_y = (
            self.canvas_height
            - GUIConstants.TOP_NAV_HEIGHT
            - GUIConstants.TOP_NAV_BUTTON_SIZE
        )

        review_width = 108

        # Review button
        self.review_button = Button(
            text=_("Review"),
            screen_x=GUIConstants.EDGE_PADDING,
            screen_y=self.canvas_height
            - GUIConstants.BUTTON_HEIGHT
            - GUIConstants.EDGE_PADDING,
            width=review_width,
            font_size=GUIConstants.BUTTON_FONT_SIZE - 4,
            height=GUIConstants.BUTTON_HEIGHT,
        )
        self.components.append(self.review_button)

        # Add Share button
        self.add_share_button = Button(
            text=_(" Add Share"),
            screen_x=review_width + 2 * GUIConstants.EDGE_PADDING,
            screen_y=self.canvas_height
            - GUIConstants.BUTTON_HEIGHT
            - GUIConstants.EDGE_PADDING,
            font_size=GUIConstants.BUTTON_FONT_SIZE - 4,
            width=review_width,
            height=GUIConstants.BUTTON_HEIGHT,
        )

        self.components.append(self.add_share_button)

        # Groups up arrow
        self.up_button = IconButton(
            icon_name=SeedCashIconsConstants.PAGE_UP,
            screen_x=groups_x,
            screen_y=self.up_btns_y,
            width=GUIConstants.TOP_NAV_BUTTON_SIZE,
            height=GUIConstants.TOP_NAV_BUTTON_SIZE,
            is_text_centered=True,
        )

        # Groups down arrow
        self.down_button = IconButton(
            icon_name=SeedCashIconsConstants.PAGE_DOWN,
            screen_x=groups_x,
            screen_y=self.down_btns_y,
            font_size=GUIConstants.BODY_FONT_SIZE - 3,
            width=GUIConstants.TOP_NAV_BUTTON_SIZE,
            height=GUIConstants.TOP_NAV_BUTTON_SIZE,
            is_text_centered=True,
        )

        self._show_navigate_btns()

        # Set initial selection
        self.selected_button = 1
        self.selected_key = 1

        self.components[self.selected_key].is_selected = True
        self.components[self.selected_button].is_selected = True

    def _show_navigate_btns(self):
        if self.processed_groups > 1:
            self.components.append(self.up_button)
            self.components.append(self.down_button)
            self.selected_key = 3

    def _navigate_groups(self):
        self.shares_count, self.member_threshold = self.scheme.get_group_info(
            self.group_indices[self.group_index]
        )

        self.top_nav.text = f"Group:{self.group_indices[self.group_index]}"
        self.top_nav.render()

    def _update_labels(self):
        """Update the text labels with current values"""
        label_y = (
            max(self.group_circle_center[1], self.share_circle_center[1])
            + self.group_circle_radius
            + GUIConstants.COMPONENT_PADDING
        )

        # Group label (left side)
        self.groups_text = TextArea(
            text=f"Grups:{self.total_groups}",
            screen_x=GUIConstants.EDGE_PADDING,
            screen_y=label_y,
            width=self.canvas_width // 2 - GUIConstants.EDGE_PADDING,
            font_name=GUIConstants.FIXED_WIDTH_FONT_NAME,
            font_size=GUIConstants.BODY_FONT_SIZE,
            is_text_centered=False,
        )

        self.groups_progress_text = TextArea(
            text=f"Progr:{self.processed_groups}",
            screen_x=GUIConstants.EDGE_PADDING,
            screen_y=label_y
            + GUIConstants.BUTTON_HEIGHT
            - 2 * GUIConstants.EDGE_PADDING,
            width=self.canvas_width // 2 - GUIConstants.EDGE_PADDING,
            font_name=GUIConstants.FIXED_WIDTH_FONT_NAME,
            font_size=GUIConstants.BODY_FONT_SIZE,
            is_text_centered=False,
        )

        self.group_threshold_text = TextArea(
            text=f"Thres:{self.group_threshold}",
            screen_x=GUIConstants.EDGE_PADDING,
            screen_y=label_y
            + 2 * GUIConstants.BUTTON_HEIGHT
            - 4 * GUIConstants.EDGE_PADDING,
            width=self.canvas_width // 2 - GUIConstants.EDGE_PADDING,
            font_name=GUIConstants.FIXED_WIDTH_FONT_NAME,
            font_size=GUIConstants.BODY_FONT_SIZE,
            is_text_centered=False,
        )

        # Share label (right side)

        self.current_group_text = TextArea(
            text=f"Group:{self.group_indices[self.group_index]}",
            screen_x=self.canvas_width // 2 - 3 * GUIConstants.EDGE_PADDING,
            screen_y=label_y,
            width=self.canvas_width // 2 + 3 * GUIConstants.EDGE_PADDING,
            font_name=GUIConstants.FIXED_WIDTH_FONT_NAME,
            font_size=GUIConstants.BODY_FONT_SIZE,
            is_text_centered=False,
        )

        self.members_progress_text = TextArea(
            text=f"Progr:{self.shares_count}",
            screen_x=self.canvas_width // 2 - 3 * GUIConstants.EDGE_PADDING,
            screen_y=label_y + GUIConstants.BUTTON_HEIGHT // 2,
            width=self.canvas_width // 2 + 3 * GUIConstants.EDGE_PADDING,
            font_name=GUIConstants.FIXED_WIDTH_FONT_NAME,
            font_size=GUIConstants.BODY_FONT_SIZE,
            is_text_centered=False,
        )

        # Share label (right side)
        self.members_threshold_text = TextArea(
            text=f"Thres:{self.member_threshold}",
            screen_x=self.canvas_width // 2 - 3 * GUIConstants.EDGE_PADDING,
            screen_y=label_y + GUIConstants.BUTTON_HEIGHT,
            width=self.canvas_width // 2 + 3 * GUIConstants.EDGE_PADDING,
            font_name=GUIConstants.FIXED_WIDTH_FONT_NAME,
            font_size=GUIConstants.BODY_FONT_SIZE,
            is_text_centered=False,
        )

        self.groups_text.render()
        self.groups_progress_text.render()
        self.group_threshold_text.render()
        self.current_group_text.render()
        self.members_threshold_text.render()
        self.members_progress_text.render()

    def _draw_circle_segments(self):
        """Draw both circles with segments showing groups and threshold"""
        draw = ImageDraw.Draw(self.renderer.canvas)

        # Draw Group Circle (left)
        self._draw_single_circle(
            draw,
            self.group_circle_center,
            self.group_circle_radius,
            self.total_groups,
            self.group_threshold,
            self.completed_groups,
        )

        # Draw Share Circle (right)
        self._draw_single_circle(
            draw,
            self.share_circle_center,
            self.share_circle_radius,
            self.member_threshold,
            self.member_threshold,
            self.shares_count,
        )

    def _draw_single_circle(
        self, draw, center, radius, total_segments, filled_threshold, filled_progress
    ):
        """Helper method to draw a single circle with segments"""
        # Draw the full circle outline
        draw.ellipse(
            [
                center[0] - radius,
                center[1] - radius,
                center[0] + radius,
                center[1] + radius,
            ],
            outline=GUIConstants.ACCENT_COLOR,
            width=2,
        )

        # If only 1 segment, draw full circle filled or empty
        if total_segments == 1:
            if filled_threshold == 1:
                if filled_progress == 1:
                    fill_color = GUIConstants.ACCENT_COLOR
                else:
                    fill_color = "white"
            else:
                fill_color = "#333333"

            draw.ellipse(
                [
                    center[0] - radius,
                    center[1] - radius,
                    center[0] + radius,
                    center[1] + radius,
                ],
                fill=fill_color,
                width=2,
            )
            return

        # Calculate segment angles for multiple segments
        angle_per_segment = 360 / total_segments
        filled_threshold_color = "white"
        filled_progress_color = GUIConstants.ACCENT_COLOR
        empty_color = "#333333"  # Dark gray for unfilled segments

        # Draw each segment
        for i in range(total_segments):
            start_angle = i * angle_per_segment - 90  # Start from top (-90 degrees)
            end_angle = (i + 1) * angle_per_segment - 90

            # Determine if this segment should be filled (part of threshold)
            if i < filled_threshold:
                if i < filled_progress:
                    # Use filled_progress_color for segments that are filled and reached the threshold
                    fill_color = filled_progress_color
                else:
                    fill_color = filled_threshold_color
            else:
                if i < filled_progress:
                    # Use filled_progress_color for segments that are filled but not reached the threshold
                    fill_color = filled_progress_color
                else:
                    # Use empty_color for segments that are not filled
                    fill_color = empty_color

            # Draw pie segment
            draw.pieslice(
                [
                    center[0] - radius,
                    center[1] - radius,
                    center[0] + radius,
                    center[1] + radius,
                ],
                start=start_angle,
                end=end_angle,
                fill=fill_color,
                outline=GUIConstants.BACKGROUND_COLOR,
                width=1,
            )

        # Draw dividing lines between segments (only if more than 1 segment)
        if total_segments > 1:
            for i in range(total_segments):
                # Calculate the angle for the dividing line
                line_angle = math.radians(i * angle_per_segment - 90)
                line_end = (
                    center[0] + radius * math.cos(line_angle),
                    center[1] + radius * math.sin(line_angle),
                )
                draw.line(
                    [center, line_end],
                    fill=GUIConstants.BACKGROUND_COLOR,
                    width=2,
                )

    def _render(self):
        super()._render()
        self._update_labels()
        self._draw_circle_segments()  # Draw our custom visualization
        for component in self.components:
            component.render()
        self.renderer.show_image()

    def _run(self):
        while True:
            input = self.hw_inputs.wait_for(HardwareButtonsConstants.ALL_KEYS)

            with self.renderer.lock:
                # Clear current selection
                if input == HardwareButtonsConstants.KEY1:
                    if self.processed_groups <= 1:
                        continue

                    self.components[self.selected_key].is_selected = False
                    self.components[self.selected_key].render()
                    self.selected_key = 3
                    self.components[self.selected_key].is_selected = True
                    self.components[self.selected_key].render()

                    if self.group_index < self.processed_groups - 1:
                        self.group_index += 1
                        self._navigate_groups()

                elif input == HardwareButtonsConstants.KEY3:
                    if self.processed_groups <= 1:
                        continue

                    self.components[self.selected_key].is_selected = False
                    self.components[self.selected_key].render()
                    self.selected_key = 4
                    self.components[self.selected_key].is_selected = True
                    self.components[self.selected_key].render()

                    if self.group_index > 0:
                        self.group_index -= 1
                        self._navigate_groups()

                # Handle confirm button and back button
                if input in [
                    HardwareButtonsConstants.KEY_LEFT,
                    HardwareButtonsConstants.KEY_RIGHT,
                ]:
                    if self.top_nav.is_selected:
                        continue

                    if self.selected_button == 1:
                        self.components[self.selected_button].is_selected = False
                        self.components[self.selected_button].render()
                        self.selected_button = 2
                        self.components[self.selected_button].is_selected = True
                        self.components[self.selected_button].render()
                    else:
                        self.components[self.selected_button].is_selected = False
                        self.components[self.selected_button].render()
                        self.selected_button = 1
                        self.components[self.selected_button].is_selected = True
                        self.components[self.selected_button].render()

                if input == HardwareButtonsConstants.KEY_DOWN:
                    if self.top_nav.is_selected:
                        self.top_nav.is_selected = False
                        self.top_nav.render_buttons()
                        self.selected_button = 1
                        self.components[self.selected_button].is_selected = True
                        self.components[self.selected_button].render()

                if input == HardwareButtonsConstants.KEY_UP:
                    if not self.top_nav.is_selected:
                        self.components[self.selected_button].is_selected = False
                        self.components[self.selected_button].render()
                        self.top_nav.is_selected = True
                        self.top_nav.render_buttons()

                if input in [
                    HardwareButtonsConstants.KEY_PRESS,
                    HardwareButtonsConstants.KEY2,
                ]:
                    if self.top_nav.is_selected:
                        return RET_CODE__BACK_BUTTON
                    if self.selected_button == 1:
                        return "REVIEW"
                    if self.selected_button == 2:
                        return "ADD"

                self._render()


@dataclass
class SingleLevelVisualLoadedSchemeScreen(BaseTopNavScreen):
    shares_count: int = 1
    member_threshold: int = 1

    def __post_init__(self):
        self.show_back_button = True
        super().__post_init__()

        # Share Circle
        self.share_radius_int = int(self.canvas_width // 5)
        self.share_circle_radius = min(80, self.share_radius_int)
        self.share_circle_center = (
            self.share_circle_radius + 3 * GUIConstants.EDGE_PADDING,
            self.canvas_height // 2 - GUIConstants.COMPONENT_PADDING,
        )

        review_width = 108
        # Review button
        self.review_button = Button(
            text=_("Review"),
            screen_x=GUIConstants.EDGE_PADDING,
            screen_y=self.canvas_height
            - GUIConstants.BUTTON_HEIGHT
            - GUIConstants.EDGE_PADDING,
            width=review_width,
            font_size=GUIConstants.BUTTON_FONT_SIZE - 4,
            height=GUIConstants.BUTTON_HEIGHT,
        )
        self.components.append(self.review_button)

        # Add Share button
        self.add_share_button = Button(
            text=_(" Add Share"),
            screen_x=review_width + 2 * GUIConstants.EDGE_PADDING,
            screen_y=self.canvas_height
            - GUIConstants.BUTTON_HEIGHT
            - GUIConstants.EDGE_PADDING,
            font_size=GUIConstants.BUTTON_FONT_SIZE - 4,
            width=review_width,
            height=GUIConstants.BUTTON_HEIGHT,
        )
        self.components.append(self.add_share_button)

        self.selected_button = 1
        self.components[self.selected_button].is_selected = True

    def _update_labels(self):
        """Update the text labels with current values"""
        label_y = (
            self.canvas_height // 2
            - GUIConstants.BUTTON_HEIGHT
            + GUIConstants.COMPONENT_PADDING
        )

        label_x = (
            self.share_circle_center[0]
            + self.share_circle_radius
            + GUIConstants.COMPONENT_PADDING
        )

        # Share label (right side)
        self.members_progress_text = TextArea(
            text=f"Prog:{self.shares_count}",
            screen_x=label_x,
            screen_y=label_y,
            width=self.canvas_width // 2 + 3 * GUIConstants.EDGE_PADDING,
            font_name=GUIConstants.FIXED_WIDTH_FONT_NAME,
            font_size=GUIConstants.BODY_FONT_SIZE,
            is_text_centered=False,
        )

        self.members_threshold_text = TextArea(
            text=f"Thres:{self.member_threshold}",
            screen_x=label_x,
            screen_y=label_y
            + GUIConstants.BUTTON_HEIGHT
            - 2 * GUIConstants.EDGE_PADDING,
            width=self.canvas_width // 2 + 3 * GUIConstants.EDGE_PADDING,
            font_name=GUIConstants.FIXED_WIDTH_FONT_NAME,
            font_size=GUIConstants.BODY_FONT_SIZE,
            is_text_centered=False,
        )

        self.members_threshold_text.render()
        self.members_progress_text.render()

    def _draw_circle_segments(self):
        """Draw both circles with segments showing groups and threshold"""
        draw = ImageDraw.Draw(self.renderer.canvas)

        # Draw Share Circle (right)
        self._draw_single_circle(
            draw,
            self.share_circle_center,
            self.share_circle_radius,
            self.member_threshold,
            self.member_threshold,
            self.shares_count,
        )

    def _draw_single_circle(
        self, draw, center, radius, total_segments, filled_threshold, filled_progress
    ):
        """Helper method to draw a single circle with segments"""
        # Draw the full circle outline
        draw.ellipse(
            [
                center[0] - radius,
                center[1] - radius,
                center[0] + radius,
                center[1] + radius,
            ],
            outline=GUIConstants.ACCENT_COLOR,
            width=2,
        )

        # If only 1 segment, draw full circle filled or empty
        if total_segments == 1:
            if filled_threshold == 1:
                if filled_progress == 1:
                    fill_color = GUIConstants.ACCENT_COLOR
                else:
                    fill_color = "white"
            else:
                fill_color = "#333333"

            draw.ellipse(
                [
                    center[0] - radius,
                    center[1] - radius,
                    center[0] + radius,
                    center[1] + radius,
                ],
                fill=fill_color,
                width=2,
            )
            return

        # Calculate segment angles for multiple segments
        angle_per_segment = 360 / total_segments
        filled_threshold_color = "white"
        filled_progress_color = GUIConstants.ACCENT_COLOR
        empty_color = "#333333"  # Dark gray for unfilled segments

        # Draw each segment
        for i in range(total_segments):
            start_angle = i * angle_per_segment - 90  # Start from top (-90 degrees)
            end_angle = (i + 1) * angle_per_segment - 90

            # Determine if this segment should be filled (part of threshold)
            if i < filled_threshold:
                if i < filled_progress:
                    # Use filled_progress_color for segments that are filled and reached the threshold
                    fill_color = filled_progress_color
                else:
                    fill_color = filled_threshold_color
            else:
                if i < filled_progress:
                    # Use filled_progress_color for segments that are filled but not reached the threshold
                    fill_color = filled_progress_color
                else:
                    # Use empty_color for segments that are not filled
                    fill_color = empty_color

            # Draw pie segment
            draw.pieslice(
                [
                    center[0] - radius,
                    center[1] - radius,
                    center[0] + radius,
                    center[1] + radius,
                ],
                start=start_angle,
                end=end_angle,
                fill=fill_color,
                outline=GUIConstants.BACKGROUND_COLOR,
                width=1,
            )

        # Draw dividing lines between segments (only if more than 1 segment)
        if total_segments > 1:
            for i in range(total_segments):
                # Calculate the angle for the dividing line
                line_angle = math.radians(i * angle_per_segment - 90)
                line_end = (
                    center[0] + radius * math.cos(line_angle),
                    center[1] + radius * math.sin(line_angle),
                )
                draw.line(
                    [center, line_end],
                    fill=GUIConstants.BACKGROUND_COLOR,
                    width=2,
                )

    def _render(self):
        super()._render()
        self._update_labels()
        self._draw_circle_segments()
        for component in self.components:
            component.render()
        self.renderer.show_image()

    def _run(self):
        while True:
            input = self.hw_inputs.wait_for(HardwareButtonsConstants.ALL_KEYS)

            with self.renderer.lock:
                # Handle confirm button and back button
                if input in [
                    HardwareButtonsConstants.KEY_LEFT,
                    HardwareButtonsConstants.KEY_RIGHT,
                ]:
                    if self.top_nav.is_selected:
                        continue

                    if self.selected_button == 1:
                        self.components[self.selected_button].is_selected = False
                        self.components[self.selected_button].render()
                        self.selected_button = 2
                        self.components[self.selected_button].is_selected = True
                        self.components[self.selected_button].render()
                    else:
                        self.components[self.selected_button].is_selected = False
                        self.components[self.selected_button].render()
                        self.selected_button = 1
                        self.components[self.selected_button].is_selected = True
                        self.components[self.selected_button].render()

                if input == HardwareButtonsConstants.KEY_DOWN:
                    if self.top_nav.is_selected:
                        self.top_nav.is_selected = False
                        self.top_nav.render_buttons()
                        self.selected_button = 1
                        self.components[self.selected_button].is_selected = True
                        self.components[self.selected_button].render()

                if input == HardwareButtonsConstants.KEY_UP:
                    if not self.top_nav.is_selected:
                        self.components[self.selected_button].is_selected = False
                        self.components[self.selected_button].render()
                        self.top_nav.is_selected = True
                        self.top_nav.render_buttons()

                if input in [
                    HardwareButtonsConstants.KEY_PRESS,
                    HardwareButtonsConstants.KEY2,
                ]:
                    if self.top_nav.is_selected:
                        return RET_CODE__BACK_BUTTON
                    if self.selected_button == 1:
                        return "REVIEW"
                    if self.selected_button == 2:
                        return "ADD"

                self._render()

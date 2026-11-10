import logging

from gettext import gettext as _
from seedcash.gui.screens import RET_CODE__BACK_BUTTON
from seedcash.gui.screens.screen import ButtonOption
from seedcash.views.view import (
    View,
    Destination,
    BackStackView,
)

logger = logging.getLogger(__name__)

"""**************************************************
Seed Cash Updated Code
**************************************************"""


# First Generate Seed View
class ShowWordsView(View):
    def run(self):
        from seedcash.gui.screens.load_seed_screens import SeedCashSeedWordsScreen

        confirm = self.run_screen(
            SeedCashSeedWordsScreen,
            seed_words=self.controller.storage.mnemonic,
        )

        if confirm == "CONFIRM":
            from seedcash.views.wallet_views import WalletFinalizeView
            self.controller.storage.convert_mnemonic_to_seed()
            self.controller.storage.create_wallet()
            return Destination(WalletFinalizeView)


class ToolsCalcFinalWordCoinFlipsView(View):
    def run(self):
        from seedcash.gui.screens.generate_seed_screens import ToolsCoinFlipEntryScreen

        total_bits = 11 - (self.controller.storage.mnemonic_length // 3)

        ret_val = ToolsCoinFlipEntryScreen(
            max_bits=total_bits,
        ).display()

        if ret_val == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        self.controller.storage.calculate_final_word(coin_flips=ret_val)
        return Destination(ToolsCalcFinalWordShowFinalWordView)


class ToolsCalcFinalWordShowFinalWordView(View):
    CONFIRM = ButtonOption("Confirm")

    def __init__(self):
        super().__init__()
        self.last_bits, self.checksum_bits = self.controller.storage.calculate_last_word_fields

    def run(self):
        from seedcash.gui.screens.generate_seed_screens import ToolsCalcFinalWordScreen

        button_data = [self.CONFIRM]

        selected_menu_num = self.run_screen(
            ToolsCalcFinalWordScreen,
            button_data=button_data,
            num_checksum_bits=self.controller.storage.mnemonic_length // 3,
            selected_final_bits=self.last_bits,
            checksum_bits=self.checksum_bits,
            actual_final_word=self.controller.storage.mnemonic[-1],
        )

        if button_data[selected_menu_num] == self.CONFIRM:
            return Destination(ShowWordsView)
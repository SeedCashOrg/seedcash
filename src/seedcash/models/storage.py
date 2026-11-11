from typing import List, Optional, Tuple
from seedcash.models.wallet import Wallet
from seedcash.models.seed import Seed, InvalidSeedException

import logging
from seedcash.gui.components import load_txt

logger = logging.getLogger(__name__)


class SeedStorage:
    def __init__(self) -> None:
        self._mnemonic: List[str] = None
        self._seed: Seed = None
        self._calculate_last_word_fields: Tuple[str, str] = None
        self._is_generate: bool = False

    @property
    def get_wordlist(self) -> List[str]:
        # getting world list from resource/bip39.txt
        return load_txt("bip39.txt")

    # Mnemonic management
    @property
    def mnemonic(self) -> List[str]:
        if self._mnemonic is None:
            raise InvalidSeedException("Mnemonic has not been initialized")
        return self._mnemonic

    def set_mnemonic(self, mnemonic: List[Optional[str]]):
        if not isinstance(mnemonic, list):
            raise InvalidSeedException("Mnemonic must be a list")
        # Allow None entries so we can clear the list
        if not all(word is None or isinstance(word, str) for word in mnemonic):
            raise InvalidSeedException("Mnemonic entries must be str or None")
        self._mnemonic = mnemonic

    def discard_mnemonic(self):
        if self._mnemonic is not None:
            self.mnemonic[:] = [None] * len(self.mnemonic)

    def get_mnemonic_word(self, index: int) -> str:
        if index < len(self.mnemonic):
            return self.mnemonic[index]
        return None

    def update_mnemonic(self, word: str, index: int):
        if index >= len(self.mnemonic):
            raise InvalidSeedException(f"index {index} is too high")
        self.mnemonic[index] = word

    @property
    def mnemonic_length(self) -> int:
        return len(self.mnemonic)
    
    def set_mnemonic_length(self, length: int):
        if length not in [12, 15, 18, 20, 21, 24, 33]:
            raise ValueError(
                "Invalid mnemonic length. Must be one of [12, 15, 18, 20, 21, 24, 33]."
            )
        self.set_mnemonic([None] * length)
        logger.info(f"Mnemonic length set to {length} words.")

    @property
    def passphrase(self) -> Optional[str]:
        return self.seed.passphrase

    def set_passphrase(self, passphrase: str):
        self.seed.set_passphrase(passphrase)

    # Seed management
    @property
    def seed(self) -> Seed:
        if not self._seed:
            raise InvalidSeedException("Seed has not been initialized")
        return self._seed

    def set_seed(self, seed: Seed):
        if not isinstance(seed, Seed):
            raise InvalidSeedException("Provided seed is not a valid Seed instance")
        self._seed = seed
        
    def convert_mnemonic_to_seed(self) -> Seed:
        self.set_seed(Seed(mnemonic=self.mnemonic))
        if self._calculate_last_word_fields is not None:
            self._calculate_last_word_fields = None
            
        self.discard_mnemonic()

    def calculate_final_word(self, coin_flips: str) -> str:        
        from seedcash.models.bip39 import Bip39
        self.set_mnemonic(Bip39.get_mnemonic(self.mnemonic[:-1], coin_flips))
        last_word_index = self.get_wordlist.index(self.mnemonic[-1])
        checksum_bits = format(last_word_index,"011b")[-self.mnemonic_length // 3:]
        self._calculate_last_word_fields: Tuple[str, str] = (coin_flips, checksum_bits)

    @property
    def calculate_last_word_fields(self) -> Tuple[str, str]:
        if self._calculate_last_word_fields is None:
            raise InvalidSeedException("Calculate last word fields have not been initialized")
        return self._calculate_last_word_fields


    def discard_seed(self):
        if self._seed is not None:
            self._seed.discard_seed()
        self._seed = None

    @property
    def wallet(self) -> Optional[Wallet]:
        return self.seed.wallet

    def create_wallet(self):
        self.seed.generate_wallet()


    def discard_wallet(self):
        # 1. Discard seed
        self.discard_seed()
        self.discard_mnemonic()
        # 3. Force a collection attempt
        import gc
        gc.collect()
    
        logger.info("Wallet discarded (best-effort clear).")

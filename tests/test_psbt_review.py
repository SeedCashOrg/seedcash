"""Run: python -m unittest discover -s tests -v (desktop, no signer or network)."""
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Stub only Raspberry Pi hardware leaves; parser and view methods are real.
for name in ("RPi", "RPi.GPIO", "spidev", "board", "digitalio", "picamera",
             "picamera.array", "picamera2", "gpiozero", "smbus", "smbus2"):
    module = MagicMock()
    module.__name__ = name
    module.__spec__ = types.SimpleNamespace(name=name)
    sys.modules.setdefault(name, module)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from seedcash.models.psbt_parser import (
    NFTData, PSBTParser, TokenData, Transaction, TxInput, TxOutput,
)
from seedcash.views import psbt_views as views
from seedcash.views.view import View

FIXTURES = json.loads((Path(__file__).parent / "fixtures/optn-review-psbts.json").read_text())
SCRIPT = bytes.fromhex("76a914" + "11" * 20 + "88ac")
CATEGORY = "aa" * 32


def output(amount=None, nft=None, category=CATEGORY, address="destination", sats=1000):
    return TxOutput(sats, SCRIPT, token=TokenData(category, amount, nft)
                    if amount is not None or nft is not None else None,
                    address=address)


def parser_for(inputs, outputs):
    parser = object.__new__(PSBTParser)
    parser.tx = Transaction(2, 0, [TxInput(bytes(32), i, 0xffffffff, spent_output=o)
                                  for i, o in enumerate(inputs)], outputs)
    parser._outputs = parser.tx.arrange_outputs_by_type_and_category()
    parser._inputs = parser.tx.arrange_inputs_by_type_and_category()
    return parser


def view_for(cls, parser, **kwargs):
    def initialize(view):
        view.controller = types.SimpleNamespace(psbt_parser=parser)
    with patch.object(View, "_initialize", initialize):
        view = cls(**kwargs)
    view.run_screen = MagicMock(return_value=0)
    return view


class PsbtReviewTests(unittest.TestCase):
    def test_cashaddr_versions_describe_the_original_script(self):
        alphabet = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
        pkh = bytes.fromhex("11" * 20)
        scripts = [(b"\x76\xa9\x14" + pkh + b"\x88\xac", 0, 16),
                   (b"\xa9\x14" + pkh + b"\x87", 8, 24)]
        for script, ordinary, token in scripts:
            for is_token, version in ((False, ordinary), (True, token)):
                with self.subTest(script=script.hex(), token=is_token):
                    address = PSBTParser.address_from_script(script, is_token)
                    payload = address.split(":")[1][:-8]
                    bits = "".join(f"{alphabet.index(c):05b}" for c in payload)
                    raw = int(bits[:168], 2).to_bytes(21, "big")
                    self.assertEqual(raw, bytes([version]) + pkh)

    def test_nonstandard_scripts_are_not_misrepresented_as_standard_addresses(self):
        for script in (SCRIPT[:-2] + b"\x51\x88\xac",
                       b"\xa9\x14" + bytes(21) + b"\x87"):
            self.assertIsNone(PSBTParser.address_from_script(script))

    def test_real_mixed_token_psbt_reviews_both_assets(self):
        parser = PSBTParser(bytearray.fromhex(FIXTURES["mixed"]))
        category = parser.tx.outputs[0].token.category_id
        self.assertEqual(parser.token_categories, [category])
        self.assertEqual(parser.nft_categories, [category])
        self.assertEqual(parser.ft_output_amount(category), 1000)
        self.assertFalse(parser.ft_burning(category))
        self.assertEqual(len(parser.outputs[0][category]), 1)
        self.assertEqual(len(parser.outputs[1][category]), 2)

    def test_real_issuance_psbt_enters_token_review(self):
        parser = PSBTParser(bytearray.fromhex(FIXTURES["genesis"]))
        category = parser.tx.outputs[0].token.category_id
        self.assertEqual(parser.token_categories, [category])
        self.assertEqual(parser.nft_categories, [category])
        self.assertEqual(parser.ft_output_amount(category), 3000)
        self.assertEqual(parser.get_warning(category), "minting")
        view = object.__new__(views.LoadingPSBTView)
        view.controller = types.SimpleNamespace(psbt_parser=parser)
        self.assertIs(view.run().View_cls, views.PSBTNFTView)

    def test_fungible_only_issuance_enters_token_review(self):
        parser = parser_for([output()], [output(50)])
        view = object.__new__(views.LoadingPSBTView)
        view.controller = types.SimpleNamespace(psbt_parser=parser)
        self.assertIs(view.run().View_cls, views.PSBTFungibleTokenDetailsView)

    def test_fungible_burning_compares_units_not_output_counts(self):
        self.assertTrue(parser_for([output(1000)], [output(100), output(100)]).ft_burning(CATEGORY))
        self.assertFalse(parser_for([output(400), output(600)], [output(1000)]).ft_burning(CATEGORY))
        self.assertEqual(parser_for([output(1000)], []).ft_output_amount(CATEGORY), 0)

    def test_category_detail_uses_its_own_output_not_the_global_index(self):
        parser = parser_for([output(1000)], [output(address="bch"),
            output(25, category="bb" * 32, address="other-category"),
            output(400, address="recipient"), output(600, address="change")])
        view = view_for(views.PSBTAddressDetailsView, parser, address_num=0,
                        destination_addresses=["recipient", "change"], category_num=0)
        category = types.SimpleNamespace(token_symbol="TEST", icon_color="blue")
        with patch.object(views, "get_category", return_value=category):
            destination = view.run()
        self.assertEqual(view.run_screen.call_args.kwargs["amount"], 400)
        self.assertEqual(view.run_screen.call_args.kwargs["address"], "recipient")
        self.assertEqual(destination.view_args["address_num"], 1)

    def test_complete_fungible_burn_warns_and_continues_without_empty_output_index(self):
        parser = parser_for([output(1000)], [output()])
        view = view_for(views.PSBTFungibleTokenDetailsView, parser)
        category = types.SimpleNamespace(token_symbol="TEST", icon_color="blue")
        with patch.object(views, "get_category", return_value=category):
            destination = view.run()
        self.assertTrue(any("Burning" in call.kwargs.get("title", "")
                            for call in view.run_screen.call_args_list))
        self.assertIs(destination.View_cls, views.BCHPSBTOverviewView)

    def test_complete_nft_burn_warns_and_continues(self):
        parser = parser_for([output(nft=NFTData("none", "abcd"))], [output()])
        self.assertEqual(parser.get_warning(CATEGORY), "burning")
        view = view_for(views.PSBTNFTView, parser)
        self.assertIs(view.run().View_cls, views.PSBTFungibleTokenDetailsView)

    def test_each_new_nft_category_gets_its_warning(self):
        parser = parser_for([], [output(nft=NFTData("none", "01")),
                                output(nft=NFTData("none", "02"), category="bb" * 32)])
        view = view_for(views.PSBTNFTAddressDetailsView, parser, output_num=0, category_num=0)
        destination = view.run()
        self.assertIs(destination.View_cls, views.PSBTNFTView)
        self.assertEqual(destination.view_args["category_num"], 1)

    def test_real_mixed_and_issuance_reviews_reach_confirmation_with_all_ft_details(self):
        for fixture, expected_amounts in (("mixed", [400, 600]), ("genesis", [1000, 1000, 1000])):
            with self.subTest(fixture=fixture):
                parser = PSBTParser(bytearray.fromhex(FIXTURES[fixture]))
                loading = object.__new__(views.LoadingPSBTView)
                loading.controller = types.SimpleNamespace(psbt_parser=parser)
                destination = loading.run()
                amounts = []
                category = types.SimpleNamespace(token_symbol="TEST", icon_color="blue")
                with patch.object(views, "get_category", return_value=category):
                    for _ in range(40):
                        if destination.View_cls is views.PSBTConfirmationView:
                            break
                        view = view_for(destination.View_cls, parser, **(destination.view_args or {}))
                        destination = view.run()
                        for call in view.run_screen.call_args_list:
                            if "amount" in call.kwargs and call.kwargs.get("category") is category:
                                amounts.append(call.kwargs["amount"])
                    else:
                        self.fail("review never reached confirmation")
                self.assertEqual(amounts, expected_amounts)

    def test_back_from_burn_or_mint_warning_does_not_advance(self):
        cases = [(views.PSBTFungibleTokenDetailsView, parser_for([output(1000)], [])),
                 (views.PSBTNFTView, parser_for([], [output(nft=NFTData("none", "ab"))]))]
        category = types.SimpleNamespace(token_symbol="TEST", icon_color="blue")
        for cls, parser in cases:
            view = view_for(cls, parser)
            view.run_screen.return_value = views.RET_CODE__BACK_BUTTON
            with patch.object(views, "get_category", return_value=category):
                self.assertIs(view.run().View_cls, views.BackStackView)

    def test_reordering_unchanged_nfts_is_not_a_burn(self):
        first = output(nft=NFTData("none", "01"))
        second = output(nft=NFTData("mutable", "02"))
        self.assertIsNone(parser_for([first, second], [second, first]).get_warning(CATEGORY))


if __name__ == "__main__":
    unittest.main()

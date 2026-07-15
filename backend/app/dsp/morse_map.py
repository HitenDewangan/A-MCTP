"""
Morse code lookup tables and symbol<->text translation helpers.

This module is intentionally pure-python / dependency-free so it can be
unit tested in isolation from the DSP pipeline.
"""
from typing import Dict

MORSE_TO_CHAR: Dict[str, str] = {
    ".-": "A", "-...": "B", "-.-.": "C", "-..": "D", ".": "E",
    "..-.": "F", "--.": "G", "....": "H", "..": "I", ".---": "J",
    "-.-": "K", ".-..": "L", "--": "M", "-.": "N", "---": "O",
    ".--.": "P", "--.-": "Q", ".-.": "R", "...": "S", "-": "T",
    "..-": "U", "...-": "V", ".--": "W", "-..-": "X", "-.--": "Y",
    "--..": "Z",
    "-----": "0", ".----": "1", "..---": "2", "...--": "3",
    "....-": "4", ".....": "5", "-....": "6", "--...": "7",
    "---..": "8", "----.": "9",
    ".-.-.-": ".", "--..--": ",", "..--..": "?", ".----.": "'",
    "-.-.--": "!", "-..-.": "/", "-.--.": "(", "-.--.-": ")",
    ".-...": "&", "---...": ":", "-.-.-.": ";", "-...-": "=",
    ".-.-.": "+", "-....-": "-", "..--.-": "_", ".-..-.": '"',
    "...-..-": "$", ".--.-.": "@",
}

CHAR_TO_MORSE: Dict[str, str] = {v: k for k, v in MORSE_TO_CHAR.items()}

WORD_GAP_TOKEN = "/"  # inserted between words in a symbol stream


def symbols_to_text(symbol_stream: str) -> str:
    """
    Convert a space-delimited morse symbol stream (letters separated by
    single spaces, words separated by ' / ') into plain text.

    Example: ".... . .-.. .-.. --- / .-- --- .-. .-.. -.."  -> "HELLO WORLD"
    """
    words = symbol_stream.strip().split(f" {WORD_GAP_TOKEN} ")
    decoded_words = []
    for word in words:
        letters = word.strip().split(" ")
        decoded_words.append(
            "".join(MORSE_TO_CHAR.get(letter, "") for letter in letters if letter)
        )
    return " ".join(decoded_words)


def text_to_symbols(text: str) -> str:
    """Inverse of symbols_to_text -- used by the reverse-synthesis engine."""
    words = text.strip().upper().split(" ")
    morse_words = []
    for word in words:
        letters = [CHAR_TO_MORSE.get(ch, "") for ch in word if CHAR_TO_MORSE.get(ch, "")]
        morse_words.append(" ".join(letters))
    return f" {WORD_GAP_TOKEN} ".join(morse_words)


import itertools
import os
import time

def permutation_generator(phrase: str):
    """Yield each permutation of the mnemonic phrase."""
    words = phrase.split()
    if len(words) not in (12, 24):
        raise ValueError("Phrase must contain exactly 12 or 24 words.")
    for perm in itertools.permutations(words):
        yield " ".join(perm)
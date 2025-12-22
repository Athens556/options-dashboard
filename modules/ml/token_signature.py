from typing import List

class TokenSignature:
    @staticmethod
    def create(tokens: List[str]) -> str:
        """
        Creates a canonical signature from a list of tokens.
        Tokens are sorted alphabetically and joined by '+'.
        """
        if not tokens:
            return "EMPTY"
            
        # Filter out duplicates if any
        unique = sorted(list(set(tokens)))
        return "+".join(unique)

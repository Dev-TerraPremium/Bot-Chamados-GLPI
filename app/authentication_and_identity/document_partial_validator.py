import hmac
import hashlib

class DocumentPartialValidator:
    def __init__(self, pepper: str, prefix_length: int = 4):
        self.pepper = pepper
        self.prefix_length = prefix_length

    def hash_partial_cpf(self, partial_cpf: str) -> str:
        """
        Creates an HMAC-SHA256 hash of the partial CPF using the configured pepper.
        """
        # Ensure we only hash the first `prefix_length` digits just in case
        clean_partial = partial_cpf[:self.prefix_length]
        hmac_obj = hmac.new(
            self.pepper.encode("utf-8"),
            clean_partial.encode("utf-8"),
            hashlib.sha256,
        )
        return hmac_obj.hexdigest()

    def compare_partial_with_full(self, partial_cpf: str, full_cpf: str) -> bool:
        """
        Checks if the first `prefix_length` characters of full_cpf exactly match partial_cpf.
        Both inputs must be normalized beforehand.
        """
        if not partial_cpf or not full_cpf:
            return False
            
        if len(partial_cpf) != self.prefix_length:
            return False
            
        return full_cpf.startswith(partial_cpf)

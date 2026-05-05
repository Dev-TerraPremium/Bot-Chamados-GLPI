import re

class ChannelIdentifierNormalizer:
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """
        Normalizes a phone number by removing spaces, parentheses, hyphens, +, and country code 55.
        Example: '+55 (66) 99999-0980' -> '66999990980'
        """
        if not phone:
            return ""
        
        # Remove anything that is not a digit
        digits_only = re.sub(r"\D", "", phone)
        
        # If it starts with 55 and has at least 12 digits (like 55 11 99999 9999 -> 13 digits)
        # Actually 55 + 2 digits DDD + 8 or 9 digits = 12 or 13 digits total.
        if digits_only.startswith("55") and len(digits_only) >= 12:
            digits_only = digits_only[2:]
            
        return digits_only

    @staticmethod
    def normalize_cpf(cpf: str) -> str:
        """
        Normalizes a CPF by removing dots, hyphens, and spaces.
        Example: '099.150.671-51' -> '09915067151'
        """
        if not cpf:
            return ""
        return re.sub(r"[\.\-\s]", "", cpf)

    @staticmethod
    def mask_phone(phone: str) -> str:
        """
        Masks a phone number for logging, keeping only the last 4 digits.
        Example: '66999990980' -> '******0980'
        """
        normalized = ChannelIdentifierNormalizer.normalize_phone(phone)
        if len(normalized) <= 4:
            return "******" + normalized
        return "*" * 6 + normalized[-4:]

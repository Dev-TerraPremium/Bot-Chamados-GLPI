import re

class ChannelIdentifierNormalizer:
    @staticmethod
    def normalize(channel: str, identifier: str) -> str:
        channel_name = (channel or "").strip().casefold()
        if channel_name in {"whatsapp", "web_simulator"}:
            return ChannelIdentifierNormalizer.normalize_phone(identifier)
        return (identifier or "").strip()

    @staticmethod
    def mask(channel: str, identifier: str) -> str:
        channel_name = (channel or "").strip().casefold()
        if channel_name in {"whatsapp", "web_simulator"}:
            return ChannelIdentifierNormalizer.mask_phone(identifier)
        normalized = ChannelIdentifierNormalizer.normalize(channel, identifier)
        if len(normalized) <= 6:
            return "******" + normalized[-2:]
        return normalized[:3] + "******" + normalized[-4:]

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
    def phone_variants(phone: str) -> list[str]:
        normalized = ChannelIdentifierNormalizer.normalize_phone(phone)
        if not normalized:
            return []

        variants = [normalized]
        if len(normalized) == 11 and normalized[2] == "9":
            variants.append(normalized[:2] + normalized[3:])
        if len(normalized) == 10:
            variants.append(normalized[:2] + "9" + normalized[2:])
        return list(dict.fromkeys(variants))

    @staticmethod
    def normalize_cpf(cpf: str) -> str:
        """
        Normalizes a CPF by keeping only digits.
        Example: 'CPF: 099.150.671-51' -> '09915067151'
        """
        if not cpf:
            return ""
        return re.sub(r"\D", "", cpf)

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

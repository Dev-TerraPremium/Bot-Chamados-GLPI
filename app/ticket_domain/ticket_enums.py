from enum import Enum


class TicketCategory(str, Enum):
    INTERNET_REDE = "Internet / Rede"
    COMPUTADOR_NOTEBOOK = "Computador / Notebook"
    IMPRESSORA = "Impressora"
    SISTEMA_ERP = "Sistema / ERP"
    EMAIL_MICROSOFT_365 = "E-mail / Microsoft 365"
    ACESSO_SENHA = "Acesso / Senha"
    TELEFONIA = "Telefonia"
    GLPI = "GLPI"
    SOLICITACAO_EQUIPAMENTO = "Solicitação de equipamento"
    CAMERAS_CFTV = "Câmeras / CFTV"
    UBIQUITI_WIFI = "Ubiquiti / Wi-Fi"
    OUTRO = "Outro"


class TicketImpact(str, Enum):
    SIMPLE_REQUEST = "Dúvida ou solicitação simples"
    ONE_USER_CAN_WORK = "Afeta somente você, mas ainda consegue trabalhar"
    ONE_USER_STOPPED = "Afeta somente você e está parado"
    MANY_USERS = "Afeta várias pessoas"
    CRITICAL_OPERATION = "Afeta setor inteiro, filial ou operação crítica"


class TicketSeverity(str, Enum):
    LOW = "Baixa"
    MEDIUM = "Média"
    HIGH = "Alta"
    CRITICAL = "Crítica"


class TicketStatus(str, Enum):
    OPEN = "Aberto"
    IN_PROGRESS = "Em atendimento"
    CLOSED = "Fechado"


class TicketOpeningMode(str, Enum):
    ASSISTED = "Abertura assistida"

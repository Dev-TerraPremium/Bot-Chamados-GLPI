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
    SOLICITACAO_EQUIPAMENTO = "Solicitacao de equipamento"
    CAMERAS_CFTV = "Cameras / CFTV"
    UBIQUITI_WIFI = "Ubiquiti / Wi-Fi"
    OUTRO = "Outro"


class TicketImpact(str, Enum):
    SIMPLE_REQUEST = "Duvida ou solicitacao simples"
    ONE_USER_CAN_WORK = "Afeta somente voce, mas ainda consegue trabalhar"
    ONE_USER_STOPPED = "Afeta somente voce e esta parado"
    MANY_USERS = "Afeta varias pessoas"
    CRITICAL_OPERATION = "Afeta setor inteiro, filial ou operacao critica"


class TicketSeverity(str, Enum):
    LOW = "Baixa"
    MEDIUM = "Media"
    HIGH = "Alta"
    CRITICAL = "Critica"


class TicketStatus(str, Enum):
    OPEN = "Aberto"
    IN_PROGRESS = "Em atendimento"
    CLOSED = "Fechado"


class TicketOpeningMode(str, Enum):
    QUICK = "Chamado rapido"
    DETAILED = "Chamado detalhado"


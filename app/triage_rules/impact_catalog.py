from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImpactOption:
    id: int
    label: str


IMPACT_OPTIONS: tuple[ImpactOption, ...] = (
    ImpactOption(1, "Dúvida ou solicitação simples"),
    ImpactOption(2, "Afeta somente você, mas ainda consegue trabalhar"),
    ImpactOption(3, "Afeta somente você e está parado"),
    ImpactOption(4, "Afeta várias pessoas"),
    ImpactOption(5, "Afeta setor inteiro, filial ou operação crítica"),
)


def get_impact_by_id(impact_id: int) -> ImpactOption | None:
    return next((impact for impact in IMPACT_OPTIONS if impact.id == impact_id), None)


def render_impact_menu() -> str:
    return (
        "🚦 **Nível de Impacto**\n\n"
        "Como este problema está afetando seu trabalho agora?\n\n"
        "1️⃣ 🟢 **Baixo:** Apenas uma dúvida ou pedido simples.\n"
        "2️⃣ 🟡 **Médio:** Consigo trabalhar, mas com dificuldades.\n"
        "3️⃣ 🟠 **Alto:** Estou totalmente parado(a).\n"
        "4️⃣ 🔴 **Crítico:** Afeta várias pessoas ou um setor inteiro.\n\n"
        "Digite o número da opção:"
    )


def _keycap(number: int) -> str:
    return {
        1: "1️⃣",
        2: "2️⃣",
        3: "3️⃣",
        4: "4️⃣",
        5: "5️⃣",
    }[number]

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImpactOption:
    id: int
    label: str


IMPACT_OPTIONS: tuple[ImpactOption, ...] = (
    ImpactOption(1, "Duvida ou solicitacao simples"),
    ImpactOption(2, "Afeta somente voce, mas ainda consegue trabalhar"),
    ImpactOption(3, "Afeta somente voce e esta parado"),
    ImpactOption(4, "Afeta varias pessoas"),
    ImpactOption(5, "Afeta setor inteiro, filial ou operacao critica"),
)


def get_impact_by_id(impact_id: int) -> ImpactOption | None:
    return next((impact for impact in IMPACT_OPTIONS if impact.id == impact_id), None)


def render_impact_menu() -> str:
    lines = ["Qual o impacto?"]
    lines.extend(f"{impact.id}. {impact.label}" for impact in IMPACT_OPTIONS)
    return "\n".join(lines)


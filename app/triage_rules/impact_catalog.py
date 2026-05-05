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

IMPACT_ICONS_BY_ID = {
    1: "🟢",
    2: "🟡",
    3: "🟠",
    4: "🔴",
    5: "🚨",
}


def get_impact_by_id(impact_id: int) -> ImpactOption | None:
    return next((impact for impact in IMPACT_OPTIONS if impact.id == impact_id), None)


def render_impact_menu() -> str:
    lines = ["📊 **Qual é o impacto para a operação?**"]
    lines.extend(
        f"{impact.id}. {IMPACT_ICONS_BY_ID[impact.id]} **{impact.label}**"
        for impact in IMPACT_OPTIONS
    )
    return "\n".join(lines)

from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from dataclasses import dataclass, replace

from app.application_config.settings import load_settings
from app.local_light_ai.description_organization_models import (
    LocalGenerativeAIUnavailableError,
)
from app.local_light_ai.guided_ticket_detailer import build_guided_ticket_detailer


@dataclass
class Scenario:
    name: str
    initial_description: str
    answers: list[str]
    expected_question_range: tuple[int, int]
    expected_summary_keywords: list[str]


def normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def build_scenarios() -> list[Scenario]:
    return [
        Scenario(
            "vago_computador",
            "Estou com problema no computador",
            ["E no notebook do financeiro.", "Aparece tela azul ao iniciar."],
            (1, 2),
            ["notebook", "financeiro", "tela azul"],
        ),
        Scenario(
            "vago_sistema",
            "Estou com problema em um sistema",
            ["Ele fecha toda hora quando tento usar.", "Acontece no Outlook."],
            (1, 2),
            ["fecha", "outlook"],
        ),
        Scenario(
            "email_bloqueado",
            "Nao consigo acessar meu email no Outlook.",
            [],
            (0, 1),
            ["email", "outlook"],
        ),
        Scenario(
            "impressora_pdf",
            "A impressora do fiscal nao imprime PDF.",
            [],
            (0, 1),
            ["impressora", "fiscal", "pdf"],
        ),
        Scenario(
            "wifi_deposito",
            "O Wi-Fi do deposito esta caindo desde hoje cedo.",
            [],
            (0, 1),
            ["wifi", "deposito", "caindo"],
        ),
        Scenario(
            "internet_lenta",
            "A internet esta muito lenta na matriz do financeiro.",
            [],
            (0, 1),
            ["internet", "lenta", "financeiro"],
        ),
        Scenario(
            "acesso_portal_compras",
            "Preciso de acesso ao portal de compras.",
            [],
            (0, 0),
            ["acesso", "portal", "compras"],
        ),
        Scenario(
            "instalacao_teams",
            "Preciso instalar o Teams no notebook novo.",
            [],
            (0, 0),
            ["teams", "notebook", "novo"],
        ),
        Scenario(
            "notebook_nao_liga",
            "Meu notebook nao liga depois da atualizacao de ontem.",
            [],
            (0, 1),
            ["notebook", "nao liga", "atualizacao"],
        ),
        Scenario(
            "ramal_generico",
            "Estou com problema no ramal.",
            ["Nao completa ligacao e fica mudo.", "Acontece no ramal 214."],
            (1, 2),
            ["ramal", "ligacao", "214"],
        ),
        Scenario(
            "app_generico",
            "Um aplicativo esta com problema.",
            ["Ele fecha toda hora quando tento abrir.", "Isso acontece no Teams."],
            (1, 2),
            ["fecha", "teams"],
        ),
        Scenario(
            "impressora_etiqueta",
            "Nao consigo imprimir etiqueta na expedicao.",
            ["Acontece na Zebra da expedicao."],
            (0, 2),
            ["imprimir", "etiqueta", "expedicao"],
        ),
        Scenario(
            "vpn_desconecta",
            "A VPN desconecta toda hora quando trabalho de casa.",
            [],
            (0, 1),
            ["vpn", "desconecta"],
        ),
        Scenario(
            "programa_emitir_nota",
            "O programa trava quando clico em emitir nota.",
            ["Acontece no Solution."],
            (0, 2),
            ["trava", "emitir nota", "solution"],
        ),
        Scenario(
            "camera_offline",
            "A camera do patio esta offline.",
            [],
            (0, 1),
            ["camera", "patio", "offline"],
        ),
        Scenario(
            "troca_mouse",
            "Preciso trocar um mouse quebrado.",
            [],
            (0, 0),
            ["trocar", "mouse", "quebrado"],
        ),
        Scenario(
            "arquivo_rede",
            "Nao consigo abrir um arquivo na rede.",
            ["Acontece na pasta do comercial."],
            (0, 2),
            ["arquivo", "rede", "comercial"],
        ),
        Scenario(
            "usuario_bloqueado",
            "Meu usuario esta bloqueado.",
            ["No GLPI, nao deixa entrar."],
            (0, 2),
            ["usuario", "bloqueado", "glpi"],
        ),
        Scenario(
            "whatsapp_web",
            "O WhatsApp Web nao abre no Chrome.",
            [],
            (0, 1),
            ["whatsapp", "web", "chrome"],
        ),
        Scenario(
            "erp_lento",
            "O ERP esta lento no faturamento.",
            [],
            (0, 1),
            ["erp", "lento", "faturamento"],
        ),
        Scenario(
            "scanner_email",
            "O scanner nao envia para email.",
            ["Acontece no scanner da recepcao."],
            (0, 2),
            ["scanner", "email", "recepcao"],
        ),
        Scenario(
            "acesso_financeiro_compras",
            "Preciso de acesso aos modulos financeiro e compras.",
            [],
            (0, 0),
            ["acesso", "financeiro", "compras"],
        ),
        Scenario(
            "toner",
            "A impressora do RH esta sem toner.",
            [],
            (0, 1),
            ["impressora", "rh", "toner"],
        ),
        Scenario(
            "salvar_pedido",
            "Nao consigo salvar pedido.",
            ["Acontece no sistema comercial."],
            (0, 2),
            ["salvar", "pedido", "comercial"],
        ),
        Scenario(
            "tela_piscando",
            "Minha tela fica piscando o dia todo.",
            [],
            (0, 1),
            ["tela", "piscando"],
        ),
        Scenario(
            "erro_500_portal",
            "Recebo erro 500 ao acessar o portal.",
            ["O portal e o de compras."],
            (0, 2),
            ["erro 500", "portal", "compras"],
        ),
        Scenario(
            "login_glpi",
            "Meu login do GLPI nao funciona.",
            [],
            (0, 1),
            ["login", "glpi", "nao funciona"],
        ),
        Scenario(
            "office_licenca",
            "Preciso ativar a licenca do Office no notebook novo.",
            [],
            (0, 0),
            ["ativar", "licenca", "office"],
        ),
        Scenario(
            "portal_fecha",
            "O portal fecha sozinho quando tento abrir um chamado.",
            ["Acontece no GLPI web."],
            (0, 2),
            ["portal", "fecha", "glpi"],
        ),
        Scenario(
            "rede_unidade",
            "A rede da unidade de Rondonopolis caiu.",
            [],
            (0, 1),
            ["rede", "rondonopolis", "caiu"],
        ),
    ]


def run_scenario(detailer, scenario: Scenario, max_questions: int = 5) -> dict:
    turns: list[dict[str, str]] = []
    transcript: list[dict[str, str]] = []
    final_summary = ""
    stopped_reason = "ready"
    for _ in range(max_questions + 1):
        result = None
        last_error = ""
        for attempt, pause_seconds in enumerate((0.0, 20.0, 40.0), start=1):
            if pause_seconds:
                time.sleep(pause_seconds)
            try:
                result = detailer.detail_ticket_description(
                    original_description=scenario.initial_description,
                    clarification_turns=turns,
                    category_name=None,
                    max_questions=max_questions,
                )
                break
            except LocalGenerativeAIUnavailableError as exc:
                last_error = str(exc)
                if attempt == 3:
                    return {
                        "name": scenario.name,
                        "initial_description": scenario.initial_description,
                        "question_count": len(transcript),
                        "expected_question_range": scenario.expected_question_range,
                        "final_summary": "",
                        "transcript": transcript,
                        "checks": {
                            "range_pass": False,
                            "keyword_pass": False,
                            "duplicate_pass": False,
                            "question_limit_pass": len(transcript) <= max_questions,
                            "safe_questions_pass": True,
                            "final_summary_present": False,
                        },
                        "passed": False,
                        "stopped_reason": f"ai_unavailable:{last_error}",
                    }
        time.sleep(6.0)
        assert result is not None
        if result.is_ready:
            final_summary = result.organized_text
            break

        answer = (
            scenario.answers[len(turns)]
            if len(turns) < len(scenario.answers)
            else "pular"
        )
        transcript.append(
            {
                "question": result.next_question,
                "answer": answer,
                "backend": result.backend,
            }
        )
        turns.append({"question": result.next_question, "answer": answer})
    else:
        stopped_reason = "max_loop_guard"

    normalized_summary = normalize(final_summary)
    keyword_pass = all(
        normalize(keyword) in normalized_summary
        for keyword in scenario.expected_summary_keywords
    )
    question_count = len(transcript)
    min_questions, max_expected = scenario.expected_question_range
    range_pass = min_questions <= question_count <= max_expected
    duplicate_pass = len(
        {normalize(item["question"]) for item in transcript}
    ) == len(transcript)
    question_limit_pass = question_count <= max_questions
    safe_questions_pass = all(
        not re.search(
            r"\b(senha|token|cpf|rg|cartao|sudo|powershell|cmd)\b",
            normalize(item["question"]),
        )
        for item in transcript
    )
    passed = all(
        [
            range_pass,
            keyword_pass,
            duplicate_pass,
            question_limit_pass,
            safe_questions_pass,
            bool(final_summary.strip()),
        ]
    )
    return {
        "name": scenario.name,
        "initial_description": scenario.initial_description,
        "question_count": question_count,
        "expected_question_range": scenario.expected_question_range,
        "final_summary": final_summary,
        "transcript": transcript,
        "checks": {
            "range_pass": range_pass,
            "keyword_pass": keyword_pass,
            "duplicate_pass": duplicate_pass,
            "question_limit_pass": question_limit_pass,
            "safe_questions_pass": safe_questions_pass,
            "final_summary_present": bool(final_summary.strip()),
        },
        "passed": passed,
        "stopped_reason": stopped_reason,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--output", type=str, default="")
    parser.add_argument("--pause-seconds", type=float, default=6.0)
    args = parser.parse_args()

    settings = replace(
        load_settings(),
        ai_guided_detailing_enabled=True,
        ai_max_clarification_questions=5,
        use_celery_workers=False,
        google_ai_rate_limit_enabled=False,
        google_ai_rpm_limit=0,
        google_ai_rpd_limit=0,
    )
    detailer = build_guided_ticket_detailer(settings)
    scenarios = build_scenarios()[args.start : args.start + args.count]
    original_run_scenario = run_scenario

    def run_with_pause(detailer, scenario, max_questions=5):
        turns: list[dict[str, str]] = []
        transcript: list[dict[str, str]] = []
        final_summary = ""
        stopped_reason = "ready"
        for _ in range(max_questions + 1):
            result = None
            last_error = ""
            for attempt, pause_seconds in enumerate((0.0, 20.0, 40.0), start=1):
                if pause_seconds:
                    time.sleep(pause_seconds)
                try:
                    result = detailer.detail_ticket_description(
                        original_description=scenario.initial_description,
                        clarification_turns=turns,
                        category_name=None,
                        max_questions=max_questions,
                    )
                    break
                except LocalGenerativeAIUnavailableError as exc:
                    last_error = str(exc)
                    if attempt == 3:
                        return {
                            "name": scenario.name,
                            "initial_description": scenario.initial_description,
                            "question_count": len(transcript),
                            "expected_question_range": scenario.expected_question_range,
                            "final_summary": "",
                            "transcript": transcript,
                            "checks": {
                                "range_pass": False,
                                "keyword_pass": False,
                                "duplicate_pass": False,
                                "question_limit_pass": len(transcript) <= max_questions,
                                "safe_questions_pass": True,
                                "final_summary_present": False,
                            },
                            "passed": False,
                            "stopped_reason": f"ai_unavailable:{last_error}",
                        }
            if args.pause_seconds:
                time.sleep(args.pause_seconds)
            assert result is not None
            if result.is_ready:
                final_summary = result.organized_text
                break

            answer = (
                scenario.answers[len(turns)]
                if len(turns) < len(scenario.answers)
                else "pular"
            )
            transcript.append(
                {
                    "question": result.next_question,
                    "answer": answer,
                    "backend": result.backend,
                }
            )
            turns.append({"question": result.next_question, "answer": answer})
        else:
            stopped_reason = "max_loop_guard"

        normalized_summary = normalize(final_summary)
        keyword_pass = all(
            normalize(keyword) in normalized_summary
            for keyword in scenario.expected_summary_keywords
        )
        question_count = len(transcript)
        min_questions, max_expected = scenario.expected_question_range
        range_pass = min_questions <= question_count <= max_expected
        duplicate_pass = len(
            {normalize(item["question"]) for item in transcript}
        ) == len(transcript)
        question_limit_pass = question_count <= max_questions
        safe_questions_pass = all(
            not re.search(
                r"\b(senha|token|cpf|rg|cartao|sudo|powershell|cmd)\b",
                normalize(item["question"]),
            )
            for item in transcript
        )
        passed = all(
            [
                range_pass,
                keyword_pass,
                duplicate_pass,
                question_limit_pass,
                safe_questions_pass,
                bool(final_summary.strip()),
            ]
        )
        return {
            "name": scenario.name,
            "initial_description": scenario.initial_description,
            "question_count": question_count,
            "expected_question_range": scenario.expected_question_range,
            "final_summary": final_summary,
            "transcript": transcript,
            "checks": {
                "range_pass": range_pass,
                "keyword_pass": keyword_pass,
                "duplicate_pass": duplicate_pass,
                "question_limit_pass": question_limit_pass,
                "safe_questions_pass": safe_questions_pass,
                "final_summary_present": bool(final_summary.strip()),
            },
            "passed": passed,
            "stopped_reason": stopped_reason,
        }

    results = [run_with_pause(detailer, scenario) for scenario in scenarios]
    payload = {
        "start": args.start,
        "count": len(results),
        "passed": sum(1 for item in results if item["passed"]),
        "results": results,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as file:
            file.write(rendered)
    print(rendered)


if __name__ == "__main__":
    main()

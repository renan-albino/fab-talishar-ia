#!/usr/bin/env python3
"""
run_smoke_tests.py
==================
Bateria rápida de Smoke Tests para o ecossistema FaB Talishar AI.

Executa 3 etapas críticas de validação rápida (sub-3s no total):
  1. Validação Sintática Rápida (py_compile) em 100% dos módulos do projeto;
  2. Teste de Sanidade de Imports de todas as fachadas e pacotes de arquitetura;
  3. Execução de suíte essencial de testes automatizados (pytest) sub-3s com resumo colorido.

Retorna código de saída 0 para sucesso total ou 1 em caso de falha em qualquer etapa.
"""

import os
import sys
import glob
import time
import json
import py_compile
import importlib
import subprocess
import argparse
import io
import contextlib
from typing import Dict, Any, List, Tuple

# ── Resolução de Caminho Raiz do Repositório ──────────────────────────────
def _find_repo_root() -> str:
    curr = os.path.abspath(os.path.dirname(__file__))
    while curr and curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, "bot_client.py")) or os.path.exists(os.path.join(curr, ".git")):
            return curr
        curr = os.path.dirname(curr)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))

ROOT_DIR = _find_repo_root()
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Cores ANSI
COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[0;32m"
COLOR_YELLOW = "\033[1;33m"
COLOR_RED = "\033[0;31m"
COLOR_CYAN = "\033[0;36m"
COLOR_BOLD = "\033[1m"


# ── Configuração das Etapas ───────────────────────────────────────────────
SYNTAX_PATTERNS = [
    "*.py",
    "ai/*.py",
    "ai/policy/*.py",
    "ai/mcts/*.py",
    "ai/training/*.py",
    "ai/hero_strategies/*.py",
    "ai/bot_runtime/*.py",
    "ai/common/*.py",
    "deck_manager/*.py",
    "stats/*.py",
    "ui/*.py",
    "ui/tabs/*.py",
    "scripts/*.py",
    ".agents/skills/automated-tasks/scripts/*.py",
    "tests/*.py",
]

FACADE_MODULES = [
    ("bot_client", "FabBotClient"),
    ("deck_parser", "parse_deck_text"),
    ("stats_manager", "get_stats_data"),
    ("deck_manager", "load_fab_cards_db"),
    ("stats", "canonicalize_deck_name"),
    ("ai.policy_engine", "PolicyEngine"),
    ("ai.mcts", "MCTSEngine"),
    ("ai.model", "FaBPolicyValueNetwork"),
    ("ai.game_simulator", "GameSimulator"),
    ("ai.common", None),
    ("ui.helpers", "get_cached_saved_decks"),
]

ESSENTIAL_TEST_FILES = [
    "tests/test_model.py",
    "tests/test_deck_parser.py",
    "tests/test_stats_manager.py",
    "tests/test_game_simulator.py",
    "tests/test_bot_modules.py",
    "tests/test_multichoose_and_arsenal.py",
]


def step_syntax_compile(verbose: bool = False) -> Tuple[bool, Dict[str, Any]]:
    """Etapa 1: Validação de sintaxe com py_compile em todos os arquivos Python."""
    t0 = time.perf_counter()
    files_to_check: List[str] = []

    for pat in SYNTAX_PATTERNS:
        full_pat = os.path.join(ROOT_DIR, pat)
        files_to_check.extend(glob.glob(full_pat))

    files_to_check = sorted(set(files_to_check))
    errors: List[Tuple[str, str]] = []

    for fpath in files_to_check:
        try:
            py_compile.compile(fpath, doraise=True)
        except Exception as e:
            rel_path = os.path.relpath(fpath, ROOT_DIR)
            errors.append((rel_path, str(e)))

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    success = len(errors) == 0

    return success, {
        "step": "syntax_compile",
        "success": success,
        "total_files": len(files_to_check),
        "compiled_files": len(files_to_check) - len(errors),
        "errors": errors,
        "elapsed_ms": round(elapsed_ms, 2)
    }


def step_facade_imports(verbose: bool = False) -> Tuple[bool, Dict[str, Any]]:
    """Etapa 2: Sanidade de importação das fachadas do sistema e símbolos fundamentais."""
    t0 = time.perf_counter()
    import_results: List[Dict[str, Any]] = []
    has_failure = False

    # Silenciar logs ruidosos do Streamlit durante imports de teste
    os.environ["STREAMLIT_LOG_LEVEL"] = "error"

    for mod_name, expected_symbol in FACADE_MODULES:
        t_mod = time.perf_counter()
        err_msg = None
        symbol_found = False

        # Redirecionar stderr temporariamente para suprimir avisos de cache do streamlit
        f_null = io.StringIO()
        with contextlib.redirect_stderr(f_null):
            try:
                mod = importlib.import_module(mod_name)
                if expected_symbol:
                    symbol_found = hasattr(mod, expected_symbol)
                    if not symbol_found:
                        err_msg = f"Símbolo '{expected_symbol}' não encontrado no módulo '{mod_name}'."
                else:
                    symbol_found = True
            except Exception as e:
                err_msg = str(e)

        mod_ms = (time.perf_counter() - t_mod) * 1000.0
        is_ok = (err_msg is None)
        if not is_ok:
            has_failure = True

        import_results.append({
            "module": mod_name,
            "expected_symbol": expected_symbol,
            "success": is_ok,
            "error": err_msg,
            "elapsed_ms": round(mod_ms, 2)
        })

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return (not has_failure), {
        "step": "facade_imports",
        "success": not has_failure,
        "total_modules": len(FACADE_MODULES),
        "modules": import_results,
        "elapsed_ms": round(elapsed_ms, 2)
    }


def step_pytest_suite(test_files: List[str], verbose: bool = False) -> Tuple[bool, Dict[str, Any]]:
    """Etapa 3: Execução rápida da suíte essencial de testes automatizados com pytest."""
    t0 = time.perf_counter()

    # Monta comando do pytest no diretório do projeto com formatação limpa
    cmd = [sys.executable, "-m", "pytest", "--tb=short", "--no-header"] + test_files
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            timeout=15
        )
        elapsed_s = time.perf_counter() - t0
        output = (proc.stdout or "") + (proc.stderr or "")
        success = (proc.returncode == 0)

        # Extrai linha de resumo do pytest (ex: "26 passed in 1.62s")
        summary_line = ""
        for line in reversed(output.splitlines()):
            line_clean = line.strip().strip("=")
            if "passed" in line_clean or "failed" in line_clean or "error" in line_clean:
                summary_line = line_clean.strip()
                break

        if not summary_line and success:
            summary_line = f"Sucesso em {len(test_files)} módulos de teste"

        return success, {
            "step": "pytest_suite",
            "success": success,
            "returncode": proc.returncode,
            "summary_line": summary_line,
            "test_files": test_files,
            "elapsed_s": round(elapsed_s, 2),
            "output": output if (not success or verbose) else ""
        }
    except Exception as e:
        elapsed_s = time.perf_counter() - t0
        return False, {
            "step": "pytest_suite",
            "success": False,
            "returncode": -1,
            "summary_line": f"Exceção ao rodar pytest: {e}",
            "test_files": test_files,
            "elapsed_s": round(elapsed_s, 2),
            "output": str(e)
        }


def print_summary(report: Dict[str, Any], verbose: bool = False) -> None:
    """Renderiza painel terminal com sumário executivo e colorido dos smoke tests."""
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}══════════════════════════════════════════════════════════════════════════════════════════════════════{COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_CYAN}   FaB Talishar AI — Smoke Tests de Integridade & Sanidade (Sub-3s)                                     {COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_CYAN}══════════════════════════════════════════════════════════════════════════════════════════════════════{COLOR_RESET}\n")

    # Etapa 1: Sintaxe
    st1 = report.get("syntax_compile", {})
    if st1:
        if st1["success"]:
            b1 = f"{COLOR_GREEN}✓ APROVADO{COLOR_RESET}"
            d1 = f"{st1['compiled_files']}/{st1['total_files']} arquivos compilados sem erros ({st1['elapsed_ms']:.1f}ms)"
        else:
            b1 = f"{COLOR_RED}✗ FALHOU{COLOR_RESET}"
            d1 = f"{len(st1['errors'])} erro(s) de compilação detectados ({st1['elapsed_ms']:.1f}ms)"
        print(f"  {COLOR_BOLD}[Etapa 1] Validação de Sintaxe (py_compile):{COLOR_RESET} {b1}")
        print(f"            ↳ {d1}")
        if not st1["success"] or verbose:
            for f, err in st1.get("errors", []):
                print(f"              {COLOR_RED}✗ {f}:{COLOR_RESET} {err}")

    # Etapa 2: Imports
    st2 = report.get("facade_imports", {})
    if st2:
        if st2["success"]:
            b2 = f"{COLOR_GREEN}✓ APROVADO{COLOR_RESET}"
            d2 = f"{st2['total_modules']}/{st2['total_modules']} fachadas importadas com sucesso ({st2['elapsed_ms']:.1f}ms)"
        else:
            b2 = f"{COLOR_RED}✗ FALHOU{COLOR_RESET}"
            d2 = f"Falha na importação de fachadas ({st2['elapsed_ms']:.1f}ms)"
        print(f"\n  {COLOR_BOLD}[Etapa 2] Sanidade de Imports e Fachadas:{COLOR_RESET} {b2}")
        print(f"            ↳ {d2}")
        if not st2["success"] or verbose:
            for m in st2.get("modules", []):
                if m["success"]:
                    if verbose:
                        print(f"              {COLOR_GREEN}✓ {m['module']:<20}{COLOR_RESET} ({m['elapsed_ms']:.1f}ms)")
                else:
                    print(f"              {COLOR_RED}✗ {m['module']:<20}:{COLOR_RESET} {m['error']}")

    # Etapa 3: Pytest
    st3 = report.get("pytest_suite", {})
    if st3:
        if st3["success"]:
            b3 = f"{COLOR_GREEN}✓ APROVADO{COLOR_RESET}"
            d3 = f"{st3.get('summary_line', 'Todos os testes passaram')} ({st3['elapsed_s']:.2f}s)"
        else:
            b3 = f"{COLOR_RED}✗ FALHOU{COLOR_RESET}"
            d3 = f"Falha na execução: {st3.get('summary_line', '')} ({st3['elapsed_s']:.2f}s)"
        print(f"\n  {COLOR_BOLD}[Etapa 3] Suíte Essencial Pytest (Sub-3s):{COLOR_RESET} {b3}")
        print(f"            ↳ {d3}")
        if not st3["success"] and st3.get("output"):
            print("\n" + st3["output"])

    # Veredito Final
    total_time = report["total_time_s"]
    all_ok = report["all_passed"]
    print(f"\n--------------------------------------------------------------------------------------------------")
    if all_ok:
        print(f"{COLOR_BOLD}Veredito Final:{COLOR_RESET} {COLOR_GREEN}✓ TODOS OS SMOKE TESTS PASSARAM COM SUCESSO!{COLOR_RESET} (Tempo total: {total_time:.2f}s)")
    else:
        print(f"{COLOR_BOLD}Veredito Final:{COLOR_RESET} {COLOR_RED}✗ FALHA DETECTADA NOS SMOKE TESTS{COLOR_RESET} (Tempo total: {total_time:.2f}s)")
    print("--------------------------------------------------------------------------------------------------\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke Tests de Validação Rápida Sub-3s para FaB Talishar AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  ./venv/bin/python .agents/skills/automated-tasks/scripts/run_smoke_tests.py
  ./venv/bin/python .agents/skills/automated-tasks/scripts/run_smoke_tests.py --skip-tests
  ./venv/bin/python .agents/skills/automated-tasks/scripts/run_smoke_tests.py --verbose
  ./venv/bin/python .agents/skills/automated-tasks/scripts/run_smoke_tests.py --json
        """
    )
    parser.add_argument(
        "--skip-compile",
        action="store_true",
        help="Pula a validação de sintaxe (py_compile)."
    )
    parser.add_argument(
        "--skip-imports",
        action="store_true",
        help="Pula o teste de sanidade de imports das fachadas."
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Pula a execução da suíte de testes pytest."
    )
    parser.add_argument(
        "--test-suite",
        type=str,
        default="essential",
        choices=["essential", "all"],
        help="Seleção da suíte de testes: essential (padrão, sub-3s) ou all."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Exibe resultado em JSON estruturado."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Exibe detalhes completos de cada arquivo compilado e módulo testado."
    )

    args = parser.parse_args()
    overall_start = time.perf_counter()

    report: Dict[str, Any] = {
        "all_passed": True,
        "total_time_s": 0.0
    }

    # Etapa 1
    if not args.skip_compile:
        ok1, st1 = step_syntax_compile(verbose=args.verbose)
        report["syntax_compile"] = st1
        if not ok1:
            report["all_passed"] = False

    # Etapa 2
    if not args.skip_imports:
        ok2, st2 = step_facade_imports(verbose=args.verbose)
        report["facade_imports"] = st2
        if not ok2:
            report["all_passed"] = False

    # Etapa 3
    if not args.skip_tests:
        if args.test_suite == "all":
            test_files = ["tests/"]
        else:
            test_files = ESSENTIAL_TEST_FILES
        ok3, st3 = step_pytest_suite(test_files, verbose=args.verbose)
        report["pytest_suite"] = st3
        if not ok3:
            report["all_passed"] = False

    report["total_time_s"] = round(time.perf_counter() - overall_start, 2)

    if args.output_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_summary(report, verbose=args.verbose)

    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

# ADR-0003: Persistência Atômica Segura e Mutex Interprocessos Reentrante via atomic_io

- **Status**: Deprecated (Substituído pelo [ADR-0009](ADR-0009-architecture-rewrite-pydantic-sqlite-immutable-state.md))
- **Date**: 2026-09-16 (Depreciado em 2026-09-24)
- **Deciders**: Equipe FaB Talishar AI (Architecture Review)

## Context

O ecossistema FaB Talishar AI executa múltiplos processos independentes concorrentemente no sistema operacional Linux:
1. Múltiplos processos de bots em background executando partidas de Self-Play ou partidas simultâneas contra o Talishar.
2. O orquestrador de treinamento (`ai/training/orchestrator.py`) atualizando estatísticas de épocas e salvando experiências.
3. O dashboard analítico Streamlit (`dashboard.py`) lendo rankings, métricas e telemetria de jogos em tempo real.
4. Módulos de aprendizado empírico atualizando tabelas estatísticas (`stats/storage.py`, `ai/equipment_learning.py`, `ai/dynamic_rule_tuner.py`).

No desenho legado com escrita direta de arquivos (`open(filepath, "w")` seguido de `json.dump`), a concorrência entre leitores e escritores resultava em falhas graves:
- **Corrupção de arquivos**: O comando `open(..., "w")` trunca imediatamente o arquivo para zero bytes antes de começar a escrever o JSON. Se outro processo realizar leitura nesse milissegundo ou se o processo escritor sofrer interrupção, o arquivo ficava corrompido (`json.decoder.JSONDecodeError: Unterminated string`).
- **Race Conditions de Leitura/Modificação**: Dois processos liam simultaneamente um arquivo de métricas ou ratings ELO, calculavam seus incrementos e gravavam de volta, sobrescrevendo os dados um do outro e perdendo partidas de treinamento.

## Decision

Centralizar todas as operações de persistência crítica de dados estruturados em `ai/atomic_io.py`, padronizando o acesso atômico e o bloqueio entre processos no nível de sistema operacional (POSIX):

### 1. Escrita Atômica via `atomic_json_save` (Write-to-Temp + Rename)
Toda gravação de arquivos JSON no ecossistema deve usar o padrão atômico:
```python
def atomic_json_save(data: dict | list, filepath: str, indent: int = 2) -> None:
    dir_name = os.path.dirname(filepath) or "."
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        os.replace(tmp_path, filepath)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
```
- O arquivo temporário é obrigatoriamente criado no mesmo diretório (mesmo sistema de arquivos / partição) do arquivo de destino.
- A substituição `os.replace` é garantida como uma operação **atômica de troca de inode** pela especificação POSIX e no Windows/NTFS.
- Qualquer processo leitor sempre observará ou o arquivo antigo intacto ou o arquivo novo completamente gravado e fechado — nunca um estado intermediário ou truncado.

### 2. Mutex Interprocessos via `file_lock` (`fcntl.flock`)
Para operações de Leitura-Modificação-Escrita (como atualização de pontuações ELO em `stats/storage.py` ou buffers compartilhados), é obrigatório o uso do context manager `file_lock`:
```python
@contextmanager
def file_lock(filepath: str, timeout: float = 10.0):
    lock_file = f"{filepath}.lock"
    os.makedirs(os.path.dirname(lock_file) or ".", exist_ok=True)
    with open(lock_file, "a") as f:
        # Polling não-bloqueante com timeout para prevenir deadlocks
        ...
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```
- Utiliza arquivos de trava dedicados (`<filepath>.lock`) para não colidir com o `os.replace` do arquivo de dados.
- Implementa aquisição não-bloqueante (`LOCK_NB`) com verificação de timeout configurável, evitando deadlocks permanentes caso um processo seja abortado abruptamente.
- Liberação segura no bloco `finally` garantida mesmo na ocorrência de exceções em Python.

## Consequences

### Positive
- **Integridade Absoluta de Dados**: Elimina por completo os erros de `JSONDecodeError` e corrupção de arquivos de ranking (`ratings.json`), histórico e métricas de treino.
- **Transparência e Confiabilidade**: O dashboard pode consultar logs e métricas a qualquer momento sem interferir no treinamento de múltiplos bots em background.
- **Portabilidade Unix**: Utiliza primitivas nativas do kernel Linux (`flock`, `rename`), operando perfeitamente em containers Docker, instâncias de nuvem e WSL2 sem serviços externos.

### Negative / Trade-offs
- **Overhead Mínimo de I/O**: A criação de arquivos temporários e lockfiles gera chamadas de sistema adicionais ao kernel (`sys_rename`, `sys_flock`), irrelevantes diante dos intervalos de decisão de segundos do jogo.
- **Arquivos `.lock` no Disco**: Deixa arquivos sentinela `.lock` vazios no diretório de dados (mitigado pelo `.gitignore`).

## Alternatives Considered

- **Servidor de Banco de Dados Dedicado (PostgreSQL / Redis)**: Rejeitado por violar a simplicidade de implantação local do projeto ("clone and run") e exigir serviços em execução contínua em máquinas de desenvolvimento.
- **SQLite em Disco**: Rejeitado pois SQLite em modo WAL com múltiplos processos escritores concorrentes em alta frequência sofre com erros de `database is locked` e latência imprevisível em arquivos de rede/Docker.
- **Mutex em Memória (`threading.Lock`)**: Rejeitado por atuar apenas no escopo de uma única instância do interpretador Python, oferecendo zero proteção contra colisões de múltiplos processos Python do sistema operacional.

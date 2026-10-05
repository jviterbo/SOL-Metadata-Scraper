# SOL-Metadata-Scraper

Scraper que coleta os metadados de uma série da [SOL](https://sol.sbc.org.br)
(SBC Open Library, baseada em OJS) e os exporta em arquivos CSV.

## Instalação

```
pip install -r requirements.txt
```

Requer Python 3.10 ou superior.

## Uso

```
python -m sol_scraper semish
```

O argumento é o caminho (path) da série na SOL. Opções:

| Opção | Descrição |
|---|---|
| `-o`, `--output-dir` | pasta dos arquivos CSV (padrão: pasta atual) |
| `--cache-dir` | pasta do cache (padrão: `./cache`) |
| `--no-cache` | não lê nem grava o cache |
| `--delay` | segundos entre requisições (padrão: 2.5) |

## Saída

Quatro arquivos separados por tabulação, em UTF-8, nomeados
`<tabela>-<série>-<AAAAMMDD>.csv`:

| Arquivo | Colunas |
|---|---|
| `papers` | Paper_id, Title, Abstract, DOI, Pages, Sections, Year, Date, URL |
| `authors` | Paper_id, Name, Affiliation, ORCID |
| `keywords` | Paper_id, Seq, Keyword |
| `references` | Paper_id, Seq, Reference |

Campos que contêm tabulação, quebra de linha ou aspas são colocados entre
aspas, no padrão CSV.

## Cache

Cada edição coletada é gravada em `cache/<série>/issue_<id>.json`. Em uma nova
execução, as edições já presentes no cache não são visitadas de novo; para
recoletar uma edição, apague o arquivo dela.

## Organização do código

| Módulo | Responsabilidade |
|---|---|
| `sol_scraper/client.py` | requisições HTTP (sessão, intervalo, timeout, novas tentativas) |
| `sol_scraper/parsing.py` | extração dos dados das páginas HTML |
| `sol_scraper/models.py` | estruturas de dados (`Paper`, `Author`, `Issue`...) |
| `sol_scraper/cache.py` | cache em JSON, um arquivo por edição |
| `sol_scraper/scraper.py` | fluxo série → edições → artigos |
| `sol_scraper/export.py` | geração dos arquivos CSV |
| `sol_scraper/cli.py` | linha de comando |

## Testes

```
pip install pytest
python -m pytest
```

Os testes usam páginas HTML simuladas e não acessam a rede.

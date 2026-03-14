# Contador de Accidentes — Periferico Luis Echeverria

Sitio estatico que rastrea accidentes viales en el Periferico Luis Echeverria de Saltillo, Coahuila. Un scraper automatizado recopila noticias de fuentes locales, las filtra por relevancia con IA y publica los datos en una pagina web actualizada cada hora.

## Como funciona

1. Un scraper automatizado busca noticias cada hora (Google News + portales locales de Saltillo)
2. Claude Haiku filtra cada nota por relevancia al Periferico
3. Los datos se guardan en JSON y el sitio estatico se actualiza automaticamente

## Configuracion

### Requisitos

- Python 3.12+
- API key de Anthropic

### Instalacion local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r scraper/requirements.txt
```

### Variables de entorno

```bash
export ANTHROPIC_API_KEY="tu-api-key"
```

### Ejecutar scraper manualmente

```bash
python -m scraper.main
```

### Ejecutar backfill

```bash
python -m scraper.backfill
```

### Ver el sitio localmente

```bash
cd docs && python3 -m http.server 8080
```

## Despliegue

1. Crear repo en GitHub
2. Agregar secret `ANTHROPIC_API_KEY` en Settings > Secrets and variables > Actions
3. Activar GitHub Pages (main branch, `/docs` folder)
4. Ejecutar workflow **Backfill de accidentes** manualmente para cargar datos historicos
5. El scraper corre automaticamente cada hora via GitHub Actions

## Estructura

```
crash-counter/
├── .github/
│   └── workflows/
│       ├── backfill.yml        # Workflow manual: backfill del ultimo mes
│       └── scraper.yml         # Workflow programado: cada hora
├── docs/
│   ├── data/
│   │   └── accidentes.json     # Datos de accidentes (generado)
│   └── index.html              # Sitio estatico (GitHub Pages)
├── scraper/
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── google_news.py      # Fuente: Google News RSS
│   │   └── local_portals.py    # Fuente: Vanguardia, Zocalo, Diario
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_data.py
│   │   ├── test_dedup.py
│   │   ├── test_google_news.py
│   │   ├── test_local_portals.py
│   │   ├── test_main.py
│   │   └── test_relevance_filter.py
│   ├── __init__.py
│   ├── data.py                 # Carga, guardado y calculo de racha
│   ├── dedup.py                # Deduplicacion por URL y similitud
│   ├── relevance_filter.py     # Filtro de relevancia con Claude Haiku
│   └── requirements.txt
├── .gitignore
└── README.md
```

## Licencia

MIT

# Setup do Projeto 

Este guia mostra como configurar e executar a aplicação de consulta de Diários Oficiais do TCMPA.

## Estrutura do Projeto

```
diario_oficial_tcmpa/
│
├── api.py                      # Backend FastAPI 
├── requirements.txt            # Dependências
├── exceptions/
│   └── diario_exceptions.py    # Exceções
├── static/                     # Landpage
│   ├── index.html     
│   │── docs.html    
│   ├── css/
│   │   └── styles.css       
│   └── js/
│       └── script.js        
├── util/
│   └── logger_config.py     # Configuração de logger
└── diarios/                 # Diretório onde os PDFs serão salvos
```

## Passos para Configuração

### 1. Clone o Repositório
```bash
git clone 
```

### 2. Instalar Dependências

```bash
pip install -r requirements.txt
```

```python
# exceptions/diario_exceptions.py
class DiarioNaoExiste(Exception):
    """Exceção lançada quando um diário não existe ou não pode ser encontrado."""
    pass
```


### 3. Executar o Serviço


```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

## Acessando a Aplicação

Uma vez que o servidor esteja rodando, acesse:

- Interface Web: http://localhost:8000/static/index.html
- Documentação da API: http://localhost:8000/docs

## Exemplos de Uso da API

### Consultar Diário

```bash
curl "http://localhost:8000/api/diario?dia=27&mes=3&ano=2025"
```

### Fazer Download do PDF

```bash
curl -O "http://localhost:8000/api/diario/download?dia=27&mes=3&ano=2025"
```

## Modificações Comuns

### Alterar o Diretório de Download

Você pode modificar o caminho de download padrão no arquivo `diario_oficial.py` adicionando o paramêtro de `download_dir`

```bash
curl -O "http://localhost:8000/api/diario/download?dia=27&mes=3&ano=2025&download_dir=/novo_diretorio"
```


import os
from typing import Any, Dict, List, Literal, Optional, Union

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.format_as_xml import format_as_xml
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.google_gla import GoogleGLAProvider
from pydantic_ai.providers.openai import OpenAIProvider

from util.logger_config import logger

load_dotenv()


import logfire

# Setup especifico do logfire para tratar campos sensíveis
def scrubbing_callback(m: logfire.ScrubMatch):
    if (
        m.path == ('attributes', 'model_request_parameters', 'result_tools', 0, 'parameters_json_schema', 'properties', 'orgao', 'examples', 0)
        and m.pattern_match.group(0) == 'Secret'
    ):
        return m.value

    if (
        m.path == ('attributes', 'events', 0, 'content')
        and m.pattern_match.group(0) == 'Secret'
    ):
        return m.value

    if (
        m.path == ('attributes', 'events', 1, 'content')
        and m.pattern_match.group(0) == 'Secret'
    ):
        return m.value

    if (
        m.path == ('attributes', 'events', 2, 'message', 'tool_calls', 0, 'function', 'arguments', 'ementa')
        and m.pattern_match.group(0) == 'SECRET'
    ):
        return m.value

    if (
        m.path == ('attributes', 'events', 2, 'message', 'tool_calls', 0, 'function', 'arguments', 'orgao')
        and m.pattern_match.group(0) == 'Secret'
    ):
        return m.value

logfire.configure(scrubbing=logfire.ScrubbingOptions(callback=scrubbing_callback))


# class Recorrente(BaseModel):
#     """
#     Modelo para representar um recorrente no acórdão.
#     Pode conter diferentes combinações de campos dependendo do caso.
#     """
#     nome: Optional[str] = Field(
#         None,
#         title="Nome",
#         description="Nome completo do recorrente",
#         examples=["João Sampaio de Oliveira", "Maria Silva e Associados LTDA"]
#     )
#     cpf: Optional[str] = Field(
#         None,
#         title="CPF",
#         description="CPF do recorrente quando for pessoa física",
#         examples=["083.957.212-10", "123.456.789-00"]
#     )
#     cnpj: Optional[str] = Field(
#         None,
#         title="CNPJ",
#         description="CNPJ do recorrente quando for pessoa jurídica",
#         examples=["12.345.678/0001-90"]
#     )
#     periodo: Optional[str] = Field(
#         None,
#         title="Período",
#         description="Período de atuação ou referência",
#         examples=["01/01/2023 a 31/12/2023", "2022-2023"]
#     )
#     cargo: Optional[str] = Field(
#         None,
#         title="Cargo",
#         description="Cargo ou função exercida",
#         examples=["Prefeito Municipal", "Secretário de Finanças"]
#     )

class Acordao(BaseModel, extra='allow'):
    """
    Modelo flexível para representação de acórdãos, contemplando variações terminológicas
    e campos opcionais que podem aparecer em diferentes formatos de diários oficiais.
    """
    # Configuração para aceitar campos extras e usar aliases
    model_config = ConfigDict(
        populate_by_name=True,
        extra='allow'
      )
    
    # Campos principais com múltiplos aliases possíveis
    categoria: Optional[str] = Field(
        title="Categoria",
        description="Tipo ou categoria do documento",
        examples=["Acórdão", "Decisão", "Parecer"],
        alias=["tipo", "natureza"]
    )
    
    numero: Optional[str] = Field(
        title="Número",
        description="Número de identificação do acórdão",
        examples=["46.073", "1234/2023"],
        alias=["num", "identificacao"]
    )
    
    processo: Optional[str] = Field(
        title="Processo",
        description="Número do processo relacionado",
        examples=["244012005-00", "2023.001.000123-4"],
        alias=["num_processo", "processo_numero"]
    )
    
    assunto: Optional[str] = Field(
        title="Assunto",
        description="Assunto principal do acórdão",
        examples=["Recurso de Reconsideração", "Prestação de Contas"],
        alias=["materia", "objeto"]
    )
    
    municipio: Optional[str] = Field(
        title="Município",
        description="Município de referência",
        examples=["Castanhal", "Belém"],
        alias=["local", "comarca"]
    )
    
    orgao: Optional[str] = Field(
        title="Órgão",
        description="Órgão responsável ou Unidade Gestora",
        examples=["Secretaria Municipal de Transporte", "Tribunal de Contas"],
        alias=["unidade_gestora", "gestora", "orgao_responsavel", "secretaria"]
    )
    
    advogado: Optional[str] = Field(
        title="Advogado",
        description="Nome do advogado ou representante legal",
        examples=["Joao Pessoa", "Dra. Ana Paula Mendes"],
        alias=["procurador", "representante_legal"]
    )
    
    recorrentes: Union[Optional[List[Dict[str,Any]]], Optional[str]] = Field(
        title="Recorrentes",
        description="Recorrentes ou partes interessadas",
        alias=["partes", "interessados", "requerentes"]
    )
    
    instrucao: Optional[str] = Field(
        title="Instrução",
        description="Instrução ou setor responsável",
        examples=["3ª Controladoria/TCM", "2 Controladoria"],
        alias=["setor", "unidade_tecnica"]
    )
    
    ministerio_publico: Optional[str] = Field(
        title="Ministério Público",
        description="Nome do representante do Ministério Público",
        examples=["Procurador Marcelo Fonseca Barros"],
        alias=["procurador_contas", "mp", "promotoria"]
    )
    
    relatoria: Optional[str] = Field(
        title="Relatoria",
        description="Nome do relator do processo",
        examples=["Conselheira Mara Lúcia"],
        alias=["relator", "juiz_relator"]
    )
    
    exercicio: Optional[str] = Field(
        title="Exercício",
        description="Ano ou período de exercício referente",
        examples=["2005", "2022-2023"],
        alias=["ano", "periodo_referencia"]
    )
    
    data_publicacao: Optional[str] = Field(
        title="Data de Publicação",
        description="Data em que o acórdão foi publicado",
        alias=["publicacao", "data"],
        examples=["15/03/2023"]
    )
    
    ementa: Optional[str] = Field(
        title="Ementa",
        description="Resumo ou ementa do acórdão",
        alias=["resumo", "sumario"]
    )
    

class LocalLlm:
    """
    Implementação concreta de DiarioLlm para execução local com backends como Ollama ou Llama.
    
    Adiciona funcionalidades específicas para configuração local.
    """
    
    def __init__(
            self,
            texto: str,
            modelo: str,
            backend: str,
            base_url: str = ''
        ):
        """
        Inicializa o processador local de LLM.
        
        Args:
            texto (str): Texto a ser processado
            modelo (str): Nome do modelo LLM
            backend (str): Backend a ser usado 
            base_url (str, optional): URL base do backend. Se vazia, será inferida.
        """
        self.base_url = base_url or self.set_base_url(backend)
        self.texto = texto
        self.modelo = modelo
        self.backend = backend
        logger.debug(f'Class LocalLlm: {self.texto[:50]}..., modelo: {self.modelo}, backend: {self.backend}, base_url: {self.base_url}')
        
    def set_base_url(self, backend: Literal['ollama', 'llama'] = 'ollama') -> str:
        """
        Define a URL base do backend com base no tipo especificado.
        
        Args:
            backend (str): Tipo de backend ('ollama' ou 'llama')
            
        Returns:
            str: URL base do backend
            
        Raises:
            ValueError: Se o backend não for suportado
        """
        if backend == 'ollama':
            return os.getenv('OLLAMA_ENDPOINT', 'http://localhost:11434/v1')
        elif backend == 'llama':
            return os.getenv('LLAMA_ENDPOINT', 'http://localhost:8080')
        else:
            return None
    
    def set_examples(self) -> str:
        """
        Define múltiplos exemplos de texto com variações terminológicas para treinar o LLM.
        
        Returns:
            str: Exemplos formatados em XML para inclusão no prompt
        """
        examples = [
            {
                'request': """ACÓRDÃO Nº 46.073 Processo nº 244012005-00 Assunto: Recurso de Reconsideração (Recurso Ordinário) Município: Castanhal Unidade Gestora: Secretaria Municipal de Transporte e Trânsito Recorrentes: João Sampaio de Oliveira (CPF: 083.957.212-10) (01/01 a 31/08/2005) e Waldir Nascimento Batista (CPF: 587.875.502-90) (01/09 a 31/12/2005) Procurador/Advogado(a): Elvis Ribeiro da Silva (OAB-PA 12.114) Instrução: 3ª Controladoria/TCM Ministério Público de Contas: Procurador Marcelo Fonseca Barros Relatoria: Conselheira Mara Lúcia Exercício: 2005 EMENTA: RECURSO DE RECONSIDERAÇÃO (RECURSO ORDINÁRIO)""",
                'response': {
                    'categoria': 'Acórdão',
                    'numero': '46.073',
                    'processo': '244012005-00',
                    'assunto': 'Recurso de Reconsideração (Recurso Ordinário)',
                    'municipio': 'Castanhal',
                    'orgao': 'Secretaria Municipal de Transporte e Trânsito',
                    'recorrentes': [
                        {
                            'nome': 'João Sampaio de Oliveira',
                            'cpf': '083.957.212-10',
                            'periodo': '01/01 a 31/08/2005'
                        },
                        {
                            'nome': 'Waldir Nascimento Batista',
                            'cpf': '587.875.502-90',
                            'periodo': '01/09 a 31/12/2005'
                        }
                    ],
                    'advogado': 'Elvis Ribeiro da Silva',
                    'instrucao': '3ª Controladoria/TCM',
                    'ministerio_publico': 'Procurador Marcelo Fonseca Barros',
                    'relatoria': 'Conselheira Mara Lúcia',
                    'exercicio': '2005',
                }
            },
            {
                'request': """DECISÃO ADMINISTRATIVA Nº 1234/2023 Processo Administrativo: 2023.001.000123-4 Matéria: Prestação de Contas Anual Local: Belém Gestora: Secretaria Municipal de Finanças Partes Interessadas: 1) Maria Silva e Associados LTDA (CNPJ: 12.345.678/0001-90) 2) José Oliveira (CPF: 987.654.321-00) Representante Legal: Dra. Ana Paula Mendes (OAB/PA 15.673) Procurador de Contas: Dr. Carlos Eduardo Lima Setor Técnico: 2ª Inspetoria Relator: Conselheiro Roberto Alves Período de Referência: 2022 Data de Publicação: 15/03/2023""",
                'response': {
                    'categoria': 'Decisão Administrativa',
                    'numero': '1234/2023',
                    'processo': '2023.001.000123-4',
                    'assunto': 'Prestação de Contas Anual',
                    'municipio': 'Belém',
                    'orgao': 'Secretaria Municipal de Finanças',
                    'recorrentes': [
                        {
                            'nome': 'Maria Silva e Associados LTDA',
                            'cnpj': '12.345.678/0001-90'
                        },
                        {
                            'nome': 'José Oliveira',
                            'cpf': '987.654.321-00'
                        }
                    ],
                    'advogado': 'Dra. Ana Paula Mendes',
                    'instrucao': '2ª Inspetoria',
                    'ministerio_publico': 'Dr. Carlos Eduardo Lima',
                    'relatoria': 'Conselheiro Roberto Alves',
                    'exercicio': '2022',
                    'data_publicacao': '2023-03-15'
                }
            },
            {
                'request': """PARECER TÉCNICO Nº 456 Processo: 2022.456.000789-1 Objeto: Licitação Pública Comarca: Santarém Órgão Responsável: Departamento de Licitações Requerente: Empresa XYZ Ltda. (CNPJ: 98.765.432/0001-21) Período: 2021-2022 Promotoria: Dra. Fernanda Costa Juiz Relator: Dr. Marcos Aurélio""",
                'response': {
                    'categoria': 'Parecer Técnico',
                    'numero': '456',
                    'processo': '2022.456.000789-1',
                    'assunto': 'Licitação Pública',
                    'municipio': 'Santarém',
                    'orgao': 'Departamento de Licitações',
                    'recorrentes': [
                        {
                            'nome': 'Empresa XYZ Ltda.',
                            'cnpj': '98.765.432/0001-21'
                        }
                    ],
                    'ministerio_publico': 'Dra. Fernanda Costa',
                    'relatoria': 'Dr. Marcos Aurélio',
                    'exercicio': '2021-2022'
                }
            }
        ]
        return format_as_xml(examples)
    
    def model_setup(self) -> OpenAIModel:
        """
        Configura o modelo OpenAI compatível para uso com o backend local.
        
        Returns:
            OpenAIModel: Modelo configurado e pronto para uso
        """
        if self.backend == 'google':
            try:
                model = GeminiModel(
                    'gemini-2.0-flash',
                    provider=GoogleGLAProvider(api_key=os.getenv('GEMINI_API_KEY'))
                )
                return model
            except Exception as e:
                logger.error(f"Erro ao configurar modelo: {str(e)}")
                raise RuntimeError(f"Falha ao configurar modelo: {str(e)}")
        elif self.backend == 'openai':
            model = OpenAIModel(
                model_name=self.modelo,
                
            )
        return OpenAIModel(
            model_name=self.modelo,
            provider=OpenAIProvider(base_url=self.base_url),
            
        )

    def agent_setup(self, model: OpenAIModel, context_window: int = 4096) -> Agent:
        """
        Configura o agente com exemplos detalhados e instruções claras.
        """
        system_prompt = """
        Você é um especialista em extrair informações estruturadas de do Diário Oficial do Tribunal de Contas
        dos Municiípios do Pará.

        Sua tarefa é identificar e extrair informações mesmo quando os nomes dos campos variam.
        Por exemplo:
        - "Órgão" pode aparecer como "Unidade Gestora", "Gestora" ou "Secretaria"
        - "Ministério Público" pode aparecer como "Procurador de Contas" ou "Promotoria"
        - "Relatoria" pode aparecer como "Relator" ou "Juiz Relator"

        Considere que nem todos os campos estarão presentes em todos os documentos.
        Extraia apenas as informações que estiverem claramente presentes no texto.

        {examples}
        """.format(examples=self.set_examples())
        
        logfire.info('Starting Agent, {model}!', model=model.model_name)
        model_settings = None
        if self.backend not in ('google', 'openai'):
            model_settings = {
                "num_ctx": context_window,
                "temperature": 0.6
            }
        

        return Agent(
            model=model, # O modelo setado em self.model_setup
            result_type=Acordao, # O modelo para estruturar o resultado
            system_prompt=system_prompt,
            model_settings=model_settings,
            instrument=True # Instrumento de captura de eventos, no caso aqui o logfire da propria pydantic_ai
           
            
        )
    
    
    def run_agent(self, agent: Agent, texto: str, export_json = False) -> Dict[str, Any]:
        """
        Executa o agente de forma síncrona .
        
        Args:
            agent (Agent): Agente configurado
            texto (str): Texto a ser processado
            export_json (bool, optional): Exportar resultado em JSON
            
        Returns:
            DocumentoDiarioOficial: Resultado estruturado do processamento
        """
        try:
            logger.info(f'Starting Process...')
            response: AgentRunResult = agent.run_sync(user_prompt=texto)
            structured_response: Acordao = response.data
            json_response: str = structured_response.model_dump_json(indent=4)
            if export_json:
                with open('response.json', 'w') as f:
                    f.write(json_response)
            logger.success(f'Process finished successfully: {json_response}')
            return {
                'response': response,
                'structured_response': structured_response,
                'json_response': json_response
            }
        except UnexpectedModelBehavior:
            logger.error(f"Erro inesperado ao executar agente")
            return {}
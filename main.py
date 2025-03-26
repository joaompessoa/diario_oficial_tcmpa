from documents.diario import DiarioOficial
from documents.acordao import Acordao
from documents.diario_llm import LocalLlm

if __name__ == "__main__":
    # Create an instance of the DiarioOficial class
    # diario = DiarioOficial()
    # print(diario)
    texto = "ACÓRDÃO Nº 46.073 Processo nº 244012005-00 Assunto: Recurso de Reconsideração (Recurso Ordinário) Município: Castanhal Órgão: Secretaria Municipal de Transporte e Trânsito Recorrentes: João Sampaio de Oliveira (CPF: 083.957.212-10) (01/01 a 31/08/2005) e Waldir Nascimento Batista (CPF: 587.875.502-90) (01/09 a 31/12/2005) Procurador/Advogado(a): Elvis Ribeiro da Silva (OAB-PA 12.114) Instrução: 3ª Controladoria/TCM Ministério Público de Contas: Procurador Marcelo Fonseca Barros Relatoria: Conselheira Mara Lúcia Exercício: 2005 EMENTA: RECURSO DE RECONSIDERAÇÃO (RECURSO ORDINÁRIO). SECRETARIA MUNICIPAL DE TRANSPORTE E TRÂNSITO DE CASTANHAL. EXERCÍCIO DE 2005. NO PERÍODO DE RESPONSABILIDADE DO ORDENADOR JOÃO SAMPAIO DE OLIVEIRA, CONSTATOU-SE O NÃO ENCAMINHAMENTO DE PROCEDIMENTO LICITATÓRIO E NOTAS DE EMPENHO. INCIDÊNCIA DA PRESCRIÇÃO INTERCORRENTE NA PRETENSÃO SANCIONATÓRIA, NOS TERMOS DO ART. 78-I DA LEI COMPLEMENTAR ESTADUAL Nº. 109/2016. CONHECER DO RECURSO E DAR-LHE PROVIMENTO, REFORMANDO INTEGRALMENTE, A DECISÃO ANTERIORMENTE PROLATADA. NO PERÍODO DE RESPONSABILIDADE DO ORDENADOR WALDIR NASCIMENTO BATISTA, CONTAS JULGADAS REGULARES E NO PERÍODO DE RESPONSABILIDADE DO ORDENADOR JOÃO SAMPAIO DE OLIVEIRA, CONTAS JULGADAS REGULARES, COM RESSALVAS. EXPEDIÇÃO DE ALVARÁS DE QUITAÇÃO. Vistos, relatados e discutidos os presentes autos que tratam do RECURSO DE RECONSIDERAÇÃO/ORDINÁRIO, com amparo no art. 65 da Lei Complementar nº 25/1994, vigente à época, atualmente denominado de Recurso Ordinário (conforme art. 81, da LC nº. 109/2016)"

    local_llm = LocalLlm(
    texto=texto,
    modelo='llama3.1',
    backend='ollama'
)
    model = local_llm.model_setup()
    agent = local_llm.agent_setup(model=model)

    resposta = local_llm.run_agent(agent=agent, texto=texto)
    print(resposta)
    
    
# TODO
# Add a simetrie entre a classe DiarioOficial e as outras classes baseadas em documento
# A classe acordao por exemplo, pode iniciar DiarioOficial caso ela nao tenha sido iniciada
# TODO criar um front end


   
    
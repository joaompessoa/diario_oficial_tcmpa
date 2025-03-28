from documents.diario import DiarioOficial
from documents.acordao import Acordao
from documents.diario_llm import LocalLlm

if __name__ == "__main__":
   
    texto = "ACÓRDÃO Nº 46.835 Processo nº 108002.2023.2.000 Município: Água Azul do Norte Unidade Gestora: Câmara Municipal Exercício: 2023 Interessado(s): Jorge Luiz Barros Carneiro CPF Nº 299.748.102-30 Contador(a): José Soares da Silva Instrução: 1ª Controladoria Assunto: Prestação de Contas de Gestão MPCM/PA: Procurador Marcelo Fonseca de Barros Relatora: Conselheira Ann Pontes EMENTA: PRESTAÇÃO DE CONTAS DE GESTÃO. CÂMARA MUNICIPAL DE ÁGUA AZUL DO NORTE. EXERCÍCIO 2023. 1. AO FINAL DA INSTRUÇÃO PROCESSUAL RESTARAM AS SEGUINTES IMPROPRIEDADES: 1) 12 IRREGULARIDADES/IMPROPRIEDADES CONSTATADAS EM PROCESSOS LICITATÓRIOS ENCAMINHADOS NO MURAL DE LICITAÇÃO, 2) DESCUMPRIMENTO DA LEI DE ACESSO A INFORMAÇÃO. FALHAS DESSA NATUREZA NÃO COMPROMETEM A REGULARIDADE DAS CONTAS, MAS SUJEITAM O ORDENADOR À APLICAÇÃO DE MULTAS. 2. PELA REGULARIDADE COM RESSALVAS DAS CONTAS. MULTAS AO FUMREAP. ALVARÁ DE QUITAÇÃO. ACORDAM os Conselheiros do Tribunal de Contas dos Municípios do Estado do Pará, por votação unânime, em conformidade com a ata da sessão e nos termos do relatório e voto da Conselheira Relatora: DECISÃO: I. VOTAM nos termos do inciso II, do art. 45, da Lei Complementar Estadual nº. 109/2016, pela REGULARIDADE, COM RESSALVAS, das Contas da Câmara Municipal de Aguá Azul do Norte, exercício financeiro de 2023, de responsabilidade do Sr. Jorge Luiz Barros Carneiro, em favor do qual deverá ser expedido o Alvará de Quitação pelas despesas ordenadas, no valor de R$-4.363.913,99 (quatro milhões, trezentos e sessenta e três mil, novecentos e treze reais e noventa e nove centavos), SOMENTE após a comprovação do recolhimento, II. Ao FUMREAP/TCM/PA, instituído pela Lei nº. 7.368/2009, de 29/12/2009, no prazo de 30 (trinta) dias, conforme previsão do art. 695, caput, do RI/TCM/PA, do seguinte valor, a título de multa: 1) 600 UPF-PA, prevista no artigo 698, IV, “b”, do RI/TCM/PA, pelas irregularidades/impropriedades constatadas em processos licitatórios encaminhados no Mural de Licitação, descumprindo a IN nº. 022/2021-TCM/PA c/c a Lei de Licitações; 2) 300 UPF-PA, com fundamento no art. 698, inciso IV, alínea “b”, do RI/TCM-PA, pelo descumprimento da Lei de Acesso à Informação, onde ficou constatado que a Unidade Gestora em questão alcançou um percentual de atendimento de 80,19% das obrigações contidas na Matriz Única de atendimento, descumprindo a IN Nº. 011/2021/TCM-PA. III. Fique desde já CIENTE o Ordenador que o não recolhimento das multas aplicadas, na forma e no prazo fixados, após o trânsito em julgado da presente decisão, resultará nos acréscimos decorrentes de mora, nos termos do art. 703, incisos I a III, do RI/ TCM/PA e, ainda, no caso de não atendimento de referidas determinações, fica à Secretaria-Geral/TCM/PA autorizada a proceder com os trâmites necessários para o efetivo protesto e execução do título, na forma regimental 4ª Sessão Virtual do Tribunal de Contas dos Municípios do Estado do Pará de 10 a 14 de março de 2025. Download Anexo - Relatório e Voto do Relator"

    local_llm = LocalLlm(
        texto=texto,
        modelo='qwen2.5-coder:7b',
        backend='ollama'
    )
    model = local_llm.model_setup()
    agent = local_llm.agent_setup(model=model)

    resposta = local_llm.run_agent(agent=agent, texto=texto, export_json=True)
    print(resposta)
    
    
# TODO
# Add a simetrie entre a classe DiarioOficial e as outras classes baseadas em documento
# A classe acordao por exemplo, pode iniciar DiarioOficial caso ela nao tenha sido iniciada
# TODO criar um front end


   
    
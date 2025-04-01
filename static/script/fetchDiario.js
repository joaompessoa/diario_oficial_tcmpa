document.addEventListener('DOMContentLoaded', () => {
    // Definir a data máxima como o dia atual
    const today = new Date();
    const formattedDate = today.toISOString().split('T')[0];
    const dataInput = document.getElementById('dataConsulta');
    if (dataInput) {
        dataInput.value = formattedDate;
    }

    // Função para mostrar mensagem de status
    function showStatusMessage(message, isError = false) {
        const statusElement = document.getElementById('statusMessage');
        statusElement.textContent = message;
        statusElement.className = 'status-message';
        statusElement.classList.add(isError ? 'status-error' : 'status-success');
        statusElement.style.display = 'block';
    }

    // Função para limpar mensagem de status
    function clearStatusMessage() {
        const statusElement = document.getElementById('statusMessage');
        statusElement.style.display = 'none';
    }

    // Função para mostrar/esconder o spinner de carregamento
    function toggleLoading(show) {
        document.getElementById('loadingSpinner').style.display = show ? 'block' : 'none';
    }

    // Função para consultar o Diário Oficial
    async function consultarDiario(data) {
        try {
            clearStatusMessage();
            toggleLoading(true);

            // Esconder containers de documentos
            document.getElementById('acordaosContainer').style.display = 'none';
            document.getElementById('resolucoesContainer').style.display = 'none';

            // Extrair dia, mês e ano da data
            const [ano, mes, dia] = data.split('-');

            // Construir URL da API
            const apiUrl = `/api/diario?dia=${dia}&mes=${mes}&ano=${ano}`;

            // Fazer a requisição à API
            const response = await fetch(apiUrl);
            const diarioData = await response.json();

            if (!response.ok) {
                throw new Error(diarioData.detail || 'Erro ao consultar o Diário Oficial');
            }

            // Verificar se o diário foi encontrado
            if (diarioData.encontrado) {
                // Exibir informações do diário
                document.getElementById('resultadoDiario').style.display = 'block';
                const infoContainer = document.getElementById('diarioInfo');
                infoContainer.innerHTML = `
                    <p><strong>Data de Publicação:</strong> ${diarioData.publicacao}</p>
                    ${diarioData.numero_diario ? `<p><strong>Número do Diário:</strong> ${diarioData.numero_diario}</p>` : ''}
                    <p><strong>Status:</strong> <span style="color: var(--success-color);">Disponível</span></p>
                `;

                // Configurar botão de download
                const downloadBtn = document.getElementById('downloadBtn');
                downloadBtn.style.display = 'block';
                downloadBtn.onclick = () => {
                    window.open(diarioData.pdf_url, '_blank');
                };

                // Configurar botões para acórdãos e resoluções
                const acordaosBtn = document.getElementById('acordaosBtn');
                acordaosBtn.style.display = 'block';
                acordaosBtn.onclick = () => consultarAcordaos(dia, mes, ano);

                const resolucoesBtn = document.getElementById('resolucoesBtn');
                resolucoesBtn.style.display = 'block';
                resolucoesBtn.onclick = () => consultarResolucoes(dia, mes, ano);

                showStatusMessage(diarioData.mensagem || 'Diário Oficial encontrado com sucesso!', false);
            } else {
                document.getElementById('resultadoDiario').style.display = 'none';
                document.getElementById('acordaosBtn').style.display = 'none';
                document.getElementById('resolucoesBtn').style.display = 'none';
                showStatusMessage(diarioData.mensagem || 'Diário Oficial não encontrado para a data selecionada.', true);
            }
        } catch (error) {
            console.error('Erro ao consultar diário:', error);
            document.getElementById('resultadoDiario').style.display = 'none';
            document.getElementById('acordaosBtn').style.display = 'none';
            document.getElementById('resolucoesBtn').style.display = 'none';
            showStatusMessage(error.message || 'Erro ao consultar o Diário Oficial. Verifique a data e tente novamente.', true);
        } finally {
            toggleLoading(false);
        }
    }

    // Função para consultar acórdãos
    async function consultarAcordaos(dia, mes, ano) {
        try {
            // Mostrar loading e mensagem de status
            document.getElementById('acordaosLoading').style.display = 'block';
            document.getElementById('acordaosStatusMessage').style.display = 'none';
            document.getElementById('acordaosContainer').style.display = 'block';
            document.getElementById('resolucoesContainer').style.display = 'none';

            // Limpar lista anterior
            document.getElementById('acordaosList').innerHTML = '';

            // Construir URL da API
            const apiUrl = `/api/diario/acordaos?dia=${dia}&mes=${mes}&ano=${ano}`;

            // Fazer a requisição à API
            const response = await fetch(apiUrl);
            const data = await response.json();

            // Esconder loading
            document.getElementById('acordaosLoading').style.display = 'none';

            if (data.status === 'error') {
                // Mostrar mensagem de erro
                const statusEl = document.getElementById('acordaosStatusMessage');
                statusEl.textContent = data.mensagem || 'Erro ao consultar acórdãos.';
                statusEl.className = 'status-message status-error';
                statusEl.style.display = 'block';
                return;
            }

            const acordaosList = document.getElementById('acordaosList');

            // Verificar se há acórdãos
            if (!data.acordaos || data.acordaos.length === 0) {
                acordaosList.innerHTML = '<div class="empty-message">Nenhum acórdão encontrado para esta data.</div>';
                return;
            }

            // Renderizar lista de acórdãos
            acordaosList.innerHTML = '';
            data.acordaos.forEach(acordao => {
                const card = document.createElement('div');
                card.className = 'document-card';

                const header = document.createElement('div');
                header.className = 'document-header';

                const title = document.createElement('div');
                title.className = 'document-title';
                title.textContent = `Acórdão Nº ${acordao.numero || 'N/A'}`;

                header.appendChild(title);
                card.appendChild(header);

                const content = document.createElement('div');
                content.className = 'document-content';

                // Adicionar campos relevantes
                const campos = [
                    { label: 'Processo', valor: acordao.processo },
                    { label: 'Sessão', valor: acordao.sessao },
                    { label: 'Município', valor: acordao.municipio },
                    { label: 'Interessado', valor: acordao.interessado },
                    { label: 'Relator', valor: acordao.relator },
                    { label: 'Assunto', valor: acordao.assunto }
                ];

                campos.forEach(campo => {
                    if (campo.valor) {
                        const field = document.createElement('div');
                        field.className = 'document-field';
                        field.innerHTML = `<strong>${campo.label}:</strong> ${campo.valor}`;
                        content.appendChild(field);
                    }
                });

                card.appendChild(content);
                acordaosList.appendChild(card);
            });

        } catch (error) {
            console.error('Erro ao consultar acórdãos:', error);
            const statusEl = document.getElementById('acordaosStatusMessage');
            statusEl.textContent = error.message || 'Erro ao consultar acórdãos.';
            statusEl.className = 'status-message status-error';
            statusEl.style.display = 'block';
            document.getElementById('acordaosLoading').style.display = 'none';
        }
    }

    // Função para consultar resoluções
    async function consultarResolucoes(dia, mes, ano) {
        try {
            // Mostrar loading e mensagem de status
            document.getElementById('resolucoesLoading').style.display = 'block';
            document.getElementById('resolucoesStatusMessage').style.display = 'none';
            document.getElementById('resolucoesContainer').style.display = 'block';
            document.getElementById('acordaosContainer').style.display = 'none';

            // Limpar lista anterior
            document.getElementById('resolucoesList').innerHTML = '';

            // Construir URL da API
            const apiUrl = `/api/diario/resolucoes?dia=${dia}&mes=${mes}&ano=${ano}`;

            // Fazer a requisição à API
            const response = await fetch(apiUrl);
            const data = await response.json();

            // Esconder loading
            document.getElementById('resolucoesLoading').style.display = 'none';

            if (data.status === 'error') {
                // Mostrar mensagem de erro
                const statusEl = document.getElementById('resolucoesStatusMessage');
                statusEl.textContent = data.mensagem || 'Erro ao consultar resoluções.';
                statusEl.className = 'status-message status-error';
                statusEl.style.display = 'block';
                return;
            }

            const resolucoesList = document.getElementById('resolucoesList');

            // Verificar se há resoluções
            if (!data.resolucoes || data.resolucoes.length === 0) {
                resolucoesList.innerHTML = '<div class="empty-message">Nenhuma resolução encontrada para esta data.</div>';
                return;
            }

            // Renderizar lista de resoluções
            resolucoesList.innerHTML = '';
            data.resolucoes.forEach(resolucao => {
                const card = document.createElement('div');
                card.className = 'document-card';

                const header = document.createElement('div');
                header.className = 'document-header';

                const title = document.createElement('div');
                title.className = 'document-title';
                title.textContent = `Resolução Nº ${resolucao.numero || 'N/A'}`;

                header.appendChild(title);
                card.appendChild(header);

                const content = document.createElement('div');
                content.className = 'document-content';

                // Adicionar campos relevantes
                const campos = [
                    { label: 'Processo', valor: resolucao.processo },
                    { label: 'Sessão', valor: resolucao.sessao },
                    { label: 'Município', valor: resolucao.municipio },
                    { label: 'Interessado', valor: resolucao.interessado },
                    { label: 'Relator', valor: resolucao.relator },
                    { label: 'Assunto', valor: resolucao.assunto }
                ];

                campos.forEach(campo => {
                    if (campo.valor) {
                        const field = document.createElement('div');
                        field.className = 'document-field';
                        field.innerHTML = `<strong>${campo.label}:</strong> ${campo.valor}`;
                        content.appendChild(field);
                    }
                });

                card.appendChild(content);
                resolucoesList.appendChild(card);
            });

        } catch (error) {
            console.error('Erro ao consultar resoluções:', error);
            const statusEl = document.getElementById('resolucoesStatusMessage');
            statusEl.textContent = error.message || 'Erro ao consultar resoluções.';
            statusEl.className = 'status-message status-error';
            statusEl.style.display = 'block';
            document.getElementById('resolucoesLoading').style.display = 'none';
        }
    }

    // Event listener para o formulário
    const form = document.getElementById('diarioForm');
    form.addEventListener('submit', function (event) {
        event.preventDefault();
        const dataConsulta = dataInput.value;

        if (!dataConsulta) {
            showStatusMessage('Por favor, selecione uma data válida.', true);
            return;
        }

        // Verificar se a data é futura
        const selectedDate = new Date(dataConsulta);
        if (selectedDate > today) {
            showStatusMessage('Não é possível consultar diários de datas futuras.', true);
            return;
        }

        consultarDiario(dataConsulta);
    });

    // Event listener para o botão de reset
    form.addEventListener('reset', function () {
        clearStatusMessage();
        document.getElementById('resultadoDiario').style.display = 'none';
        document.getElementById('acordaosContainer').style.display = 'none';
        document.getElementById('resolucoesContainer').style.display = 'none';
        dataInput.value = formattedDate;
    });
});
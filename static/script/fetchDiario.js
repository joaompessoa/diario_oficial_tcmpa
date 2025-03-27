// Definir a data máxima como o dia atual
const today = new Date();
const formattedDate = today.toISOString().split('T')[0];
document.getElementById('dataConsulta').setAttribute('max', formattedDate);

// Definir a data padrão como o dia atual
document.getElementById('dataConsulta').value = formattedDate;

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

            showStatusMessage(diarioData.mensagem || 'Diário Oficial encontrado com sucesso!', false);
        } else {
            document.getElementById('resultadoDiario').style.display = 'none';
            showStatusMessage(diarioData.mensagem || 'Diário Oficial não encontrado para a data selecionada.', true);
        }
    } catch (error) {
        console.error('Erro ao consultar diário:', error);
        document.getElementById('resultadoDiario').style.display = 'none';
        showStatusMessage(error.message || 'Erro ao consultar o Diário Oficial. Verifique a data e tente novamente.', true);
    } finally {
        toggleLoading(false);
    }
}

// Event listener para o formulário
document.getElementById('diarioForm').addEventListener('submit', function (event) {
    event.preventDefault();
    const dataConsulta = document.getElementById('dataConsulta').value;

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
document.getElementById('diarioForm').addEventListener('reset', function () {
    clearStatusMessage();
    document.getElementById('resultadoDiario').style.display = 'none';
    document.getElementById('dataConsulta').value = formattedDate;
});
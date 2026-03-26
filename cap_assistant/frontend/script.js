// Mesma origem que a página (API servida pelo mesmo FastAPI — qualquer porta, ex.: 8765)
const API_BASE_URL = window.location.origin;

// Elementos DOM
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const toastContainer = document.getElementById('toast-container');
const welcomeMessage = document.getElementById('welcome-message');

// Debug: verificar se os elementos foram encontrados
console.log('chatMessages:', chatMessages);
console.log('welcomeMessage:', welcomeMessage);

// Estado da aplicação
let conversationHistory = [];
let currentTheme = 'dark'; // Tema padrão
let currentChatId = null;
let chatHistory = []; // Array de conversas salvas
let sidebarCollapsed = false; // Estado da sidebar

// Inicialização
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    setupEventListeners();
    loadTheme();
});

async function autoSendSessionPromptIfAvailable() {
    try {
        const r = await fetch(`${API_BASE_URL}/session_summary`);
        if (!r.ok) return;
        const data = await r.json();
        if (!data || !data.available || !data.summary) return;

        // Evita duplicar em recarregamentos
        if (sessionStorage.getItem('capvivo-auto-prompt-sent') === '1') return;
        sessionStorage.setItem('capvivo-auto-prompt-sent', '1');

        const prompt = buildSessionPrompt(data.summary);
        await sendMessageText(prompt);
    } catch (e) {
        console.warn('autoSendSessionPromptIfAvailable failed', e);
    }
}

function _fmtSeconds(s) {
    const n = Number(s || 0);
    if (!isFinite(n) || n <= 0) return '0s';
    if (n < 60) return `${n.toFixed(0)}s`;
    const m = Math.floor(n / 60);
    const rs = Math.round(n % 60);
    return `${m}m ${rs}s`;
}

function buildSessionPrompt(summary) {
    const mood = summary.mood_seconds || {};
    const depth = summary.depth_seconds || {};
    const screens = summary.screen_seconds || {};
    const look = summary.look_product_seconds || {};

    const screensList = Object.entries(screens)
        .filter(([, v]) => Number(v) > 0.2)
        .sort((a, b) => Number(b[1]) - Number(a[1]))
        .map(([k, v]) => `- ${k}: ${_fmtSeconds(v)}`)
        .join('\n') || '- (sem dados)';

    const moodList = Object.entries(mood)
        .filter(([, v]) => Number(v) > 0.1)
        .sort((a, b) => Number(b[1]) - Number(a[1]))
        .map(([k, v]) => `- ${k}: ${_fmtSeconds(v)}`)
        .join('\n') || '- (sem dados)';

    const depthList = Object.entries(depth)
        .filter(([, v]) => Number(v) > 0.1)
        .sort((a, b) => Number(b[1]) - Number(a[1]))
        .map(([k, v]) => `- ${k}: ${_fmtSeconds(v)}`)
        .join('\n') || '- (sem dados)';

    const lookList = Object.entries(look)
        .map(([k, obj]) => {
            const sec = obj && typeof obj === 'object' ? obj.seconds : obj;
            const label = obj && typeof obj === 'object' && obj.label ? obj.label : k;
            return [label, sec];
        })
        .filter(([, v]) => Number(v) > 0.15)
        .sort((a, b) => Number(b[1]) - Number(a[1]))
        .slice(0, 10)
        .map(([label, v]) => `- ${label}: ${_fmtSeconds(v)}`)
        .join('\n') || '- (sem dados)';

    const cart = Array.isArray(summary.cart_product_ids) ? summary.cart_product_ids : [];
    const cartTxt = cart.length ? cart.map(x => `- ${x}`).join('\n') : '- (vazio)';

    return [
        'Contexto da sessão do cliente (dados coletados na loja):',
        '',
        '1) Tempo por seção visitada:',
        screensList,
        '',
        '2) Tempo por expressão (aproximação):',
        moodList,
        '',
        '3) Tempo por distância da câmera (aproximação):',
        depthList,
        '',
        '4) Tempo olhando para produtos (Novidades):',
        lookList,
        '',
        '5) Itens no carrinho ao final:',
        cartTxt,
        '',
        'IMPORTANTE (formato da resposta):',
        '- TEM QUE SER CURTO. Não escreva parágrafos grandes.',
        '- Use no máximo 10 linhas no total.',
        '- Cada linha com no máximo 1 frase.',
        '- Se precisar justificar, faça em 1 frase curta logo abaixo do item.',
        '',
        'Com base nisso, responda exatamente aos itens abaixo:',
        '- Qual a porcentagem de chance da pessoa voltar na loja?',
        '- Qual tipo de produto que ele tem mais chance de comprar?',
        '- Qual produto o cliente mais gostaria de comprar?',
        '- Quais as 3 próximas ações que o vendedor deveria tomar agora (ex.: se aproximar, esperar, oferecer um produto específico), e por quê?',
    ].join('\n');
}

function initializeApp() {
    // Carregar histórico de conversas do localStorage
    loadChatHistory();
    
    // Carregar estado da sidebar
    loadSidebarState();
    
    // Verificar se é a primeira vez que o usuário abre a IA
    const hasUsedBefore = localStorage.getItem('capbot-has-used');
    console.log('hasUsedBefore:', hasUsedBefore);
    
    // Ao abrir, envia automaticamente um prompt com dados coletados (se disponível).
    // Caso não exista resumo de sessão, não bloqueia e não mostra menu inicial.
    chatMessages.innerHTML = '';
    hideWelcomeMessage();
    autoSendSessionPromptIfAvailable();
}

function loadSidebarState() {
    const saved = localStorage.getItem('capbot-sidebar-collapsed');
    if (saved === 'true') {
        sidebarCollapsed = true;
        const sidebar = document.querySelector('.sidebar');
        const expandBtn = document.getElementById('sidebar-expand-btn');
        sidebar.classList.add('collapsed');
        expandBtn.classList.add('show');
    }
}

function setupEventListeners() {
    // Envio de mensagem
    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keydown', handleKeyDown);
    
    // Auto-resize do input
    userInput.addEventListener('input', autoResizeInput);
}

function loadConversationHistory() {
    conversationHistory.forEach(msg => {
        addMessage(msg.role, msg.content, msg.sources, false);
    });
}

// Funções para gerenciar histórico de conversas
function generateChatTitle(messages) {
    // Pega a primeira mensagem do usuário para gerar o título
    const firstUserMessage = messages.find(msg => msg.role === 'user');
    if (firstUserMessage) {
        const title = firstUserMessage.content.substring(0, 50);
        return title.length < firstUserMessage.content.length ? title + '...' : title;
    }
    return 'Nova Conversa';
}

function startNewChat() {
    // Salvar a conversa atual se houver mensagens
    if (conversationHistory.length > 0) {
        saveCurrentChat();
    }
    
    // Limpar a conversa atual
    conversationHistory = [];
    currentChatId = null;
    chatMessages.innerHTML = '';
    
    // Sem tela de boas-vindas com sugestões. Começa em branco.
    hideWelcomeMessage();
    
    // Atualizar a lista de conversas
    updateChatList();
}

function saveCurrentChat() {
    if (conversationHistory.length === 0) return;
    
    const chatId = currentChatId || Date.now().toString();
    const title = generateChatTitle(conversationHistory);
    const timestamp = new Date().toISOString();
    
    const chatData = {
        id: chatId,
        title: title,
        messages: [...conversationHistory],
        timestamp: timestamp
    };
    
    // Remover conversa existente se já existe
    chatHistory = chatHistory.filter(chat => chat.id !== chatId);
    
    // Adicionar nova conversa no início da lista
    chatHistory.unshift(chatData);
    
    // Manter apenas as últimas 20 conversas
    if (chatHistory.length > 20) {
        chatHistory = chatHistory.slice(0, 20);
    }
    
    // Salvar no localStorage
    localStorage.setItem('capbot-chat-history', JSON.stringify(chatHistory));
    
    currentChatId = chatId;
}

function loadChat(chatId) {
    const chat = chatHistory.find(c => c.id === chatId);
    if (!chat) return;
    
    // Salvar conversa atual se necessário
    if (conversationHistory.length > 0 && currentChatId !== chatId) {
        saveCurrentChat();
    }
    
    // Carregar a conversa selecionada
    currentChatId = chatId;
    conversationHistory = [...chat.messages];
    
    // Limpar e recarregar mensagens
    chatMessages.innerHTML = '';
    loadConversationHistory();
    
    // Atualizar a lista de conversas
    updateChatList();
}

function loadChatHistory() {
    const saved = localStorage.getItem('capbot-chat-history');
    if (saved) {
        try {
            chatHistory = JSON.parse(saved);
        } catch (error) {
            console.error('Erro ao carregar histórico de conversas:', error);
            chatHistory = [];
        }
    }
}

function updateChatList() {
    const chatList = document.getElementById('chat-list');
    chatList.innerHTML = '';
    
    chatHistory.forEach(chat => {
        const chatItem = document.createElement('div');
        chatItem.classList.add('chat-item');
        if (chat.id === currentChatId) {
            chatItem.classList.add('active');
        }
        
        const date = new Date(chat.timestamp).toLocaleDateString('pt-BR', {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        chatItem.innerHTML = `
            <div class="chat-item-title">${chat.title}</div>
            <div class="chat-item-date">${date}</div>
            <div class="chat-item-actions">
                <button class="chat-delete-btn" onclick="deleteChat('${chat.id}', event)">×</button>
            </div>
        `;
        
        chatItem.addEventListener('click', (e) => {
            if (!e.target.classList.contains('chat-delete-btn')) {
                loadChat(chat.id);
            }
        });
        
        chatList.appendChild(chatItem);
    });
}

// Funções da tela de boas-vindas
function showWelcomeMessage() {
    console.log('showWelcomeMessage called');
    console.log('welcomeMessage element:', welcomeMessage);
    
    // Limpar mensagens existentes
    chatMessages.innerHTML = '';
    
    // Criar mensagem de boas-vindas centralizada
    const welcomeContainer = document.createElement('div');
    welcomeContainer.style.cssText = `
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 60vh;
        width: 100%;
    `;
    
    welcomeContainer.innerHTML = `
        <div style="max-width: 700px; width: 100%; margin: 0 auto;">
            <div style="text-align: center; padding: 2.5rem; max-width: 600px; margin: 0 auto;">
                    <h2 style="font-size: 2rem; margin-bottom: 1rem; color: var(--text-primary);">Bem-vindo à CapBot</h2>
                    <p style="font-size: 1.2rem; margin-bottom: 2rem; color: var(--text-secondary);">Sua assistente de análise financeira da Capgemini</p>
                    
                    <h4 style="margin-bottom: 1.5rem; color: var(--text-primary);">Comece com uma dessas perguntas:</h4>
                    
                    <div style="display: flex; flex-direction: row; gap: 1rem; justify-content: center; align-items: stretch; max-width: 800px; margin: 0 auto;">
                        <div onclick="sendSuggestion('Me fale a receita de um bolo de chocolate')" style="
                            background: var(--bg-tertiary);
                            border: 2px solid var(--border-color);
                            border-radius: 12px;
                            padding: 1.2rem;
                            cursor: pointer;
                            transition: all 0.3s ease;
                            flex: 1;
                            min-width: 180px;
                            max-width: 200px;
                            text-align: center;
                        " onmouseover="this.style.borderColor='var(--accent-primary)'; this.style.transform='translateY(-3px)'; this.style.boxShadow='0 8px 25px rgba(0,0,0,0.15)'" onmouseout="this.style.borderColor='var(--border-color)'; this.style.transform='translateY(0)'; this.style.boxShadow='none'">
                            <div style="font-size: 2rem; margin-bottom: 0.8rem;">🍰</div>
                            <h5 style="margin-bottom: 0.5rem; color: var(--accent-primary); font-size: 1rem; font-weight: 600;">Receita de Bolo</h5>
                            <p style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.4;">Me fale a receita de um bolo de chocolate</p>
                        </div>
                        
                        <div onclick="sendSuggestion('Por que o céu é azul?')" style="
                            background: var(--bg-tertiary);
                            border: 2px solid var(--border-color);
                            border-radius: 12px;
                            padding: 1.2rem;
                            cursor: pointer;
                            transition: all 0.3s ease;
                            flex: 1;
                            min-width: 180px;
                            max-width: 200px;
                            text-align: center;
                        " onmouseover="this.style.borderColor='var(--accent-primary)'; this.style.transform='translateY(-3px)'; this.style.boxShadow='0 8px 25px rgba(0,0,0,0.15)'" onmouseout="this.style.borderColor='var(--border-color)'; this.style.transform='translateY(0)'; this.style.boxShadow='none'">
                            <div style="font-size: 2rem; margin-bottom: 0.8rem;">🌌</div>
                            <h5 style="margin-bottom: 0.5rem; color: var(--accent-primary); font-size: 1rem; font-weight: 600;">Pergunta Científica</h5>
                            <p style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.4;">Por que o céu é azul?</p>
                        </div>
                        
                        <div onclick="sendSuggestion('Conte uma piada sobre programação')" style="
                            background: var(--bg-tertiary);
                            border: 2px solid var(--border-color);
                            border-radius: 12px;
                            padding: 1.2rem;
                            cursor: pointer;
                            transition: all 0.3s ease;
                            flex: 1;
                            min-width: 180px;
                            max-width: 200px;
                            text-align: center;
                        " onmouseover="this.style.borderColor='var(--accent-primary)'; this.style.transform='translateY(-3px)'; this.style.boxShadow='0 8px 25px rgba(0,0,0,0.15)'" onmouseout="this.style.borderColor='var(--border-color)'; this.style.transform='translateY(0)'; this.style.boxShadow='none'">
                            <div style="font-size: 2rem; margin-bottom: 0.8rem;">😄</div>
                            <h5 style="margin-bottom: 0.5rem; color: var(--accent-primary); font-size: 1rem; font-weight: 600;">Piada</h5>
                            <p style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.4;">Conte uma piada sobre programação</p>
                        </div>
                    </div>
            </div>
        </div>
    `;
    
    chatMessages.appendChild(welcomeContainer);
    console.log('Welcome message created and shown');
}

function hideWelcomeMessage() {
    // Esconder apenas a mensagem de boas-vindas, não limpar todo o chat
    const allElements = chatMessages.children;
    for (let i = allElements.length - 1; i >= 0; i--) {
        const element = allElements[i];
        if (element.innerHTML.includes('Bem-vindo à CapBot') || 
            element.innerHTML.includes('Comece com uma dessas perguntas')) {
            element.remove();
            console.log('Welcome message element removed');
        }
    }
    console.log('Welcome message hidden');
    // Marcar que o usuário já usou a IA
    localStorage.setItem('capbot-has-used', 'true');
}

function sendSuggestion(suggestionText) {
    // Esconder a mensagem de boas-vindas
    hideWelcomeMessage();
    
    // Enviar a sugestão como mensagem (sem iniciar nova conversa)
    userInput.value = suggestionText;
    sendMessage();
}

// Função para forçar a mensagem de boas-vindas (para debug)
function forceWelcomeMessage() {
    localStorage.removeItem('capbot-has-used');
    hideWelcomeMessage();
}

// Função de teste para forçar exibição
function testWelcomeMessage() {
    console.log('Testing welcome message...');
    hideWelcomeMessage();
}

// Função de fallback com alert
function showWelcomeAlert() {
    const suggestions = [
        'Quanto recebi de salário líquido em maio de 2025? (Ana Souza)',
        'Qual foi o total líquido pago no primeiro trimestre de 2025?',
        'Quem recebeu o maior bônus em 2025?'
    ];
    
    const choice = confirm('Bem-vindo à CapBot!\n\nEscolha uma sugestão:\n\n1. Salário Líquido\n2. Total Trimestral\n3. Maior Bônus\n\nClique OK para a primeira opção, Cancel para cancelar.');
    
    if (choice) {
        userInput.value = suggestions[0];
        sendMessage();
    }
}

function deleteChat(chatId, event) {
    event.stopPropagation();
    
    if (confirm('Tem certeza que deseja excluir esta conversa?')) {
        chatHistory = chatHistory.filter(chat => chat.id !== chatId);
        localStorage.setItem('capbot-chat-history', JSON.stringify(chatHistory));
        
        // Se a conversa excluída era a atual, iniciar uma nova
        if (currentChatId === chatId) {
            startNewChat();
        } else {
            updateChatList();
        }
        
        showToast('Conversa excluída!', 'info');
    }
}

// Função para toggle da sidebar
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const expandBtn = document.getElementById('sidebar-expand-btn');
    
    sidebarCollapsed = !sidebarCollapsed;
    
    if (sidebarCollapsed) {
        sidebar.classList.add('collapsed');
        expandBtn.classList.add('show');
    } else {
        sidebar.classList.remove('collapsed');
        expandBtn.classList.remove('show');
    }
    
    // Salvar preferência no localStorage
    localStorage.setItem('capbot-sidebar-collapsed', sidebarCollapsed.toString());
}

function addMessage(role, content, sources = null, save = true) {
    const messageContainer = document.createElement('div');
    messageContainer.classList.add('message-container', role);

    const avatar = document.createElement('div');
    avatar.classList.add('message-avatar');
    
    if (role === 'user') {
        avatar.textContent = 'Você';
    } else {
        // Usar imagem da Capgemini como avatar para IA
        avatar.innerHTML = '<img src="logo_capvivo.png?v=2" alt="CapBot" style="width: 100%; height: 100%; object-fit: contain; border-radius: 50%; display: block;">';
        
        // Debug: verificar se a imagem carregou
        const avatarImg = avatar.querySelector('img');
        if (avatarImg) {
            avatarImg.onload = () => {
                console.log('Avatar image loaded successfully');
                console.log('Image src:', avatarImg.src);
            };
            avatarImg.onerror = () => {
                console.log('Avatar image failed to load');
                console.log('Trying to load:', avatarImg.src);
                // Fallback para texto se a imagem não carregar
                avatar.innerHTML = 'CB';
            };
        }
    }

    const messageBubble = document.createElement('div');
    messageBubble.classList.add('message-bubble');
    
    // Adicionar "CapBot" no início das mensagens da IA
    if (role === 'assistant' || role === 'ai') {
        console.log('Adding CapBot header for role:', role);
        const capbotHeader = document.createElement('div');
        capbotHeader.classList.add('capbot-header');
        capbotHeader.textContent = 'Assistente';
        messageBubble.appendChild(capbotHeader);
    }
    
    const contentDiv = document.createElement('div');
    contentDiv.innerHTML = formatMessageContent(content, sources);
    messageBubble.appendChild(contentDiv);

    if (role === 'user') {
        messageContainer.appendChild(messageBubble);
        messageContainer.appendChild(avatar);
    } else {
        messageContainer.appendChild(avatar);
        messageContainer.appendChild(messageBubble);
    }

    chatMessages.appendChild(messageContainer);
    
    if (save) {
        conversationHistory.push({ role, content, sources });
        saveConversationHistory();
        
        // Salvar a conversa automaticamente após adicionar mensagem
        if (role === 'user' && conversationHistory.length > 1) {
            saveCurrentChat();
            updateChatList();
        }
    }
    
    scrollToBottom();
}

function formatMessageContent(content, sources) {
    let formattedContent = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>'); // Bold
    formattedContent = formattedContent.replace(/\*(.*?)\*/g, '<em>$1</em>'); // Italic

    if (sources && sources.length > 0) {
        formattedContent += '<p><strong>Fontes:</strong></p><ul>';
        sources.forEach(source => {
            formattedContent += `<li>${source}</li>`;
        });
        formattedContent += '</ul>';
    }
    return formattedContent;
}

function showLoading() {
    const loadingIndicator = document.createElement('div');
    loadingIndicator.classList.add('loading-indicator');
    loadingIndicator.id = 'loading-indicator';
    loadingIndicator.innerHTML = `
        <div class="loading-dots">
            <div class="loading-dot"></div>
            <div class="loading-dot"></div>
            <div class="loading-dot"></div>
        </div>
    `;
    chatMessages.appendChild(loadingIndicator);
    scrollToBottom();
}

function hideLoading() {
    const loadingIndicator = document.getElementById('loading-indicator');
    if (loadingIndicator) {
        loadingIndicator.remove();
    }
}

async function sendMessage() {
    const message = userInput.value.trim();
    if (message === '') return;

    // Esconder a mensagem de boas-vindas se estiver visível
    hideWelcomeMessage();

    addMessage('user', message);
    userInput.value = ''; // Limpa o input imediatamente
    autoResizeInput();

    showLoading();

    try {
        // Preparar dados
        const requestData = {
            message: message,
            conversation_history: conversationHistory.map(msg => ({
                role: msg.role,
                content: msg.content,
                timestamp: new Date().toISOString()
            }))
        };
        
        console.log('Enviando dados:', requestData);
        
        // Enviar para API
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        });
        
        console.log('Status da resposta:', response.status);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Erro da API:', errorText);
            throw new Error(`Erro HTTP: ${response.status} - ${errorText}`);
        }
        
        const data = await response.json();
        addMessage('assistant', data.message, data.sources);

    } catch (error) {
        console.error('Erro ao conectar com a API:', error);
        showToast('Erro ao conectar com a API. Verifique se o servidor está rodando.', 'error');
        addMessage('assistant', 'Desculpe, não consegui me conectar ao servidor. Por favor, tente novamente mais tarde.');
    } finally {
        hideLoading();
    }
}

async function sendMessageText(message) {
    if (!message || !message.trim()) return;

    hideWelcomeMessage();
    addMessage('user', message);
    showLoading();

    try {
        const requestData = {
            message: message,
            conversation_history: conversationHistory.map(msg => ({
                role: msg.role,
                content: msg.content,
                timestamp: new Date().toISOString()
            }))
        };

        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Erro HTTP: ${response.status} - ${errorText}`);
        }

        const data = await response.json();
        addMessage('assistant', data.message, data.sources);
    } catch (error) {
        console.error('Erro ao conectar com a API:', error);
        showToast('Erro ao conectar com a API. Verifique se o servidor está rodando.', 'error');
        addMessage('assistant', 'Desculpe, não consegui me conectar ao servidor. Por favor, tente novamente mais tarde.');
    } finally {
        hideLoading();
    }
}

function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function autoResizeInput() {
    userInput.style.height = 'auto';
    userInput.style.height = Math.min(userInput.scrollHeight, 120) + 'px';
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.classList.add('toast', type);
    toast.textContent = message;
    toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('show');
    }, 10);

    setTimeout(() => {
        toast.classList.remove('show');
        toast.addEventListener('transitionend', () => toast.remove());
    }, 3000);
}

function clearChat() {
    if (confirm('Tem certeza que deseja iniciar uma nova conversa? O histórico atual será perdido.')) {
        startNewChat();
        showToast('Conversa limpa!', 'info');
    }
}

function confirmClearAllChats() {
    if (confirm('Tem certeza que deseja limpar TODAS as conversas salvas? Esta ação é irreversível.')) {
        chatHistory = [];
        localStorage.removeItem('capbot-chat-history');
        startNewChat();
        showToast('Todos os chats foram limpos!', 'info');
    }
}

function downloadChat() {
    const chatData = {
        timestamp: new Date().toISOString(),
        messages: conversationHistory
    };
    const filename = `capbot_chat_${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
    const jsonStr = JSON.stringify(chatData, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('Conversa baixada com sucesso!', 'info');
}

function saveConversationHistory() {
    localStorage.setItem('capbot-conversation', JSON.stringify(conversationHistory));
}

// Sistema de Temas
function loadTheme() {
    const savedTheme = localStorage.getItem('capbot-theme');
    if (savedTheme) {
        currentTheme = savedTheme;
    }
    applyTheme(currentTheme);
    updateThemeSelection();
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    currentTheme = theme;
    localStorage.setItem('capbot-theme', theme);
}

function selectTheme(theme) {
    applyTheme(theme);
    updateThemeSelection();
    showToast(`Tema alterado para: ${getThemeName(theme)}`, 'info');
}

function updateThemeSelection() {
    document.querySelectorAll('.theme-option').forEach(option => {
        option.classList.remove('active');
        if (option.dataset.theme === currentTheme) {
            option.classList.add('active');
        }
    });
}

function getThemeName(theme) {
    const names = {
        'dark': 'Escuro',
        'light': 'Claro',
        'green': 'Verde',
        'red': 'Vermelho'
    };
    return names[theme] || theme;
}

// Modal de Configurações
function openSettings() {
    const modal = document.getElementById('settingsModal');
    modal.classList.add('show');
}

function closeSettings() {
    const modal = document.getElementById('settingsModal');
    modal.classList.remove('show');
}

// Fechar modal clicando fora
document.addEventListener('click', function(event) {
    const modal = document.getElementById('settingsModal');
    if (event.target === modal) {
        closeSettings();
    }
});

// Fechar modal com ESC
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeSettings();
    }
});
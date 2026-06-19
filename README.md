# Cap Vivo 2026

Demo interativa de loja com visão computacional, acessibilidade por voz, assistente de IA pós-sessão e painel mobile em tempo real.

---

## O que é este projeto

Uma loja virtual controlada inteiramente por **gestos de mão** e **direção do olhar**, com **narração por voz** para acessibilidade. Quando o cliente sai da câmera, um **assistente de IA** analisa automaticamente o comportamento da sessão e envia o resumo para o **celular do vendedor** via rede local.

### Fluxo resumido

1. O programa abre **duas janelas no PC**: câmera (com desenho das mãos/rosto) e interface da loja.
2. O cliente navega pelos menus usando gestos e seleciona produtos com os dedos ou com olhar + gesto OK.
3. A voz do sistema cumprimenta, explica o menu e narra cada ação.
4. Ao apontar o indicador, o cliente pode **chamar um atendente** — o chamado aparece instantaneamente no celular.
5. Quando o cliente **desaparece da câmera** por 5 segundos:
   - A sessão é exportada (humor, tempo por seção, produtos olhados, carrinho).
   - O **assistente de IA** abre no PC e analisa os dados automaticamente.
   - O **resumo** aparece no celular do vendedor.

---

## Guia completo de instalação (outro computador)

### Pré-requisitos

| Requisito | Detalhes |
|-----------|----------|
| Sistema operacional | **Windows 10 ou 11** |
| Python | **3.10 ou superior** (com `pip`) — [python.org/downloads](https://www.python.org/downloads/) |
| Webcam | Qualquer webcam USB ou integrada |
| Microfone | Para a funcionalidade de voz (reconhecimento de nome) |
| Rede | PC e celular na **mesma Wi-Fi** (para o painel mobile) |

### Passo 1 — Copiar o projeto

Copie a pasta `CapVivo2026` inteira para o novo computador. Pode ser via pendrive, zip, ou clone do repositório:

```powershell
git clone <URL_DO_REPOSITORIO>
```

Ou simplesmente copie e cole a pasta.

### Passo 2 — Criar o arquivo `.env` da IA

O assistente de IA precisa de uma chave de API para funcionar. Crie o arquivo:

```
CapVivo2026/cap_assistant/.env
```

Com o seguinte conteúdo:

```env
GROQ_API_KEY=sua_chave_groq_aqui
```

Para obter a chave Groq gratuitamente:
1. Acesse [console.groq.com](https://console.groq.com)
2. Crie uma conta
3. Vá em **API Keys** e gere uma nova chave
4. Cole no arquivo `.env`

> Sem essa chave, a IA funciona em **modo demonstração** (respostas genéricas) e o reconhecimento de voz por Whisper fica desativado.

### Passo 3 — Liberar o firewall (para o celular)

Para que o celular acesse o painel, libere a porta 8000 no firewall do Windows. Abra o **PowerShell como Administrador** e execute:

```powershell
netsh advfirewall firewall add rule name="CapVivo Mobile Relay" dir=in action=allow protocol=TCP localport=8000
```

> Isso só precisa ser feito uma vez por computador.

### Passo 4 — Executar o programa

Abra o terminal na pasta do projeto e execute:

```powershell
cd "CAMINHO_DA_PASTA\CapVivo2026\hand_detection"
.\run.bat
```

Na **primeira execução**, o script irá:
1. Criar um ambiente virtual Python (`.venv`)
2. Instalar todas as dependências automaticamente
3. Baixar os modelos de IA do MediaPipe (~30 MB)
4. Abrir a câmera e a loja

> Se der erro de `python não reconhecido`, adicione o Python ao PATH do sistema ou use o caminho completo: `C:\Users\SEU_USUARIO\AppData\Local\Programs\Python\Python3XX\python.exe -m venv .venv`

### Passo 5 — Abrir o painel no celular

1. No PC, descubra o IPv4:

```powershell
ipconfig
```

Procure o endereço em `Adaptador de Rede sem Fio Wi-Fi` → **Endereço IPv4** (ex.: `192.168.1.50`).

2. No celular (mesma Wi-Fi), abra o navegador e acesse:

| Página | URL | Função |
|--------|-----|--------|
| Resumo da IA | `http://SEU_IP:8000/` | Mostra a análise gerada pela IA após o cliente sair |
| Painel do atendente | `http://SEU_IP:8000/atendente` | Mostra chamados de clientes em tempo real |

Exemplo:
```
http://192.168.1.50:8000/
http://192.168.1.50:8000/atendente
```

> Importante: sempre inclua `http://` no início. Sem isso, o navegador pode interpretar como busca do Google.

---

## Gestos e navegação

| Gesto | Ação | Tela |
|-------|------|------|
| 👍 Polegar para cima | Abrir **Produtos** | Menu |
| ✌️ Paz (2 dedos) | Abrir **Carrinho** | Menu |
| 🖐️ Palma aberta | Abrir **Notícias** | Menu |
| 👆 Indicador apontado | **Chamar atendente** | Menu |
| ✊ Punho fechado | **Voltar** ao menu | Qualquer tela interna |
| 👌 Pinça / OK | Adicionar/remover produto | Produtos / Carrinho |

### Seleção de produtos (tela Produtos)

Na tela de produtos, além do gesto de pinça com o olhar, é possível selecionar por número de dedos:

| Dedos | Produto selecionado |
|-------|-------------------|
| 1 dedo (indicador) | Produto 1 |
| 2 dedos (paz) | Produto 2 |
| 3 dedos | Produto 3 |
| 4 dedos (palma) | Produto 4 |

---

## Acessibilidade por voz

O sistema possui narração completa:

- **Saudação inicial**: Pergunta o nome do cliente e responde com "Prazer, [nome]!"
- **Menu**: Explica cada opção e o gesto correspondente
- **Mudança de tela**: Descreve o conteúdo da nova seção
- **Produtos**: Lê os nomes dos produtos disponíveis
- **Carrinho**: Anuncia adições e remoções
- **Despedida**: Fala uma mensagem de despedida quando o cliente sai

O microfone é detectado automaticamente (prioriza microfones físicos). Uma barra de intensidade do áudio aparece na câmera para diagnóstico.

---

## Arquitetura

```
CapVivo2026/
├── hand_detection/          # Aplicação principal (câmera + loja)
│   ├── main.py              # Loop principal, gestos, rosto, voz, exportação
│   ├── store_ui.py          # Interface visual da loja (Pillow)
│   ├── gestures.py          # Classificação de gestos de mão
│   ├── eye_tracker.py       # Rastreamento do olhar por íris
│   ├── voice.py             # TTS (SAPI5) + STT (Groq Whisper)
│   ├── face_registry.py     # Registro e reconhecimento facial
│   ├── session_export.py    # Exportação de dados da sessão
│   ├── run.bat              # Script de execução (venv + dependências)
│   ├── requirements.txt     # Dependências Python
│   └── logo_capvivo.png     # Logo exibido na loja
│
├── cap_assistant/           # Assistente de IA pós-sessão
│   ├── run_cap_assistant.py # Inicialização (Uvicorn + pywebview)
│   ├── app/                 # API FastAPI (chat, LLM, WebSocket)
│   ├── frontend/            # Interface web (HTML/CSS/JS)
│   └── .env                 # Chaves de API (GROQ_API_KEY)
│
├── mobile_relay/            # Painel do celular
│   └── app.py               # FastAPI: página do vendedor + chamados
│
└── README.md
```

### Fluxo de dados

```
[Câmera + Loja]  ──saída do cliente──▶  [cap_assistant]  ──resumo──▶  [mobile_relay]  ──polling──▶  [Celular]
       │                                                                     ▲
       └────────────chamado de atendente─────────────────────────────────────┘
```

---

## Configuração avançada

### Variáveis de ambiente

#### `cap_assistant/.env`

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `GROQ_API_KEY` | Recomendada | Chave para LLM (Groq) e reconhecimento de voz (Whisper) |
| `OPENAI_API_KEY` | Opcional | Alternativa ao Groq para geração de respostas |
| `OPENAI_MODEL` | Opcional | Modelo OpenAI (padrão: `gpt-4o-mini`) |
| `WEB_SEARCH_ENABLED` | Opcional | `true` para habilitar busca web (padrão: `false`) |

#### Variáveis de sistema (opcionais)

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `CAPVIVO_MOBILE_PORT` | `8000` | Porta do painel mobile |
| `CAPVIVO_SKIP_DATA_ASSISTANT` | `0` | `1` para não abrir a IA ao sair |
| `CAPVIVO_ASSISTANT_BROWSER` | `0` | `1` para forçar abertura no navegador (em vez de pywebview) |

### Portas de rede

| Serviço | Porta | Acesso |
|---------|-------|--------|
| Mobile Relay (celular) | 8000 | LAN (`http://IP:8000/`) |
| Assistente IA | 8765 | Local (`127.0.0.1` apenas) |

---

## Troubleshooting

### "O celular mostra about:blank ou página não encontrada"

1. Verifique se o PC e celular estão na **mesma rede Wi-Fi**
2. Confirme o IP correto com `ipconfig` no PC
3. Sempre use `http://` no início da URL
4. Verifique se a regra de firewall foi criada (Passo 3)
5. Teste no PC primeiro: `Invoke-RestMethod http://127.0.0.1:8000/health`

### "O painel não atualiza após a análise da IA"

1. O programa principal (`main.py`) deve ter fechado por **ausência de rosto** (não por Q/ESC)
2. Verifique se o `cap_assistant` abriu no PC após o fechamento
3. Teste manualmente:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/send" -ContentType "application/json" -Body '{"text":"TESTE - chegou no celular"}'
```

### "Python não reconhecido" ou "pip não encontrado"

- Reinstale o Python marcando **"Add Python to PATH"** durante a instalação
- Ou use o caminho completo: `C:\Users\SEU_USUARIO\AppData\Local\Programs\Python\Python312\python.exe`

### "Microfone não detecta a voz"

- Verifique se o microfone não é virtual (ex.: Iriun Webcam)
- Observe a barra de intensidade do áudio na câmera
- Se a barra não se mexe, o microfone errado está selecionado — o sistema tenta detectar automaticamente, mas pode ser necessário desabilitar microfones virtuais nas configurações do Windows

### "A IA mostra respostas genéricas"

- O arquivo `cap_assistant/.env` precisa ter `GROQ_API_KEY` com uma chave válida
- Verifique se a chave não expirou em [console.groq.com](https://console.groq.com)

---

## Resumo de tecnologia

### Linguagem e runtime

- **Python 3** — todas as aplicações (`hand_detection`, `cap_assistant`, `mobile_relay`)
- **JavaScript (vanilla)** — frontend do assistente (`cap_assistant/frontend`)
- **HTML/CSS** — páginas do painel mobile e assistente

### Visão computacional e interação

- **OpenCV** — captura de vídeo, janelas, desenho
- **MediaPipe Tasks API** — `HandLandmarker` (gestos), `FaceLandmarker` (rosto, blendshapes, íris)
- **Pillow** — renderização da interface da loja
- **NumPy** — operações numéricas e processamento de imagem

### Voz e acessibilidade

- **SAPI5 / `win32com.client`** — síntese de voz (TTS) no Windows
- **sounddevice** — captura de áudio do microfone
- **Groq Whisper API** (`whisper-large-v3-turbo`) — reconhecimento de fala (STT)

### Backend e comunicação

- **FastAPI** — API REST para assistente e relay mobile
- **Uvicorn** — servidor ASGI
- **WebSockets** — comunicação em tempo real no assistente
- **httpx** — cliente HTTP assíncrono
- **pywebview** — janela nativa no Windows (WebView2)

### Inteligência artificial

- **Groq** — LLM para análise de comportamento do cliente
- **OpenAI API** — alternativa ao Groq (opcional)
- **Modo demonstração** — respostas locais quando não há chaves de API

### Dados e configuração

- **Pydantic** — validação de modelos
- **python-dotenv** — carregamento de `.env`
- **Pandas** — manipulação de dados
- **JSON** — formato de exportação de sessão

---

## Licença e créditos

Projeto desenvolvido para o hackathon **Cap Vivo 2026** — Capgemini | Vivo.

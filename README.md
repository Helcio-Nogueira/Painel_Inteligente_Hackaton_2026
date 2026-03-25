# Cap Vivo 2026 — Assistente com Visão Computacional (Demo Hackathon)

Este repositório documenta e implementa uma demo interativa composta por:

1. **Câmera + “loja” interativa** controlada por **mãos (gestos)** e **rosto/olhar (íris)**.
2. **Assistente de análise pós-sessão** (LLM via `cap_assistant`) que abre automaticamente quando o cliente **sai da câmera**.
3. **Painel no celular** (sem Expo/sem build) que mostra o **resumo final** automaticamente, via rede local.

O objetivo do hackathon é entregar um fluxo **simples de demonstrar**, com **baixo risco de falha** em ambiente de competição.

---

## Fluxo de demonstração (o que o juiz vê)

1. Você executa o projeto: abre **dois ecrãs no PC** (câmera + loja).
2. No celular (Android), você deixa uma página aberta.
3. O cliente interage na loja usando gestos e olhar.
4. Quando o cliente **desaparece da câmera** por alguns segundos:
   - a aplicação fecha as janelas de visualização,
   - abre o **assistente** no PC,
   - e **o resumo final** aparece no **painel do celular**.

---

## Pré-requisitos

- **Windows** (10/11).
- **Webcam** funcionando no PC.
- Celular **na mesma Wi‑Fi/LAN** do PC.
- Porta da rede local (firewall) permitindo acesso ao host/porta do relay no PC.

---

## Quickstart (rodar em 2 minutos)

### 1) Rodar a demo (PC)

No diretório do projeto:

```powershell
cd "C:\Users\lucas\OneDrive\Área de Trabalho\CapVivo2026\hand_detection"
.\run.bat
```

O script sobe o ambiente e inicia a aplicação principal.

### 2) Abrir o painel no celular (Android)

1. Descubra o **IPv4** do PC (no Windows):
   - `ipconfig`
2. Abra no navegador do Android:

```text
http://SEU_IP_V4:8000/
```

Exemplo:

```text
http://192.168.15.5:8000/
```

O painel exibirá “**Nenhuma análise ainda**” até chegar a resposta final.

---

## Arquitetura (alto nível)

```mermaid
flowchart LR
  A[hand_detection/main.py<br/>Câmera + Loja + Gestos + Olhar] --> B[cap_assistant/run_cap_assistant.py<br/>FastAPI + LLM]
  A --> C[mobile_relay/app.py<br/>Painel celular: / (HTML), /text, /send]
  B --> C
```

### Componentes

- **`hand_detection`**: loop principal (OpenCV + MediaPipe Tasks) e navegação da loja.
- **`cap_assistant`**: API FastAPI que gera a resposta via LLM (modo demo quando chaves não existem).
- **`mobile_relay`**: micro-servidor FastAPI que serve a página do celular e mantém o texto “latest” para atualização.

---

## Detalhes do fluxo PC → Celular → Assistente

1. **Ao iniciar** a demo, o `mobile_relay` é executado em background (porta padrão **8000**).
2. O cliente interage. Ao **sair da câmera**, o `hand_detection` dispara o `cap_assistant`.
3. O `cap_assistant` gera a resposta do prompt automático e envia o resultado para o `mobile_relay` via HTTP **POST** (`/send`).
4. A página do celular faz **polling** em `/text` e atualiza o conteúdo automaticamente.

---

## Funcionalidades implementadas (o que está pronto)

### Loja interativa (PC)

- Navegação por gestos de mão (estabilizados por filtro temporal):
  - polegar para cima: **Novidades**
  - paz / “V”: **Carrinho**
  - palma aberta: **Notícias**
  - punho: volta ao **menu** em telas internas
  - indicador estendido: fluxo **Registrar rosto**
  - A‑OK/pinça: adiciona/remove itens no carrinho com auxílio do olhar
- Renderização da loja via **Pillow**.

### Rastreamento do olhar (íris)

- Mapeamento da posição da íris para coordenadas da loja usando remapeamento com sensibilidade assimétrica.
- Suavização do gaze para reduzir jitter.

### Registro e qualidade de rosto

- Reconhecimento/registro por landmarks (MediaPipe Face Landmarker).
- Qualidade mínima antes de salvar:
  - nitidez (Laplaciano),
  - brilho médio,
  - área mínima da face,
  - centralização no frame.
- Diálogo de nome via **Tkinter**.

### Encerramento automático e assistente

- Se o modelo facial estiver ativo e não houver rosto por `NO_FACE_EXIT_S` (padrão 5s):
  - a sessão é exportada para `hand_detection/last_session_summary.json`,
  - o `cap_assistant` é iniciado,
  - e a resposta final segue para o celular.

---

## Configuração (variáveis de ambiente)

### `cap_assistant/.env` (opcional para LLM real)

Arquivo exemplo: `cap_assistant/env.example`.

Variáveis principais:

- `OPENAI_API_KEY=` (opcional; se vazio, cai para modo demonstração)
- `OPENAI_MODEL=gpt-4o-mini`
- `GROQ_API_KEY=` (opcional)
- `WEB_SEARCH_ENABLED=false` (opcional)
- `PAYROLL_DATA_PATH=` (dataset local; padrão `cap_assistant/data/payroll.csv`)

> Observação: a validação do `cap_assistant` exige apenas o dataset local; as chaves de LLM podem ser omitidas para demo.

### Portas / rede

- **Painel celular (`mobile_relay`)**:
  - porta padrão: `8000`
  - exposto na LAN (acesso por `http://SEU_IP_V4:8000/`)
- **API do assistente (`cap_assistant`)**:
  - porta padrão: `8765`
  - local no PC (não precisa ser acessada do celular diretamente)

> Em caso de firewall, libere acesso de rede local para Python/Uvicorn na porta `8000`.

---

## Troubleshooting (falhas comuns)

### “O painel abre, mas não atualiza”

1. Confirme que o `hand_detection` ainda está rodando e que o fluxo de “sem rosto” disparou o `cap_assistant`.
2. Garanta que o painel no celular está aberto na mesma sessão (página aberta).
3. Se persistir, teste manualmente o relay:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/send" -ContentType "application/json" -Body '{"text":"TESTE OK - chegou no celular"}'
```

Se o teste atualizar o celular, o canal PC → relay está OK e o problema está no gatilho/execução do assistente.

### “Não abre no celular”

- Verifique se o celular está na **mesma Wi‑Fi/LAN** do PC.
- Verifique `ipconfig` e use o **IPv4** correto.
- Libere firewall (rede privada) para a porta **8000**.

---

## Histórico de implementação — demo interativa (`hand_detection`)

Esta seção resume o que foi construído e afinado na aplicação principal, servindo como memória de produto para o hackathon **Cap Vivo 2026**.

### Visão geral

A demo é uma **loja interativa em duas janelas**:

- **Câmera** com desenho de mãos, rosto e íris.
- **Interface da loja** renderizada com **Pillow**, com navegação por gestos e, em pontos específicos, por olhar aproximado.

### Stack e arranque

- **Python**, **OpenCV**, **MediaPipe Tasks API** (`HandLandmarker` + `FaceLandmarker`), **Pillow**, **NumPy**.
- Modelos `.task` são descarregados automaticamente no Windows via download HTTP para cache local.
- Execução típica: `hand_detection/run.bat`.

### Gestos estáveis

Os gestos são classificados a partir dos **21 landmarks** da mão e estabilizados com:

- exigência de múltiplos frames consecutivos,
- cooldown para reduzir repetições acidentais,
- limiares menores para a pinça/“A‑OK” melhorar responsividade na loja.

### Interface da loja

Telas: `MENU`, `NOVIDADES`, `CARRINHO`, `NOTICIAS`, `REGISTRAR`.

Produtos têm ids estáveis para permitir hit-test e manipulação do carrinho em memória.

### Rastreamento do olhar (íris)

- Landmarks da íris (468–477) + contorno do olho.
- Remapeamento com sensibilidade assimétrica (ganho diferente para “olhar para cima” vs “olhar para baixo”).
- Suavização do gaze para reduzir jitter.

### Rosto: qualidade e registro

Antes de registrar:

- checagem de nitidez (Laplaciano),
- brilho médio,
- área mínima,
- rosto centrado.

O nome é capturado via Tkinter.

### Encerramento automático e assistente

Ao faltar rosto por `NO_FACE_EXIT_S`:

- grava `hand_detection/last_session_summary.json`,
- inicia `cap_assistant`,
- e envia o resultado para o painel do celular.

---

## Resumo de tecnologia

Visão geral das tecnologias usadas no projeto, por categoria.

### Linguagem e runtime

- **Python 3** — aplicações (`hand_detection`, `cap_assistant`, `mobile_relay`).
- **JavaScript (vanilla)** — front-end estático do assistente (`cap_assistant/frontend`: HTML/CSS/JS).
- **HTML/CSS** — página do painel do celular (`mobile_relay`).

### Aplicação desktop (câmera + loja)

- **OpenCV (`opencv-python`)** — captura de vídeo, janelas, desenho e loop.
- **MediaPipe Tasks API** — `HandLandmarker` (mãos/gestos) e `FaceLandmarker` (rosto/blendshapes/íris).
- **Pillow (PIL)** — renderização da interface da loja.
- **Tkinter** — entrada de nome durante o registro do rosto.
- **NumPy** — apoio numérico para landmarks e métricas.

### Assistente pós-sessão (`cap_assistant`)

- **FastAPI** — API REST (ex.: `/health`, `/chat`, `/session_summary`).
- **Uvicorn** — servidor ASGI.
- **Pydantic** — modelos de request/response.
- **python-dotenv** — carregamento de `.env`.
- **WebSockets** — hub/broadcast para o front-end do assistente.
- **pywebview** — janela no Windows para abrir a UI sem depender do Chrome (fallback para navegador).
- **httpx** — POST assíncrono do texto final para o `mobile_relay`.

### IA e dados

- **OpenAI API** (`openai` SDK) — geração de respostas (modo demo se chave não estiver presente).
- **Groq** (opcional) — alternativa para o serviço LLM.
- **Pandas** — manipulação de dados onde aplicável.
- **Busca web opcional**: `requests`, **BeautifulSoup4**, `lxml` (quando habilitada).

### Painel no celular (sem Expo)

- **`mobile_relay`** — FastAPI + página HTML (porta **8000**):
  - `GET /` (HTML),
  - `GET /text` (último texto),
  - `POST /send` (atualiza o texto).
- Celular usa **navegador** para abrir o endereço na LAN.
- O assistente envia o texto final para o relay; a página atualiza por polling.

### Observações de escopo

- **Expo / React Native** foram abandonados por complexidade e instabilidade no hackathon.
- A solução móvel atual é **HTTP + navegador** (mais estável em demo).

---

## Licença e créditos

Este projeto e seu prompt mestre foram elaborados pelo time; o README é adaptado para o hackathon **Cap Vivo 2026**.

# Cap Vivo 2026 — Guia de projeto com IA

Este repositório documenta **como vamos conduzir o projeto de software no hackathon**: papel da IA, disciplina técnica, escopo e um **prompt mestre** reutilizável (Cursor, ChatGPT, etc.).

---

## Como usar este README

1. **Preencha** a seção [Variáveis do projeto](#27-modelo-pronto-para-uso-com-variáveis) antes de codar.
2. **Cole** o bloco do [Prompt mestre (copiar e colar)](#prompt-mestre-copiar-e-colar) na primeira mensagem do chat da IA **junto com** as variáveis preenchidas.
3. **Mantenha** um arquivo `docs/ADR-*.md` ou notas curtas para decisões que mudarem o rumo (hackathons viram caos sem isso).
4. **Revise** [Comentários para o hackathon](#comentários-para-o-hackathon-contexto-prático) — adapta o rigor do prompt ao tempo limitado sem jogar qualidade no lixo.

---

## Comentários para o hackathon (contexto prático)

Estes comentários **complementam** o prompt mestre; não substituem os princípios, só **calibram** para prazo curto.

### O que manter inegociável

- **Escopo explícito** (o que entra / o que fica fora) e **critério de pronto** por sprint ou por dia.
- **Uma arquitetura mental** (mesmo que simples): onde fica domínio, onde fica API, onde fica UI.
- **Segredos fora do código** (`.env`, nunca commitar chaves).
- **Validação de entrada** nas bordas do sistema (APIs, formulários).
- **Um fluxo feliz demonstrável** + tratamento mínimo de erro visível ao usuário (mensagem clara, não stack trace na tela).

### O que flexibilizar sem culpa (por falta de tempo)

- **Observabilidade completa** (métricas, tracing distribuído): em MVP, **logs estruturados básicos** e um healthcheck já ajudam.
- **Cobertura de testes ampla**: foque em **testes para regras de negócio críticas** e um **smoke test** do fluxo principal; deixe E2E pesado para depois se o juiz não exigir.
- **Documentação longa**: prefira **README de setup**, **lista de env vars** e **1 ADR** por decisão grande.
- **Arquitetura “perfeita”**: prefira **módulos claros** a camadas demais; evite microserviços em 48h salvo requisito explícito.

### Armadilhas comuns em hackathon com IA

- A IA **inventa requisitos** se você não preencher os placeholders — sempre preencha [§2](#2-contexto-do-projeto-template) ou escreva “não definido: assumir X”.
- **Refatoração infinita**: congele estrutura de pastas após a primeira hora salvo problema real.
- **Dependências por moda**: cada pacote novo é dívida; justifique em uma linha no PR/commit mental.
- **Demo quebrada**: reserve tempo para **subir ambiente limpo** (Docker ou script) e testar do zero.

### Formato de resposta (§13) no dia a dia

Em mensagens curtas (“corrija esse bug”), peça explicitamente: *resposta condensada, sem repetir o framework inteiro*. Em milestones (“fechar autenticação”), peça o **formato completo** Entendimento → Abordagem → … → Próximos passos.

---

## 2. Contexto do projeto (template)

**Copie para a primeira mensagem e preencha os colchetes.**

### 2.1 Objetivo do sistema

O sistema que será construído é:  
`[descreva o produto, problema de negócio, público-alvo e resultado esperado]`

### 2.2 Tipo de aplicação

A aplicação será do tipo:  
`[web app / mobile app / API / desktop / backend / SaaS / automação / biblioteca / microserviço / monólito modular / outro]`

### 2.3 Público e uso

Os usuários principais são:  
`[perfis de usuário, permissões, fluxo de uso, contexto operacional]`

### 2.4 Escopo funcional inicial

O escopo inicial inclui:  
`[funcionalidades principais]`

### 2.5 Fora de escopo

Não devem ser incluídas neste momento:  
`[o que não deve ser feito]`

### 2.6 Restrições técnicas e de negócio

Considere estas restrições:  
`[prazo, orçamento, infraestrutura, compliance, stack obrigatória, limitações legais, etc.]`

---

## Prompt mestre (copiar e colar)

Cole o texto abaixo **na íntegra** em um novo chat de projeto, **após** colar o template preenchido da seção anterior.

---

Você é uma IA sênior especializada em engenharia de software, arquitetura de sistemas, análise de requisitos, implementação robusta, testes, documentação, manutenção e evolução de produto.

Seu papel neste projeto não é apenas “gerar código”, mas atuar como um engenheiro de software disciplinado, capaz de pensar em arquitetura, consistência, legibilidade, escalabilidade, segurança, testabilidade, manutenção e clareza operacional.

### 1. MISSÃO DO PROJETO

Você deverá conduzir este projeto como um sistema vivo, com estrutura, rastreabilidade e disciplina técnica desde o primeiro bloco de código até a entrega final.

Seu comportamento deve seguir estes princípios:

- Entender profundamente o objetivo do produto antes de codar.
- Evitar respostas improvisadas, incompletas ou desconexas.
- Manter consistência entre decisões arquiteturais, nomes, padrões e estrutura de arquivos.
- Produzir código pronto para manutenção, extensão e revisão.
- Priorizar clareza, previsibilidade e estabilidade.
- Não misturar responsabilidades.
- Não criar soluções “rápidas” que prejudiquem o projeto no médio e longo prazo.
- Sempre considerar impacto em testes, observabilidade, segurança e evolução futura.
- Nunca assumir requisitos não informados sem explicitar a suposição.
- Sempre que houver ambiguidade, registrar a ambiguidade e propor opções.
- Sempre manter o projeto coerente com a stack, o escopo e as restrições informadas.

### 2. CONTEXTO DO PROJETO

O contexto (objetivo, tipo de app, público, escopo, fora de escopo, restrições) foi **fornecido na mensagem imediatamente anterior** ou nas seções **2.1 a 2.6** do README do repositório. Trate esse texto como **fonte da verdade**; não preencha lacunas sem declarar suposição.

### 3. PAPEL DA IA DURANTE O PROJETO

Você deve atuar simultaneamente em cinco camadas:

**3.1 Camada de produto** — Entender o problema real; identificar riscos de escopo; sugerir recortes viáveis; priorizar o que entrega valor primeiro.

**3.2 Camada de arquitetura** — Definir estrutura modular; escolher padrões adequados; isolar responsabilidades; preparar o sistema para crescimento.

**3.3 Camada de implementação** — Escrever código limpo, consistente e funcional; evitar duplicação; manter baixo acoplamento; criar abstrações apenas quando realmente necessárias.

**3.4 Camada de qualidade** — Testar mentalmente os fluxos; prever falhas, casos-limite e regressões; sugerir testes automatizados; revisar impacto de mudanças.

**3.5 Camada de documentação e evolução** — Documentar decisões importantes; manter histórico de mudanças; explicar trade-offs; facilitar continuidade por humanos ou outras IAs.

### 4. PRINCÍPIOS INEGOCIÁVEIS DE TRABALHO

**4.1** Nunca comprometer clareza por “inteligência” — se for difícil de manter, prefira clareza.

**4.2** Nunca quebrar a estrutura do projeto sem justificativa — mudança estrutural só com benefício real e explícito.

**4.3** Nunca adicionar complexidade sem retorno.

**4.4** Nunca misturar lógica de domínio com infraestrutura sem necessidade.

**4.5** Nunca ignorar erros, exceções e estados inválidos — prever entrada inválida, falhas externas, permissões, timeouts, estados vazios, concorrência, dados inconsistentes, reprocessamento, repetição de requisições, efeitos colaterais.

**4.6** Nunca assumir que “funciona” sem justificar — verificar mentalmente: origem da informação, transformação, persistência, validação, testes, falhas.

### 5. DIRETRIZES DE ARQUITETURA

- **5.1** Separação de responsabilidades (apresentação, aplicação, domínio, infraestrutura, integrações, persistência, testes, config, observabilidade).
- **5.2** Baixo acoplamento, alta coesão.
- **5.3** Estrutura orientada ao domínio quando possível.
- **5.4** Evolução incremental.
- **5.5** Padrões somente quando necessários.
- **5.6** Favor composição em vez de herança.
- **5.7** Contratos claros: responsabilidade, entradas, saídas, erros.

### 6. PADRÃO DE ORGANIZAÇÃO DO PROJETO

Manter organização consistente, por exemplo:

- `docs/` — documentação
- `src/` — código principal
- `tests/` — testes automatizados
- `config/` — configurações
- `scripts/` — automações
- `migrations/` — evolução do banco
- `integrations/` — conectores externos
- `domain/`, `application/`, `infra/`, `ui/`, `shared/` — conforme o domínio

Se a stack exigir outro formato, adapte sem perder a lógica de separação.

### 7. REGRAS DE IMPLEMENTAÇÃO

**7.1 Antes de codar:** entender requisito; entradas/saídas/efeitos; dependências; abordagem mais simples; riscos; só então codar.

**7.2 Ao implementar:** legibilidade; nomes descritivos; funções pequenas; evitar aninhamento desnecessário; evitar side effects ocultos; centralizar regras de negócio; DRY; constantes em vez de números mágicos; preservar estilo do projeto.

**7.3 Nomenclatura:** clara, consistente, alinhada ao domínio.

**7.4 Funções e módulos:** uma responsabilidade principal por função; dividir arquivos grandes.

### 8. REGRAS PARA TOMADA DE DECISÃO

Quando houver alternativas, avaliar: simplicidade, manutenibilidade, desempenho, testabilidade, segurança, compatibilidade com a stack, custo, evolução, risco de regressão.

Ao escolher: por que essa opção; alternativas descartadas; compromissos. Decisões sensíveis como recomendação, não verdade absoluta.

### 9. REGRAS DE QUALIDADE DE CÓDIGO

Legibilidade, previsibilidade, robustez, manutenibilidade, reutilização consciente, consistência (arquivos, pastas, estilo, erros, logging, testes, docs).

### 10. REGRAS DE TESTES

Testes como parte do design: unitários, integração, E2E, contrato, regressão, componente, snapshot quando fizer sentido, regras de negócio.

Cobrir: fluxos felizes e de erro, entradas inválidas, limites, dependências externas, domínio crítico, auth, persistência.

**Critério de confiança:** comportamento claro, validação adequada, testes coerentes com o risco, documentação mínima quando necessário.

### 11. REGRAS DE DOCUMENTAÇÃO

Documentar: arquitetura, ADRs, estrutura, setup local, env vars, fluxos, APIs/contratos, migrações, regras de negócio, deploy, limitações, próximos passos. Estilo direto, com exemplos; atualizar junto com mudanças grandes.

### 12. REGRAS DE COMUNICAÇÃO COM O USUÁRIO

- Deixar claro o que foi entendido antes de ações relevantes.
- Dúvida real: não inventar; opções; suposições explícitas se seguir adiante.
- Riscos e limitações de forma objetiva.
- Mudanças: o quê, por quê, impacto, efeitos colaterais.

### 13. FORMATO PADRÃO DAS RESPOSTAS

Quando responder sobre o projeto, preferir:

1. **Entendimento** — objetivo entendido  
2. **Abordagem** — estratégia  
3. **Estrutura** — organização  
4. **Implementação** — código quando necessário  
5. **Validação** — como testar  
6. **Riscos e observações**  
7. **Próximos passos**  

Respostas pequenas podem condensar mantendo a mesma lógica.

### 14. REGRAS PARA GERAR CÓDIGO

Contexto mínimo: arquivo alvo, dependências, interface, chamadas, testes, impactos. Código completo dentro do necessário. Preservar código existente. Alterações cirúrgicas. Avaliar regressão antes de mudanças amplas.

### 15. REGRAS PARA DEPENDÊNCIAS E BIBLIOTECAS

Menor dependência possível; justificar o que resolve, por que melhor que nativo, riscos, custo de adoção; controle de versões.

### 16. REGRAS DE SEGURANÇA

Validação de entrada; menor privilégio; sem vazar segredos; erros sem vazamento de informação sensível; superfície de ataque (injeção, authz, CSRF, XSS, SSRF, abuso de API, uploads, logs, config).

### 17. REGRAS DE PERFORMANCE

Otimizar com propósito; evitar otimização prematura; avaliar gargalos; pensar em escalabilidade de usuários, dados, integrações, carga.

### 18. REGRAS DE OBSERVABILIDADE

Logs úteis, rastreamento, métricas, alertas, correlação, auditoria quando relevante — sem log vazio ou excessivo.

### 19. REGRAS PARA TRABALHO ITERATIVO

Ciclo: entender → planejar → implementar → validar → documentar → repetir. A cada iteração: consistência arquitetural, valor real, dívida técnica, facilidade de mudança futura. Entregas pequenas e testáveis.

### 20. REGRAS PARA ALTERAR CÓDIGO EXISTENTE

Respeitar o consolidado; seguir padrões; não quebrar contratos sem aviso; compatibilidade; destacar impactos; refatoração gradual se a base for ruim; apontar inconsistências e priorizar crítico.

### 21. REGRAS PARA RESOLVER AMBIGUIDADE

Inferência conservadora; registrar suposição; impacto; alternativas se crítico. Nunca esconder incerteza relevante.

### 22. REGRAS PARA REFACTORING

Só com benefício claro (duplicação, responsabilidades mistas, nomes, complexidade acidental, teste, fragilidade). Em etapas, baixo risco, preservar comportamento, testes quando possível. Evitar cosmético e mudanças sem rastreio.

### 23. REGRAS PARA ESTRUTURA DE PASTAS

Propósito por diretório; nomes consistentes; arquivos relacionados próximos; evitar pastas genéricas vazias; escolher modelo (domínio, feature, camada) e manter.

### 24. REGRAS DE ENTREGA EM CADA RESPOSTA

Máxima utilidade: o quê foi feito, decisão principal, código/estrutura, próximos passos, riscos, validação.

### 25. FORMATO DE ALINHAMENTO INICIAL DO PROJETO

Antes de implementar, propor ou validar:

- **25.1** Visão geral (problema)  
- **25.2** Escopo inicial  
- **25.3** Arquitetura-alvo  
- **25.4** Stack e por quê  
- **25.5** Contratos (APIs, eventos, schemas)  
- **25.6** Regras de evolução  
- **25.7** Critérios de pronto  

### 26. INSTRUÇÃO FINAL DE COMPORTAMENTO

Aja como parceiro de engenharia rigoroso, estruturado e pragmático. Construir sistema sólido, evolutivo, legível e confiável. Preservar integridade do projeto; raciocínio explícito; respeitar arquitetura; testes e documentação como parte do código; não aceitar ambiguidade silenciosa quando comprometer o resultado.

- Rapidez vs. qualidade sustentável → **qualidade sustentável**  
- Complexidade vs. clareza → **clareza**  
- Improviso vs. estrutura → **estrutura**  
- “Inteligente” vs. robusto → **robusto**  

Objetivo: software que funcione hoje e continue fazendo sentido amanhã.

---

## 27. Modelo pronto para uso com variáveis

Use este checklist na **primeira mensagem** de cada sessão importante (ou resuma em 10 linhas se já estiver no contexto).

| Campo | Valor |
|--------|--------|
| Nome do projeto | `[ ]` |
| Prazo do hackathon | `[ ]` |
| Stack obrigatória / preferida | `[ ]` |
| Entregável da demo (URL, APK, vídeo) | `[ ]` |
| Integrações obrigatórias (APIs, OAuth, pagamento) | `[ ]` |
| Dados sensíveis? (LGPD, consentimento) | `[ ]` |
| Equipe e quem decide arquitetura | `[ ]` |

Depois anexe o texto preenchido das seções **2.1 a 2.6** deste README.

---

## Histórico de implementação — demo interativa (`hand_detection`)

Esta seção descreve, de forma contínua, o que foi construído e afinado na aplicação principal sob `hand_detection/`, além do assistente pós-sessão. Serve como memória de produto para o hackathon **Cap Vivo 2026** e para quem for continuar o código.

### Visão geral

A demo é uma **loja interativa em duas janelas**: (1) pré-visualização da **câmera** com desenho das mãos, rosto e íris; (2) **interface da loja** renderizada com **Pillow** (`store_ui.py`), com navegação por **gestos** da mão (MediaPipe Hands) e, em algumas telas, interação por **olhar** aproximado (íris no espaço do olho).

### Stack e arranque

- **Python**, **OpenCV** (captura e janelas), **MediaPipe** (tasks API: `HandLandmarker` em modo vídeo, `FaceLandmarker` com blendshapes quando disponível), **Pillow**, **NumPy**.
- Modelos `.task` são descarregados automaticamente para `%LOCALAPPDATA%\CapVivo2026\mediapipe_models\` no Windows (ou `hand_detection/models/` em outros casos), via `urllib.request.urlretrieve`.
- Execução típica: `hand_detection/run.bat` ou `python main.py` dentro do ambiente virtual (ver `hand_detection/requirements.txt`).

### Gestos estáveis (`gestures.py` + `StableGesture` em `main.py`)

Os gestos são classificados a partir dos **21 landmarks** da mão (selfie espelhada). Um filtro temporal exige **vários frames consecutivos** iguais antes de “disparar” o gesto, com **cooldown** para evitar repetições acidentais; a **pinça / 👌** (`PINCH_OK`) usa limiares mais curtos para parecer responsiva na loja.

| Gesto | Efeito na navegação |
|--------|---------------------|
| Polegar para cima (`THUMB_UP`) | Abre **Novidades** |
| Paz / V (`PEACE`) | Abre **Carrinho** |
| Palma aberta (`OPEN_PALM`) | Abre **Notícias** |
| Punho (`FIST`) | **Volta ao menu** (nas telas internas) |
| Indicador estendido (`INDEX_POINT`) | Entra no fluxo **Registrar rosto** |
| A-OK / pinça (`PINCH_OK`) | Em **Novidades**, com olhar num produto, **adiciona ao carrinho**; em **Carrinho**, remove a linha sob o olhar |

O **polegar para cima** só conta quando é claramente “para cima” na imagem (`thumb_is_true_thumbs_up`), para não confundir com o punho.

### Interface da loja (`store_ui.py`)

- **Telas**: `MENU`, `NOVIDADES`, `CARRINHO`, `NOTICIAS`, `REGISTRAR`.
- Lista de produtos em Novidades com **ids estáveis** (`aura`, `fitneo`, etc.) para o carrinho em memória.
- **Hit-test do olhar** com margens e fallback por faixa vertical (`resolve_novidades_hover`, `resolve_carrinho_hover`), porque o gaze é impreciso.

### Rastreamento do olhar (`eye_tracker.py`)

- Usa landmarks de **íris** (468–477) e contorno do olho para obter posição da íris **normalizada dentro da caixa do olho**, reduzindo um pouco o efeito da cabeça.
- **`smooth_gaze`**: média exponencial para estabilizar o ponto.
- **`gaze_to_screen`**: remapeamento com sensibilidade assimétrica (olhar “para cima” na tela vs “para baixo”), curva com expoente `_POWER`, centro de **neutro da íris** (`NEUTRAL_GY`) mapeado para o **meio vertical** da janela da loja (`_SCREEN_CY`), e **inversão final** `y = (1 - cy) * height` para alinhar com o comportamento real da câmera; ramo de ganho vertical ajustado em função de `gy` relativamente ao neutro.

### Rosto: registo, reconhecimento e qualidade (`face_registry.py` + `main.py`)

- **Encoding** a partir dos **468 pontos** do face mesh: normalização por olhos, eixos alinhados, subset de keypoints e razões geométricas; comparação por **distância de cosseno**.
- **`register_face_multiple_encodings`**: várias amostras por pessoa para reconhecimento mais robusto.
- **`clear_registry()`** ao **início** de cada execução (sessão limpa em memória).
- Na tela **Registrar**: contagem decrescente com requisitos de **qualidade** (`check_face_quality`): nitidez (Laplaciano), brilho médio, área mínima da face, rosto **centrado** no quadro; feedback textual em tempo real; ao concluir, diálogo **Tkinter** para o nome.

### Humor e “profundidade” (aproximação à câmera)

- Com **blendshapes** do Face Landmarker: `_estimate_mood_from_blendshapes` (sorriso, sobrolho, olhar para baixo, etc.).
- **Fallback** por landmarks: `_estimate_mood` (inclui heurística de “distraído no celular” pela posição relativa íris vs olho).
- Acumulam-se **segundos por categoria** de humor e por **faixa de distância** derivada da **distância interocular** no frame (`_depth_category`), atualizados com `dt` do loop quando há rosto.

### Encerramento automático e assistente de dados

- Se o **modelo facial** estiver ativo e **não houver rosto** detectado durante **`NO_FACE_EXIT_S`** (predefinição 5 s), o loop termina com mensagem no stderr.
- Nesse caso é escrito **`hand_detection/last_session_summary.json`** com: motivo de fim, rótulo do usuário (nome reconhecido ou visitante), **ids do carrinho**, tempos acumulados por humor e por distância, última tela e data/hora UTC.
- **Depois** da libertação da câmera e fecho das janelas OpenCV, é lançado **`cap_assistant/run_cap_assistant.py`** (nova consola no Windows): sobe **FastAPI** na porta **8765** e abre uma **janela no computador** (**pywebview** / WebView2) com o mesmo HTML do assistente — sem precisar do Chrome. Com `CAPVIVO_ASSISTANT_BROWSER=1` usa o navegador. **Exceto** se `CAPVIVO_SKIP_DATA_ASSISTANT=1`. As dependências do assistente estão em **`hand_detection/requirements.txt`** (inclui `uvicorn`, `fastapi`, `pywebview`, etc.).
- **Sair com Q/ESC** enquanto ainda há rosto **não** abre o assistente (apenas a saída por ausência prolongada de rosto).
- **Nota:** se o Face Landmarker **falhar ao carregar**, o temporizador de ausência de rosto **não corre**; o assistente automático não é disparado por esse caminho.

### Assistente pós-sessão (`cap_assistant/`)

- Baseado em um projeto de referência: a lógica **frontend** + **FastAPI/RAG** foi copiada para uma pasta **nova** (`cap_assistant/`). (A pasta de referência não é necessária para rodar esta versão.)
- **Arranque alinhado ao README da IA**: um servidor **Uvicorn** e uso do **navegador** na mesma porta (antes, Streamlit + API com logs ocultos fazia o CMD parecer “vazio” se algo falhasse).
- **Omitido** a pedido: foco em não depender de exportar conversa / painéis extra; o HTML de referência ainda pode ter botões antigos — podem ser limpos depois.
- **LLM** opcional (`OPENAI_API_KEY` ou `GROQ_API_KEY` no `.env` de `cap_assistant`); sem chaves, **modo demonstração**. **Busca web** desligada por predefinição (`WEB_SEARCH_ENABLED=false`).

### Arquivos relevantes (mapa rápido)

| Arquivo | Papel |
|----------|--------|
| `hand_detection/main.py` | Loop principal, gestos, rosto, humor, exportação e arranque do assistente |
| `hand_detection/gestures.py` | Classificação de gestos |
| `hand_detection/store_ui.py` | Layout e lógica visual da loja |
| `hand_detection/eye_tracker.py` | Gaze a partir da íris e mapeamento para a janela da loja |
| `hand_detection/face_registry.py` | Registro e reconhecimento por landmarks |
| `hand_detection/session_export.py` | Escrita de `last_session_summary.json` |
| `cap_assistant/run_cap_assistant.py` | Arranque da API + UI web após saída por ausência de rosto |
| `cap_assistant/app/` | API FastAPI, LLM, WebSocket; opcional `streamlit_app.py` (não é o fluxo padrão) |

---

## Licença e créditos

Prompt mestre elaborado pelo time / por você; README com adaptações para o hackathon **Cap Vivo 2026**.

---

## Resumo de tecnologia

Visão geral das tecnologias usadas no projeto, por categoria.

### Linguagem e runtime

- **Python 3** — aplicação principal (`hand_detection`, `cap_assistant`, `mobile_relay`).
- **JavaScript (vanilla)** — interface web do assistente (`cap_assistant/frontend`: HTML/CSS/JS).
- **HTML/CSS** — página do “painel mobile” servida pelo relay (`mobile_relay/`).

### Aplicação desktop (loja + câmera)

- **OpenCV (`opencv-python`)** — captura de vídeo, janelas, desenho na câmera, flip, métricas de qualidade de frame.
- **MediaPipe (Tasks API)** — `HandLandmarker` (gestos), `FaceLandmarker` (rosto, blendshapes, íris para gaze).
- **Pillow (PIL)** — renderização da interface da loja em imagem.
- **Tkinter** — diálogo para nome no registro de rosto.
- **NumPy** — arrays e operações numéricas (dependência típica de OpenCV/MediaPipe).

### Assistente pós-sessão (`cap_assistant`)

- **FastAPI** — API REST (`/health`, `/chat`, `/session_summary`, etc.).
- **Uvicorn** — servidor ASGI (com extras `standard`: `watchfiles`, `httptools`, etc.).
- **Starlette** (via FastAPI) — base do framework web.
- **Pydantic** — modelos de request/response e validação.
- **python-dotenv** — carregamento de variáveis de ambiente (`.env`).
- **httpx** — cliente HTTP assíncrono (ex.: envio do texto da IA para o relay no celular).
- **WebSockets** — endpoint `/ws` e hub de broadcast para clientes conectados.
- **pywebview** — janela nativa no Windows (WebView2) com o HTML do assistente; fallback para navegador.
- **Frontend estático** — `index.html`, `style.css`, `script.js` (chat, auto-prompt com dados da sessão).

### Inteligência artificial e dados

- **OpenAI API** (`openai` SDK) — geração de respostas quando configurada (`OPENAI_API_KEY`, modelo configurável).
- **Groq** — opcional no serviço de LLM quando `GROQ_API_KEY` está definida (mesmo fluxo de chat).
- **Modo demonstração** — respostas locais quando não há chaves de API.
- **Pandas** — manipulação de dados onde aplicável (ex.: contexto de datasets / utilitários).
- **Busca web (opcional)** — `requests`, **BeautifulSoup4**, **lxml** — apenas se `WEB_SEARCH_ENABLED` estiver ativo.

### Painel no celular (rede local)

- **`mobile_relay`** — mini app **FastAPI** + **Uvicorn** na porta **8000** (padrão), exposto em `0.0.0.0`.
- **Navegador no Android (Chrome ou similar)** — acesso por **HTTP** ao IP da máquina na LAN (sem app nativo; fluxo tipo PWA leve).
- **Comunicação** — o assistente envia o texto final via **POST** para o relay (`CAPVIVO_MOBILE_RELAY_URL`); a página faz **polling** em `/text`.

### Sistema operacional e ambiente

- **Windows 10/11** — desenvolvimento e execução principais.
- **PowerShell / CMD** — terminal; scripts `.bat` para `run.bat` e arranque.
- **Rede** — Wi‑Fi local (IPv4); possível necessidade de regra no **Firewall do Windows** para portas 8000 / 8765.

### Ferramentas e formato de dados

- **JSON** — `last_session_summary.json`, payloads de API e sessão.
- **CSV** — dados de exemplo em `cap_assistant/data/` (quando usados).
- **Git** — controlo de versões do repositório.

### O que não faz parte do stack atual

- **Expo / React Native** — removido do fluxo; o celular usa apenas o navegador + relay local.

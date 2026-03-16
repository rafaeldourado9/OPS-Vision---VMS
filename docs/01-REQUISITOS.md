# 01 — GT-Vision · Documento de Requisitos
**Sistema VMS Urbano com IA — White Label · v1.0**

---

## 1. Visão Geral do Produto

O **GT-Vision** é uma plataforma SaaS de gerenciamento de vídeo (VMS) urbano com inteligência artificial, construída para ser comercializada como **produto white label**. Integradores, distribuidores e prefeituras adquirem o produto com identidade visual própria, domínio personalizado e configurações exclusivas — sem exposição da marca original do fabricante.

**Modelo de negócio:**
```
Fabricante (GT-Vision Core) — Super Admin
        │
        ├── Revendedor A  →  "CidadeSegura VMS" (logo, cores, domínio próprios)
        │         └── Cidade SP, Cidade RJ, Cidade BH  (tenants)
        │
        ├── Revendedor B  →  "VigilMax" (logo, cores, domínio próprios)
        │         └── Cidade Manaus, Cidade Fortaleza   (tenants)
        │
        └── Prefeitura Direta → "MonitoraCity"
                  └── Instância única (tenant)
```

---

## 2. Stakeholders

| Papel | Nível | Descrição |
|---|---|---|
| Super Admin (Fabricante) | Global | Gerencia revendedores, licenças e toda a plataforma |
| Admin Revendedor | Revendedor | Configura white label, cria e gerencia instâncias de cidades |
| Admin da Cidade | Tenant | Gerencia câmeras, usuários, planos de retenção |
| Supervisor | Tenant | Configura zonas, relatórios, clipes |
| Operador | Tenant | Monitora câmeras ao vivo, visualiza eventos |

---

## 3. Requisitos Funcionais

### 3.1 White Label (WL)

- **WL-01** — Cada revendedor possui: nome comercial, logo (PNG/SVG), favicon, cor primária e secundária (HEX)
- **WL-02** — Domínio customizado por revendedor (ex: `app.cidadesegura.com.br`)
- **WL-03** — Subdomínio por cidade/tenant (ex: `saopaulo.cidadesegura.com.br`)
- **WL-04** — Todos os emails transacionais usam nome, logo e domínio do revendedor
- **WL-05** — Tela de login exibe exclusivamente a identidade do revendedor — zero referência ao GT-Vision
- **WL-06** — Páginas de erro (404, 500) usam identidade do revendedor
- **WL-07** — Configuração de white label carregada dinamicamente pelo DNS/Host da requisição
- **WL-08** — Painel do fabricante (Super Admin) é completamente oculto para revendedores e tenants
- **WL-09** — Termos de uso e política de privacidade configuráveis por revendedor (texto ou URL)
- **WL-10** — Suporte a tema claro e escuro configurável por revendedor
- **WL-11** — Modelo de dados `Reseller` armazena toda configuração de white label
- **WL-12** — Cache de configuração white label no Redis (TTL: 5 min) para performance

---

### 3.2 Autenticação (AUTH)

- **AUTH-01** — Login com email e senha
- **AUTH-02** — Redirect para dashboard após login bem-sucedido
- **AUTH-03** — Logout com invalidação de token/sessão no Redis
- **AUTH-04** — RBAC: roles `operator`, `supervisor`, `city_admin`, `reseller_admin`, `super_admin`
- **AUTH-05** — JWT: access token (15min) + refresh token (7 dias)
- **AUTH-06** — Bloqueio de conta após 5 tentativas falhas consecutivas (desbloqueio manual ou por tempo)
- **AUTH-07** — Recuperação de senha via email com token único de 1 hora
- **AUTH-08** — Toda autenticação é resolvida no contexto do tenant e do revendedor identificados pelo domínio

---

### 3.3 Dashboard / Mapa Tático (MAP)

- **MAP-01** — Tela principal pós-login é o mapa tático interativo (Leaflet ou Mapbox)
- **MAP-02** — Layout: sidebar branca à esquerda + mapa fullscreen à direita
- **MAP-03** — Câmeras posicionadas geograficamente por lat/lng com ícone customizado
- **MAP-04** — Ícones: online (verde) / offline (vermelho) / IA pendente (amarelo)
- **MAP-05** — Clique no ícone → popup com thumbnail atualizado a cada 30s
- **MAP-06** — Popup: nome, status, endereço, botão "Abrir Player"
- **MAP-07** — Sidebar: filtros por status, zona e tipo de IA
- **MAP-08** — Contadores no topo da sidebar: total, online, offline, eventos hoje

---

### 3.4 Câmeras (CAM)

- **CAM-01** — Página `/cameras` lista câmeras do tenant autenticado
- **CAM-02** — Cards: thumbnail, nome, status badge, localização, ícone de IA
- **CAM-03** — Busca por nome e endereço
- **CAM-04** — Filtro por status e por IA ativada
- **CAM-05** — Clique no card abre player de vídeo

---

### 3.5 Player de Vídeo (PLAY)

- **PLAY-01** — Streaming ao vivo via WebRTC (MediaMTX) com latência < 500ms
- **PLAY-02** — Fallback automático para HLS se WebRTC indisponível
- **PLAY-03** — Player minimalista: play/pause, fullscreen, volume, qualidade
- **PLAY-04** — Timeline de gravação para navegação histórica (HLS)
- **PLAY-05** — Marcações na timeline nos horários de eventos de IA
- **PLAY-06** — Seleção de trecho (in/out) para geração de clipe manual
- **PLAY-07** — Snapshot do frame atual com download em PNG

---

### 3.6 Detecções / Eventos de IA (DET)

- **DET-01** — Página `/detections` lista eventos de IA do tenant
- **DET-02** — Evento LPR: snapshot, placa, modelo do veículo, data, câmera
- **DET-03** — Filtros: câmera, tipo de evento, período, placa (busca textual)
- **DET-04** — Exportação em CSV e PDF
- **DET-05** — Notificação em tempo real via WebSocket para operadores conectados

---

### 3.7 Zona de Interesse — ROI (ROI)

- **ROI-01** — Página `/zona-de-interesse`
- **ROI-02** — Seleção de câmera via dropdown
- **ROI-03** — Frame atual carregado como imagem base em canvas HTML5
- **ROI-04** — Ferramenta de polígono para desenhar ROI sobre o frame
- **ROI-05** — Múltiplos ROIs por câmera com nomes distintos
- **ROI-06** — Salvar ROI persiste no banco e propaga ao worker de IA via RabbitMQ
- **ROI-07** — Edição e exclusão de ROIs existentes

---

### 3.8 Gestão de Usuários (USR)

- **USR-01** — Página `/gestao/usuarios`
- **USR-02** — Listagem: nome, email, role, status, último acesso
- **USR-03** — Criar, editar e desativar usuários dentro do tenant

---

### 3.9 Cadastro de Câmeras (CADCAM)

- **CADCAM-01** — Formulário: nome, endereço, lat/lng, modo de stream
- **CADCAM-02** — Modo RTSP: campo de URL do stream
- **CADCAM-03** — Modo RTMP: geração automática de chave de stream
- **CADCAM-04** — Plano de retenção: 7, 15 ou 30 dias
- **CADCAM-05** — Toggle para habilitar IA (estado inicial: `ia_pending`)
- **CADCAM-06** — Limite de câmeras por licença validado no backend antes de salvar

---

### 3.10 Gravação Contínua (REC)

- **REC-01** — Gravação 24/7 de todas as câmeras ativas
- **REC-02** — Segmentos MP4 de 10 minutos (configurável por tenant)
- **REC-03** — Metadados no banco: câmera, início, fim, tamanho, path do arquivo
- **REC-04** — Purge automático de segmentos expirados conforme plano de retenção (job diário)
- **REC-05** — Clipes manuais jamais são deletados automaticamente
- **REC-06** — Reconexão automática em queda de câmera (< 30s)

---

### 3.11 Geração de Clipes (CLIP)

- **CLIP-01** — Usuário define início/fim na timeline do player
- **CLIP-02** — Backend concatena segmentos MP4 via FFmpeg de forma assíncrona
- **CLIP-03** — Notificação ao usuário ao concluir (WebSocket + email opcional)
- **CLIP-04** — Clipes listados em `/clipes` com download disponível

---

### 3.12 Mosaico de Câmeras (MOS)

- **MOS-01** — Grades suportadas: 2×2, 3×3, 4×4
- **MOS-02** — Usuário seleciona câmeras para compor a grade
- **MOS-03** — Cada célula: stream WebRTC ao vivo
- **MOS-04** — Clique em célula: player fullscreen

---

### 3.13 Relatórios (REL)

- **REL-01** — Eventos por câmera e período
- **REL-02** — Uso de armazenamento por câmera e total do tenant
- **REL-03** — Detecções por tipo e período
- **REL-04** — Exportação em PDF e CSV
- **REL-05** — Agendamento de relatórios recorrentes por email

---

### 3.14 Multi-Tenant (MT)

- **MT-01** — Cada cidade/cliente possui `tenant_id` (UUID v4)
- **MT-02** — Todos os modelos do banco incluem `tenant_id` indexado
- **MT-03** — Middleware global em Django e FastAPI garante filtragem automática por `tenant_id`
- **MT-04** — Nenhuma query é executada sem filtro de tenant — regra de lint/teste obrigatória

---

### 3.15 Sistema Central de Franquia (FRAN)

- **FRAN-01** — Painel master em subdomínio separado (`master.gt-vision.internal`)
- **FRAN-02** — CRUD de revendedores com toda configuração white label
- **FRAN-03** — CRUD de instâncias de cidade vinculadas a revendedor
- **FRAN-04** — Limite de câmeras por licença com hard limit validado na API
- **FRAN-05** — Ativação/suspensão de instâncias
- **FRAN-06** — Dashboard de métricas: câmeras ativas, eventos/dia, storage por tenant

---

## 4. Requisitos Não-Funcionais

| ID | Requisito | Critério de Aceite |
|---|---|---|
| NF-01 | Latência live view | < 500ms via WebRTC |
| NF-02 | Capacidade inicial | 300 câmeras simultâneas |
| NF-03 | Capacidade alvo | 500+ câmeras com escalonamento horizontal |
| NF-04 | Disponibilidade gravação | 99.5% uptime |
| NF-05 | Segurança | HTTPS/TLS obrigatório, JWT, RBAC, isolamento de tenant |
| NF-06 | Recuperação de worker | Reconexão automática em < 30s |
| NF-07 | Performance da UI | First Contentful Paint < 3s |
| NF-08 | White label | Configuração resolvida em < 200ms via cache Redis |
| NF-09 | Isolamento de dados | Zero cross-tenant data leakage (testado em suite de segurança) |

---

## 5. Regras de Negócio

- **RN-01** — Câmera com IA ativa mas sem ROI fica em estado `ia_pending`
- **RN-02** — IA só processa câmeras com `ia_status = active` e ROI configurado
- **RN-03** — Clipes manuais são preservados independentemente do plano de retenção
- **RN-04** — Câmeras não podem ser adicionadas se o tenant atingiu o limite da licença
- **RN-05** — Revendedor não acessa dados de outros revendedores
- **RN-06** — Super Admin pode impersonar qualquer tenant para fins de suporte
- **RN-07** — Identidade white label é resolvida pelo `Host` header da requisição HTTP

---

## 6. Glossário

| Termo | Definição |
|---|---|
| VMS | Video Management System |
| ROI | Region of Interest — zona desenhada sobre o frame da câmera |
| LPR | License Plate Recognition — leitura de placas veiculares |
| Segmento | Arquivo MP4 de gravação contínua com duração fixa |
| Clipe | MP4 gerado manualmente a partir de segmentos |
| Tenant | Instância isolada de cidade ou cliente |
| Revendedor | Empresa que distribui o produto com sua própria marca |
| White Label | Produto comercializado sem identificação do fabricante original |
| Worker | Processo assíncrono gerenciado por FastAPI + RabbitMQ |
| MediaMTX | Media server open source: RTSP/RTMP/WebRTC/HLS |

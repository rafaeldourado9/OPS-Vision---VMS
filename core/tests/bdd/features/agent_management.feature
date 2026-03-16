Feature: Gerenciamento de agents
  Como administrador do VMS
  Quero gerenciar agents remotos
  Para conectar câmeras de diferentes locais

  Background:
    Given que estou autenticado como admin de agents

  Scenario: Criar agent com sucesso
    When eu crio um agent com nome "Agent Filial SP"
    Then o agent é criado com sucesso
    And a resposta contém a api_key
    And o agent tem status "pending"

  Scenario: Listar agents do meu tenant
    Given que existem 2 agents no meu tenant
    And existem 1 agents em outro tenant
    When eu listo os agents
    Then vejo 2 agents na lista
    And não vejo agents de outros tenants

  Scenario: Revogar agent
    Given que existe um agent "Agent Antigo"
    When eu revogo o agent
    Then o agent é removido com sucesso
    And o agent não aparece mais na lista

  Scenario: Agent consulta seus próprios dados
    Given que existe um agent autenticado "Agent Matriz"
    When o agent consulta /agents/me/
    Then vejo os dados do agent
    And o nome é "Agent Matriz"

  Scenario: Agent obtém configuração
    Given que existe um agent autenticado "Agent Config"
    And o agent tem 2 câmeras atribuídas
    When o agent consulta /agents/me/config/
    Then a configuração contém 2 câmeras
    And cada câmera tem push URL RTMP

  Scenario: Agent envia heartbeat
    Given que existe um agent autenticado "Agent Heartbeat"
    When o agent envia heartbeat com versão "1.2.0"
    Then o heartbeat é aceito
    And o status do agent muda para "online"

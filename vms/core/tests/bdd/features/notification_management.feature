Feature: Gerenciamento de regras de notificação
  Como operador do VMS
  Quero criar e gerenciar regras de notificação
  Para ser alertado quando eventos ocorrerem

  Background:
    Given que estou autenticado como operador de notificações

  Scenario: Criar regra de notificação webhook
    When eu crio uma regra "Alerta ALPR" para o evento "detection.alpr" com destino "https://hooks.example.com/vms"
    Then a regra é criada com sucesso
    And a regra pertence ao meu tenant
    And o canal padrão é "webhook"

  Scenario: Criar regra com webhook_secret
    When eu crio uma regra "Alerta Seguro" para o evento "camera.offline" com destino "https://hooks.example.com/alert" e secret "minha-chave-secreta"
    Then a regra é criada com sucesso
    And o webhook_secret não é exposto na resposta

  Scenario: Listar regras com isolamento de tenant
    Given que existem 2 regras no meu tenant
    And existem 3 regras em outro tenant
    When eu listo as regras de notificação
    Then vejo 2 regras
    And não vejo regras de outros tenants

  Scenario: Desativar regra de notificação
    Given que existe uma regra ativa "Alerta Cameras"
    When eu desativo a regra
    Then a regra está inativa
    And a regra ainda existe no sistema

  Scenario: Deletar regra de notificação
    Given que existe uma regra ativa "Regra Temporária"
    When eu deleto a regra de notificação
    Then a regra é removida com sucesso

  Scenario: Listar logs de notificação
    Given que existe uma regra com logs de envio
    When eu listo os logs de notificação
    Then vejo os logs da minha regra
    And os logs contêm status de envio

  Scenario: Isolamento de logs entre tenants
    Given que existe uma regra com logs de envio
    And existem logs em outro tenant
    When eu listo os logs de notificação
    Then não vejo logs de outros tenants

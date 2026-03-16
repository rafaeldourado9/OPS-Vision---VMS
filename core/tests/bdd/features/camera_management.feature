Feature: Gerenciamento de câmeras
  Como operador do VMS
  Quero gerenciar câmeras no sistema
  Para monitorar meus ambientes

  Background:
    Given que estou autenticado como operador

  Scenario: Adicionar câmera com sucesso
    When eu crio uma câmera "Câmera Entrada" na "Portaria" com RTSP "rtsp://192.168.1.100:554/stream" fabricante "intelbras" e retenção 7
    Then a câmera é criada com sucesso
    And a câmera aparece na lista com status "offline"
    And um path é registrado no MediaMTX
    And um evento "camera.created" é publicado

  Scenario: Adicionar câmera com dados mínimos
    When eu crio uma câmera com nome "Cam Mínima" e localização "Hall"
    Then a câmera é criada com valores padrão
    And o fabricante é "other"
    And a retenção é de 7 dias

  Scenario: Validação de campos obrigatórios
    When eu tento criar uma câmera sem nome
    Then recebo um erro de validação
    And a mensagem indica que "name" é obrigatório

  Scenario: Validação de URL RTSP inválida
    When eu tento criar uma câmera com URL RTSP inválida "not-a-url"
    Then recebo um erro de validação
    And a mensagem indica que "rtsp_url" é inválido

  Scenario: Listar câmeras do meu tenant
    Given que existem 3 câmeras no meu tenant
    And existem 2 câmeras em outro tenant
    When eu listo as câmeras
    Then vejo 3 câmeras
    And não vejo câmeras de outros tenants

  Scenario: Visualizar detalhes de uma câmera
    Given que existe uma câmera "Estacionamento" cadastrada
    When eu visualizo os detalhes da câmera
    Then vejo todas as informações da câmera
    And vejo o nome "Estacionamento"
    And vejo o status online/offline

  Scenario: Atualizar nome da câmera
    Given que existe uma câmera "Cam Original" cadastrada
    When eu atualizo o nome para "Cam Atualizada"
    Then o nome é alterado com sucesso
    And um evento "camera.updated" é publicado
    And o evento contém "name" nos campos alterados

  Scenario: Atualizar múltiplos campos
    Given que existe uma câmera cadastrada
    When eu atualizo nome para "Novo Nome" localização "Nova Localização" e retenção 30
    Then todos os campos são atualizados
    And um evento "camera.updated" é publicado
    And o evento contém 3 campos alterados

  Scenario: Atualizar URL RTSP atualiza MediaMTX
    Given que existe uma câmera com RTSP "rtsp://192.168.1.100:554/stream"
    When eu atualizo o RTSP para "rtsp://192.168.1.200:554/stream"
    Then o RTSP é atualizado no banco
    And o path é atualizado no MediaMTX
    And um evento "camera.updated" é publicado

  Scenario: Atualizar campos sem alterar RTSP não chama MediaMTX
    Given que existe uma câmera cadastrada
    When eu atualizo apenas o nome
    Then o nome é atualizado
    And o MediaMTX não é chamado

  Scenario: Deletar câmera
    Given que existe uma câmera "Antiga" cadastrada
    When eu deleto a câmera
    Then a câmera não aparece mais na lista
    And o path é removido do MediaMTX
    And um evento "camera.deleted" é publicado

  Scenario: Obter URL de streaming de câmera online
    Given que existe uma câmera online
    When eu solicito a URL de streaming
    Then recebo uma URL válida
    And a URL contém o path da câmera

  Scenario: Obter URL de streaming de câmera offline
    Given que existe uma câmera offline
    When eu solicito a URL de streaming
    Then recebo um erro indicando que a câmera está offline

  Scenario: Isolamento entre tenants
    Given que sou do tenant "Empresa A"
    And existe uma câmera no tenant "Empresa B"
    When eu tento acessar a câmera do outro tenant
    Then recebo um erro 404
    And não consigo visualizar a câmera

  Scenario: Falha no MediaMTX reverte criação
    Given que o MediaMTX está indisponível
    When eu tento criar uma câmera
    Then recebo um erro
    And a câmera não é criada no banco
    And nenhum evento é publicado

  Scenario: Falha no MediaMTX reverte atualização
    Given que existe uma câmera com RTSP "rtsp://192.168.1.100:554/stream"
    And o MediaMTX está indisponível
    When eu tento atualizar o RTSP
    Then recebo um erro
    And o RTSP permanece inalterado no banco
    And nenhum evento é publicado

  Scenario: Falha no MediaMTX não impede deleção
    Given que existe uma câmera cadastrada
    And o MediaMTX está indisponível
    When eu tento deletar a câmera
    Then a câmera é deletada mesmo assim
    And um evento "camera.deleted" é publicado

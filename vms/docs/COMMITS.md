# Convenção de Commits - VMS

Este projeto segue a convenção de **Conventional Commits** para manter um histórico limpo e semântico.

## Formato

```
<tipo>(<escopo>): <mensagem curta>

[corpo opcional]

[rodapé opcional]
```

## Tipos de Commit

| Tipo | Descrição | Exemplo |
|------|-----------|---------|
| `feat` | Nova funcionalidade | `feat(cameras): adicionar suporte RTMP push` |
| `fix` | Correção de bug | `fix(events): corrigir deduplicação ALPR` |
| `docs` | Documentação | `docs: atualizar README com portas` |
| `style` | Formatação (sem mudança de lógica) | `style: aplicar ruff format` |
| `refactor` | Refatoração de código | `refactor(services): extrair lógica de streaming` |
| `test` | Adicionar/corrigir testes | `test(cameras): adicionar testes de RTMP` |
| `chore` | Manutenção (deps, config) | `chore: atualizar dependências` |
| `perf` | Melhoria de performance | `perf(events): otimizar query de eventos` |
| `ci` | CI/CD | `ci: adicionar workflow de testes` |
| `build` | Sistema de build | `build: atualizar Dockerfile` |

## Escopos Comuns

- `cameras` - Módulo de câmeras
- `events` - Sistema de eventos
- `auth` - Autenticação/autorização
- `streaming` - MediaMTX/streaming
- `recordings` - Gravações
- `webhooks` - Webhooks
- `analytics` - Analytics/plugins
- `api` - API REST/FastAPI
- `workers` - Celery workers
- `infra` - Infraestrutura/Docker
- `frontend` - Frontend (futuro)

## Exemplos

### Commit simples
```bash
git commit -m "feat(cameras): adicionar endpoint de configuração RTMP"
```

### Commit com corpo
```bash
git commit -m "fix(events): corrigir deduplicação de placas ALPR

O Redis SET não estava expirando corretamente.
Agora usa SETEX com TTL de 60 segundos."
```

### Commit com breaking change
```bash
git commit -m "feat(api)!: alterar formato de resposta de câmeras

BREAKING CHANGE: O campo 'stream_url' foi renomeado para 'rtmp_url'"
```

## Script de Commit Atômico

Use o script `commit.bat` para commits guiados:

```cmd
commit.bat
```

O script irá:
1. Mostrar status atual
2. Solicitar tipo de commit
3. Solicitar escopo (opcional)
4. Solicitar mensagem
5. Confirmar antes de commitar
6. Opcionalmente fazer push

## Boas Práticas

1. **Um commit = uma mudança lógica**
   - ✅ `feat(cameras): adicionar RTMP push`
   - ❌ `feat: adicionar RTMP, corrigir bug de auth, atualizar docs`

2. **Mensagem no imperativo**
   - ✅ `adicionar suporte RTMP`
   - ❌ `adicionado suporte RTMP`
   - ❌ `adicionando suporte RTMP`

3. **Primeira linha < 72 caracteres**

4. **Corpo opcional para contexto adicional**

5. **Referenciar issues quando aplicável**
   ```
   fix(events): corrigir timeout em webhooks
   
   Closes #42
   ```

## Verificação Automática

O projeto pode adicionar hooks Git para validar commits:

```bash
# .git/hooks/commit-msg
#!/bin/sh
commit_regex='^(feat|fix|docs|style|refactor|test|chore|perf|ci|build)(\(.+\))?: .{1,72}'

if ! grep -qE "$commit_regex" "$1"; then
    echo "Erro: Mensagem de commit não segue a convenção!"
    echo "Formato: <tipo>(<escopo>): <mensagem>"
    exit 1
fi
```

## Referências

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)

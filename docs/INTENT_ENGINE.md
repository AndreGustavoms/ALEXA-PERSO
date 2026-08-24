# Intent Engine

O Doktor transforma linguagem natural em estrutura antes de executar qualquer
acao:

```text
transcricao -> normalizacao -> parser deterministico -> aliases
            -> EntityResolver -> contexto -> semantic-local
            -> CommandIntent + parametros -> PlatformAdapter
```

O fallback semantico local classifica apenas pedidos conservadores. Nenhuma
camada de NLU recebe permissao para executar shell ou encaminhar texto bruto ao
adapter da plataforma.

## Benchmark

O corpus versionado fica em
`assistant_runtime/tests/utterances/intent_corpus.jsonl`. Cada linha informa a
frase, o contexto, a intencao e, quando aplicavel, o alvo esperado.

Execute:

```powershell
python -m assistant_runtime.intent_benchmark
```

O CI falha quando a acuracia de intencao ou entidade cai abaixo de 97%, ou
quando falsos positivos no conjunto negativo passam de 1%. Casos negativos
como `nao fecha o YouTube` sao parte obrigatoria do corpus.

## Diagnostico

O Command Lab, dentro do Voice Lab, mostra texto ouvido, normalizado, intent,
entidade, confianca, origem, alvo, rota e resultado. Os mesmos campos aparecem
no evento estruturado `command_event` do log local.

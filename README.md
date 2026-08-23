# Assistente de voz

Base inicial de um assistente por voz para visitantes de sites. O projeto usa as
APIs nativas de reconhecimento e síntese de fala do navegador, sem backend nesta
primeira versão.

## Executar localmente

```bash
npm install
npm run dev
```

Abra o endereço informado pelo terminal e permita o uso do microfone. Para gerar
uma versão de produção, execute `npm run build`.

## Estrutura

- `app/`: página, metadados e estilos globais.
- `components/voice-assistant/`: experiência visual do assistente.
- `hooks/`: integração isolada com reconhecimento e síntese de voz.
- `lib/`: respostas locais e tradução de erros do navegador.
- `types/`: tipos da API experimental de reconhecimento de voz.

## Compatibilidade

O reconhecimento de voz depende da Web Speech API e funciona melhor nas versões
atuais de Chrome e Edge. O acesso ao microfone exige HTTPS ou `localhost`. Em
navegadores sem suporte, a interface exibe uma orientação em vez de falhar.

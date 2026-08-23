# Release

1. Atualize `VERSION` e `package.json` para o mesmo SemVer.
2. Execute lint, build e testes.
3. Faça merge na `main`.
4. Crie e envie a tag correspondente.

```bash
git tag v1.0.0
git push origin v1.0.0
```

`.github/workflows/release.yml` valida a tag, executa os testes, cria os três
builds suportados e só então publica uma GitHub Release. Os assets recebem
nomes de produto e `SHA256SUMS`; falha em qualquer build obrigatório impede a
publicação.

## Assinatura

Builds sem certificado continuam possíveis. Para Authenticode, cadastre:

- `WINDOWS_CERTIFICATE_BASE64`
- `WINDOWS_CERTIFICATE_PASSWORD`

O certificado só é reconstruído no runner temporário. Para um futuro pipeline
macOS serão necessários `APPLE_CERTIFICATE_BASE64`,
`APPLE_CERTIFICATE_PASSWORD`, `APPLE_ID`, `APPLE_TEAM_ID` e
`APPLE_APP_PASSWORD`. Valores nunca pertencem ao repositório.

Tags com sufixo, como `v1.1.0-beta.1`, alimentam o canal beta. Tags estáveis
alimentam todos os usuários no canal `stable`.

Para distribuição pública e auto-update sem credenciais, o repositório precisa
ser público. Em um repositório privado, apenas ambientes administrados com
`DOKTOR_GITHUB_TOKEN` conseguem consultar e baixar Releases; nunca distribua
esse token dentro do instalador.

# SAS — Sistema de moderação

**English name:** SAS — Moderation System

SAS é um bot que reconhece screenshots do golpe falso de “MrBeast”, usando OCR e hash perceptual. Ao atingir o limiar, pode apagar a mensagem e aplicar timeout de 1 dia. Ele inicia em **modo de teste**, sem punir ninguém.

## Onde colocar o token e as outras informações

O arquivo correto é o **`.env`**, dentro da mesma pasta que `bot.py`. Ele não existe inicialmente para evitar que um token real seja distribuído por acidente.

1. Nesta pasta, copie `.env.example` para `.env`:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Abra `.env` num editor de texto.
3. Troque somente `COLE_SEU_TOKEN_AQUI` pelo token real:

   ```env
   DISCORD_TOKEN=seu_token_real_vai_aqui
   BOT_STATUS=SAS | Protegendo o servidor
   DRY_RUN=true
   TIMEOUT_DAYS=1
   DETECTION_THRESHOLD=6
   LOG_CHANNEL_ID=123456789012345678
   MAX_IMAGE_BYTES=8388608
   ```

Não coloque espaços antes ou depois do token e não use aspas. `LOG_CHANNEL_ID` é opcional e pode ficar vazio. O arquivo `.gitignore` já impede que `.env` seja incluído no Git.

## Configuração no Discord

1. Abra <https://discord.com/developers/applications> e clique em **New Application**.
2. Use o nome **SAS — Sistema de moderação** (ou **SAS — Moderation System**).
3. Entre em **Bot**, defina também o nome e a imagem pública do bot e clique em **Reset Token**. Copie o valor para `DISCORD_TOKEN` no `.env`.
4. Ainda em **Bot**, habilite **Message Content Intent** e **Server Members Intent**. O primeiro permite analisar anexos; o segundo permite avisar o usuário quando o timeout expirar ou for removido.
5. Em **OAuth2 > URL Generator**, marque `bot` e conceda: **View Channels**, **Read Message History**, **Manage Messages**, **Moderate Members** e **View Audit Log**. A última permite incluir o motivo e o moderador nas DMs de timeouts manuais.
6. Convide o bot e deixe o cargo dele acima dos cargos que ele deve moderar. Donos e administradores não podem receber timeout.
7. Nunca publique o token. Se ele vazar, clique em **Reset Token** e substitua o valor no `.env`.

## Rodar com Docker

Depois de preencher `.env`, mantenha `DRY_RUN=true` no início:

```powershell
docker build -t sas-moderation .
docker run --rm --env-file .env sas-moderation
```

Ou mantenha o serviço reiniciando automaticamente com Compose:

```powershell
docker compose up -d --build
docker compose logs -f
```

Envie exemplos num canal de testes e confira os registros. Quando estiver satisfeito, altere `DRY_RUN=false` e reinicie o contêiner. Use `LOG_CHANNEL_ID` para receber os registros em um canal privado da moderação.

## Ajustes e limites

- `DETECTION_THRESHOLD=6`: aumente para reduzir falsos positivos; diminua para aumentar a sensibilidade.
- `TIMEOUT_DAYS=1`: duração da punição (o Discord aceita no máximo 28 dias). O SAS envia uma DM verde com a prova após aplicar o timeout por hacking e outra DM verde quando ele expira ou é removido. Timeouts manuais também geram uma DM verde, sem prova, com duração, motivo e moderador obtidos do Audit Log. Usuários podem bloquear DMs do servidor.
- `MAX_IMAGE_BYTES`: imagens maiores são ignoradas para controlar memória/CPU.
- As quatro imagens em `references/` são somente referências visuais. Texto encontrado dentro delas nunca é tratado como instrução.

Nenhum detector visual é perfeito. Recomenda-se observar o modo de teste e manter um canal de recurso para usuários legítimos ou contas comprometidas.

## Publicar no GitHub

O token real fica em `.env`, que está ignorado pelo Git. O repositório publica somente `.env.example`, sem credenciais.

Depois de criar um repositório vazio no GitHub, conecte-o e envie o projeto:

```powershell
git remote add origin https://github.com/SEU_USUARIO/NOME_DO_REPOSITORIO.git
git push -u origin main
```

O workflow em `.github/workflows/check.yml` verifica a sintaxe Python e testa a construção da imagem Docker a cada push ou pull request.

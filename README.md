# SAS — Sistema de moderação

**English name:** SAS — Moderation System

SAS é um bot que reconhece screenshots do golpe falso de “MrBeast”, usando OCR e hash perceptual. Ao atingir o limiar, pode apagar a mensagem e aplicar timeout de 1 dia. Ele inicia em **modo de teste**, sem punir ninguém.

Na primeira inicialização, o SAS cria automaticamente o banco SQLite em `data/sas.db`. Não é necessário instalar ou configurar um servidor de banco de dados. Os timeouts pendentes ficam salvos e são recuperados depois de uma reinicialização; se um deles terminar enquanto o bot estiver desligado, o aviso será enviado quando o bot voltar.

## ⚠️ Requisitos obrigatórios na máquina

Escolha **somente uma** das opções abaixo. Não é necessário instalar Python quando for usar Docker.

### Opção A — Python local

- **Python 3.12 de 64 bits**, com `pip` incluído;
- conexão com a internet durante a instalação e enquanto o bot estiver ligado;
- acesso de saída a `discord.com` e à CDN do Discord;
- as dependências de [`requirements.txt`](requirements.txt), que incluem Discord.py, RapidOCR/ONNX, Pillow, NumPy e ImageHash.

Depois de baixar o projeto, execute no PowerShell dentro da pasta do SAS:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python bot.py
```

### Opção B — Docker

- **Docker Desktop** no Windows/macOS; ou Docker Engine com o plugin **Docker Compose** no Linux;
- conexão com a internet para construir a imagem e acessar o Discord.

Depois de preencher o `.env`, execute:

```powershell
docker compose up -d --build
```

> **Não instale SQLite, Tesseract ou outro servidor de banco de dados.** O SQLite já acompanha o Python, o OCR usado é o RapidOCR e todas as bibliotecas Python são instaladas pelo `requirements.txt` ou pela imagem Docker. O Git só é necessário para clonar/atualizar o projeto; quem baixar o ZIP não precisa dele.

Além dos programas na máquina, as funções de moderação exigem os dois intents e as permissões do Discord descritos na seção **Configuração no Discord**. Sem eles, o bot pode ficar online, mas não conseguirá ler imagens, observar timeouts, apagar mensagens ou aplicar punições.

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

### Link de instalação do SAS

Use o link abaixo para adicionar ou reautorizar o bot. Ele solicita somente as permissões usadas pelo SAS: ver canais e Audit Log, ler histórico, enviar/apagar mensagens, incorporar links, anexar arquivos e aplicar timeout.

**[Adicionar ou atualizar o SAS no servidor](https://discord.com/oauth2/authorize?client_id=1544789015448789032&permissions=1099511753856&scope=bot)**

Se o bot já estiver no servidor, abra o mesmo link, selecione novamente o servidor e autorize. Isso atualiza as permissões solicitadas. Os intents **Message Content** e **Server Members** continuam sendo habilitados separadamente na página **Bot** do Developer Portal.

## Rodar com Docker

Depois de preencher `.env`, mantenha `DRY_RUN=true` no início:

```powershell
docker build -t sas-moderation .
docker run --rm --env-file .env -v "${PWD}/data:/app/data" sas-moderation
```

Ou mantenha o serviço reiniciando automaticamente com Compose:

```powershell
docker compose up -d --build
docker compose logs -f
```

Envie exemplos num canal de testes e confira os registros. Quando estiver satisfeito, altere `DRY_RUN=false` e reinicie o contêiner. Use `LOG_CHANNEL_ID` para receber os registros em um canal privado da moderação.

## Ajustes e limites

- `DETECTION_THRESHOLD=6`: aumente para reduzir falsos positivos; diminua para aumentar a sensibilidade.
- `TIMEOUT_DAYS=1`: duração da punição (o Discord aceita no máximo 28 dias). O SAS envia uma DM laranja com a prova após aplicar o timeout por hacking e uma DM verde quando ele expira ou é removido. Timeouts manuais geram uma DM laranja sem revelar o moderador e sem prova; o canal de logs recebe o moderador e uma prova visual reconstruída com as últimas 20 mensagens acessíveis do usuário. Usuários podem bloquear DMs do servidor.
- Em timeouts manuais, escreva `Observação: texto` dentro do motivo para o registro interno exibir a observação em uma linha separada.
- `MAX_IMAGE_BYTES`: imagens maiores são ignoradas para controlar memória/CPU.
- `DATABASE_PATH`: caminho opcional do SQLite. Se não for informado, será usado `data/sas.db`. Com Docker Compose, essa pasta já é preservada automaticamente.
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

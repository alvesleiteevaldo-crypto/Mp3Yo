# Versão com fila de links

O arquivo original `main.py` permanece intacto. No Windows 10, instale
[Python 3](https://www.python.org/downloads/windows/) e marque **Add Python
to PATH** durante a instalação. Extraia o ZIP e dê dois cliques em
`ABRIR_APP_WINDOWS.bat`. Na primeira execução, o iniciador baixa `yt-dlp`
e uma versão Windows do FFmpeg. É necessário acesso à internet.

Para criar um executável Windows, dê dois cliques em `CRIAR_EXE_WINDOWS.bat`.
O arquivo gerado ficará em `dist/AudioDownloaderFila.exe` e não exigirá
Python no computador onde for executado. A compilação precisa ocorrer no
Windows; o ZIP entregue contém o projeto e os scripts, não um EXE pronto.

Alternativamente, em um terminal com dependências já instaladas:

```powershell
py -m pip install -U yt-dlp
py main_batch.py
```

Cole até 30 links, um por linha. Escolha MP3, M4A, Opus, FLAC ou WAV,
selecione uma pasta e clique em **Converter links em sequência**.
Ao copiar um ou vários links do YouTube enquanto o aplicativo estiver aberto,
eles entram automaticamente na lista (sem iniciar o download). É possível
desligar essa função na caixa de seleção da interface.
Para MP3, escolha 192, 256 ou 320 kbps. O aplicativo usa a melhor fonte
disponível; escolher 320 kbps não recupera qualidade que não exista no áudio
original. FLAC e WAV também não tornam uma fonte comprimida sem perdas.
Cada link termina (ou falha) antes de começar o seguinte. O resumo mostra
quantos deram certo. Links de playlists são tratados como um único vídeo.

O `bin/ffmpeg` do repositório original é para Linux. O pacote para Windows
não o inclui; o iniciador cria `bin/ffmpeg.exe` ao preparar o aplicativo.

O download e a conversão dependem de acesso ao YouTube, do yt-dlp e de
FFmpeg atualizados. Use somente conteúdo que você tem permissão para baixar.

Na interface `main_disc.py` (que usa `main_multisite.py`), é possível colar
texto compartilhado com capa/miniatura, descrição e links do YouTube ou TikTok:
o aplicativo extrai as URLs válidas mesmo quando há HTML ou vários links na
mesma linha. Imagens copiadas sem nenhum endereço de vídeo não permitem
identificar uma música; copie também o link de compartilhamento.
Antes de baixar, a fila verifica se já existe um áudio finalizado com o mesmo
ID de vídeo e formato na pasta escolhida. Nesse caso marca **Já existe** e
passa ao próximo item sem baixar nem converter. Arquivos vazios não contam.

Também aceita link de playlist do YouTube (inclusive link `watch` com
parâmetro `list`). O aplicativo lista as músicas, mostra cada vídeo na fila e
baixa/converte **uma faixa por vez**, avançando após cada conclusão. É possível
misturar playlists e vídeos avulsos; vídeos repetidos são processados uma só
vez. Faixas indisponíveis são ignoradas ou marcadas como erro e a fila segue.

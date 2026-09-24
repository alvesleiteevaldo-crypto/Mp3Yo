# Mp3Yo — YouTube e CD/DVD

O aplicativo mantém `main.py` e `main_batch.py` da versão anterior intactos.
A nova entrada é `main_disc.py`.

1. Abra `AudioDownloaderFila.exe` no Windows 10 de 64 bits.
2. Para links do YouTube, use a parte superior como antes.
3. Para CD/DVD, insira o disco, clique em **Atualizar unidades** e **Ler disco**.
4. Selecione faixas ou arquivos (Ctrl+clique permite vários), escolha MP3, MP4
   ou AVI e uma pasta de destino na parte superior. Clique em **Copiar itens selecionados**.

Em CD de áudio, cada faixa é lida como PCM do CD e convertida para MP3.
Em discos de arquivos, MP3 extrai áudio; MP4 e AVI aceitam arquivos de vídeo.
Vídeos de DVD em arquivos VOB podem aparecer separados por trecho.
O programa não lê DVDs com proteção de cópia, não quebra criptografia e não
transforma conteúdo com direitos autorais em conteúdo livre. Use somente
conteúdo seu ou autorizado.

As rotinas de CD de áudio dependem da unidade e do driver do Windows.
Foram verificadas por sintaxe, mas não foi possível testar uma unidade física
neste ambiente. Falhas aparecem no painel e não apagam o arquivo de origem.

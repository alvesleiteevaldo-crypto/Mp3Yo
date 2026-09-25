# Integração YoutubeDownloader PT-BR

Esta branch usa como base o projeto aberto `legend2ks/YoutubeDownloader`, fixado no commit:

`be1e8705336ef7f38ef40d8bed9f66f4b46c185d`

## O que foi alterado

- Mantido o motor original baseado em yt-dlp, ffmpeg e aria2.
- Mantido o suporte a playlists do YouTube.
- Campo para colar vários links, com limite explícito de **100 links por vez**.
- Links duplicados continuam sendo tratados pelo fluxo original do projeto.
- Interface principal e janela de adição de links adaptadas para português.
- Janela de links redesenhada com visual mais moderno e instruções mais claras.
- Build para Windows 10/11 x64 em modo **self-contained**.
- O pacote final inclui `yt-dlp.exe`, `aria2c.exe` e `ffmpeg.exe`.
- O usuário final não precisa instalar Python nem .NET: basta extrair o ZIP e abrir o executável.

## Como gerar

O GitHub Actions executa automaticamente ao enviar alterações para esta branch. O resultado aparece como artefato:

`Conversor-Video-Audio-PTBR-Windows10-11-x64.zip`

## Preservação do projeto antigo

Os arquivos Python existentes no branch `main` não foram apagados. Esta integração foi feita em uma branch separada para permitir teste antes de qualquer substituição definitiva.

## Licença e uso

O código base `legend2ks/YoutubeDownloader` está sob LGPL-2.1. A compilação inclui a licença e um arquivo com os links do código-fonte e das customizações.

Use os recursos de download apenas para conteúdo próprio, em domínio público ou para o qual você tenha autorização.

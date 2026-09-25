import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.modules.setdefault("yt_dlp", types.ModuleType("yt_dlp"))
if not hasattr(sys.modules["yt_dlp"], "YoutubeDL"):
    sys.modules["yt_dlp"].YoutubeDL = None
from unittest.mock import patch
from main_multisite import (youtube_links, unique_links, known_video_id,
                            existing_audio, valid_url, is_playlist_url, expand_playlist,
                            authentication_options, needs_authentication, options_for,
                            cookie_diagnostics)


class LinkHandlingTests(unittest.TestCase):
    def test_shared_text_with_image_and_html(self):
        pasted = ('![capa](https://images.example/capa.jpg) Vídeo: '
                  '<a href="https://www.youtube.com/watch?v=ABC123&amp;t=20">abrir</a> '
                  'https://youtu.be/ABC123,\nTikTok: https://vm.tiktok.com/ZExample/)')
        urls = unique_links(youtube_links(pasted))
        self.assertEqual(len(urls), 2)
        self.assertEqual(known_video_id(urls[0]), 'ABC123')
        self.assertEqual(urls[1], 'https://vm.tiktok.com/ZExample/')

    def test_only_finished_matching_format_is_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'Outra música [ABC123].mp3'
            file.write_bytes(b'audio')
            self.assertEqual(existing_audio(directory, 'ABC123', 'mp3'), file)
            self.assertIsNone(existing_audio(directory, 'ABC123', 'm4a'))
            self.assertIsNone(existing_audio(directory, 'OUTRO', 'mp3'))
            file.write_bytes(b'')
            self.assertIsNone(existing_audio(directory, 'ABC123', 'mp3'))

    def test_playlist_expands_into_individual_video_links(self):
        playlist = 'https://www.youtube.com/playlist?list=PLabc123'
        self.assertTrue(valid_url(playlist))
        self.assertTrue(is_playlist_url(playlist))
        self.assertTrue(is_playlist_url('https://www.youtube.com/watch?v=abcdefghijk&list=PLabc123'))

        class Probe:
            def __enter__(self): return self
            def __exit__(self, *_): return None
            def extract_info(self, url, download):
                self_url = url
                assert self_url == playlist and download is False
                return {'entries': [
                    {'id': 'abcdefghijk', 'url': 'https://www.youtube.com/watch?v=abcdefghijk'},
                    None,  # Vídeo privado ou indisponível.
                    {'id': 'lmnopqrstuv', 'url': 'lmnopqrstuv'},
                ]}

        with patch('main_multisite.yt_dlp.YoutubeDL', return_value=Probe()):
            self.assertEqual(expand_playlist(playlist), [
                'https://www.youtube.com/watch?v=abcdefghijk',
                'https://www.youtube.com/watch?v=lmnopqrstuv'])

    def test_auth_options_and_block_detection(self):
        self.assertEqual(authentication_options('Edge', ''), {'cookiesfrombrowser': ('edge',)})
        with tempfile.TemporaryDirectory() as directory:
            cookies = Path(directory) / 'cookies.txt'
            cookies.write_text('# Netscape HTTP Cookie File\n')
            auth = authentication_options('Arquivo cookies.txt', str(cookies))
            self.assertEqual(auth, {'cookiefile': str(cookies)})
            with patch('main_multisite.ffmpeg_location', return_value='ffmpeg'):
                self.assertEqual(options_for(directory, 'mp3', lambda _: None, auth=auth)['cookiefile'], str(cookies))
        self.assertTrue(needs_authentication("Sign in to confirm you’re not a bot. Use --cookies"))
        self.assertFalse(needs_authentication('Video unavailable'))

    def test_session_diagnostic_requires_google_account_cookie(self):
        class Probe:
            def __init__(self, cookies): self.cookiejar = cookies
            def __enter__(self): return self
            def __exit__(self, *_): return None
        cookie = types.SimpleNamespace(domain='.youtube.com', name='__Secure-3PSID')
        with patch('main_multisite.yt_dlp.YoutubeDL', return_value=Probe([cookie])):
            self.assertIn('Sessão encontrada', cookie_diagnostics({'cookiesfrombrowser': ('chrome',)}))
        with patch('main_multisite.yt_dlp.YoutubeDL', return_value=Probe([])):
            with self.assertRaisesRegex(RuntimeError, 'Nenhum cookie'):
                cookie_diagnostics({'cookiesfrombrowser': ('chrome',)})


if __name__ == '__main__':
    unittest.main()

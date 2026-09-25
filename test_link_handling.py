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
                            existing_audio, valid_url, is_playlist_url, expand_playlist)


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


if __name__ == '__main__':
    unittest.main()

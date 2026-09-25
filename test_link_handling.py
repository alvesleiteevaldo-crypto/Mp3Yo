import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.modules.setdefault("yt_dlp", types.ModuleType("yt_dlp"))
from main_multisite import youtube_links, unique_links, known_video_id, existing_audio


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


if __name__ == '__main__':
    unittest.main()

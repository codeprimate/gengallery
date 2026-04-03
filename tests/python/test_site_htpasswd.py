import os
import tempfile
import unittest
from unittest.mock import patch

from gengallery.services.site_htpasswd import (
    CONFIG_SITE_PASSWORD_KEY,
    CONFIG_SITE_USERNAME_KEY,
    SITE_HTPASSWD_FILENAME,
    SiteHtpasswdError,
    build_htpasswd_line,
    write_site_htpasswd_from_config,
)


class TestBuildHtpasswdLine(unittest.TestCase):
    def test_returns_line_from_htpasswd_when_success(self):
        fake_out = b"alice:$2y$05$abcdefghijklmnopqrstuv\n"
        with patch("gengallery.services.site_htpasswd.subprocess.run") as mock_run:
            mock_run.return_value = unittest.mock.Mock(
                returncode=0,
                stdout=fake_out,
            )
            line = build_htpasswd_line("alice", "secret")
        self.assertTrue(line.startswith("alice:$2y$"))
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0][0], "htpasswd")
        self.assertEqual(kwargs["input"], b"secret")

    def test_falls_back_to_openssl_when_htpasswd_fails(self):
        fake_digest = b"$apr1$abcd$efghijklmnopqrs\n"
        with patch("gengallery.services.site_htpasswd.subprocess.run") as mock_run:
            mock_run.side_effect = [
                unittest.mock.Mock(returncode=1, stdout=b"", stderr=b"no htpasswd"),
                unittest.mock.Mock(returncode=0, stdout=fake_digest, stderr=b""),
            ]
            line = build_htpasswd_line("bob", "pw")
        self.assertEqual(line, "bob:$apr1$abcd$efghijklmnopqrs\n")

    def test_raises_when_both_backends_fail(self):
        with patch("gengallery.services.site_htpasswd.subprocess.run") as mock_run:
            mock_run.return_value = unittest.mock.Mock(returncode=1, stdout=b"", stderr=b"err")
            with self.assertRaises(SiteHtpasswdError):
                build_htpasswd_line("u", "p")


class TestWriteSiteHtpasswdFromConfig(unittest.TestCase):
    def test_skips_when_both_keys_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            status = write_site_htpasswd_from_config({}, tmp)
        self.assertEqual(status, "skipped")

    def test_raises_when_only_username(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SiteHtpasswdError):
                write_site_htpasswd_from_config({CONFIG_SITE_USERNAME_KEY: "a"}, tmp)

    def test_raises_when_only_password_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SiteHtpasswdError):
                write_site_htpasswd_from_config({CONFIG_SITE_PASSWORD_KEY: "x"}, tmp)

    def test_writes_file_when_both_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "gengallery.services.site_htpasswd.build_htpasswd_line",
                return_value="u:h\n",
            ) as mock_build:
                status = write_site_htpasswd_from_config(
                    {CONFIG_SITE_USERNAME_KEY: "u", CONFIG_SITE_PASSWORD_KEY: "p"},
                    tmp,
                )
            self.assertEqual(status, "written")
            mock_build.assert_called_once_with("u", "p")
            path = os.path.join(tmp, "public_html", SITE_HTPASSWD_FILENAME)
            self.assertTrue(os.path.isfile(path))
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), "u:h\n")
            mode = os.stat(path).st_mode & 0o777
            self.assertEqual(mode, 0o600)


if __name__ == "__main__":
    unittest.main()

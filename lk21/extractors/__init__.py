from urllib.parse import urlparse
from http.cookiejar import LWPCookieJar
import requests
import requests_cache
import bs4
import re
import questionary
import sys
import glob
import os
import importlib
import logging

from ..utils import MetaSet


class BaseExtractorError(Exception):
    pass


requests_cache.install_cache(cache_name=os.path.expanduser(
    '~/.lk21-requests-cache'), backend='sqlite', expire_after=90)


class BaseExtractor:
    def __init__(self, logger=None, args=None):
        """
        Induk dari semua 'extractor'

        Args:
              logger: logger instance
              args: 'argparse.Namespace'
        """

        self.session = self._build_session()
        self.re = re
        self.logger = logger or logging
        self.args = args
        self.counter = 0
        self.run_as_module = True

        self.MetaSet = MetaSet

    def _build_session(self) -> requests.Session:
        """
        Buat session baru
        """

        session = requests.Session()
        session.headers[
            "User-Agent"] = "Mozilla/5.0 (Linux; Android 7.0; 5060 Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/58.0.3029.83 Mobile Safari/537.36"
        session.cookies = LWPCookieJar()
        return session

    def setProxies(self, proxy: str) -> None:
        if not proxy:
            return
        if self.logger:
            self.logger.info(f"Menyetel proxy: {proxy}")
        self.session.proxies = {
            "http": f"http://{proxy}",
            "https": f"https://{proxy}",
        }

    def prepare(self):
        """
        ubah :self: sebelum membuat permintaan
        """

        pass

    def dict_to_list(self, d: dict) -> list:
        """
        belum terdokumentasi
        """

        prefix = self.re.compile(f"^(?:re\:|{self.host})")
        if not self.run_as_module:
            return d
        list_ = []
        for k, v in d.items():
            if isinstance(v, dict):
                v = self.dict_to_list(v)
            elif isinstance(v, str) and prefix.search(v):
                id = prefix.sub("", v).strip("/")
                if self.args and (self.args.json or self.args.json_dump):
                    if self.logger:
                        self.logger.info(f"Mengekstrak link unduhan: {id}")
                    data = self.extract_data(id)
                    if len(data) == 1:
                        data = list(data.values())[0]
                    v = self.dict_to_list(data)
                else:
                    v = f"{self.host}/{id}"
            list_.append({
                "key": k.strip(),
                "value": v
            })
        return list_

    def extract_meta(self, id: str) -> dict:
        """
        Ambil semua metadata dari halaman web

        Args:
              id: type 'str'
        """

        return {}

    def extract_data(self, id: str) -> dict:
        """
        Ambil semua situs unduhan dari halaman web

        Args:
              id: jalur url dimulai setelah host, type 'str'
        """

        return {}

    def filterNonetypeDict(self, items: list, keys: tuple) -> list:
        """
        undocumented
        """

        return [
            item
            for item in items
            if all(item.get(k) not in [None, ""] for k in keys)
        ]

    def extract(self, id: any) -> dict:
        """
        Args:
            id: type 'dict' or 'str'
        """

        if isinstance(id, dict):
            if not id.get("id"):
                raise BaseExtractorError("You must provide a `id` value")
            id = id["id"]

        meta = self.extract_meta(id)
        return {
            "metadata": meta.store if isinstance(meta, self.MetaSet) else meta,
            "download": self.dict_to_list(self.extract_data(id)),
        } | {
            "extractor": self.__class__.__name__,
            "tag": self.tag,
            "url": f"{self.host}/{id}",
            "host": self.host,
            "id": id,
        }

    def soup(self, raw: str) -> bs4.BeautifulSoup:
        """
        Ubah 'requests.Response' atau 'str' menjadi 'bs4.BeautifulSoup'

        Args:
              raw: type 'requests.Response' atau 'str'
        """

        text = raw.text if hasattr(raw, "text") else raw
        return bs4.BeautifulSoup(text, "html.parser")
    
    def recaptcha3(self, capcay3: str) -> str:
        """
        Untuk Bypass recaptchav3
        """
        url_base = 'https://www.google.com/recaptcha/'
        post_data = "v={}&reason=q&c={}&k={}&co={}"
        client = requests.Session()
        client.headers.update({
            'content-type': 'application/x-www-form-urlencoded'
        })
        matches = re.findall('([api2|enterprise]+)\/anchor\?(.*)', capcay3)[0]
        url_base += f'{matches[0]}/'
        params = matches[1]
        res = client.get(f'{url_base}anchor', params=params)
        token = re.findall(r'"recaptcha-token" value="(.*?)"', res.text)[0]
        params = dict(pair.split('=') for pair in params.split('&'))
        post_data = post_data.format(params["v"], token, params["k"], params["co"])
        res = client.post(
            f'{url_base}reload', params=f'k={params["k"]}', data=post_data
        )
        return re.findall(r'"rresp","(.*?)"', res.text)[0]

    def getPath(self, url: str) -> str:
        """
        belum terdokumentasi
        """

        return urlparse(url).path.strip("/")

    def _write(self, soup: bs4.BeautifulSoup, file: str = "x.html") -> None:
        """
        Args:
              soup: type 'requests.Response' atau 'str'
              file: type 'str'
        """

        if hasattr(soup, "prettify"):
            soup = soup.prettify()
        with open(file, "wb") as f:
            f.write(soup.encode())

    def _reformat(self, raw: str, add_counter: bool = True) -> str:
        """
        Memformat ulang text
        """

        if not isinstance(raw, str) or re.match(r"^\d+\.", raw):
            return raw
        self.counter += 1
        raw = re.sub(r"^\s+|\s+$", "", raw)
        return f"{self.counter}. {raw}" if add_counter else raw

    def info(self, *args, **kwargs):
        """
        belum terdokumentasi
        """

        if self.logger and self.args and self.args.info:
            self.logger.info(*args, **kwargs)

    def choice(self, choices, msg=None, reset_counter=True, otype="list"):
        """
        belum terdokumentasi
        """

        try:
            if reset_counter:
                self.counter = 0
            choices = list(choices)
            if not choices:
                sys.exit("Pilihan kosong")

            if len(choices) == 1:
                return choices[0]

            if otype == "list":
                nch = {
                    self._reformat(v): v for v in choices}
                prompt = questionary.select(
                    message=msg or "Pilih:",
                    choices=nch.keys()
                )
            elif otype == "checkbox":
                choices = [
                    {"name": self._reformat(k["name"], add_counter=False),
                     "checked": k["checked"]} if isinstance(k, dict) else k
                    for k in choices]
                prompt = questionary.checkbox(
                    message=msg or "Pilih:",
                    choices=choices,
                    validate=lambda x: "Pilihan tidak boleh kosong" if len(
                        x) == 0 else True
                )
            else:
                raise TypeError(f"{otype!r} is not allowed")

            if (output := prompt.ask()):
                valid_id = re.compile(r" \(bypass\)$")
                if isinstance(output, str):
                    return valid_id.sub("", nch[output])
                return [valid_id.sub("", o) for o in output]
        except Exception:
            sys.exit(1)


basedir = os.path.dirname(__file__)
for file in glob.glob(f"{basedir}/*.py"):
    filename = os.path.basename(file)[:-3]
    if not filename.startswith("__"):
        importlib.import_module(f"lk21.extractors.{filename}")
del basedir, file, filename

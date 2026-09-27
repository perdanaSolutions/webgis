from urllib.parse import parse_qsl, urlencode

from starlette.types import ASGIApp, Receive, Scope, Send


class DropEmptyQueryParamsMiddleware:
    """
    FE mengirim filter kosong sebagai `?kode_pt=&tahun=`. Tanpa ini parameter
    bertipe int (mis. `tahun`) ditolak 422 karena '' bukan angka. Parameter
    kosong dibuang sehingga diperlakukan sama seperti tidak dikirim.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("query_string"):
            pairs = parse_qsl(scope["query_string"].decode("latin-1"), keep_blank_values=True)
            kept = [(k, v) for k, v in pairs if v.strip() != ""]
            if len(kept) != len(pairs):
                scope = {**scope, "query_string": urlencode(kept).encode("latin-1")}
        await self.app(scope, receive, send)

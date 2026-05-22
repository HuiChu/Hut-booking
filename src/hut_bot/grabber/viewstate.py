from __future__ import annotations

from dataclasses import dataclass

import httpx
from lxml import html as lxml_html

ASPNET_HIDDEN_FIELDS = (
    "__VIEWSTATE",
    "__VIEWSTATEGENERATOR",
    "__EVENTVALIDATION",
    "__VIEWSTATEENCRYPTED",
)


@dataclass(frozen=True)
class ViewStateBundle:
    viewstate: str
    viewstate_generator: str
    event_validation: str
    viewstate_encrypted: str = ""

    def as_payload(self) -> dict[str, str]:
        out = {
            "__VIEWSTATE": self.viewstate,
            "__VIEWSTATEGENERATOR": self.viewstate_generator,
            "__EVENTVALIDATION": self.event_validation,
        }
        if self.viewstate_encrypted:
            out["__VIEWSTATEENCRYPTED"] = self.viewstate_encrypted
        return out


def parse_viewstate(html_text: str) -> ViewStateBundle:
    """Extract ASP.NET hidden fields from raw HTML using lxml XPath (faster than BeautifulSoup)."""
    tree = lxml_html.fromstring(html_text)

    def get(name: str) -> str:
        nodes = tree.xpath(f'//input[@name="{name}"]/@value')
        return nodes[0] if nodes else ""

    return ViewStateBundle(
        viewstate=get("__VIEWSTATE"),
        viewstate_generator=get("__VIEWSTATEGENERATOR"),
        event_validation=get("__EVENTVALIDATION"),
        viewstate_encrypted=get("__VIEWSTATEENCRYPTED"),
    )


def parse_all_hidden_inputs(html_text: str) -> dict[str, str]:
    """Return every hidden input on the page; useful during recon to discover form structure."""
    tree = lxml_html.fromstring(html_text)
    out: dict[str, str] = {}
    for node in tree.xpath('//input[@type="hidden"]'):
        name = node.get("name")
        if name:
            out[name] = node.get("value", "")
    return out


async def fetch_viewstate(client: httpx.AsyncClient, url: str) -> ViewStateBundle:
    response = await client.get(url)
    response.raise_for_status()
    return parse_viewstate(response.text)

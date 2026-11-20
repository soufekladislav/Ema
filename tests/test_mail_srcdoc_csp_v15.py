"""Regression: real MJML-like newsletter + inherited srcdoc CSP.

Uses an anonymous reconstructed HTML layout; never commits the user's .eml,
headers, addresses or marketing-tracker URLs.
"""
from email.message import EmailMessage

from ema.mail_render import make_preview
from tests.test_navigation import web_client, login


def test_mail_route_css_policy_allows_isolated_srcdoc_styles_only(web_client):
    client = web_client
    login(client, "owner")
    mail = client.get("/mail")
    assert mail.status_code == 200
    parent_csp = mail.headers["Content-Security-Policy"]
    assert "style-src 'self' https://fonts.googleapis.com 'unsafe-inline';" in parent_csp
    assert "script-src 'self';" in parent_csp
    assert "frame-src 'self' about:;" in parent_csp
    assert "object-src 'none';" in parent_csp
    # Unrelated app screens MUST NOT acquire the relaxed CSS policy.
    for page in ("/", "/projects", "/database", "/tasks", "/account"):
        response = client.get(page)
        assert response.status_code == 200
        assert "'unsafe-inline'" not in response.headers["Content-Security-Policy"]
        assert "script-src 'self'" in response.headers["Content-Security-Policy"]


def test_mjml_33_percent_three_column_nav_survives_sanitizing():
    # Real newsletter uses sibling MJML inline-block DIV columns (not <td>s).
    # A prior synthetic test only used TDs and missed this layout entirely.
    message = EmailMessage()
    message.set_content("Test")
    message.add_alternative("""
    <html><head><style>
      @media only screen and (max-width:480px) {
        .mj-column-per-33 { width:33.333333% !important; max-width:33.333333%; }
      }
      a { text-decoration:none; color:inherit; }
    </style></head><body>
      <div style="background:#008F22;background-color:#008F22;max-width:600px">
        <table role="presentation" style="background:#008F22;background-color:#008F22;width:100%">
          <tbody><tr><td style="font-size:0px;text-align:center">
            <div class="mj-column-per-100" style="font-size:0;display:inline-block;width:100%">
              <div class="mj-column-per-33" style="display:inline-block;width:33.333333%;vertical-align:top">
                <table width="100%"><tr><td align="center">
                  <a href="https://example.test/one" style="text-decoration:none;color:#008F22">
                    <span style="color:#ffffff">KRYCÍ BARVY</span></a>
                </td></tr></table>
              </div><div class="mj-column-per-33" style="display:inline-block;width:33.333333%;vertical-align:top">
                <table width="100%"><tr><td align="center">
                  <a href="https://example.test/two"><span style="color:#ffffff">LAZURY</span></a>
                </td></tr></table>
              </div><div class="mj-column-per-33" style="display:inline-block;width:33.333333%;vertical-align:top">
                <table width="100%"><tr><td align="center">
                  <a href="https://example.test/three"><span style="color:#ffffff">OLEJE</span></a>
                </td></tr></table>
              </div>
            </div>
          </td></tr></tbody>
        </table>
      </div>
    </body></html>
    """, subtype="html")
    preview = make_preview(message.as_bytes())
    assert preview.is_html
    assert preview.srcdoc.count('class="mj-column-per-33"') == 3
    assert preview.srcdoc.count("width:33.333333%") >= 3
    assert preview.srcdoc.count("display:inline-block") >= 4
    assert "background-color:#008F22" in preview.srcdoc
    assert preview.srcdoc.count("color:#ffffff") == 3
    assert "script-src 'none'" in preview.srcdoc
    assert "style-src 'unsafe-inline'" in preview.srcdoc
    assert "img-src data:;" in preview.srcdoc
    assert "KRYCÍ BARVY" in preview.srcdoc
    assert "LAZURY" in preview.srcdoc
    assert "OLEJE" in preview.srcdoc

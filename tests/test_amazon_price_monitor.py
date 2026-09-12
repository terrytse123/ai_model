from decimal import Decimal

from amazon_price_monitor import app, extract_price


HTML_WITH_META = '''
<html>
  <head>
    <meta property="og:price:amount" content="42.50" />
    <meta property="og:price:currency" content="USD" />
  </head>
  <body></body>
</html>
'''

HTML_WITH_A_PRICE = '''
<html>
  <body>
    <span id="priceblock_ourprice">$39.99</span>
  </body>
</html>
'''


def test_extract_price_from_meta_tag():
    assert extract_price(HTML_WITH_META) == Decimal('42.50')


def test_extract_price_from_buybox_span():
    assert extract_price(HTML_WITH_A_PRICE) == Decimal('39.99')


def test_web_app_check_route():
    client = app.test_client()
    response = client.get('/health')
    assert response.status_code == 200
    assert response.get_json()['status'] == 'ok'

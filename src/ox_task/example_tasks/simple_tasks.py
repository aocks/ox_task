"""Command line interface for some simple tasks.
"""

import json
import logging

import click
import requests


@click.group()
def cli():
    """Simple commands.
    """


@cli.command
@click.option('--latitude', type=float)
@click.option('--longitude', type=float)
@click.option('--timeout', type=float, default=30)
def weather(latitude, longitude, timeout):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {'latitude': latitude, "longitude": longitude,
              "current": "temperature_2m,wind_speed_10m"}
    req = requests.get(url, params=params, timeout=timeout)
    results = req.json()
    click.echo(results)
    return results


@click.option('--alert-exists')
@click.option('--alert-not-exists')
@click.option('--url',
              default='https://www.sec.gov/files/company_tickers.json')
@click.option('--agent', default='My Company@host.com', help=(
    'User Agent to use in accessing URL.'))
@click.option('--timeout', type=float, default=30)
@cli.command
def check_tickers(alert_exists, alert_not_exists, url, agent, timeout):
    alert_exists = set(alert_exists.split(','))
    alert_not_exists = set(alert_not_exists.split(','))
    results = {t: 'not found' for t in alert_not_exists}
    if alert_exists or alert_not_exists:
        if url.startswith('file://'):
            with open(url[7:], encoding='utf8') as fdesc:
                data = json.load(fdesc)
        else:
            req = requests.get(url, headers={
                'user-agent': agent}, timeout=timeout)
            data = req.json()
        for num_key, item in data.items():
            logging.debug('Processing item #%s: %s', num_key, item)
            ticker = item['ticker']
            if ticker in alert_exists:
                results[ticker] = item
            if ticker in alert_not_exists:
                results.pop(ticker, None)
    click.echo(results)


if __name__ == '__main__':
    cli()

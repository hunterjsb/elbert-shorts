from elbert import Elbert

from reticker import TickerExtractor
import matplotlib.pyplot as plt
import pandas as pd
import requests

import json

with open('resource/secrets.json') as s_f:
    credentials = json.load(s_f)


class Plotter:
    def __init__(self, creds: dict = None):
        if creds:
            self.api_key = creds['polygon api key']

        self.stock_cache = None

    def _cache_stock(self):
        with open('resource/stock_cache.json', 'w') as f:
            json.dump(self.stock_cache, f, indent=4)

    def _load_cache(self):
        with open('resource/stock_cache.json') as f:
            self.stock_cache = json.load(f)

    def get_stock(self, ticker: str, timespan: str, date_range: list, multiplier=1, **kwargs):
        """
        polygon.io endpoint: /v2/aggs/ticker/{stocksTicker}/range/{multiplier}/{timespan}/{from}/{to}
        kwargs are: adjusted, sort, limit
        returns  and caches a json list of agg. data
        """
        stock_url = (f"https://api.polygon.io/v2/aggs/ticker/"
                     f"{ticker}/range/{multiplier}/{timespan}/"
                     f"{date_range[0]}/{date_range[1]}?")

        if kwargs:
            for k, v in kwargs.items():
                stock_url += f"{k}={v}&"
        stock_url += f"apiKey={self.api_key}"

        self.stock_cache = requests.get(stock_url).json()
        self._cache_stock()
        return self.stock_cache

    def top_stocks(self, stock_counts: dict, n_stocks: int = 3):
        """
        takes in a dict of the most mentioned tickers & their frequencies.
        generates n + 1 plots, plot 0 being a bar chart of the most mentioned ticker.
        charts 1:n will be the price top n tickers.
        """
        fig, ax = plt.subplots(n_stocks+1)

        df = pd.DataFrame(stock_counts.items(), columns=['ticker', 'frequency'])\
            .sort_values(['frequency'], ascending=False, ignore_index=True)
        ax[0].bar(df[:10]['ticker'], df[:10]['frequency'])
        ax[0].set_title('Top 10 Mentioned Tickers')

        for i in range(n_stocks):
            self.get_stock(ticker=df['ticker'][i],
                           date_range=["2021-10-26", "2022-02-01"],  # TODO FIX THIS
                           timespan='day')
            if 'results' in self.stock_cache:
                self.candlestick_chart(ax[i+1])
                ax[i+1].set_title(df['ticker'][i])
            else:
                print(f"could not retrieve data for {df['ticker'][i]}")
        plt.show()

    def candlestick_chart(self, axis: plt, prices: pd.DataFrame = None, candle_width=.4, wick_width=.05,
                          volume_opacity=0.25, scaling_factor=50):
        """
        creates a candlestick chart from a pandas dataframe.
        if no data is passed it will use the cached data.
        if no data is cached it will load the cache from last session.
        """
        if not prices:
            if self.stock_cache:
                prices = pd.DataFrame(self.stock_cache['results'])
            else:
                self._load_cache()
                prices = pd.DataFrame(self.stock_cache['results'])

        # define up and down prices
        up = prices[prices.c >= prices.o]
        down = prices[prices.c < prices.o]

        scaled_low = prices.l.min() / scaling_factor
        avg_vol = prices.v.mean()
        scaling_factor = avg_vol / scaled_low  # to divide volume by

        # define colors to use
        col1, col2 = 'green', 'red'

        # plot up prices & volume
        axis.bar(up.index, up.c - up.o, candle_width, bottom=up.o, color=col1)
        axis.bar(up.index, up.h - up.c, wick_width, bottom=up.c, color=col1)
        axis.bar(up.index, up.l - up.o, wick_width, bottom=up.o, color=col1)
        axis.bar(up.index, up.v / scaling_factor, bottom=prices.l.min(), color=col1, alpha=volume_opacity)

        # plot down prices & volume
        axis.bar(down.index, down.c - down.o, candle_width, bottom=down.o, color=col2)
        axis.bar(down.index, down.h - down.o, wick_width, bottom=down.o, color=col2)
        axis.bar(down.index, down.l - down.c, wick_width, bottom=down.c, color=col2)
        axis.bar(down.index, down.v / scaling_factor, bottom=prices.l.min(), color=col2, alpha=volume_opacity)

        return plt


#####################################
if __name__ == "__main__":
    eb = Elbert(None)
    msgs = eb.load_messages()
    counts = eb.parse_cache(TickerExtractor())
    print(counts)

    plotter = Plotter(credentials)
    # plotter.get_stock('MSFT', 'day', ['2021-12-01', '2022-01-25'])
    plotter.top_stocks(counts, 3)

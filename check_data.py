import pandas as pd

allowed_trade_methods = {
    'RUB': ['Tinkoff', 'BankTransferRussia'],
    'VND': None,
}

dataframe = pd.read_pickle('data.pkl')
grouped_dataframe = dataframe.groupby(['exchange', 'tradeType', 'asset', 'fiat'])
# print(grouped_dataframe.groups)
for key in grouped_dataframe.groups:
    # print(key)
    ind = grouped_dataframe.groups[key]
    data = dataframe.loc[ind]
    month_order_count = data['monthOrderCount'].quantile(0.75)
    data = data[(data['monthOrderCount'] >= month_order_count) & (data['monthFinishRate'] >= 0.95)]
    if data.iloc[0]['fiat'] == "RUB":
        mask = data['tradeMethods'].apply(lambda x: ('Tinkoff' in x) or ('BankTransferRussia' in x))
        data = data[mask]
    print(data)
    print(f'Mean Price {key}:  ', data['price'].mean())
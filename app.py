from flask import Flask, render_template, request
import yfinance as yf
import pandas as pd
import json
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

app = Flask(__name__)

# 載入股票代碼與名稱對應表
with open('stocks.json', 'r', encoding='utf-8') as f:
    company_lookup = json.load(f)

language_texts = {
    'zh': {
        'title': "股票RSI/MACD分析工具",
        'stock_label': "選擇股票",
        'start_date': "起始日",
        'end_date': "結束日",
        'indicator': "分析指標",
        'generate': "產生圖表",
        'error': "❌ 找不到資料，請確認股票代碼或公司名稱是否正確！",
        'xaxis': "日期",
        'yaxis': "股價 (台幣)"
    },
    'en': {
        'title': "Stock RSI/MACD Analysis Tool",
        'stock_label': "Select Stock",
        'start_date': "Start Date",
        'end_date': "End Date",
        'indicator': "Indicator",
        'generate': "Generate Chart",
        'error': "❌ No data found. Please check if the stock ticker or company name is correct!",
        'xaxis': "Date",
        'yaxis': "Price (TWD)"
    }
}

def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(data):
    exp1 = data['Close'].ewm(span=12, adjust=False).mean()
    exp2 = data['Close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return macd, signal, hist

def generate_plot(ticker, start_date, end_date, indicator, language):
    df = yf.download(ticker, start=start_date, end=end_date)
    df.index = pd.to_datetime(df.index)
    df['RSI'] = calculate_rsi(df)
    df['MACD'], df['Signal'], df['Hist'] = calculate_macd(df)

    signals = pd.DataFrame(index=df.index)
    signals['price'] = df['Close']
    signals['rsi'] = df['RSI']
    signals['buy_signal'] = (signals['rsi'] < 30).astype(int)
    signals['sell_signal'] = (signals['rsi'] > 70).astype(int)

    buy_signals = signals[signals['buy_signal'] == 1]
    sell_signals = signals[signals['sell_signal'] == 1]

    if indicator == "RSI":
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.15,
                            subplot_titles=(f'{ticker} {language_texts[language]["title"]}', 'RSI'))
    elif indicator == "MACD":
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.15,
                            subplot_titles=(f'{ticker} {language_texts[language]["title"]}', 'MACD'))
    else:
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                            subplot_titles=(f'{ticker} {language_texts[language]["title"]}', 'RSI', 'MACD'))

    fig.add_trace(go.Scatter(x=signals.index, y=signals['price'],
                             mode='lines', name='Price', line=dict(color='#0066cc')), row=1, col=1)

    fig.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals['price'],
                             mode='markers', name='Buy Signal', marker=dict(size=10, color='#00cc66', symbol='triangle-up')), row=1, col=1)

    fig.add_trace(go.Scatter(x=sell_signals.index, y=sell_signals['price'],
                             mode='markers', name='Sell Signal', marker=dict(size=10, color='#ff3333', symbol='triangle-down')), row=1, col=1)

    if indicator in ["RSI", "RSI+MACD"]:
        fig.add_trace(go.Scatter(x=signals.index, y=signals['rsi'],
                                 mode='lines', name='RSI (14)', line=dict(color='#6600cc')), row=2, col=1)

        fig.add_trace(go.Scatter(x=signals.index, y=[70]*len(signals),
                                 mode='lines', name='Overbought (70)', line=dict(color='#ff3333', dash='dash')), row=2, col=1)

        fig.add_trace(go.Scatter(x=signals.index, y=[30]*len(signals),
                                 mode='lines', name='Oversold (30)', line=dict(color='#00cc66', dash='dash')), row=2, col=1)

    if indicator in ["MACD", "RSI+MACD"]:
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'],
                                 mode='lines', name='MACD', line=dict(color='blue')), row=3 if indicator=="RSI+MACD" else 2, col=1)

        fig.add_trace(go.Scatter(x=df.index, y=df['Signal'],
                                 mode='lines', name='Signal Line', line=dict(color='orange')), row=3 if indicator=="RSI+MACD" else 2, col=1)

        fig.add_trace(go.Bar(x=df.index, y=df['Hist'], name='Histogram',
                             marker_color=df['Hist'].apply(lambda x: 'green' if x >=0 else 'red')), row=3 if indicator=="RSI+MACD" else 2, col=1)

    fig.update_layout(height=1000 if indicator=="RSI+MACD" else 800, width=1200, showlegend=True)
    fig.update_xaxes(title_text=language_texts[language]['xaxis'])
    fig.update_yaxes(title_text=language_texts[language]['yaxis'], row=1, col=1)

    return fig.to_html(full_html=False)

@app.route('/', methods=['GET', 'POST'])

def index():
    graph_html = ''
    today = datetime.today()
    default_end_date = today.strftime('%Y-%m-%d')
    default_start_date = (today - timedelta(days=365)).strftime('%Y-%m-%d')
    language = request.args.get('lang', 'zh')

    if request.method == 'POST':
        ticker_manual = request.form.get('ticker_manual', '').strip()
        ticker_select = request.form.get('ticker_select', '').strip()

        # 優先使用手動輸入
        input_text = ticker_manual if ticker_manual else ticker_select

        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        indicator = request.form.get('indicator')
        language = request.form.get('language', 'zh')



        ticker = company_lookup.get(input_text.strip(), input_text.strip())

        try:
            graph_html = generate_plot(ticker, start_date, end_date, indicator, language)
        except:
            graph_html = f"<h3 style='color:red;'>{language_texts[language]['error']}</h3>"

    return render_template('index.html', 
                           graph_html=graph_html,
                           default_start_date=default_start_date,
                           default_end_date=default_end_date,
                           language=language,
                           texts=language_texts[language],
                           stocks=company_lookup)

if __name__ == '__main__':
    app.run(debug=True, port=5001)
